# =========================
# Mini-MES Item Master (FROZEN STABLE)
# Patched by 沁然 — 5 fixes + UX patch:
# 1. Vendor combo uniqueness check restored
# 2. Vendor_Name uses up() for uppercase
# 3. Save local PermissionError protection restored
# 4. confirm_save_open added to FORM_KEYS
# 5. missing_value restored to v <= 0 (Standard Pack=0 not allowed)
# 6. Roll/Sheet/Life fields → text_input (blank default, autocomplete off)
#    Standard Pack → min_value=1
# =========================
import streamlit as st
import pandas as pd
import re
from pathlib import Path
from datetime import datetime

# =========================
# Page config
# =========================
st.set_page_config(layout="wide")
st.title("Mini-MES Item Master")

# ── UI: Professional label styling for dark background ──
st.markdown("""
<style>
div[data-testid="stTextInput"] label,
div[data-testid="stTextArea"] label,
div[data-testid="stSelectbox"] label,
div[data-testid="stNumberInput"] label,
div[data-testid="stRadio"] > label,
div[data-testid="stCheckbox"] label,
div[data-testid="stFileUploader"] label {
    color: #C8D6E5 !important;
    font-weight: 500 !important;
    letter-spacing: 0.02em;
}
</style>
""", unsafe_allow_html=True)
st.sidebar.caption(f"RUNNING FILE: {__file__}")

# =========================
# Form keys (for reset_form_only)
# =========================
# =========================
# Utilities
# =========================
def fv() -> int:
    """Return current form version — used as widget key suffix."""
    return st.session_state.get("form_version", 0)

def fk(key: str) -> str:
    """Return versioned widget key e.g. 'item_name_3'."""
    return f"{key}_{fv()}"

def to_upper_key(key: str):
    k = fk(key)
    v = st.session_state.get(k, "")
    if isinstance(v, str):
        st.session_state[k] = v.upper()
    if key in ("item_name", "item_desc", "vendor_name", "vendor_item_code", "customer_item_code"):
        st.session_state.pop("last_add_msg", None)

def gs(key: str, default=None):
    """Get session value by base key (version-aware)."""
    return st.session_state.get(fk(key), default)

def reset_form_only(rerun: bool = True):
    """Bump form_version → all widget keys change → Streamlit renders fresh widgets."""
    st.session_state["form_version"] = fv() + 1
    st.session_state.pop("pending_row", None)
    st.session_state.pop("pending_preview", None)
    st.session_state.pop("last_add_msg", None)
    if rerun:
        st.rerun()

def up(x: str) -> str:
    return str(x or "").strip().upper()

def norm_num(x) -> str:
    if x is None:
        return ""
    if isinstance(x, (int, float)):
        return str(x)
    return str(x).strip()

def missing_value(v) -> bool:
    if isinstance(v, str):
        return not v.strip()
    if isinstance(v, (int, float)):
        return v <= 0   # ✅ FIX #5: restored to <= 0 (Standard Pack=0 not allowed)
    return v is None

def parse_dim_field(val, field_name: str) -> tuple:
    """
    Parse a dimension text_input value.
    Returns (float_value, error_msg_or_None).
    Accepts: "100", "100.5", empty string (→ 0.0 for optional fields).
    Rejects: letters, negative, comma numbers.
    """
    s = str(val or "").strip().replace(",", "")
    if s == "":
        return (0.0, None)   # empty = 0, caller decides if required
    try:
        v = float(s)
    except ValueError:
        return (None, f"❌ {field_name}: '{val}' 不是有效数字（请输入如 100 或 25.5）")
    if v < 0:
        return (None, f"❌ {field_name}: 不允许负数")
    return (v, None)

# =========================
# V13 Item Code Engine
# =========================
# Category → (range_start, range_end, ownership)
CATEGORY_RANGE = {
    "RAW_MATERIAL":            (100000, 199999, "COMPANY"),
    "CHEMICAL":                (200000, 299999, "COMPANY"),
    "PACKAGING":               (300000, 399999, "COMPANY"),
    "WIP":                     (400000, 499999, "COMPANY"),
    "FINISHED_GOODS":          (500000, 599999, "COMPANY"),
    "CONSUMABLE":              (600000, 699999, "COMPANY"),
    "TOOLS_AND_JIGS":          (700000, 799999, "COMPANY"),
    "MACHINERY_EQUIPMENT":     (800000, 899999, "COMPANY"),
    "CUSTOMER_OWNED_MATERIAL": (900000, 949999, "CUSTOMER"),
    "RESERVED":                (950000, 999999, "COMPANY"),
}

CATEGORY_DISPLAY = {
    "RAW_MATERIAL":            "RAW MATERIAL (100000–199999)",
    "CHEMICAL":                "CHEMICAL (200000–299999)",
    "PACKAGING":               "PACKAGING (300000–399999)",
    "WIP":                     "WIP / SEMI-FINISHED (400000–499999)",
    "FINISHED_GOODS":          "FINISHED GOODS (500000–599999)",
    "CONSUMABLE":              "CONSUMABLE (600000–699999)",
    "TOOLS_AND_JIGS":          "TOOLS & JIGS (700000–799999)",
    "MACHINERY_EQUIPMENT":     "MACHINERY / EQUIPMENT (800000–899999)",
    "CUSTOMER_OWNED_MATERIAL": "CUSTOMER OWNED MATERIAL (900000–949999)",
    "RESERVED":                "RESERVED (950000–999999)",
}

CATEGORY_GUIDE = {
    "RAW_MATERIAL":            "铁/塑料/电线/螺丝/零件/原材料",
    "CHEMICAL":                "胶水/油漆/溶剂/清洁剂/润滑油/助剂",
    "PACKAGING":               "纸箱/标签/胶带/珍珠棉/包装袋",
    "WIP":                     "半成品（在产品）",
    "FINISHED_GOODS":          "可出货成品",
    "CONSUMABLE":              "手套/砂纸/刀片/抹布/工厂消耗品",
    "TOOLS_AND_JIGS":          "治具/夹具/工装/量具",
    "MACHINERY_EQUIPMENT":     "机器/设备（含客户借放设备）",
    "CUSTOMER_OWNED_MATERIAL": "客供/代工客户资产物料",
    "RESERVED":                "预留未来扩展",
}

# Sub-categories for CUSTOMER_OWNED_MATERIAL only
# Mirrors the main categories so analysts can report by material type
CUSTOMER_SUB_CATEGORIES = [
    "",
    "RAW_MATERIAL",
    "CHEMICAL",
    "PACKAGING",
    "WIP",
    "FINISHED_GOODS",
    "CONSUMABLE",
    "TOOLS_AND_JIGS",
    "MACHINERY_EQUIPMENT",
    "OTHER",
]
CUSTOMER_SUB_GUIDE = {
    "RAW_MATERIAL":        "铁/塑料/电线/螺丝/零件",
    "CHEMICAL":            "胶水/油漆/溶剂/助剂",
    "PACKAGING":           "纸箱/标签/胶带/包装袋",
    "WIP":                 "客供半成品",
    "FINISHED_GOODS":      "客供成品",
    "CONSUMABLE":          "手套/砂纸/刀片/消耗品",
    "TOOLS_AND_JIGS":      "治具/夹具/工装/量具",
    "MACHINERY_EQUIPMENT": "设备/机器",
    "OTHER":               "其他客供物料",
}

def get_ownership(category: str) -> str:
    """Return COMPANY or CUSTOMER based on category."""
    return CATEGORY_RANGE.get(category, (None, None, "COMPANY"))[2]

def generate_next_code(category: str, item_df: pd.DataFrame) -> str:
    """
    Generate next system_item_code for given category.
    Format: NNNNNN-00/00
    Finds MAX existing base in range, returns MAX+1.
    Returns '' if category invalid.
    """
    if category not in CATEGORY_RANGE:
        return ""
    range_start, range_end, _ = CATEGORY_RANGE[category]
    import re as _re
    pattern = _re.compile(r"^(\d{6})-\d{2}/\d{2}$")
    max_base = range_start - 1
    for code in item_df.get("system_item_code", pd.Series(dtype=str)).dropna().astype(str):
        m = pattern.match(code.strip())
        if m:
            base = int(m.group(1))
            if range_start <= base <= range_end:
                max_base = max(max_base, base)
    next_base = max_base + 1
    if next_base > range_end:
        return f"RANGE_FULL_{category}"
    return f"{next_base:06d}-00/00"

def norm_prefix(x: str) -> str:
    x = str(x or "").strip().upper()
    x = re.sub(r"\s+", "_", x)
    x = re.sub(r"[^A-Z0-9_]", "", x)
    return x

def locked_field(label: str, value: str):
    safe_value = (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    st.markdown(f"##### {label}")
    st.markdown(
        f"""
        <div style="
            padding:10px;
            background-color:#1f2937;
            border:1px solid #374151;
            border-radius:6px;
            font-weight:600;
            font-size:16px;
            color:#ffffff;">
            {safe_value}
        </div>
        """,
        unsafe_allow_html=True
    )

def get_options(df: pd.DataFrame, col: str):
    if col not in df.columns:
        return []
    return (
        df[col]
        .dropna()
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .unique()
        .tolist()
    )

def read_sheet_csv(uploaded_file, must_have: list[str]) -> pd.DataFrame:
    raw = pd.read_csv(uploaded_file, header=None)

    header_idx = None
    must_norm = [re.sub(r"\s+", " ", str(k)).strip().lower() for k in must_have]

    for i in range(min(len(raw), 40)):
        row = raw.iloc[i].astype(str).tolist()
        row_norm = [re.sub(r"\s+", " ", str(c)).strip().lower() for c in row]
        if all(any(k == cell for cell in row_norm) for k in must_norm):
            header_idx = i
            break

    if header_idx is None:
        sample = raw.head(12).astype(str).values.tolist()
        raise ValueError(f"找不到表头行：需要包含 {must_have}. 前12行={sample}")

    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file, header=header_idx)
    df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in df.columns]
    return df

def normalize_vendor_cols(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize ALL column names to canonical V17 names.
    Handles any capitalisation variant from CSV exports.
    """
    if df is None:
        return df

    # Canonical map: lowercase_with_underscores → target column name
    CANONICAL = {
        "system_item_code":          "system_item_code",
        "item_code":                 "system_item_code",   # legacy
        "customer_item_code":        "Customer_Item_Code",
        "item_category":             "Item_Category",
        "material_sub_category":     "Material_Sub_Category",
        "item_name":                 "Item_Name",
        "item descriptions":         "Item Descriptions",
        "item_descriptions":         "Item Descriptions",
        "ownership":                 "Ownership",
        "status_consign":            "STATUS_CONSIGN",
        "vendor_name":               "Vendor_Name",
        "vendor name":               "Vendor_Name",
        "vendor_item_code":          "Vendor_Item_Code",
        "vendor item_code":          "Vendor_Item_Code",
        "vendor item code":          "Vendor_Item_Code",
        "delivery lead time (week)": "Delivery Lead Time (Week)",
        "delivery_lead_time_(week)": "Delivery Lead Time (Week)",
        "standard pack":             "Standard Pack",
        "standard_pack":             "Standard Pack",
        "item_group":                "Item_Group",
        "uom_family":                "Uom_Family",
        "uom_base":                  "Uom_Base",
        "track lot":                 "Track Lot",
        "track_lot":                 "Track Lot",
        "default location":          "Default Location",
        "default_location":          "Default Location",
        "pack_uom":                  "Pack_Uom",
        "pack_size / units":         "Pack_Size / units",
        "pack_size_/_units":         "Pack_Size / units",
        "pack_size_uom":             "Pack_Size_Uom",
        "roll_length_mm":            "Roll_Length_mm",
        "roll_width_mm":             "Roll_Width_mm",
        "roll_thickness_mm":         "Roll_Thickness_mm",
        "sheet_length_mm":           "Sheet_Length_mm",
        "sheet_width_mm":            "Sheet_Width_mm",
        "sheet_thickness_mm":        "Sheet_Thickness_mm",
        "open_life_hours":           "Open_life_hours",
        "shelf_life_days":           "Shelf_life_days",
        "rohs":                      "ROHS",
        "esd":                       "ESD",
        "ul":                        "UL",
        "other":                     "OTHER",
        "status":                    "Status",
        "entered_by":                "Entered_By",
        "entered_at":                "Entered_At",
    }

    rename_map = {}
    seen_targets = set()
    for col in df.columns:
        key = col.strip().lower().replace(" ", "_")
        # also try with spaces preserved for "item descriptions" etc
        key2 = col.strip().lower()
        target = CANONICAL.get(key) or CANONICAL.get(key2)
        if target and col != target and target not in seen_targets:
            rename_map[col] = target
        if target:
            seen_targets.add(target)

    if rename_map:
        df = df.rename(columns=rename_map)

    # Drop any exact duplicate column names that may result
    df = df.loc[:, ~df.columns.duplicated(keep="first")]
    return df

# V17 canonical column order
V14_COLS = [
    "system_item_code", "Customer_Item_Code", "Item_Category", "Material_Sub_Category",
    "Item_Name", "Item Descriptions", "Ownership", "STATUS_CONSIGN",
    "Vendor_Name", "Vendor_Item_Code",
    "Delivery Lead Time (Week)", "Standard Pack", "Item_Group",
    "Uom_Family", "Uom_Base", "Track Lot", "Default Location",
    "Pack_Uom", "Pack_Size / units", "Pack_Size_Uom",
    "Roll_Length_mm", "Roll_Width_mm", "Roll_Thickness_mm",
    "Sheet_Length_mm", "Sheet_Width_mm", "Sheet_Thickness_mm",
    "Open_life_hours", "Shelf_life_days",
    "ROHS", "ESD", "UL", "OTHER",
    "Status", "Entered_By", "Entered_At",
]

# =========================
# Boot: clear form only once
# =========================
if "_boot_cleared" not in st.session_state:
    st.session_state["_boot_cleared"] = True
    reset_form_only(rerun=False)

# =========================
# Sidebar uploads
# =========================
st.sidebar.header("Upload Google Sheet CSV")

if st.sidebar.button("Reset Form", key="btn_reset_form"):
    reset_form_only()

dropdown_file = st.sidebar.file_uploader("Upload DropDown CSV", type=["csv"], key="uploader_dropdown")
itemmaster_file = st.sidebar.file_uploader("Upload ItemMaster CSV", type=["csv"], key="uploader_itemmaster")

if dropdown_file is None or itemmaster_file is None:
    st.warning("请上传 DropDown.csv 与 ItemMaster.csv")
    st.stop()

dropdown_sig = (getattr(dropdown_file, "name", ""), getattr(dropdown_file, "size", 0))
itemmaster_sig = (getattr(itemmaster_file, "name", ""), getattr(itemmaster_file, "size", 0))

# =========================
# Load CSVs
# =========================
try:
    dropdown_df = read_sheet_csv(
        dropdown_file,
        must_have=["Item_Group", "Uom_Family", "Default Location", "Pack_Uom"]
    )
except ValueError:
    st.error("DropDown.csv 格式不正确：找不到模板表头。请使用系统提供的 DropDown 模板文件再上传。")
    st.stop()

try:
    loaded_item_df = read_sheet_csv(
        itemmaster_file,
        must_have=["System_Item_Code", "Item_Name", "Item_Category", "Uom_Family"],
    )
    loaded_item_df = normalize_vendor_cols(loaded_item_df)
except ValueError:
    # fallback: try legacy column names
    try:
        itemmaster_file.seek(0)
        loaded_item_df = read_sheet_csv(
            itemmaster_file,
            must_have=["Item_Name", "Uom_Family"],
        )
        loaded_item_df = normalize_vendor_cols(loaded_item_df)
    except ValueError:
        st.error("ItemMaster.csv 格式不正确：找不到模板表头。请使用系统导出的 ItemMaster 模板文件再上传。")
        st.stop()

if st.sidebar.button("Reload from ItemMaster CSV", key="btn_reload_itemmaster"):
    st.session_state["item_df"] = loaded_item_df.copy()
    st.session_state["base_cols"] = loaded_item_df.columns.tolist()
    st.session_state["itemmaster_sig"] = itemmaster_sig
    st.session_state["dirty"] = False
    reset_form_only(rerun=False)
    st.rerun()

if "item_df" not in st.session_state or st.session_state.get("itemmaster_sig") != itemmaster_sig:
    st.session_state["item_df"] = loaded_item_df.copy()
    st.session_state["base_cols"] = loaded_item_df.columns.tolist()
    st.session_state["itemmaster_sig"] = itemmaster_sig
    st.session_state["dirty"] = False
    reset_form_only(rerun=False)

item_df = st.session_state["item_df"]

# Normalize all column names to canonical V17 names (covers any capitalisation)
item_df = normalize_vendor_cols(item_df)
st.session_state["item_df"] = item_df

# Ensure system_item_code exists
if "system_item_code" not in item_df.columns:
    item_df["system_item_code"] = ""
    st.session_state["item_df"] = item_df

with st.expander("DEBUG (optional)", expanded=False):
    st.write("DropDown columns =", list(dropdown_df.columns))
    st.write("ItemMaster columns =", list(item_df.columns))
    st.dataframe(dropdown_df.head(10), use_container_width=True)
    st.dataframe(item_df.head(10), use_container_width=True)

# =========================
# Item Code (always visible above tabs)
# =========================
st.subheader("New Item Entry")

# V13: Compute next_code from Category (not Item Group)
selected_category = gs("item_category", "")
next_code     = generate_next_code(selected_category, item_df) if selected_category else "SELECT_CATEGORY_FIRST"
ownership_auto = get_ownership(selected_category) if selected_category else "—"

code_color = "#d4edda" if ("-" in str(next_code) and "RANGE_FULL" not in str(next_code) and next_code != "SELECT_CATEGORY_FIRST") else "#f8d7da"
st.markdown(
    f"""
    <div style="padding:10px;border:2px solid #111;border-radius:10px;
                font-size:26px;font-weight:900;color:#111;background:{code_color};
                margin-bottom:4px;">
        ITEM CODE: {next_code}
    </div>
    <div style="font-size:13px;color:#555;margin-bottom:12px;">
        Ownership: <b>{ownership_auto}</b> &nbsp;|&nbsp; Category: <b>{selected_category or "— (select category in Tab 1)"}</b>
    </div>
    """,
    unsafe_allow_html=True
)
st.text_input("System Item Code (Auto Generated)", value=next_code, key=fk("item_code"), disabled=True)

UOMTYPE_TO_BASE = {"PCS/COUNT": "PCS", "LENGTH": "MM", "AREA": "MM2", "WEIGHT": "KG"}

# =========================
# Tabs
# =========================
tab1, tab2, tab3 = st.tabs(["📋 Item Info", "⚙️ Specification", "📦 Pack & Save"])

# ── TAB 1: Item Info ─────────────────────────────────────────
with tab1:
    col_a, col_b = st.columns(2)

    with col_a:
        # V13: Category drives Item Code range — replaces Item Group as primary selector
        cat_opts = [""] + list(CATEGORY_DISPLAY.keys())
        cat_labels = ["— Select Category —"] + [CATEGORY_DISPLAY[k] for k in CATEGORY_DISPLAY]
        cat_idx = cat_opts.index(gs("item_category", "")) if gs("item_category", "") in cat_opts else 0
        chosen_cat = st.selectbox(
            "Item Category (Required — determines Item Code range)",
            options=cat_opts,
            format_func=lambda x: CATEGORY_DISPLAY.get(x, "— Select Category —") if x else "— Select Category —",
            key=fk("item_category")
        )
        if chosen_cat:
            guide = CATEGORY_GUIDE.get(chosen_cat, "")
            owns = get_ownership(chosen_cat)
            st.caption(f"💡 {guide}  |  Ownership: **{owns}**")

        # Sub-Category — only visible when CUSTOMER_OWNED_MATERIAL is selected
        if gs("item_category", "") == "CUSTOMER_OWNED_MATERIAL":
            sub_chosen = st.selectbox(
                "Material Sub-Category (Required for Customer Material)",
                options=CUSTOMER_SUB_CATEGORIES,
                format_func=lambda x: f"{x} — {CUSTOMER_SUB_GUIDE[x]}" if x in CUSTOMER_SUB_GUIDE else "— Select material type —",
                key=fk("material_sub_category")
            )

        st.text_input("Item Name (Required)", key=fk("item_name"),
                      on_change=to_upper_key, args=("item_name",), autocomplete="off")
        st.text_area("Item Descriptions (Required)", height=100, key=fk("item_desc"),
                     on_change=to_upper_key, args=("item_desc",))

    with col_b:
        st.text_input("Vendor Name (Required)", key=fk("vendor_name"),
                      on_change=to_upper_key, args=("vendor_name",),
                      autocomplete="off", placeholder="e.g. ABC TRADING  — or type N/A if not applicable")
        st.text_input("Vendor Item Code (Required)", key=fk("vendor_item_code"),
                      on_change=to_upper_key, args=("vendor_item_code",),
                      autocomplete="off", placeholder="Vendor's part number — or N/A if not applicable")
        # V13: Customer Item Code — for clients who have their own coding system
        st.text_input("Customer Item Code (Optional)",
                      key=fk("customer_item_code"),
                      on_change=to_upper_key, args=("customer_item_code",),
                      autocomplete="off",
                      placeholder="Client's own code e.g. A001 / PCB-REV2 — leave blank if none")
        st.number_input("Delivery Lead Time (Week)", min_value=0.0, step=0.5,
                        format="%.1f", key=fk("delivery_lead_time"))
        st.number_input("Standard Pack (Required, min 1)", min_value=1, step=1,
                        format="%d", key=fk("standard_pack"))

# ── TAB 2: Specification ─────────────────────────────────────
with tab2:
    col_c, col_d = st.columns(2)

    with col_c:
        st.radio("UOM Type (Required)", ["PCS/COUNT", "LENGTH", "WEIGHT", "AREA"],
                 horizontal=True, key=fk("uom_type"))
        uom_type_now = gs("uom_type", "PCS/COUNT")
        uom_auto  = UOMTYPE_TO_BASE.get(uom_type_now, "PCS")
        uom_family = uom_auto
        uom_base   = uom_auto
        locked_field("UOM Family (Auto)", uom_auto)
        locked_field("UOM Base (Auto)",   uom_auto)

        track_lot_opts = [""] + (get_options(dropdown_df, "Track Lot") or ["Y", "N"])
        st.selectbox("Track Lot (Required)", track_lot_opts, key=fk("track_lot"))
        st.selectbox("Default Location (Required)",
                     [""] + get_options(dropdown_df, "Default Location"), key=fk("default_location"))

    with col_d:
        STATUS_OPTIONS = ["", "ACTIVE", "SLOW_MOVING", "HOLD", "OBSOLETE"]
        st.selectbox("Status (Required)", STATUS_OPTIONS, key=fk("status"))
        # STATUS_CONSIGN is auto-derived from Category/Ownership — NOT user editable
        _consign_auto = "TRUE" if get_ownership(gs("item_category", "")) == "CUSTOMER" else "FALSE"
        _consign_color = "#d4edda" if _consign_auto == "TRUE" else "#e2e3e5"
        st.markdown(
            f"<div style='font-size:0.82rem;color:#C8D6E5;font-weight:500;margin-bottom:2px;'>STATUS CONSIGN (Auto)</div>"
            f"<div style='background:{_consign_color};color:#111;padding:4px 10px;"
            f"border-radius:4px;font-weight:700;display:inline-block;margin-bottom:8px;'>"
            f"{_consign_auto}</div>",
            unsafe_allow_html=True
        )

        st.caption("Compliance")
        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            st.checkbox("ROHS", key=fk("rohs"), value=False)
        with col_r2:
            st.checkbox("ESD",  key=fk("esd"),  value=False)
        with col_r3:
            st.checkbox("UL",   key=fk("ul"),   value=False)
        st.text_input("OTHER Compliance (If any)", key=fk("other_compliance"),
                      on_change=to_upper_key, args=("other_compliance",), autocomplete="off")

# ── TAB 3: Pack & Save ───────────────────────────────────────
with tab3:
    uom_type_now  = gs("uom_type", "PCS/COUNT")
    uom_auto      = UOMTYPE_TO_BASE.get(uom_type_now, "PCS")
    pack_size_uom = uom_auto if uom_type_now in ["LENGTH", "AREA"] else ""

    # ── Packaging ──
    st.markdown("##### 📦 Packaging")
    if uom_type_now in ["LENGTH", "AREA"]:
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            st.selectbox("Pack UOM (Required)", [""] + get_options(dropdown_df, "Pack_Uom"), key=fk("pack_uom"))
        with col_p2:
            st.number_input("Pack Size / Unit (Required)", min_value=0.0, step=1.0, key=fk("pack_size_units"))
        with col_p3:
            locked_field("Pack Size UOM (Auto)", uom_auto)
    else:
        st.info(f"UOM = {uom_type_now} — Packaging not required.")
        pack_size_uom = ""

    st.divider()

    # ── Dimensions / Life ──
    st.markdown("##### 📐 Dimensions / Life")

    if uom_type_now == "LENGTH":
        st.caption("All 3 fields required ✱")
        col_d1, col_d2, col_d3 = st.columns(3)
        with col_d1:
            st.text_input("Roll Length mm ✱", key=fk("roll_len"), placeholder="e.g. 1000", autocomplete="off")
        with col_d2:
            st.text_input("Roll Width mm ✱",  key=fk("roll_wid"), placeholder="e.g. 500",  autocomplete="off")
        with col_d3:
            st.text_input("Roll Thickness mm ✱", key=fk("roll_thk"), placeholder="e.g. 0.5", autocomplete="off")

    elif uom_type_now == "AREA":
        st.caption("All 3 fields required ✱")
        col_d1, col_d2, col_d3 = st.columns(3)
        with col_d1:
            st.text_input("Sheet Length mm ✱", key=fk("sheet_len"), placeholder="e.g. 1200", autocomplete="off")
        with col_d2:
            st.text_input("Sheet Width mm ✱",  key=fk("sheet_wid"), placeholder="e.g. 900",  autocomplete="off")
        with col_d3:
            st.text_input("Sheet Thickness mm ✱", key=fk("sheet_thk"), placeholder="e.g. 1.2", autocomplete="off")

    elif uom_type_now == "WEIGHT":
        st.caption("Both fields required ✱")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.text_input("Open Life Hour ✱",  key=fk("open_life_hours"), placeholder="e.g. 24",  autocomplete="off")
        with col_d2:
            st.text_input("Shelf Life Days ✱", key=fk("shelf_life_days"), placeholder="e.g. 365", autocomplete="off")

    else:  # PCS/COUNT
        st.info("UOM = PCS/COUNT — no dimension fields required.")

 # ── EMP + Timestamp ──
    st.markdown("##### 🖊️ Record")
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        st.text_input("EMP NO / EMP NAME (Required)", key=fk("entered_by"),
                      on_change=to_upper_key, args=("entered_by",), autocomplete="off")
    with col_e2:
        entered_at_display = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.caption(f"Entered At (Auto): {entered_at_display}")

    st.divider()

    # ── Success banner ──
    if st.session_state.get("last_add_msg"):
        st.success(st.session_state["last_add_msg"])
        st.caption("👆 Form has been cleared. Fill in the fields above for the next item.")

    # ── Save / Export ──
    st.markdown("##### 💾 Save / Export")
    if st.session_state.get("dirty", False):
        st.warning("⚠ Unsaved changes — please Save or Download.")

# read back uom values after tabs (needed by Add Item below)
uom_type_now  = gs("uom_type", "PCS/COUNT")
uom_auto      = UOMTYPE_TO_BASE.get(uom_type_now, "PCS")
uom_family    = uom_auto
uom_base      = uom_auto
pack_size_uom = uom_auto if uom_type_now in ["LENGTH", "AREA"] else ""



# =========================
# Add Item + Save/Export — Tab 3
# Uses a function to avoid Streamlit indentation issues
# =========================

def run_add_item_logic():
    """All validation + new_row build. Returns new_row dict or None."""
    entered_at   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    code_to_save = up(next_code)

    uom_type_v = gs("uom_type", "")
    REQUIRED = {
        "Item Name":                 gs("item_name", ""),
        "Item Descriptions":         gs("item_desc", ""),
        "Vendor Name":               gs("vendor_name", ""),
        "Vendor Item Code":          gs("vendor_item_code", ""),
        "Item Category":             gs("item_category", ""),        "UOM Type":                  uom_type_v,
        "Track Lot":                 gs("track_lot", ""),
        "Default Location":          gs("default_location", ""),
        "Delivery Lead time (Week)": gs("delivery_lead_time", 0.0),
        "Standard Pack":             gs("standard_pack", 0),
        "Entered By":                gs("entered_by", ""),
        "Status":                    gs("status", ""),
    }
    if uom_type_v in ["LENGTH", "AREA"]:
        REQUIRED.update({
            "Pack UOM":         gs("pack_uom", ""),
            "Pack Size / Unit": gs("pack_size_units", 0.0),
        })
    if uom_type_v == "WEIGHT":
        REQUIRED.update({
            "Open Life Hour":  gs("open_life_hours", ""),
            "Shelf life days": gs("shelf_life_days", ""),
        })

    missing = [k for k, v in REQUIRED.items() if missing_value(v)]
    if missing:
        st.error("❌ Required fields missing: " + ", ".join(missing))
        return None

    # Sub-category required when CUSTOMER_OWNED_MATERIAL
    if gs("item_category", "") == "CUSTOMER_OWNED_MATERIAL":
        if not gs("material_sub_category", ""):
            st.error("❌ Material Sub-Category is required for CUSTOMER_OWNED_MATERIAL.")
            return None

    # Dimension parsing
    dim_errors = []
    def pd_wrap(key, label):
        v, err = parse_dim_field(gs(key, ""), label)
        if err:
            dim_errors.append(err)
            return None
        return v

    if uom_type_v == "LENGTH":
        roll_len_v = pd_wrap("roll_len", "Roll Length mm")
        roll_wid_v = pd_wrap("roll_wid", "Roll Width mm")
        roll_thk_v = pd_wrap("roll_thk", "Roll Thickness mm")
        if roll_len_v == 0.0: dim_errors.append("❌ Roll Length mm: 必填，不能为空或0")
        if roll_wid_v == 0.0: dim_errors.append("❌ Roll Width mm: 必填，不能为空或0")
        if roll_thk_v == 0.0: dim_errors.append("❌ Roll Thickness mm: 必填，不能为空或0")
        sheet_len_v = sheet_wid_v = sheet_thk_v = open_life_v = shelf_life_v = 0.0
    elif uom_type_v == "AREA":
        sheet_len_v = pd_wrap("sheet_len", "Sheet Length mm")
        sheet_wid_v = pd_wrap("sheet_wid", "Sheet Width mm")
        sheet_thk_v = pd_wrap("sheet_thk", "Sheet Thickness mm")
        if sheet_len_v == 0.0: dim_errors.append("❌ Sheet Length mm: 必填，不能为空或0")
        if sheet_wid_v == 0.0: dim_errors.append("❌ Sheet Width mm: 必填，不能为空或0")
        if sheet_thk_v == 0.0: dim_errors.append("❌ Sheet Thickness mm: 必填，不能为空或0")
        roll_len_v = roll_wid_v = roll_thk_v = open_life_v = shelf_life_v = 0.0
    elif uom_type_v == "WEIGHT":
        open_life_v  = pd_wrap("open_life_hours", "Open Life Hour")
        shelf_life_v = pd_wrap("shelf_life_days", "Shelf life days")
        if open_life_v  == 0.0: dim_errors.append("❌ Open Life Hour: 必填，不能为空或0")
        if shelf_life_v == 0.0: dim_errors.append("❌ Shelf life days: 必填，不能为空或0")
        roll_len_v = roll_wid_v = roll_thk_v = 0.0
        sheet_len_v = sheet_wid_v = sheet_thk_v = 0.0
    else:
        roll_len_v = roll_wid_v = roll_thk_v = 0.0
        sheet_len_v = sheet_wid_v = sheet_thk_v = open_life_v = shelf_life_v = 0.0

    if dim_errors:
        for e in dim_errors:
            st.error(e)
        return None

    # AREA: pack size must not exceed sheet area
    if uom_type_v == "AREA" and sheet_len_v and sheet_wid_v:
        sheet_area = sheet_len_v * sheet_wid_v
        try:
            pack_size_val = float(str(gs("pack_size_units", 0.0)).strip() or 0)
        except (ValueError, TypeError):
            pack_size_val = 0.0
        if pack_size_val > 0 and pack_size_val > sheet_area:
            st.error(
                f"❌ Pack Size ({pack_size_val:,.2f} MM²) cannot exceed Sheet Area "
                f"({sheet_len_v} × {sheet_wid_v} = {sheet_area:,.2f} MM²)."
            )
            return None

    # Item code guard
    if code_to_save in ("SELECT_CATEGORY_FIRST", "") or "RANGE_FULL" in str(code_to_save):
        st.error("❌ Please select a valid Item Category first.")
        return None

    # Uniqueness checks
    code_col = "system_item_code" if "system_item_code" in item_df.columns else "Item_Code"
    if item_df[code_col].dropna().astype(str).str.strip().str.upper().eq(code_to_save.upper()).any():
        st.error(f"❌ Item Code already exists: {code_to_save}")
        return None

    vic = up(gs("vendor_item_code", ""))
    if "Vendor_Item_Code" in item_df.columns and vic and vic != "N/A":
        if item_df["Vendor_Item_Code"].fillna("").astype(str).str.strip().str.upper().eq(vic).any():
            st.error(f"❌ Vendor Item Code already exists: {vic}")
            return None

    cust_ic = up(gs("customer_item_code", ""))
    if cust_ic and "Customer_Item_Code" in item_df.columns:
        if item_df["Customer_Item_Code"].fillna("").astype(str).str.strip().str.upper().eq(cust_ic).any():
            st.error(f"❌ Customer Item Code already linked to another item: {cust_ic}")
            return None

    # Duplicate content check
    _uom_now = gs("uom_type", "PCS/COUNT")
    _cat     = up(gs("item_category", ""))
    pack_size_uom2 = uom_auto if _uom_now in ["LENGTH", "AREA"] else ""

    candidate = {
        "Item_Name":              up(gs("item_name", "")),
        "Item Descriptions":      up(gs("item_desc", "")),
        "Vendor_Name":            up(gs("vendor_name", "")),
        "Vendor_Item_Code":       up(gs("vendor_item_code", "")),
        "Delivery Lead Time (Week)": norm_num(gs("delivery_lead_time", 0.0)),
        "STATUS_CONSIGN":         "TRUE" if get_ownership(gs("item_category", "")) == "CUSTOMER" else "FALSE",
        "Standard Pack":          norm_num(gs("standard_pack", 0)),
        "Item_Category":          _cat,
        "Ownership":              get_ownership(gs("item_category", "")),
        "Uom_Family":             up(uom_family),
        "Uom_Base":               up(uom_base),
        "Track Lot":              up(gs("track_lot", "")),
        "Default Location":       up(gs("default_location", "")),
        "Pack_Uom":               up(gs("pack_uom", "")),
        "Pack_Size / units":      "" if _uom_now in ["PCS/COUNT", "WEIGHT"] else norm_num(gs("pack_size_units", 0.0)),
        "Roll_Length_mm":         norm_num(roll_len_v),
        "Roll_Width_mm":          norm_num(roll_wid_v),
        "Roll_Thickness_mm":      norm_num(roll_thk_v),
        "Sheet_Length_mm":        norm_num(sheet_len_v),
        "Sheet_Width_mm":         norm_num(sheet_wid_v),
        "Sheet_Thickness_mm":     norm_num(sheet_thk_v),
        "Open_life_hours":        norm_num(open_life_v),
        "Shelf_life_days":        norm_num(shelf_life_v),
        "Status":                 up(gs("status", "")),
        "ROHS": "TRUE" if gs("rohs", False) else "FALSE",
        "ESD":  "TRUE" if gs("esd",  False) else "FALSE",
        "UL":   "TRUE" if gs("ul",   False) else "FALSE",
        "OTHER": up(gs("other_compliance", "")),
    }
    EXCLUDE_FROM_DUP = {"system_item_code", "Item_Code", "Entered_At", "Entered_By"}
    for _, existing_row in item_df.iterrows():
        match = all(
            str(existing_row.get(f, "") or "").strip().upper() == str(cval).strip().upper()
            for f, cval in candidate.items() if f not in EXCLUDE_FROM_DUP
        )
        if match:
            dup_code = str(existing_row.get(code_col, "?"))
            st.error(f"❌ Duplicate entry — all fields match existing item: **{dup_code}**")
            return None

    # Build new_row
    new_row = {
        "system_item_code":          code_to_save,
        "Customer_Item_Code":        up(gs("customer_item_code", "")),
        "Item_Category":             _cat,
        "Material_Sub_Category":     up(gs("material_sub_category", "")) if _cat == "CUSTOMER_OWNED_MATERIAL" else "",
        "Item_Name":                 up(gs("item_name", "")),
        "Item Descriptions":         up(gs("item_desc", "")),
        "Ownership":                 get_ownership(gs("item_category", "")),
        "STATUS_CONSIGN":            "TRUE" if get_ownership(gs("item_category", "")) == "CUSTOMER" else "FALSE",
        "Vendor_Name":               up(gs("vendor_name", "")),
        "Vendor_Item_Code":          up(gs("vendor_item_code", "")),
        "Delivery Lead Time (Week)": norm_num(gs("delivery_lead_time", 0.0)),
        "Standard Pack":             norm_num(gs("standard_pack", 0)),
        "Item_Group":                "",
        "Uom_Family":                up(uom_family),
        "Uom_Base":                  up(uom_base),
        "Track Lot":                 up(gs("track_lot", "")),
        "Default Location":          up(gs("default_location", "")),
        "Pack_Uom":                  up(gs("pack_uom", "")),
        "Pack_Size / units":         "" if _uom_now in ["PCS/COUNT", "WEIGHT"] else norm_num(gs("pack_size_units", 0.0)),
        "Pack_Size_Uom":             up(pack_size_uom2),
        "Roll_Length_mm":            norm_num(roll_len_v),
        "Roll_Width_mm":             norm_num(roll_wid_v),
        "Roll_Thickness_mm":         norm_num(roll_thk_v),
        "Sheet_Length_mm":           norm_num(sheet_len_v),
        "Sheet_Width_mm":            norm_num(sheet_wid_v),
        "Sheet_Thickness_mm":        norm_num(sheet_thk_v),
        "Open_life_hours":           norm_num(open_life_v),
        "Shelf_life_days":           norm_num(shelf_life_v),
        "ROHS":  "TRUE" if gs("rohs", False) else "FALSE",
        "ESD":   "TRUE" if gs("esd",  False) else "FALSE",
        "UL":    "TRUE" if gs("ul",   False) else "FALSE",
        "OTHER": up(gs("other_compliance", "")),
        "Status":                    up(gs("status", "")),
        "Entered_By":                up(gs("entered_by", "")),
        "Entered_At":                entered_at,
    }
    return new_row


with tab3:
    st.markdown("---")

    if st.button("➕ Add Item (append to ItemMaster)", key="btn_add_item", type="primary"):
        new_row = run_add_item_logic()
        if new_row is not None:
            # Write directly — no preview step
            _df = st.session_state["item_df"]
            for k in new_row.keys():
                if k not in _df.columns:
                    _df[k] = ""
            _df.loc[len(_df)] = new_row
            st.session_state["item_df"]  = _df
            st.session_state["dirty"]    = True
            st.session_state["last_add_msg"] = (
                f"✅ SAVED: {new_row.get('system_item_code','')}  |  "
                f"{new_row.get('Item_Name','')}  |  "
                f"Vendor: {new_row.get('Vendor_Name','')}  |  "
                f"Ready for next entry."
            )
            reset_form_only(rerun=True)

    if st.session_state.get("last_add_msg"):
        st.success(st.session_state["last_add_msg"])
        st.caption("👆 Form cleared — fill in the next item.")

    st.markdown("---")

    # ── Download ──
    export_df    = st.session_state["item_df"].copy()
    ordered_cols = [c for c in V14_COLS if c in export_df.columns]
    extra_cols   = [c for c in export_df.columns if c not in V14_COLS]
    export_df    = export_df.reindex(columns=ordered_cols + extra_cols)
    csv_out      = export_df.to_csv(index=False).encode("utf-8-sig")

    if st.session_state.get("dirty", False):
        st.warning("⚠ Unsaved changes — please Download or Save.")

    st.download_button(
        "⬇️ Download Updated ItemMaster CSV",
        data=csv_out,
        file_name="ItemMaster.updated.csv",
        mime="text/csv",
        key="btn_download_csv",
    )

    # ── Save local (2-step confirm) ──
    if st.button("💾 Save to local file", key="btn_save_local"):
        st.session_state["confirm_save_open"] = True

    if st.session_state.get("confirm_save_open", False):
        st.warning("请确认：你要把当前 ItemMaster 保存到本机文件吗？")
        col_yes, col_no = st.columns(2)
        with col_no:
            if st.button("NO - Cancel", key="btn_confirm_save_no"):
                st.session_state["confirm_save_open"] = False
                st.rerun()
        with col_yes:
            if st.button("YES - Confirm Save", key="btn_confirm_save_yes"):
                out_path = (Path(__file__).parent.parent / "data" / "ItemMaster.SAVED.csv").resolve()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                export_df2    = st.session_state["item_df"].copy()
                ordered_cols2 = [c for c in V14_COLS if c in export_df2.columns]
                extra_cols2   = [c for c in export_df2.columns if c not in V14_COLS]
                export_df2    = export_df2.reindex(columns=ordered_cols2 + extra_cols2)
                csv_out2      = export_df2.to_csv(index=False).encode("utf-8-sig")
                try:
                    out_path.write_bytes(csv_out2)
                except PermissionError:
                    ts2      = datetime.now().strftime("%Y%m%d_%H%M%S")
                    out_path = out_path.with_name(f"ItemMaster.SAVED_{ts2}.csv")
                    out_path.write_bytes(csv_out2)
                st.session_state["confirm_save_open"] = False
                st.session_state["dirty"] = False
                st.success(f"Saved ✅ → {out_path}")
                st.rerun()