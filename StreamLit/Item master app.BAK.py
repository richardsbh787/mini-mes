import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Mini-MES | Item Master",
    page_icon="🏭",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .stApp {
        background: linear-gradient(180deg,
            #C8E6E0 0%, #B8DDD6 30%, #A5D4CB 60%, #96C9BF 85%, #8BC3B8 100%
        ) !important;
        min-height: 100vh;
    }

    .page-title {
        font-size: 22px; font-weight: 700; color: #1A4A42;
        padding: 16px 0 2px 0; letter-spacing: -0.3px;
    }
    .page-sub { font-size: 12px; color: #5A8880; margin-bottom: 20px; }

    /* Form table - matches screenshot style */
    .form-table {
        width: 100%; border-collapse: collapse;
        background: rgba(255,255,255,0.93);
        border: 1px solid #A0CCC6; border-radius: 10px;
        overflow: hidden; box-shadow: 0 2px 12px rgba(0,100,90,0.10);
        margin-top: 16px;
    }
    .form-table td {
        padding: 12px 18px; border-bottom: 1px solid #C8E2DE;
        font-size: 13.5px; vertical-align: middle;
    }
    .form-table tr:last-child td { border-bottom: none; }
    .form-table tr:nth-child(even) td { background: rgba(184,221,214,0.25); }
    .form-table tr:nth-child(odd) td  { background: rgba(255,255,255,0.80); }
    .td-label {
        font-weight: 600; color: #1A4A42; width: 45%;
        font-size: 13px; letter-spacing: 0.1px;
    }
    .td-value { color: #1C3530; width: 55%; }
    .section-row td {
        background: #5AADA0 !important;
        color: white !important; font-size: 11px;
        font-weight: 700; letter-spacing: 1.2px;
        text-transform: uppercase; padding: 8px 18px !important;
    }

    /* Part number display */
    .pn-ready {
        font-family: 'Courier New', monospace;
        font-size: 20px; font-weight: 700; color: #1A4A42;
        letter-spacing: 3px; background: rgba(180,225,218,0.5);
        padding: 8px 16px; border-radius: 6px;
        border: 1.5px solid #7DBFB5; display: inline-block;
    }
    .pn-pending {
        font-family: 'Courier New', monospace;
        font-size: 20px; font-weight: 700; color: #A0A0A0;
        letter-spacing: 3px; background: #F0F0F0;
        padding: 8px 16px; border-radius: 6px;
        border: 1.5px dashed #C0C0C0; display: inline-block;
    }
    .pn-auto-tag {
        font-size: 10px; color: white; background: #5AADA0;
        padding: 2px 9px; border-radius: 10px;
        margin-left: 8px; font-weight: 600;
        letter-spacing: 0.5px; vertical-align: middle;
    }

    /* Save button */
    .stButton > button {
        background-color: #3A9E92 !important; color: white !important;
        font-size: 14px !important; font-weight: 600 !important;
        padding: 13px 0 !important; border-radius: 8px !important;
        border: none !important; width: 100%;
        letter-spacing: 0.5px; margin-top: 14px;
    }
    .stButton > button:hover { background-color: #2E8078 !important; }

    .success-box {
        background: #E0F5F0; border: 1px solid #7DBFB5;
        border-radius: 8px; padding: 14px 18px;
        color: #1A5C50; font-weight: 600;
        font-size: 14px; margin-top: 12px; text-align: center;
    }

    /* List table */
    .list-table {
        width: 100%; border-collapse: collapse;
        border: 1px solid #A0CCC6; border-radius: 8px;
        overflow: hidden; font-size: 13px;
    }
    .list-table th {
        background: #3A9E92; color: white;
        padding: 10px 13px; font-size: 12px;
        font-weight: 600; text-align: left;
    }
    .list-table td {
        padding: 10px 13px; border-bottom: 1px solid #C8E2DE; color: #1C3530;
    }
    .list-table tr:nth-child(even) td { background: rgba(184,221,214,0.2); }
    .list-table tr:hover td { background: rgba(184,221,214,0.4); }
    .pn-mono { font-family:'Courier New',monospace; font-weight:700; color:#1A4A42; }
    .badge-yes { background:#C8EFE5; color:#0D5C3A; padding:2px 9px; border-radius:10px; font-size:11px; font-weight:600; }
    .badge-no  { background:#F8D7DA; color:#721C24; padding:2px 9px; border-radius:10px; font-size:11px; font-weight:600; }

    /* Metrics */
    .metric-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:20px; }
    .metric-box { background:rgba(255,255,255,0.85); border:1px solid #A0CCC6; border-radius:8px; padding:14px 10px; text-align:center; }
    .metric-n { font-size:28px; font-weight:700; color:#1A4A42; }
    .metric-l { font-size:11px; color:#5A8880; margin-top:3px; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255,255,255,0.85);
        border: 1px solid #A0CCC6; border-radius: 8px;
        padding: 3px; gap: 3px; margin-bottom: 16px;
    }
    .stTabs [data-baseweb="tab"] {
        color: #5A8880; font-weight: 500; font-size: 13px;
        border-radius: 6px; padding: 7px 18px;
    }
    .stTabs [aria-selected="true"] { background: #3A9E92 !important; color: white !important; }

    /* Input styling */
    .stTextInput > div > div > input {
        background: white !important; border: 1px solid #A0CCC6 !important;
        border-radius: 6px !important; font-size: 13px !important; color: #1C3530 !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: #3A9E92 !important; box-shadow: 0 0 0 2px rgba(58,158,146,0.15) !important;
    }
    .stSelectbox > div > div {
        background: white !important; border: 1px solid #A0CCC6 !important;
        border-radius: 6px !important;
    }
    .stNumberInput > div > div > input {
        background: white !important; border: 1px solid #A0CCC6 !important;
    }
    label { font-size: 12px !important; font-weight: 600 !important; color: #2A6058 !important; }

    #MainMenu {visibility:hidden;} footer {visibility:hidden;}
    .stDeployButton {display:none;}
    div[data-testid="stDecoration"] {display:none;}
</style>
""", unsafe_allow_html=True)

# ── Session State ──
if "item_list" not in st.session_state:
    st.session_state.item_list = []
if "seq_counter" not in st.session_state:
    st.session_state.seq_counter = {"RM": 1, "FG": 1, "PKG": 1, "SFG": 1}

# ── Reference Data ──
MATERIAL_NAMES_BY_CATEGORY = {
    "Metal":       ["SCREW","BOLT","NUT","WASHER","BRACKET","PLATE","SPRING","HINGE","RAIL","LEG","PIN","SHAFT"],
    "Plastics":    ["HOUSING","COVER","LENS","CLIP","KNOB","PANEL","TUBE","CAP","BODY","CONN","GRIP"],
    "Electronics": ["PCB","LED","PSU","ADPT","CHIP","RELAY","FUSE","SWITCH","SENSOR","WIRE","CABLE","XFMR"],
    "Rubber":      ["SEAL","ORING","GSKT","PAD","BUMP","BELT","BOOT"],
    "Paper":       ["BOX","LABEL","INSERT","MANUAL","CARD","WRAP","TAPE"],
    "Foam":        ["FOAM","PAD","LINER","INLAY"],
    "Wood":        ["PANEL","BOARD","FRAME","STRIP","BLOCK"],
    "Fabric":      ["FABR","COVER","LINER","MESH"],
    "Chemical":    ["GLUE","INK","COAT","LUBE","FLUX","SOLV"],
    "Others":      ["PART","COMP","ASSY","MISC"],
}
UOM_LIST = ["PCS","KG","G","M","CM","MM","L","ML","ROLL","SHT","SET","BOX","BAG","PAIR","REEL"]
ITEM_CATEGORIES = ["RM","FG","PKG","SFG"]
CATEGORY_LABELS = {"RM":"Raw Material","FG":"Finished Goods","PKG":"Packaging","SFG":"Semi-Finished"}

def gen_pn(cat, mat_name, seq, rev_maj, rev_min):
    return f"{cat}-{seq:04d}-{mat_name}-{rev_maj}{rev_min:03d}"

def is_valid_input(s):
    return bool(s and s.strip() and s.strip() not in ["", "??"])

# ── Header ──
st.markdown('<div class="page-title">🏭 Item Master</div>', unsafe_allow_html=True)
st.markdown('<div class="page-sub">Mini-MES System &nbsp;·&nbsp; Demo Version</div>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📝  Data Entry", "📋  Item List", "📊  Summary"])

# ══════════════════════════════════════════
# TAB 1 — DATA ENTRY
# ══════════════════════════════════════════
with tab1:

    # ── Row 1: Item Category ──
    st.markdown("##### Classification")
    c1, c2 = st.columns(2)
    with c1:
        item_cat_input = st.text_input(
            "Item Category ＊",
            value="RM",
            placeholder="RM / FG / PKG / SFG",
            help="RM=Raw Material | FG=Finished Goods | PKG=Packaging | SFG=Semi-Finished",
            key="item_cat"
        )
        item_cat = item_cat_input.upper().strip()
        # Validate
        if item_cat and item_cat not in ITEM_CATEGORIES:
            st.caption(f"⚠️ Suggested: {' / '.join(ITEM_CATEGORIES)}")

    with c2:
        mat_category = st.selectbox(
            "Material Category ＊",
            list(MATERIAL_NAMES_BY_CATEGORY.keys()),
            key="mat_cat"
        )

    # ── Row 2: Material Name & UOM ──
    c3, c4 = st.columns(2)
    with c3:
        suggestions = MATERIAL_NAMES_BY_CATEGORY.get(mat_category, ["PART"])
        hint = " / ".join(suggestions[:5])
        mat_name_input = st.text_input(
            "Material Name ＊",
            value=suggestions[0],
            placeholder=f"e.g. {hint}",
            help=f"Type your own or use suggestions: {', '.join(suggestions)}",
            key="mat_name"
        )
        mat_name = mat_name_input.upper().strip()

    with c4:
        uom_sel = st.selectbox("Unit of Measurement ＊", UOM_LIST + ["Custom..."], key="uom_sel")
        if uom_sel == "Custom...":
            uom_custom = st.text_input("Enter Custom UOM", placeholder="e.g. REEL, SPOOL", key="uom_custom")
            uom = uom_custom.upper().strip() or "PCS"
        else:
            uom = uom_sel

    # ── Description ──
    description = st.text_input(
        "Description of Material ＊",
        placeholder="e.g.  Screw M3x8 Stainless Steel",
        key="desc"
    )

    # ── Version ──
    st.markdown("##### Version")
    c5, c6, c7 = st.columns([1, 1, 2])
    with c5:
        rev_maj_input = st.text_input(
            "Rev Major ＊",
            value="A",
            placeholder="A / B / C",
            help="Change to B, C... when ECN issued",
            key="rev_maj"
        )
        rev_maj = (rev_maj_input.upper().strip() or "A")[0]

    with c6:
        rev_min = st.number_input(
            "Rev Minor ＊",
            min_value=0, max_value=999, value=10, step=1,
            help="010→011 for small changes",
            key="rev_min"
        )
    with c7:
        st.markdown("<br><span style='font-size:12px;color:#5A8880'>A→B = Major change (ECN) &nbsp;|&nbsp; 010→011 = Minor change</span>", unsafe_allow_html=True)

    # ── Supplier & Packing ──
    st.markdown("##### Supplier & Packing")
    supplier = st.text_input(
        "Supplier ＊",
        placeholder="e.g.  ABC Trading Sdn Bhd",
        key="supplier"
    )
    c8, c9 = st.columns(2)
    with c8:
        std_inner = st.text_input("Standard Pack (Inner)", placeholder="e.g.  500 PCS x 10 BAGS", key="std_inner")
    with c9:
        std_carton = st.number_input("Standard Pack / Carton", min_value=0, value=0, step=100, key="std_carton")

    c10, c11 = st.columns(2)
    with c10:
        lead_time = st.number_input("Lead Time (days) ＊", min_value=1, max_value=365, value=14, key="lead_time")
    with c11:
        moq = st.number_input("MOQ", min_value=0, value=0, step=100, key="moq")

    # ── Compliance ──
    st.markdown("##### Compliance & Reference")
    c12, c13 = st.columns([1, 3])
    with c12:
        rohs = st.checkbox("✅  RoHS Compliant", key="rohs")
    with c13:
        spec_ref = st.text_input("Product Spec REF (Link)", placeholder="https://... or SPEC-001", key="spec_ref")

    # ── Substitutes ──
    st.markdown("##### Substitute Parts  *(Optional)*")
    existing_pns = [i["part_number"] for i in st.session_state.item_list]
    if existing_pns:
        cs1, cs2, cs3 = st.columns(3)
        with cs1: sub1 = st.selectbox("Substitute 1", ["—"] + existing_pns, key="sub1")
        with cs2: sub2 = st.selectbox("Substitute 2", ["—"] + existing_pns, key="sub2")
        with cs3: sub3 = st.selectbox("Substitute 3", ["—"] + existing_pns, key="sub3")
    else:
        st.caption("💡 Save your first item to enable substitute linking.")
        sub1 = sub2 = sub3 = "—"

    # ── PART NUMBER LOGIC ──
    # All required fields
    required_ok = all([
        is_valid_input(item_cat),
        is_valid_input(mat_name),
        is_valid_input(description),
        is_valid_input(rev_maj),
        is_valid_input(supplier),
    ])

    seq = st.session_state.seq_counter.get(item_cat if item_cat in ITEM_CATEGORIES else "RM", 1)

    if required_ok:
        auto_pn = gen_pn(item_cat, mat_name, seq, rev_maj, rev_min)
        pn_html = f'<span class="pn-ready">{auto_pn}</span><span class="pn-auto-tag">AUTO GENERATED</span>'
    else:
        auto_pn = None
        missing = []
        if not is_valid_input(item_cat):    missing.append("Item Category")
        if not is_valid_input(mat_name):    missing.append("Material Name")
        if not is_valid_input(description): missing.append("Description")
        if not is_valid_input(supplier):    missing.append("Supplier")
        pn_html = f'<span class="pn-pending">??-????-????-???</span> &nbsp;<span style="color:#B04040;font-size:12px">Please fill: {", ".join(missing)}</span>'

    # ── Preview Table ──
    st.markdown(f"""
    <table class="form-table">
        <tr class="section-row"><td colspan="2">ITEM MASTER DATA ENTRY</td></tr>
        <tr>
            <td class="td-label">PART NUMBER</td>
            <td class="td-value">{pn_html}</td>
        </tr>
        <tr>
            <td class="td-label">ITEM CATEGORY</td>
            <td class="td-value">{item_cat or '—'} &nbsp;<span style="color:#5A8880;font-size:11px">{CATEGORY_LABELS.get(item_cat,'')}</span></td>
        </tr>
        <tr>
            <td class="td-label">MATERIAL CATEGORY</td>
            <td class="td-value">{mat_category}</td>
        </tr>
        <tr>
            <td class="td-label">MATERIAL NAME</td>
            <td class="td-value">{mat_name or '—'}</td>
        </tr>
        <tr>
            <td class="td-label">DESCRIPTION</td>
            <td class="td-value">{description or '<span style="color:#C0C8C4">—</span>'}</td>
        </tr>
        <tr>
            <td class="td-label">UNIT OF MEASUREMENT</td>
            <td class="td-value">{uom}</td>
        </tr>
        <tr class="section-row"><td colspan="2">VERSION CONTROL</td></tr>
        <tr>
            <td class="td-label">VERSION</td>
            <td class="td-value">{rev_maj}{rev_min:03d} &nbsp;<span style="color:#5A8880;font-size:11px">Major: {rev_maj} · Minor: {rev_min:03d}</span></td>
        </tr>
        <tr class="section-row"><td colspan="2">SUPPLIER & PACKING</td></tr>
        <tr>
            <td class="td-label">SUPPLIER</td>
            <td class="td-value">{supplier or '<span style="color:#C0C8C4">—</span>'}</td>
        </tr>
        <tr>
            <td class="td-label">STANDARD PACK (INNER)</td>
            <td class="td-value">{std_inner or '<span style="color:#C0C8C4">—</span>'}</td>
        </tr>
        <tr>
            <td class="td-label">STANDARD PACK / CARTON</td>
            <td class="td-value">{f"{std_carton:,} {uom}" if std_carton > 0 else '<span style="color:#C0C8C4">—</span>'}</td>
        </tr>
        <tr>
            <td class="td-label">LEAD TIME</td>
            <td class="td-value">{lead_time} days</td>
        </tr>
        <tr>
            <td class="td-label">MOQ</td>
            <td class="td-value">{f"{moq:,} {uom}" if moq > 0 else '<span style="color:#C0C8C4">—</span>'}</td>
        </tr>
        <tr class="section-row"><td colspan="2">COMPLIANCE</td></tr>
        <tr>
            <td class="td-label">ROHS</td>
            <td class="td-value">{'<span class="badge-yes">✅ Compliant</span>' if rohs else '<span class="badge-no">Not Specified</span>'}</td>
        </tr>
        <tr>
            <td class="td-label">PRODUCT SPEC REF</td>
            <td class="td-value">{spec_ref or '<span style="color:#C0C8C4">—</span>'}</td>
        </tr>
        <tr class="section-row"><td colspan="2">SUBSTITUTE PARTS</td></tr>
        <tr>
            <td class="td-label">SUBSTITUTE PART 1</td>
            <td class="td-value">{sub1 if sub1 != '—' else '<span style="color:#C0C8C4">—</span>'}</td>
        </tr>
        <tr>
            <td class="td-label">SUBSTITUTE PART 2</td>
            <td class="td-value">{sub2 if sub2 != '—' else '<span style="color:#C0C8C4">—</span>'}</td>
        </tr>
        <tr>
            <td class="td-label">SUBSTITUTE PART 3</td>
            <td class="td-value">{sub3 if sub3 != '—' else '<span style="color:#C0C8C4">—</span>'}</td>
        </tr>
    </table>
    """, unsafe_allow_html=True)

    # ── Save Button ──
    save = st.button("💾   SAVE ITEM", use_container_width=True, disabled=(not required_ok))

    if save and required_ok and auto_pn:
        st.session_state.item_list.append({
            "part_number":  auto_pn,
            "category":     item_cat,
            "mat_category": mat_category,
            "mat_name":     mat_name,
            "description":  description.strip(),
            "uom":          uom,
            "rev":          f"{rev_maj}{rev_min:03d}",
            "supplier":     supplier.strip(),
            "std_inner":    std_inner,
            "std_carton":   std_carton,
            "lead_time":    lead_time,
            "moq":          moq,
            "rohs":         rohs,
            "spec_ref":     spec_ref,
            "sub1":         sub1 if sub1 != "—" else "",
            "sub2":         sub2 if sub2 != "—" else "",
            "sub3":         sub3 if sub3 != "—" else "",
            "created":      datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        key = item_cat if item_cat in ITEM_CATEGORIES else "RM"
        st.session_state.seq_counter[key] = seq + 1
        st.markdown(f"""
        <div class="success-box">
            ✅ Saved Successfully！&nbsp;&nbsp;
            <span style="font-family:Courier New;font-size:17px;letter-spacing:2px;color:#1A4A42">{auto_pn}</span>
        </div>
        """, unsafe_allow_html=True)
        st.balloons()

# ══════════════════════════════════════════
# TAB 2 — ITEM LIST
# ══════════════════════════════════════════
with tab2:
    items = st.session_state.item_list
    if not items:
        st.info("No items yet. Go to Data Entry tab to add your first item.")
    else:
        cf1, cf2, cf3 = st.columns(3)
        with cf1: f_cat  = st.selectbox("Filter: Category", ["All","RM","FG","PKG","SFG"], key="fcat2")
        with cf2: f_rohs = st.selectbox("Filter: RoHS",     ["All","RoHS ✅","Non-RoHS"],  key="frohs2")
        with cf3: search = st.text_input("🔍 Search", placeholder="Part no / Description", key="srch2")

        filtered = items.copy()
        if f_cat  != "All":      filtered = [i for i in filtered if i["category"] == f_cat]
        if f_rohs == "RoHS ✅":  filtered = [i for i in filtered if i["rohs"]]
        if f_rohs == "Non-RoHS": filtered = [i for i in filtered if not i["rohs"]]
        if search:
            s = search.lower()
            filtered = [i for i in filtered if s in i["part_number"].lower() or s in i["description"].lower() or s in i["supplier"].lower()]

        st.markdown(f"<p style='color:#5A8880;font-size:12px;margin-bottom:10px'>{len(filtered)} item(s)</p>", unsafe_allow_html=True)

        rows = ""
        for i in filtered:
            rb   = '<span class="badge-yes">✅</span>' if i["rohs"] else '<span class="badge-no">No</span>'
            subs = " · ".join(filter(None,[i["sub1"],i["sub2"],i["sub3"]])) or "—"
            rows += f"""<tr>
                <td><span class="pn-mono">{i['part_number']}</span></td>
                <td>{i['category']}</td>
                <td>{i['description']}</td>
                <td>{i['mat_name']}</td>
                <td>{i['uom']}</td>
                <td>{i['supplier']}</td>
                <td>{i['lead_time']}d</td>
                <td>{rb}</td>
                <td style="font-size:11px;color:#5A8880">{subs}</td>
            </tr>"""

        st.markdown(f"""
        <table class="list-table">
            <thead><tr>
                <th>Part Number</th><th>Cat</th><th>Description</th>
                <th>Material</th><th>UOM</th><th>Supplier</th>
                <th>Lead Time</th><th>RoHS</th><th>Substitutes</th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📥 Export CSV", key="export2"):
            df = pd.DataFrame(items)
            st.download_button("⬇️ Download CSV", df.to_csv(index=False),
                f"item_master_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", key="dl2")

# ══════════════════════════════════════════
# TAB 3 — SUMMARY
# ══════════════════════════════════════════
with tab3:
    items = st.session_state.item_list
    if not items:
        st.info("No items yet.")
    else:
        total   = len(items)
        rohs_ok = sum(1 for i in items if i["rohs"])
        w_sub   = sum(1 for i in items if i["sub1"])
        long_lt = sum(1 for i in items if i["lead_time"] > 14)

        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-box"><div class="metric-n">{total}</div><div class="metric-l">Total Items</div></div>
            <div class="metric-box"><div class="metric-n" style="color:#1D6A3A">{rohs_ok}</div><div class="metric-l">RoHS OK</div></div>
            <div class="metric-box"><div class="metric-n" style="color:#1A4A42">{w_sub}</div><div class="metric-l">With Substitutes</div></div>
            <div class="metric-box"><div class="metric-n" style="color:#7A5A00">{long_lt}</div><div class="metric-l">Long Lead &gt;14d</div></div>
        </div>""", unsafe_allow_html=True)

        df = pd.DataFrame(items)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Items by Category**")
            st.bar_chart(df["category"].value_counts(), color="#3A9E92")
        with col2:
            st.markdown("**Items by Material**")
            st.bar_chart(df["mat_name"].value_counts(), color="#5AADA0")
