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
    if key in ("item_name", "item_desc", "vendor_name", "vendor_item_code"):
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
    must_norm = [re.sub(r"\s+", " ", str(k)).strip() for k in must_have]

    for i in range(min(len(raw), 40)):
        row = raw.iloc[i].astype(str).tolist()
        row_norm = [re.sub(r"\s+", " ", str(c)).strip() for c in row]
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
    if df is None:
        return df
    rename_map = {}
    if "Vendor_Name" not in df.columns and "Vendor Name" in df.columns:
        rename_map["Vendor Name"] = "Vendor_Name"
    if "Vendor_Item_Code" not in df.columns:
        if "Vendor Item Code" in df.columns:
            rename_map["Vendor Item Code"] = "Vendor_Item_Code"
        if "Vendor Item_Code" in df.columns:
            rename_map["Vendor Item_Code"] = "Vendor_Item_Code"
    if rename_map:
        df = df.rename(columns=rename_map)
    return df

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
        must_have=["Item_Code", "Item_Name", "Item_Group", "Uom_Family", "Default Location"],
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

# Ensure Item_Code col exists
if "Item_Code" not in item_df.columns:
    item_df["Item_Code"] = ""

with st.expander("DEBUG (optional)", expanded=False):
    st.write("DropDown columns =", list(dropdown_df.columns))
    st.write("ItemMaster columns =", list(item_df.columns))
    st.dataframe(dropdown_df.head(10), use_container_width=True)
    st.dataframe(item_df.head(10), use_container_width=True)

# =========================
# Item Code (always visible above tabs)
# =========================
st.subheader("New Item Entry")

# Compute next_code from item_group session value
group_val = gs("item_group", "")
prefix = norm_prefix(group_val)
max_n = 0
if prefix:
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    for code in item_df["Item_Code"].dropna().astype(str).str.strip().str.upper():
        m = pattern.match(code)
        if m:
            max_n = max(max_n, int(m.group(1)))
next_code = f"{prefix}-{max_n + 1:04d}" if prefix else "WAITING_ITEM_GROUP"
# ✅ Don't set item_code in session_state — widget key is versioned, value derived from next_code directly

st.markdown(
    f"""
    <div style="padding:10px;border:2px solid #111;border-radius:10px;
                font-size:26px;font-weight:900;color:#111;background:#f3f4f6;
                margin-bottom:12px;">
        ITEM CODE: {next_code}
    </div>
    """,
    unsafe_allow_html=True
)
st.text_input("Item Code (Auto Generated)", value=next_code, key=fk("item_code"), disabled=True)

UOMTYPE_TO_BASE = {"PCS/COUNT": "PCS", "LENGTH": "MM", "AREA": "MM2", "WEIGHT": "KG"}

# =========================
# Tabs
# =========================
tab1, tab2, tab3 = st.tabs(["📋 Item Info", "⚙️ Specification", "📦 Pack & Save"])

# ── TAB 1: Item Info ─────────────────────────────────────────
with tab1:
    col_a, col_b = st.columns(2)

    with col_a:
        st.selectbox("Item Group (Required)", [""] + get_options(dropdown_df, "Item_Group"), key=fk("item_group"))
        ITEM_CATEGORY_OPTS = ["", "RAW_MATERIAL", "WIP", "FINISHED_GOODS", "CONSUMABLE"]
        st.selectbox("Item Category (Required)", ITEM_CATEGORY_OPTS, key=fk("item_category"))
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
        st.checkbox("STATUS CONSIGN", key=fk("status_consign"), value=False)

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
# Add Item + Save/Export (inside Tab 3 context)
# =========================
with tab3:
 st.markdown("---")

 # ── STEP 1: User clicks "Add Item" → validate → store pending_row → show preview ──
 if st.button("➕ Add Item (append to ItemMaster)", key="btn_add_item", type="primary"):
    # Clear any previous pending
    st.session_state.pop("pending_row", None)
    st.session_state.pop("pending_preview", None)

    entered_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    code_to_save = up(next_code)

    REQUIRED = {
        "Item Name":                    gs("item_name", ""),
        "Item Descriptions":            gs("item_desc", ""),
        "Vendor Name":                  gs("vendor_name", ""),
        "Vendor Item Code":             gs("vendor_item_code", ""),
        "Item Group":                   gs("item_group", ""),
        "Item Category":                gs("item_category", ""),
        "UOM Type":                     gs("uom_type", ""),
        "Track Lot":                    gs("track_lot", ""),
        "Default Location":             gs("default_location", ""),
        "Delivery Lead time (Week)":    gs("delivery_lead_time", 0.0),
        "Standard Pack":                gs("standard_pack", 0),
        "Entered By":                   gs("entered_by", ""),
        "Status":                       gs("status", ""),
    }
    uom_type_now2 = gs("uom_type", "")
    if uom_type_now2 in ["LENGTH", "AREA"]:
        REQUIRED.update({
            "Pack_Uom":         gs("pack_uom", ""),
            "Pack Size / Unit": gs("pack_size_units", 0.0),
        })
    if uom_type_now2 == "WEIGHT":
        REQUIRED.update({
            "Open Life Hour":  gs("open_life_hours", ""),
            "Shelf life days": gs("shelf_life_days", ""),
        })

    missing = [k for k, v in REQUIRED.items() if missing_value(v)]
    if missing:
        st.error("❌ Required fields missing: " + ", ".join(missing))
        st.stop()

    # Dimension validation
    dim_errors = []
    def pd_wrap(key, label):
        v, err = parse_dim_field(gs(key, ""), label)
        if err:
            dim_errors.append(err)
            return None
        return v

    uom_type_now3 = gs("uom_type", "")
    if uom_type_now3 == "LENGTH":
        roll_len_v = pd_wrap("roll_len", "Roll Length mm")
        roll_wid_v = pd_wrap("roll_wid", "Roll Width mm")
        roll_thk_v = pd_wrap("roll_thk", "Roll Thickness mm")
        if roll_len_v is not None and roll_len_v == 0.0:
            dim_errors.append("❌ Roll Length mm: 必填，不能为空或0")
        if roll_wid_v is not None and roll_wid_v == 0.0:
            dim_errors.append("❌ Roll Width mm: 必填，不能为空或0")
        if roll_thk_v is not None and roll_thk_v == 0.0:
            dim_errors.append("❌ Roll Thickness mm: 必填，不能为空或0")
        sheet_len_v = sheet_wid_v = sheet_thk_v = 0.0
        open_life_v = shelf_life_v = 0.0
    elif uom_type_now3 == "AREA":
        sheet_len_v = pd_wrap("sheet_len", "Sheet Length mm")
        sheet_wid_v = pd_wrap("sheet_wid", "Sheet Width mm")
        sheet_thk_v = pd_wrap("sheet_thk", "Sheet Thickness mm")
        if sheet_len_v is not None and sheet_len_v == 0.0:
            dim_errors.append("❌ Sheet Length mm: 必填，不能为空或0")
        if sheet_wid_v is not None and sheet_wid_v == 0.0:
            dim_errors.append("❌ Sheet Width mm: 必填，不能为空或0")
        if sheet_thk_v is not None and sheet_thk_v == 0.0:
            dim_errors.append("❌ Sheet Thickness mm: 必填，不能为空或0")
        roll_len_v = roll_wid_v = roll_thk_v = 0.0
        open_life_v = shelf_life_v = 0.0
    elif uom_type_now3 == "WEIGHT":
        open_life_v  = pd_wrap("open_life_hours", "Open Life Hour")
        shelf_life_v = pd_wrap("shelf_life_days",  "Shelf life days")
        if open_life_v is not None and open_life_v == 0.0:
            dim_errors.append("❌ Open Life Hour: 必填，不能为空或0")
        if shelf_life_v is not None and shelf_life_v == 0.0:
            dim_errors.append("❌ Shelf life days: 必填，不能为空或0")
        roll_len_v = roll_wid_v = roll_thk_v = 0.0
        sheet_len_v = sheet_wid_v = sheet_thk_v = 0.0
    else:
        roll_len_v = roll_wid_v = roll_thk_v = 0.0
        sheet_len_v = sheet_wid_v = sheet_thk_v = 0.0
        open_life_v = shelf_life_v = 0.0

    if dim_errors:
        for e in dim_errors:
            st.error(e)
        st.stop()

    if code_to_save == "WAITING_ITEM_GROUP" or not code_to_save:
        st.error("❌ Please select Item Group first.")
        st.stop()

    exists_code = (
        item_df["Item_Code"].dropna().astype(str).str.strip().str.upper()
        .eq(code_to_save).any()
    )
    if exists_code:
        st.error(f"❌ Item_Code already exists: {code_to_save}")
        st.stop()

    vic = up(gs("vendor_item_code", ""))
    # ✅ N/A is acceptable — skip uniqueness check (e.g. consumables with no vendor code)
    if "Vendor_Item_Code" in item_df.columns and vic and vic != "N/A":
        if (item_df["Vendor_Item_Code"].fillna("").astype(str).str.strip().str.upper().eq(vic)).any():
            st.error(f"❌ Vendor Item Code already exists: {vic}")
            st.stop()

    # ✅ Duplicate content check — reject if all fields (except Item_Code & Entered_At) are identical
    EXCLUDE_FROM_DUP = {"Item_Code", "Entered_At", "Entered_By"}
    _uom_now = gs("uom_type", "PCS/COUNT")

    candidate = {
        "Item_Name":               up(gs("item_name", "")),
        "Item Descriptions":       up(gs("item_desc", "")),
        "Vendor_Name":             up(gs("vendor_name", "")),
        "Vendor_Item_Code":        up(gs("vendor_item_code", "")),
        "Delivery Lead Time (Week)": norm_num(gs("delivery_lead_time", 0.0)),
        "STATUS_CONSIGN":          "TRUE" if gs("status_consign", False) else "FALSE",
        "Standard Pack":           norm_num(gs("standard_pack", 0)),
        "Item_Group":              up(gs("item_group", "")),
        "Item_Category":           up(gs("item_category", "")),
        "Uom_Family":              up(uom_family),
        "Uom_Base":                up(uom_base),
        "Track Lot":               up(gs("track_lot", "")),
        "Default Location":        up(gs("default_location", "")),
        "Pack_Uom":                up(gs("pack_uom", "")),
        "Pack_Size / units":       "" if _uom_now in ["PCS/COUNT", "WEIGHT"] else norm_num(gs("pack_size_units", 0.0)),
        "Roll_Length_mm":          norm_num(roll_len_v),
        "Roll_Width_mm":           norm_num(roll_wid_v),
        "Roll_Thickness_mm":       norm_num(roll_thk_v),
        "Sheet_Length_mm":         norm_num(sheet_len_v),
        "Sheet_Width_mm":          norm_num(sheet_wid_v),
        "Sheet_Thickness_mm":      norm_num(sheet_thk_v),
        "Open_life_hours":         norm_num(open_life_v),
        "Shelf_life_days":         norm_num(shelf_life_v),
        "Status":                  up(gs("status", "")),
        "ROHS":  "TRUE" if gs("rohs", False) else "FALSE",
        "ESD":   "TRUE" if gs("esd",  False) else "FALSE",
        "UL":    "TRUE" if gs("ul",   False) else "FALSE",
        "OTHER": up(gs("other_compliance", "")),
    }

    # Compare against every existing row — match = all shared fields identical
    dup_found = False
    dup_code  = ""
    for _, existing_row in item_df.iterrows():
        match = True
        for field, cval in candidate.items():
            if field in EXCLUDE_FROM_DUP:
                continue
            eval_str = str(existing_row.get(field, "") or "").strip().upper()
            if eval_str != str(cval).strip().upper():
                match = False
                break
        if match:
            dup_found = True
            dup_code  = str(existing_row.get("Item_Code", "?"))
            break

    if dup_found:
        st.error(
            f"❌ Duplicate entry detected — all fields match existing item: **{dup_code}**. "
            f"Please verify this is not an accidental re-entry."
        )
        st.stop()

    # ✅ All validation passed → build new_row and store as pending
    new_row = {
        "Item_Code":               code_to_save,
        "Item_Name":               up(gs("item_name", "")),
        "Item Descriptions":       up(gs("item_desc", "")),
        "Vendor_Name":             up(gs("vendor_name", "")),
        "Vendor_Item_Code":        up(gs("vendor_item_code", "")),
        "Delivery Lead Time (Week)": norm_num(gs("delivery_lead_time", 0.0)),
        "STATUS_CONSIGN":          "TRUE" if gs("status_consign", False) else "FALSE",
        "Standard Pack":           norm_num(gs("standard_pack", 0)),
        "Item_Group":              up(gs("item_group", "")),
        "Item_Category":           up(gs("item_category", "")),
        "Uom_Family":              up(uom_family),
        "Uom_Base":                up(uom_base),
        "Track Lot":               up(gs("track_lot", "")),
        "Default Location":        up(gs("default_location", "")),
        "Pack_Uom":                up(gs("pack_uom", "")),
        "Pack_Size / units":       "" if _uom_now in ["PCS/COUNT", "WEIGHT"] else norm_num(gs("pack_size_units", 0.0)),
        "Pack_Size_Uom":           up(pack_size_uom),
        "Roll_Length_mm":          norm_num(roll_len_v),
        "Roll_Width_mm":           norm_num(roll_wid_v),
        "Roll_Thickness_mm":       norm_num(roll_thk_v),
        "Sheet_Length_mm":         norm_num(sheet_len_v),
        "Sheet_Width_mm":          norm_num(sheet_wid_v),
        "Sheet_Thickness_mm":      norm_num(sheet_thk_v),
        "Open_life_hours":         norm_num(open_life_v),
        "Shelf_life_days":         norm_num(shelf_life_v),
        "Entered_By":              up(gs("entered_by", "")),
        "Entered_At":              entered_at,
        "Status":                  up(gs("status", "")),
        "ROHS":  "TRUE" if gs("rohs", False) else "FALSE",
        "ESD":   "TRUE" if gs("esd",  False) else "FALSE",
        "UL":    "TRUE" if gs("ul",   False) else "FALSE",
        "OTHER": up(gs("other_compliance", "")),
    }
    st.session_state["pending_row"]     = new_row
    st.session_state["pending_preview"] = True
    st.rerun()

 # ── STEP 2: Show preview table + Confirm / Back ──
 if st.session_state.get("pending_preview") and st.session_state.get("pending_row"):
    nr = st.session_state["pending_row"]

    st.markdown("---")
    st.warning("⚠️ Please review before confirming — this will be written to ItemMaster.")

    uom_fam = nr.get("Uom_Family", "PCS")

    # Helper: render a compact section as markdown table (no wide spacing)
    def preview_block(title: str, rows: list):
        """rows = list of (label, value) tuples. Skips empty/zero/dash values."""
        filtered = [(k, v) for k, v in rows if v and v not in ("0", "0.0", "—", "FALSE")]
        if not filtered:
            return
        st.markdown(f"**{title}**")
        lines = ["| Field | Value |", "|---|---|"]
        for k, v in filtered:
            lines.append(f"| {k} | {v} |")
        st.markdown("\n".join(lines))
        st.markdown("")

    preview_block("🔖 Identification", [
        ("Item Code",        nr.get("Item_Code","")),
        ("Item Group",       nr.get("Item_Group","")),
        ("Item Category",    nr.get("Item_Category","")),
        ("Item Name",        nr.get("Item_Name","")),
        ("Description",      nr.get("Item Descriptions","")),
        ("Status",           nr.get("Status","")),
    ])

    preview_block("🏭 Vendor", [
        ("Vendor Name",      nr.get("Vendor_Name","")),
        ("Vendor Item Code", nr.get("Vendor_Item_Code","")),
        ("Lead Time (Wk)",   nr.get("Delivery Lead Time (Week)","")),
        ("Standard Pack",    nr.get("Standard Pack","")),
        ("Status Consign",   nr.get("STATUS_CONSIGN","") if nr.get("STATUS_CONSIGN") == "TRUE" else ""),
    ])

    preview_block("📐 UOM & Location", [
        ("UOM Family",       nr.get("Uom_Family","")),
        ("UOM Base",         nr.get("Uom_Base","")),
        ("Track Lot",        nr.get("Track Lot","")),
        ("Default Location", nr.get("Default Location","")),
    ])

    # Packaging — only show if LENGTH or AREA
    if uom_fam in ("MM", "MM2"):
        preview_block("📦 Packaging", [
            ("Pack UOM",         nr.get("Pack_Uom","") or "—"),
            ("Pack Size / Unit", nr.get("Pack_Size / units","") or "—"),
            ("Pack Size UOM",    nr.get("Pack_Size_Uom","") or "—"),
        ])

    # Dimensions — only show relevant rows per UOM
    if uom_fam == "MM":
        preview_block("📏 Roll Dimensions", [
            ("Roll Length mm",    nr.get("Roll_Length_mm","")),
            ("Roll Width mm",     nr.get("Roll_Width_mm","")),
            ("Roll Thickness mm", nr.get("Roll_Thickness_mm","")),
        ])
    elif uom_fam == "MM2":
        preview_block("📏 Sheet Dimensions", [
            ("Sheet Length mm",    nr.get("Sheet_Length_mm","")),
            ("Sheet Width mm",     nr.get("Sheet_Width_mm","")),
            ("Sheet Thickness mm", nr.get("Sheet_Thickness_mm","")),
        ])
    elif uom_fam == "KG":
        preview_block("⏱ Shelf Life", [
            ("Open Life Hours", nr.get("Open_life_hours","")),
            ("Shelf Life Days", nr.get("Shelf_life_days","")),
        ])

    # Compliance — only show TRUE values
    compliance_val = " / ".join(
        k for k, v in [("ROHS", nr.get("ROHS")), ("ESD", nr.get("ESD")), ("UL", nr.get("UL"))]
        if v == "TRUE"
    ) or "None"
    preview_block("✅ Compliance & Record", [
        ("Compliance",   compliance_val),
        ("Other",        nr.get("OTHER","") or ""),
        ("Entered By",   nr.get("Entered_By","")),
        ("Entered At",   nr.get("Entered_At","")),
    ])

    st.markdown("---")
    col_confirm, col_back = st.columns(2)

    with col_back:
        if st.button("✏️ Back to Edit", key="btn_preview_back"):
            st.session_state.pop("pending_row", None)
            st.session_state.pop("pending_preview", None)
            st.rerun()

    with col_confirm:
        if st.button("✅ Confirm & Save to ItemMaster", key="btn_preview_confirm", type="primary"):
            nr = st.session_state["pending_row"]
            item_df = st.session_state["item_df"]

            for k in nr.keys():
                if k not in item_df.columns:
                    item_df[k] = ""

            item_df.loc[len(item_df)] = nr
            st.session_state["item_df"] = item_df
            st.session_state["dirty"]   = True

            st.session_state["last_add_msg"] = (
                f"✅ SAVED: {nr['Item_Code']}  |  "
                f"{nr.get('Item_Name','')}  |  "
                f"Vendor: {nr.get('Vendor_Name','')}  |  "
                f"Form cleared — ready for next entry."
            )
            st.session_state.pop("pending_row", None)
            st.session_state.pop("pending_preview", None)
            reset_form_only(rerun=True)

 # ── Success banner ──
 if st.session_state.get("last_add_msg") and not st.session_state.get("pending_preview"):
    st.success(st.session_state["last_add_msg"])
    st.caption("👆 Form cleared. Fill in the fields for the next item.")

 # ── Download ──
 export_df = st.session_state["item_df"].copy()
 base_cols = st.session_state.get("base_cols", export_df.columns.tolist())
 export_df = export_df.reindex(columns=base_cols + [c for c in export_df.columns if c not in base_cols])
 csv_out = export_df.to_csv(index=False).encode("utf-8-sig")
 st.download_button(
     "⬇️ Download Updated ItemMaster CSV",
     data=csv_out,
     file_name="ItemMaster.updated.csv",
     mime="text/csv",
     key="btn_download_csv"
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
             st.info("已取消保存。")
             st.rerun()
     with col_yes:
         if st.button("YES - Confirm Save", key="btn_confirm_save_yes"):
             out_path = (Path(__file__).parent.parent / "data" / "ItemMaster.SAVED.csv").resolve()
             out_path.parent.mkdir(parents=True, exist_ok=True)
             export_df2 = st.session_state["item_df"].copy()
             base_cols2 = st.session_state.get("base_cols", export_df2.columns.tolist())
             export_df2 = export_df2.reindex(columns=base_cols2 + [c for c in export_df2.columns if c not in base_cols2])
             csv_out2 = export_df2.to_csv(index=False).encode("utf-8-sig")
             try:
                 out_path.write_bytes(csv_out2)
             except PermissionError:
                 ts2 = datetime.now().strftime("%Y%m%d_%H%M%S")
                 out_path = out_path.with_name(f"ItemMaster.SAVED_{ts2}.csv")
                 out_path.write_bytes(csv_out2)
             st.session_state["confirm_save_open"] = False
             st.session_state["dirty"] = False
             reset_form_only(rerun=False)
             st.success(f"Saved ✅ → {out_path}")
             st.rerun()