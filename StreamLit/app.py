import streamlit as st
import pandas as pd
import re
from pathlib import Path
from datetime import datetime

st.set_page_config(layout="wide")
st.title("Mini-MES Item Master")
st.sidebar.caption(f"RUNNING FILE: {__file__}")

# =========================
# Helpers
# =========================
FORM_KEYS = [
    "item_code","item_name","item_desc","vendor_name","vendor_item_code","delivery_lead_time","standard_pack",
    "uom_type",
    "item_group","uom_family","uom_base","track_lot","default_location",
    "item_category",  # ✅ NEW
    "pack_uom","pack_size_units","pack_size_uom",
    "roll_len","roll_wid","roll_thk","sheet_len","sheet_wid","sheet_thk",
    "open_life_hours","shelf_life_days",
]

def to_upper_key(key: str):
    v = st.session_state.get(key, "")
    if isinstance(v, str):
        st.session_state[key] = v.upper()





def reset_form_only(rerun: bool = True):
    for k in FORM_KEYS:
        st.session_state.pop(k, None)
    if rerun:
        st.rerun()

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


# =========================
# Sidebar: Upload
# =========================

st.sidebar.header("Upload Google Sheet CSV")

colA, colB = st.sidebar.columns(2)
with colA:
    if st.sidebar.button("Reset Form", key="btn_reset_form"):
        reset_form_only()   # 只清表单字段，不要清 uploader

dropdown_file = st.sidebar.file_uploader(
    "Upload DropDown CSV", type=["csv"], key="uploader_dropdown"
)
itemmaster_file = st.sidebar.file_uploader(
    "Upload ItemMaster CSV", type=["csv"], key="uploader_itemmaster"
)



# ✅ 关键：一定要在 read_sheet_csv 之前挡住 None
if dropdown_file is None or itemmaster_file is None:
    st.warning("请上传 DropDown.csv 与 ItemMaster.csv")
    st.stop()

# =========================
# Load CSVs (Dropdown + ItemMaster)
# =========================
dropdown_sig = (getattr(dropdown_file, "name", ""), getattr(dropdown_file, "size", 0))
itemmaster_sig = (getattr(itemmaster_file, "name", ""), getattr(itemmaster_file, "size", 0))

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
        must_have=["Item_Code", "Item_Name", "Item_Group", "Uom_Family", "Default Location"]
    )
except ValueError:
    st.error("ItemMaster.csv 格式不正确：找不到模板表头。请使用系统导出的 ItemMaster 模板文件再上传。")
    st.stop()

# 允许你强制回到上传的原始 ItemMaster（丢弃未保存追加）
if st.sidebar.button("Reload from ItemMaster CSV", key="btn_reload_itemmaster"):
    st.session_state["item_df"] = loaded_item_df.copy()
    st.session_state["base_cols"] = loaded_item_df.columns.tolist()
    st.session_state["dirty"] = False
    reset_form_only(rerun=False)
    st.rerun()







# 初始化 session 工作副本（关键：不再因 rerun 丢失）
if "item_df" not in st.session_state or st.session_state.get("itemmaster_sig") != itemmaster_sig:
    st.session_state["item_df"] = loaded_item_df.copy()
    st.session_state["base_cols"] = loaded_item_df.columns.tolist()   # ✅ 记住原列顺序
    st.session_state["itemmaster_sig"] = itemmaster_sig
    st.session_state["dirty"] = False
    reset_form_only(rerun=False)

item_df = st.session_state["item_df"]



# =========================
# DEBUG（你不要可以注释掉）
# =========================
with st.expander("DEBUG (optional)", expanded=False):
    st.write("DropDown columns =", list(dropdown_df.columns))
    st.write("ItemMaster columns =", list(item_df.columns))
    st.dataframe(dropdown_df.head(10), use_container_width=True)
    st.dataframe(item_df.head(10), use_container_width=True)

# =========================
# Form UI
# =========================
st.subheader("New Item Entry (1–22)")

# =========================
# Item Code Auto (TOP + BIG)
# =========================
if "Item_Code" not in item_df.columns:
    item_df["Item_Code"] = ""

def norm_prefix(x: str) -> str:
    x = str(x or "").strip().upper()
    x = re.sub(r"\s+", "_", x)
    x = re.sub(r"[^A-Z0-9_]", "", x)
    return x

prefix = norm_prefix(st.session_state.get("item_group", ""))  # ✅ 用 session，避免顺序问题
pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$") if prefix else None

max_n = 0
if prefix:
    for code in item_df["Item_Code"].dropna().astype(str).str.strip().str.upper():
        m = pattern.match(code)
        if m:
            max_n = max(max_n, int(m.group(1)))

next_code = f"{prefix}-{max_n + 1:04d}" if prefix else "PLEASE_SELECT_ITEM_GROUP"

# ✅ 让 reset 能清，但依然 disabled
st.session_state["item_code"] = next_code

st.markdown(
    f"""
    <div style="padding:10px;border:2px solid #111;border-radius:10px;
                font-size:26px;font-weight:900;color:#111;background:#f3f4f6;">
        ITEM CODE: {next_code}
    </div>
    """,
    unsafe_allow_html=True
)

st.text_input(
    "Item Code (Auto Generated)",
    value=next_code,
    key="item_code",
    disabled=True
)



item_name = st.text_input(
    "1. Item Name",
    key="item_name",
    on_change=to_upper_key,
    args=("item_name",),
)

item_desc = st.text_area(
    "2. Item Descriptions",
    height=80,
    key="item_desc",
    on_change=to_upper_key,
    args=("item_desc",),
)

vendor_name = st.text_input(
    "3. Vendor Name",
    key="vendor_name",
    on_change=to_upper_key,
    args=("vendor_name",),
)

vendor_item_code = st.text_input(
    "4. Vendor Item Code",
    key="vendor_item_code",
    on_change=to_upper_key,
    args=("vendor_item_code",),
)

delivery_lead_time = st.number_input(
    "5. Delivery Lead time (Week)",
    min_value=0,
    step=1,
    format="%d",
    key="delivery_lead_time"
)

standard_pack = st.number_input(
    "6. Standard Pack",
    min_value=0,
    step=1,
    format="%d",
    key="standard_pack"
)

# 如果你希望 Standard Pack 也强制大写（有时会写 CARTON / BAG），改成：
# standard_pack = st.text_input("6. Standard Pack", key="standard_pack", on_change=to_upper_key, args=("standard_pack",))

st.divider()

uom_type = st.radio(
    "UOM Type (先选这个，系统才显示相关字段)",
    ["PCS/COUNT", "LENGTH", "WEIGHT", "AREA"],
    horizontal=True,
    key="uom_type"
)

# UOM Type → 自动单位映射（必须与你 DropDown 的 Uom_Base 列一致）
UOMTYPE_TO_BASE = {
    "PCS/COUNT": "PCS",
    "LENGTH": "MM",
    "AREA": "MM2",
    "WEIGHT": "KG",
}

uom_auto = UOMTYPE_TO_BASE.get(uom_type, "")



item_group = st.selectbox(
    "7. Item Group",
    [""] + get_options(dropdown_df, "Item_Group"),
    key="item_group",
)

ITEM_CATEGORY_OPTS = ["", "RAW_MATERIAL", "WIP", "FINISHED_GOODS", "CONSUMABLE"]
item_category = st.selectbox(
    "8. Item Category (Required)",
    ITEM_CATEGORY_OPTS,
    key="item_category",
)

locked_field("9. Uom_Family (Auto)", uom_auto)
locked_field("10. Uom_Base (Auto)", uom_auto)

uom_family = uom_auto
uom_base = uom_auto


track_lot_opts = [""] + (get_options(dropdown_df, "Track Lot") or ["Y", "N"])
track_lot = st.selectbox("11. Track Lot", track_lot_opts, key="track_lot")

default_location = st.selectbox(
    "12. Default Location",
    [""] + get_options(dropdown_df, "Default Location"),
    key="default_location"
)

# ✅ Pack 只给 LENGTH / AREA（WEIGHT 不要 pack）
if uom_type in ["LENGTH", "AREA"]:

    pack_uom = st.selectbox(
        "12. Pack_Uom",
        [""] + get_options(dropdown_df, "Pack_Uom"),
        key="pack_uom"
    )

    pack_size_units = st.number_input(
        "13. Pack Size / Unit",
        min_value=0.0,
        step=1.0,
        key="pack_size_units"
    )

    locked_field("14. Pack Size Uom (Auto)", uom_auto)

    pack_size_uom = uom_auto

else:
    pack_uom = ""
    pack_size_units = ""
    pack_size_uom = ""

st.divider()

# 15–20 尺寸：只在 LENGTH/AREA 才出现（WEIGHT 不需要这些尺寸）
# LENGTH = ROLL ONLY
if uom_type == "LENGTH":
    roll_len = st.number_input("15. Roll Length mm", min_value=0.0, step=1.0, key="roll_len")
    roll_wid = st.number_input("16. Roll Width mm",  min_value=0.0, step=1.0, key="roll_wid")
    roll_thk = st.number_input("17. Roll Thickness mm", min_value=0.0, step=0.1, key="roll_thk")

    sheet_len = sheet_wid = sheet_thk = ""
    open_life_hours = shelf_life_days = ""

# AREA = SHEET ONLY
elif uom_type == "AREA":
    sheet_len = st.number_input("18. Sheet Length mm", min_value=0.0, step=1.0, key="sheet_len")
    sheet_wid = st.number_input("19. Sheet Width mm",  min_value=0.0, step=1.0, key="sheet_wid")
    sheet_thk = st.number_input("20. Sheet Thickness mm", min_value=0.0, step=0.1, key="sheet_thk")

    roll_len = roll_wid = roll_thk = ""
    open_life_hours = shelf_life_days = ""

# WEIGHT = Life only (暂时)
elif uom_type == "WEIGHT":
    roll_len = roll_wid = roll_thk = ""
    sheet_len = sheet_wid = sheet_thk = ""

    open_life_hours = st.number_input("21. Open Life Hour", min_value=0.0, step=1.0, format="%.0f", key="open_life_hours")
    shelf_life_days = st.number_input("22. Shelf_life_days", min_value=0.0, step=1.0, format="%.0f", key="shelf_life_days")

# PCS/COUNT（保持你原本隐藏逻辑）
else:
    roll_len = roll_wid = roll_thk = ""
    sheet_len = sheet_wid = sheet_thk = ""
    open_life_hours = ""
    shelf_life_days = ""

st.divider()




# =========================
# Save / Export
# =========================
st.divider()
st.subheader("Save / Export")

# ✅ 强制同步 dirty：如果已回到原始上传版本，就不该显示未保存
try:
    same_as_uploaded = st.session_state["item_df"].reset_index(drop=True).equals(
        loaded_item_df.reset_index(drop=True)
    )
    if same_as_uploaded:
        st.session_state["dirty"] = False
except Exception:
    pass
if st.session_state.get("dirty", False):
    st.warning("⚠️ You have unsaved changes. Click 'Save to local file' or 'Download' to keep it.")
else:
    st.info("ℹ️ No pending changes.")

# --- Add Item ---
if st.button("Add Item (append to ItemMaster)", key="btn_add_item"):
    # 必填校验
    if not item_name.strip():
        st.error("Item Name is required.")
        st.stop()
    if not item_group.strip():
        st.error("Item Group is required.")
        st.stop()
    if not item_category.strip():
        st.error("Item Category is required.")
        st.stop()
    if not uom_family.strip():
        st.error("Uom_Family is required.")
        st.stop()
    if not uom_base.strip():
        st.error("Uom_Base is required.")
        st.stop()
    if not track_lot.strip():
        st.error("Track Lot is required.")
        st.stop()
    if next_code == "PLEASE_SELECT_ITEM_GROUP":
        st.error("Please select Item Group first.")
        st.stop()
    if not item_category.strip():
        st.error("Item Category is required.")
        st.stop()

    def up(x: str) -> str:
        return str(x or "").strip().upper()

    def norm_num(x) -> str:
        if x is None:
            return ""
        if isinstance(x, (int, float)):
            return str(x)
        return str(x).strip()

    new_row = {
        "Item_Code": up(next_code),
        "Item_Name": up(item_name),
        "Item Descriptions": up(item_desc),
        "Vendor Name": up(vendor_name),
        "Vendor Item_Code": up(vendor_item_code),

        "Delivery Lead Time (Week)": norm_num(delivery_lead_time),
        "Standard Pack": norm_num(standard_pack),

        "Item_Group": up(item_group),
        "Item_Category": up(item_category),   # ✅ 加在这里
        "Uom_Family": up(uom_family),
        "Uom_Base": up(uom_base),
        "Track Lot": up(track_lot),
        "Default Location": up(default_location),

        "Pack_Uom": up(pack_uom),
        "Pack_Size / units": norm_num(pack_size_units),
        "Pack_Size_Uom": up(pack_size_uom),

        "Roll_Length_mm": norm_num(roll_len),
        "Roll_Width_mm": norm_num(roll_wid),
        "Roll_Thickness_mm": norm_num(roll_thk),
        "Sheet_Length_mm": norm_num(sheet_len),
        "Sheet_Width_mm": norm_num(sheet_wid),
        "Sheet_Thickness_mm": norm_num(sheet_thk),

        "Open_life_hours": norm_num(open_life_hours),
        "Shelf_life_days": norm_num(shelf_life_days),
    }
    
    # 缺列补齐
    for k in new_row.keys():
        if k not in item_df.columns:
            item_df[k] = ""

    item_df.loc[len(item_df)] = new_row
    st.session_state["dirty"] = True

# ✅ Add Item 后清空表单（但保留 item_df）
    reset_form_only(rerun=True)

# 生成导出内容（永远从 session 的 item_df）
export_df = st.session_state["item_df"]

base_cols = st.session_state.get("base_cols", export_df.columns.tolist())
extra_cols = [c for c in export_df.columns if c not in base_cols]

save_ts = st.session_state.get("last_save_ts", "")
save_path = st.session_state.get("last_save_path", "")

export_df = export_df.copy()
export_df["Saved_At"] = save_ts
export_df["Saved_File"] = save_path

# ✅ 按原表顺序导出 + 把新列放最后
export_df = export_df.reindex(columns=base_cols + [c for c in export_df.columns if c not in base_cols])

csv_out = export_df.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "Download Updated ItemMaster CSV",
    data=csv_out,
    file_name="ItemMaster.updated.csv",
    mime="text/csv",
    key="btn_download_csv"
)



# Save to local file
if st.button("Save to local file", key="btn_save_local"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out_path = (Path(__file__).parent.parent / "data" / "ItemMaster.SAVED.csv").resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # ✅ 再重新生成一次 csv_out（包含 Saved_At/Saved_File）
    export_df = st.session_state["item_df"].copy()
    base_cols = st.session_state.get("base_cols", export_df.columns.tolist())
    export_df["Saved_At"] = ts
    export_df["Saved_File"] = str(out_path)
    export_df = export_df.reindex(columns=base_cols + [c for c in export_df.columns if c not in base_cols])
    csv_out2 = export_df.to_csv(index=False).encode("utf-8-sig")

    saved_ok = False
    try:
        out_path.write_bytes(csv_out2)
        saved_ok = True
    except PermissionError:
        try:
            ts2 = datetime.now().strftime("%Y%m%d_%H%M%S")
            alt_path = out_path.with_name(f"ItemMaster.SAVED_{ts2}.csv")
            alt_path.write_bytes(csv_out2)
            out_path = alt_path
            saved_ok = True
        except Exception as e:
            st.error(f"Save failed: {e}")

    if saved_ok:
        st.session_state["dirty"] = False
        st.session_state["last_save_ts"] = ts
        st.session_state["last_save_path"] = str(out_path)
        st.session_state["last_save_msg"] = f"Saved ✅ {ts} → {out_path}"
        st.rerun()
    else:
        st.session_state["dirty"] = True

# ✅ 永久显示最后一次保存位置
if st.session_state.get("last_save_msg"):
    st.success(st.session_state["last_save_msg"])