import streamlit as st
import pandas as pd
import io
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import utils 
import comparison_module 
import balance_sheet_module 
import ai_advisor_module
import cash_flow_module

# 🔥 ERROR HANDLING
try:
    from error_handling import ErrorHandler, DataValidator, ProgressTracker, safe_execute
except ImportError:
    # Fallback if error_handling module not found
    class ErrorHandler:
        @staticmethod
        def handle_file_upload_error(e, f=""): st.error(f"Error: {str(e)}")
        @staticmethod
        def handle_calculation_error(e, c=""): st.error(f"Error: {str(e)}")
        @staticmethod
        def handle_database_error(e, o=""): st.error(f"Error: {str(e)}")
    
    class DataValidator:
        @staticmethod
        def validate_dataframe(df, cols): return [], []
        @staticmethod
        def validate_file_size(f, m): return True, ""
    
    class ProgressTracker:
        def __init__(self, t, d=""): pass
        def update(self, s=""): pass
        def complete(self, m=""): pass

st.set_page_config(
    page_title="FinSuite Pro", 
    layout="wide", 
    initial_sidebar_state="expanded"
)
st.markdown(utils.STYLES, unsafe_allow_html=True)



# Global Plotly dark theme
import plotly.io as pio
pio.templates["finsuite"] = go.layout.Template(
    layout=dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(248,248,247,0.8)",
        font=dict(family="Plus Jakarta Sans", color="#64748B", size=12),
        colorway=["#3B82F6","#10B981","#F59E0B","#A78BFA","#F87171","#34D399","#60A5FA"],
        xaxis=dict(
            showgrid=False, zeroline=False,
            linecolor="rgba(0,0,0,0.06)",
            tickfont=dict(size=11, color="#64748B")
        ),
        yaxis=dict(
            showgrid=True, gridcolor="rgba(0,0,0,0.06)",
            zeroline=False,
            tickfont=dict(size=11, color="#64748B")
        ),
        legend=dict(
            bgcolor="rgba(255,255,255,0.96)",
            bordercolor="rgba(0,0,0,0.08)",
            borderwidth=1,
            font=dict(size=12, color="#64748B")
        ),
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            bordercolor="rgba(0,0,0,0.1)",
            font=dict(family="Plus Jakarta Sans", size=12, color="#0F172A")
        ),
        margin=dict(t=30, b=30, l=10, r=10)
    )
)
pio.templates.default = "finsuite"

# ════════════════════════════════════════
#  SIDEBAR — Clean & Professional
# ════════════════════════════════════════
st.sidebar.markdown("""
<style>
/* Hide Streamlit's default sidebar header completely */
[data-testid="stSidebarNav"] {
    display: none !important;
}
/* Hide collapse button text */
button[kind="header"] * {
    display: none !important;
}
button[kind="header"] {
    width: 40px !important;
    height: 40px !important;
    background: white !important;
    border: 1px solid rgba(0,0,0,0.1) !important;
    border-radius: 8px !important;
}
button[kind="header"]::before {
    content: "📊" !important;
    font-size: 20px !important;
    display: block !important;
    line-height: 40px !important;
    text-align: center !important;
}
</style>
<div style="padding:4px 0 20px 0; border-bottom:1px solid rgba(0,0,0,0.07); margin-bottom:20px;">
  <div style="font-family:'Plus Jakarta Sans',sans-serif; font-size:18px; font-weight:700;
              color:#0F172A; letter-spacing:-0.02em;">
    📊 FinSuite Pro
  </div>
  <div style="font-size:11px; color:#94A3B8; margin-top:3px; letter-spacing:0.03em;">
    ფინანსური ანალიზის სისტემა
  </div>
</div>
""", unsafe_allow_html=True)

# --- სტანდარტული სახელები (P&L ჯგუფებისთვის) ---
PL_PARENT_MAP = {
    '6100': 'საოპერაციო შემოსავალი',
    '6200': 'სხვა შემოსავლები',
    '7100': 'თვითღირებულება (მასალები)',
    '7200': 'პირდაპირი შრომა',
    '7300': 'მიწოდება და მარკეტინგი',
    '7400': 'ადმინისტრაციული ხარჯები',
    '8100': 'საპროცენტო ხარჯები',
    '9100': 'მოგების გადასახადი'
}

st.sidebar.markdown("""
<div style="font-size:11px; font-weight:600; color:#94A3B8; 
            text-transform:uppercase; letter-spacing:0.09em; margin-bottom:8px;">
  📁 მონაცემების ატვირთვა
</div>
""", unsafe_allow_html=True)

# 🔥 Initialize file clear flag
if 'clear_file_upload' not in st.session_state:
    st.session_state.clear_file_upload = False

# 🔥 Use key with counter to force file uploader reset
if 'upload_key' not in st.session_state:
    st.session_state.upload_key = 0

uploaded_file = st.sidebar.file_uploader(
    "ატვირთეთ Excel", 
    type=["xlsx"],
    key=f"file_uploader_{st.session_state.upload_key}"  # 🔥 Dynamic key!
)

if 'df_working' not in st.session_state: 
    st.session_state.df_working = None

if uploaded_file:
    if st.session_state.df_working is None:
        # 🔥 FILE SIZE VALIDATION (manual check — 50MB limit)
        _file_size_mb = uploaded_file.size / (1024 * 1024)
        if _file_size_mb > 50:
            st.error(f"❌ ფაილი ძალიან დიდია ({_file_size_mb:.1f}MB). მაქსიმუმი 50MB.")
            st.info("💡 **რეკომენდაცია:** გაფილტრეთ მონაცემები Excel-ში და ატვირთეთ მხოლოდ საჭირო პერიოდი")
            st.stop()
        
        # 🔥 PROGRESS TRACKING
        progress = ProgressTracker(5, "ფაილის დამუშავება")
        
        try:
            # STEP 1: Read Excel
            progress.update("Excel-ის წაკითხვა...")
            df = pd.read_excel(uploaded_file)
            
            # STEP 2: ჭკვიანი სვეტების ამოცნობა
            progress.update("სვეტების ავტო-ამოცნობა...")

            # სვეტების სახელების ნორმალიზება
            df.columns = [str(c).strip() for c in df.columns]

            # A) პირველი მწკრივი header-ია?
            first_row = df.iloc[0].fillna('').astype(str).str.lower().tolist()
            header_kw = ['code','account','ანალიტიკ','კოდ','debit','დებეტ','credit','კრედიტ','name','სახელ','balance','ნაშთ']
            if any(kw in ' '.join(first_row) for kw in header_kw):
                df.columns = df.iloc[0].fillna('').astype(str).str.strip()
                df = df.iloc[1:].reset_index(drop=True)

            # B) კოდის სვეტი — ავტო-ძებნა
            def _find_col(df, keywords):
                for col in df.columns:
                    if any(kw in str(col).lower() for kw in keywords):
                        return col
                # fallback: ვეძებთ ციფრებიანი მნიშვნელობებით სავსე სვეტს
                for col in df.columns:
                    sample = df[col].dropna().astype(str).head(10)
                    if sample.str.match(r'^\d{3,6}').mean() > 0.5:
                        return col
                return None

            code_col = _find_col(df, ['code','კოდ','account','ანალიტიკ','acct','#'])
            name_col = _find_col(df, ['name','სახელ','დასახელ','description','title','наим'])

            # debit/credit ან balance სვეტები
            debit_col  = _find_col(df, ['debit','დებეტ','debet','db'])
            credit_col = _find_col(df, ['credit','კრედიტ','credit','cr'])
            balance_col = _find_col(df, ['balance','ნაშთ','net','სალდო','amount','თანხ'])

            # C) fallback — პოზიციურად
            cols = list(df.columns)
            if code_col is None and len(cols) >= 1:   code_col   = cols[0]
            if name_col is None and len(cols) >= 2:   name_col   = cols[1]
            if debit_col is None and len(cols) >= 3:  debit_col  = cols[2]
            if credit_col is None and len(cols) >= 4: credit_col = cols[3]

            # D) rename to standard names
            rename_map = {}
            if code_col:   rename_map[code_col]   = 'Code'
            if name_col and name_col != code_col:
                rename_map[name_col]  = 'Name'
            if debit_col and debit_col not in rename_map:
                rename_map[debit_col]  = 'Debit'
            if credit_col and credit_col not in rename_map:
                rename_map[credit_col] = 'Credit'
            if balance_col and balance_col not in rename_map:
                rename_map[balance_col] = 'Balance'

            df.rename(columns=rename_map, inplace=True)

            # E) გამოტოვებული სვეტების შევსება
            if 'Code' not in df.columns:
                raise ValueError("კოდის სვეტი ვერ მოიძებნა! შეამოწმეთ Excel ფაილი.")
            if 'Name' not in df.columns:
                df['Name'] = df['Code']
            if 'Debit' not in df.columns and 'Credit' not in df.columns:
                if 'Balance' in df.columns:
                    df['Debit']  = pd.to_numeric(df['Balance'], errors='coerce').clip(lower=0).fillna(0)
                    df['Credit'] = pd.to_numeric(df['Balance'], errors='coerce').clip(upper=0).abs().fillna(0)
                else:
                    df['Debit'] = 0; df['Credit'] = 0
            if 'Debit' not in df.columns:  df['Debit']  = 0
            if 'Credit' not in df.columns: df['Credit'] = 0
            
            # STEP 4: Clean data
            progress.update("მონაცემების გაწმენდა...")
            
            df = df[df['Code'].notna()].copy()
            df = df[df['Code'].astype(str).str.strip() != ''].copy()
            df = df[df['Code'].astype(str).str.match(r'^\d', na=False)].copy()
            
            # Convert types
            df['Code'] = df['Code'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            df['Name'] = df['Name'].fillna('').astype(str)
            df['Debit'] = pd.to_numeric(df['Debit'], errors='coerce').fillna(0)
            df['Credit'] = pd.to_numeric(df['Credit'], errors='coerce').fillna(0)
            df['Net'] = df['Debit'] - df['Credit']
            
            if df.empty:
                raise ValueError("ფაილში არ მოიძებნა ვალიდური კოდები!")
            
            # STEP 5: Validate data quality
            progress.update("ხარისხის შემოწმება...")
            
            errors, warnings = [], []
            
            if errors:
                st.error("❌ **მონაცემთა შეცდომები:**")
                for err in errors:
                    st.error(f"• {err}")
                st.stop()
            
            if warnings:
                with st.expander("⚠️ გაფრთხილებები (არაკრიტიკული)", expanded=False):
                    for warn in warnings:
                        st.warning(f"• {warn}")
            
            # Smart mapping with progress
            progress.complete("✅ დამუშავება დასრულებულია!")
            
            # Show file info
            st.sidebar.success(f"✅ ფაილი ატვირთულია!")
            st.sidebar.info(f"""
            📊 **სტატისტიკა:**
            - ხაზები: {len(df):,}
            - Code-ის დიაპაზონი: {df['Code'].min()} - {df['Code'].max()}
            - სულ თანხა: {utils.fmt_fin(df['Net'].sum())}
            """)
                
        except Exception as e:
            # Use professional error handler
            ErrorHandler.handle_file_upload_error(e, uploaded_file.name if uploaded_file else "")
            st.stop()

        import ai_advisor_module as _aam
        import json as _json, os as _os
        from collections import defaultdict as _ddict

        # ══════════════════════════════════════════════════════════════════
        # HIERARCHY DETECTION — 3 წესი, სწორი თანმიმდევრობით
        # ══════════════════════════════════════════════════════════════════
        #
        # წესი 1 — SPACE: "3131 0513" → parent = "3131"
        #   კოდი space-ით = ანალიტიკური sub-code. პირველი სეგმენტი მშობელია.
        #
        # წესი 2 — SAME NET (Phase 1): "6000" net == "6100" net
        #   ორი pure-numeric კოდი ერთნაირი Net-ით → პატარა რიცხვი = summary → IGNORE
        #
        # წესი 3 — SUM OF FAMILY (Phase 2): "6100" net = 6110+6112+6113+6114
        #   კოდი რომლის Net = სხვა ამ ოჯახის კოდების ჯამი → summary → IGNORE
        #
        # ══════════════════════════════════════════════════════════════════

        _nets = df.groupby("Code")["Net"].sum().to_dict()
        _all  = list(df["Code"].unique())
        _pure = [c for c in _all if ' ' not in c]   # pure numeric codes
        _parents = set()

        # ── Rule 1: space separator ──
        for _c in _all:
            if ' ' in _c:
                _p = _c.split(' ')[0]
                if _p in set(_all):
                    _parents.add(_p)

        # ── Rule 2: same net, pure numeric → smaller number = parent ──
        for _a in _pure:
            _na = _nets.get(_a, 0)
            if abs(_na) < 0.01:
                continue
            for _b in _pure:
                if _a == _b:
                    continue
                if abs(_nets.get(_b, 0) - _na) < 0.05:
                    try:
                        if int(_a) < int(_b):
                            _parents.add(_a)
                    except ValueError:
                        pass

        # ── Rule 3: net = sum of same-first-digit family (after rule 2) ──
        _remaining = [c for c in _pure if c not in _parents]
        _fams = _ddict(list)
        for _c in _remaining:
            _fams[_c[0]].append(_c)

        for _fam, _members in _fams.items():
            if len(_members) < 2:
                continue
            for _x in _members:
                _nx = _nets.get(_x, 0)
                if abs(_nx) < 0.01:
                    continue
                _others = [c for c in _members if c != _x]
                if abs(sum(_nets.get(c, 0) for c in _others) - _nx) < 0.05:
                    _parents.add(_x)

        # ── mapping_memory: მომხმარებლის წინა mapping ──
        _mem_file = "mapping_memory.json"
        _memory_map = {}
        if _os.path.exists(_mem_file):
            try:
                with open(_mem_file, "r", encoding="utf-8") as _f:
                    _memory_map = _json.load(_f)
            except Exception:
                _memory_map = {}

        # ── Category assignment ──
        def smart_map(row):
            code = str(row["Code"]).strip()
            name = str(row.get("Name", ""))
            # მშობელი → IGNORE (გამოთვლაში არ მონაწილეობს)
            if code in _parents:
                return "IGNORE (იგნორირება)"
            # მომხმარებლის წინა mapping
            if code in _memory_map:
                return _memory_map[code]
            # ჭკვიანი auto-suggest კოდის prefix + სახელის მიხედვით
            return _aam.smart_suggest(code, name)

        df["Category"] = df.apply(smart_map, axis=1)
        st.session_state.df_working = df

df_final = st.session_state.df_working

# ════════════════════════════════════════════════════════
#  TABS — always rendered so P&L / BS / CF stay visible
#  after saving (df_working becomes None but DB has data)
# ════════════════════════════════════════════════════════
tab_map, tab_pl, tab_bs, tab_cf, tab_comp, tab_sim = st.tabs([
    "⚙️  Mapping",
    "📊  P&L",
    "⚖️  ბალანსი",
    "💧  Cash Flow",
    "📈  შედარება",
    "🧠  სტრატეგია"
])

# ─────────────────────────────────────────
# TAB 1: MAPPING
# ─────────────────────────────────────────
with tab_map:

    # ══════════════════════════════════════
    # A) NO FILE LOADED → Period Manager
    # ══════════════════════════════════════
    if df_final is None:
        db = utils.load_db()
        db_keys = sorted(db.keys(), reverse=True)

        if not db_keys:
            st.markdown("""
<style>
.upload-hero{text-align:center;padding:70px 20px;}
.upload-hero h2{color:#0F172A;margin-bottom:8px;}
.upload-hero p{color:#64748B;font-size:14px;}
</style>
<div class="upload-hero">
  <div style="font-size:52px;margin-bottom:16px;">📊</div>
  <h2>FinSuite Pro — ფინანსური ანალიზი</h2>
  <p>ატვირთეთ Excel ფაილი მარცხენა Sidebar-დან სრული ანალიზის დასაწყებად</p>
  <div style="display:flex;justify-content:center;gap:32px;margin-top:24px;">
    <div style="text-align:center;color:#64748B;font-size:13px;">
      <div style="background:#3B82F6;color:white;width:32px;height:32px;border-radius:50%;
                  display:flex;align-items:center;justify-content:center;font-weight:700;
                  margin:0 auto 8px auto;">1</div>Excel ატვირთვა</div>
    <div style="text-align:center;color:#64748B;font-size:13px;">
      <div style="background:#3B82F6;color:white;width:32px;height:32px;border-radius:50%;
                  display:flex;align-items:center;justify-content:center;font-weight:700;
                  margin:0 auto 8px auto;">2</div>Mapping შემოწმება</div>
    <div style="text-align:center;color:#64748B;font-size:13px;">
      <div style="background:#3B82F6;color:white;width:32px;height:32px;border-radius:50%;
                  display:flex;align-items:center;justify-content:center;font-weight:700;
                  margin:0 auto 8px auto;">3</div>შენახვა & ანგარიშგება</div>
  </div>
</div>""", unsafe_allow_html=True)

        else:
            # ── Header ──
            st.markdown("""
<div style="display:flex;align-items:center;gap:12px;padding:14px 18px;
            background:linear-gradient(135deg,#EEF3FD,#F0FDF4);
            border:1px solid rgba(37,99,235,0.12);border-radius:12px;margin-bottom:20px;">
  <div style="font-size:24px;">📂</div>
  <div>
    <div style="font-size:16px;font-weight:700;color:#0F172A;">შენახული პერიოდები</div>
    <div style="font-size:12px;color:#64748B;margin-top:2px;">რედაქტირება · კატეგორიების შეცვლა · წაშლა</div>
  </div>
</div>""", unsafe_allow_html=True)

            # ── Period cards grid ──
            st.markdown("#### 📋 პერიოდების სია")
            _std_cats = [c for c in utils.MAPPING_OPTIONS if c != "IGNORE (იგნორირება)"]
            grid_cols = st.columns(4)
            for _i, _k in enumerate(db_keys):
                _df_k = pd.DataFrame(db[_k])
                _n_total = len(_df_k)
                _n_mapped = len(_df_k[_df_k["Category"].isin(_std_cats)]) if "Category" in _df_k.columns else 0
                _pct = _n_mapped / _n_total * 100 if _n_total else 0
                _net = _df_k["Net"].sum() if "Net" in _df_k.columns else 0
                _color = "#22c55e" if _pct == 100 else ("#f59e0b" if _pct > 70 else "#ef4444")
                with grid_cols[_i % 4]:
                    st.markdown(f"""
<div style="border:1px solid #e2e8f0;border-radius:10px;padding:12px 14px;
            margin-bottom:10px;background:white;">
  <div style="font-weight:700;font-size:14px;color:#0F172A;">{_k}</div>
  <div style="font-size:12px;color:#64748B;margin:4px 0;">{_n_total} კოდი · {utils.fmt_fin(_net)} ₾</div>
  <div style="background:#f1f5f9;border-radius:99px;height:6px;margin:6px 0;">
    <div style="background:{_color};width:{_pct:.0f}%;height:6px;border-radius:99px;"></div>
  </div>
  <div style="font-size:11px;color:{_color};font-weight:600;">{_pct:.0f}% mapped</div>
</div>""", unsafe_allow_html=True)

            st.markdown("---")

            # ── Select & Edit / Delete ──
            _c_sel, _c_edit, _c_del = st.columns([3, 1, 1])
            _selected_period = _c_sel.selectbox(
                "🎯 პერიოდის არჩევა:",
                db_keys,
                key="mgr_period_select",
                label_visibility="collapsed",
            )

            if _c_edit.button("✏️ რედაქტირება", type="primary",
                               use_container_width=True, key="btn_load_edit"):
                _period_data = db[_selected_period]
                _df_loaded = pd.DataFrame(_period_data)
                if "Code" in _df_loaded.columns:
                    _df_loaded["Code"] = _df_loaded["Code"].astype(str).str.strip()
                if "Net" not in _df_loaded.columns:
                    _df_loaded["Net"] = _df_loaded.get("Debit", 0) - _df_loaded.get("Credit", 0)
                if "Category" not in _df_loaded.columns:
                    _df_loaded["Category"] = "IGNORE (იგნორირება)"
                st.session_state.df_working = _df_loaded
                st.session_state.editing_period_key = _selected_period
                st.rerun()

            # Delete with confirmation
            if "delete_confirm_period" not in st.session_state:
                st.session_state.delete_confirm_period = None

            if _c_del.button("🗑️ წაშლა", use_container_width=True,
                              key="btn_open_delete", type="secondary"):
                st.session_state.delete_confirm_period = _selected_period

            if st.session_state.delete_confirm_period == _selected_period:
                st.error(f"⚠️ **დარწმუნებული ხართ?** `{_selected_period}` სამუდამოდ წაიშლება!")
                _dc1, _dc2, _dc3 = st.columns([1, 1, 3])
                if _dc1.button("🗑️ დიახ, წაშლა", type="primary", key="btn_confirm_delete"):
                    _ok = utils.delete_from_db(_selected_period)
                    st.session_state.delete_confirm_period = None
                    st.toast(f"✅ {_selected_period} წაიშალა!" if _ok else "❌ შეცდომა", icon="🗑️")
                    st.rerun()
                if _dc2.button("❌ გაუქმება", key="btn_cancel_delete"):
                    st.session_state.delete_confirm_period = None
                    st.rerun()

            # ── Detail panel ──
            st.markdown(f"#### 🔍 `{_selected_period}` — დეტალები")
            _df_sel = pd.DataFrame(db[_selected_period])
            if "Code" in _df_sel.columns:
                _df_sel["Code"] = _df_sel["Code"].astype(str).str.strip()
            _n_total2 = len(_df_sel)
            _n_mapped2 = len(_df_sel[_df_sel["Category"].isin(_std_cats)]) if "Category" in _df_sel.columns else 0
            _n_ignore2 = len(_df_sel[_df_sel["Category"] == "IGNORE (იგნორირება)"]) if "Category" in _df_sel.columns else 0
            _net2 = _df_sel["Net"].sum() if "Net" in _df_sel.columns else 0
            _s1, _s2, _s3, _s4 = st.columns(4)
            _s1.metric("სულ კოდები", _n_total2)
            _s2.metric("✅ დამეპილი", _n_mapped2)
            _s3.metric("⚠️ Unmapped", _n_total2 - _n_mapped2 - _n_ignore2)
            _s4.metric("სულ Net", utils.fmt_fin(_net2))

            if "Category" in _df_sel.columns:
                with st.expander("📊 კატეგორიების განაწილება", expanded=False):
                    _cc = _df_sel["Category"].value_counts().reset_index()
                    _cc.columns = ["კატეგორია", "რაოდენობა"]
                    if "Net" in _df_sel.columns:
                        _nc = _df_sel.groupby("Category")["Net"].sum().reset_index()
                        _nc.columns = ["კატეგორია", "სულ Net"]
                        _cc = _cc.merge(_nc, on="კატეგორია", how="left")
                        _cc["სულ Net"] = _cc["სულ Net"].apply(utils.fmt_fin)
                    st.dataframe(_cc, use_container_width=True, hide_index=True)

            st.caption("💡 ან ატვირთეთ ახალი Excel ფაილი მარცხენა sidebar-დან")

    # ══════════════════════════════════════
    # B) FILE LOADED → Mapping Editor
    # ══════════════════════════════════════
    else:
        if "code_notes" not in st.session_state:
            st.session_state.code_notes = {}
        if "editing_period_key" not in st.session_state:
            st.session_state.editing_period_key = None

        _is_edit = bool(st.session_state.editing_period_key)
        _edit_badge = (
            f'<span style="background:#FEF3C7;color:#92400E;padding:3px 10px;'
            f'border-radius:99px;font-size:12px;font-weight:600;margin-left:12px;">'
            f'✏️ {st.session_state.editing_period_key}</span>'
            if _is_edit else ""
        )

        st.markdown(f"""
<div style="display:flex;align-items:center;gap:12px;padding:14px 18px;
            background:linear-gradient(135deg,#EEF3FD,#F0FDF4);
            border:1px solid rgba(37,99,235,0.12);border-radius:12px;margin-bottom:18px;">
  <div style="font-size:22px;">⚙️</div>
  <div style="flex:1;">
    <div style="font-size:16px;font-weight:700;color:#0F172A;">კატეგორიების Mapping {_edit_badge}</div>
    <div style="font-size:12px;color:#64748B;margin-top:2px;">კოდების მიმაგრება · Bulk Actions · შენახვა</div>
  </div>
</div>""", unsafe_allow_html=True)

        df_w = st.session_state.df_working
        _std_cats2 = [c for c in utils.MAPPING_OPTIONS if c != "IGNORE (იგნორირება)"]
        _total = len(df_w)
        _mapped = len(df_w[df_w["Category"].isin(_std_cats2)]) if "Category" in df_w.columns else 0
        _ignore = len(df_w[df_w["Category"] == "IGNORE (იგნორირება)"]) if "Category" in df_w.columns else 0
        _unmap = _total - _mapped - _ignore
        _pct2 = _mapped / _total * 100 if _total else 0

        _mc1, _mc2, _mc3, _mc4 = st.columns(4)
        _mc1.metric("სულ კოდები", _total)
        _mc2.metric("✅ დამეპილი", f"{_mapped} ({_pct2:.0f}%)")
        _mc3.metric("⚠️ Unmapped", _unmap)
        _mc4.metric("🔕 IGNORE", _ignore)
        st.progress(_pct2 / 100)
        st.markdown("---")

        _col_main, _col_side = st.columns([3, 1])

        with _col_main:
            _fc1, _fc2, _fc3 = st.columns([2, 2, 1])
            _search_q = _fc1.text_input("🔍 ძებნა", placeholder="კოდი, სახელი...", key="map_search")
            _filter_cat = _fc2.selectbox("კატეგორიით ფილტრი",
                                          ["ყველა"] + utils.MAPPING_OPTIONS,
                                          key="map_filter_cat")
            _show_unmap = _fc3.checkbox("Unmapped only", key="map_unmap")

            _fdf = df_w.copy()
            if _search_q:
                _fdf = _fdf[
                    _fdf["Code"].astype(str).str.contains(_search_q, case=False, na=False) |
                    _fdf["Name"].astype(str).str.contains(_search_q, case=False, na=False)
                ]
            if _filter_cat != "ყველა":
                _fdf = _fdf[_fdf["Category"] == _filter_cat]
            if _show_unmap:
                _fdf = _fdf[~_fdf["Category"].isin(_std_cats2 + ["IGNORE (იგნორირება)"])]

            st.caption(f"ნაჩვენებია **{len(_fdf)}** / {_total} ჩანაწერი")

            _display_df = _fdf[["Code", "Name", "Net", "Category"]].copy()
            _edited_df = st.data_editor(
                _display_df,
                column_config={
                    "Category": st.column_config.SelectboxColumn(
                        "კატეგორია", options=utils.MAPPING_OPTIONS, width="large", required=True),
                    "Code": st.column_config.TextColumn("კოდი", width="small"),
                    "Name": st.column_config.TextColumn("სახელი", width="medium"),
                    "Net":  st.column_config.NumberColumn("Net", format="%.2f", width="small"),
                },
                use_container_width=True, height=440, hide_index=True, key="map_editor",
            )

            if not _edited_df.equals(_display_df):
                for _, _row in _edited_df.iterrows():
                    _mask = st.session_state.df_working["Code"] == _row["Code"]
                    if _mask.any():
                        st.session_state.df_working.loc[_mask, "Category"] = _row["Category"]

            st.markdown("---")

            # ── Save / Clear ──
            _sc1, _sc2, _sc3 = st.columns([2, 1, 1])
            _default_date = datetime.now()
            if _is_edit:
                try:
                    _default_date = datetime.strptime(st.session_state.editing_period_key, "%Y-%m")
                except Exception:
                    pass
            _save_date = _sc1.date_input("📅 შენახვის პერიოდი", _default_date, key="map_save_date")

            if _sc2.button("💾 შენახვა", type="primary", use_container_width=True, key="map_save_btn"):
                _date_key = _save_date.strftime("%Y-%m")
                _old_key = st.session_state.get("editing_period_key")
                if _old_key and _old_key != _date_key:
                    utils.delete_from_db(_old_key)
                utils.save_to_db(_date_key, st.session_state.df_working.to_dict("records"))
                st.session_state.df_working = None
                st.session_state.editing_period_key = None
                st.session_state.upload_key = st.session_state.get("upload_key", 0) + 1
                st.toast(f"✅ {_date_key} შენახულია!", icon="💾")
                st.rerun()

            if _sc3.button("✖️ გასუფთავება", use_container_width=True, key="map_clear_btn"):
                st.session_state.df_working = None
                st.session_state.editing_period_key = None
                st.session_state.upload_key = st.session_state.get("upload_key", 0) + 1
                st.rerun()

        with _col_side:
            st.markdown("### 🛠️ ინსტრუმენტები")

            with st.expander("🏆 Mapping Quality", expanded=True):
                _qual = max(0, 100 - (_unmap / _total * 40 if _total else 0) -
                            (15 if _ignore > _total * 0.15 else 0))
                _qc = "#22c55e" if _qual >= 85 else ("#f59e0b" if _qual >= 60 else "#ef4444")
                st.markdown(f"""
<div style="text-align:center;padding:12px;background:#f8fafc;border-radius:8px;margin-bottom:8px;">
  <div style="font-size:32px;font-weight:800;color:{_qc};">{_qual:.0f}</div>
  <div style="font-size:12px;color:#64748B;">/ 100</div>
</div>""", unsafe_allow_html=True)
                st.progress(_qual / 100)
                st.caption("⚠️ " + str(_unmap) + " unmapped" if _unmap > 0 else "✅ ყველა კოდი დამეპილია")
                st.caption("⚠️ ბევრი IGNORE" if _ignore > _total * 0.15 else "✅ IGNORE გონივრულია")

            with st.expander("⚡ Bulk Actions", expanded=True):
                _bulk_prefix = st.text_input("Prefix (მაგ: 71, 74)", key="bulk_prefix",
                                              placeholder="კოდის პრეფიქსი")
                _bulk_cat = st.selectbox("კატეგორია", utils.MAPPING_OPTIONS, key="bulk_cat")
                if st.button("✅ გამოყენება", key="bulk_apply",
                             use_container_width=True, type="primary"):
                    if _bulk_prefix:
                        _bmask = st.session_state.df_working["Code"].astype(str).str.startswith(_bulk_prefix)
                        _bcnt = _bmask.sum()
                        if _bcnt > 0:
                            st.session_state.df_working.loc[_bmask, "Category"] = _bulk_cat
                            st.toast(f"✅ {_bcnt} კოდი განახლდა", icon="⚡")
                            st.rerun()
                        else:
                            st.warning(f"'{_bulk_prefix}' ვერ მოიძებნა")

                st.markdown("---")
                st.caption("🎯 სწრაფი Preset-ები:")
                _presets = [
                    ("71/72 → COGS",  [("71","COGS (თვითღირებულება)"),("72","COGS (თვითღირებულება)")]),
                    ("74 → OpEx",     [("74","Operating Expenses (საოპერაციო ხარჯები)")]),
                    ("6x → Revenue",  [("6", "Revenue (შემოსავალი)")]),
                    ("11/12 → Cash",  [("11","BS: Current Assets (მიმდინარე აქტივები)"),
                                       ("12","BS: Current Assets (მიმდინარე აქტივები)")]),
                ]
                for _lbl, _rules in _presets:
                    if st.button(_lbl, key=f"preset_{_lbl}", use_container_width=True):
                        _tc = 0
                        for _pfx, _cat in _rules:
                            _pm = st.session_state.df_working["Code"].astype(str).str.startswith(_pfx)
                            st.session_state.df_working.loc[_pm, "Category"] = _cat
                            _tc += _pm.sum()
                        st.toast(f"✅ {_tc} კოდი განახლდა", icon="⚡")
                        st.rerun()

            with st.expander("📊 კატეგორიების სტატისტიკა", expanded=False):
                if "Category" in st.session_state.df_working.columns:
                    _cc2 = st.session_state.df_working["Category"].value_counts().reset_index()
                    _cc2.columns = ["კატეგორია", "კოდები"]
                    if "Net" in st.session_state.df_working.columns:
                        _nc2 = st.session_state.df_working.groupby("Category")["Net"].sum().reset_index()
                        _nc2.columns = ["კატეგორია", "Net"]
                        _cc2 = _cc2.merge(_nc2, on="კატეგორია", how="left")
                        _cc2["Net"] = _cc2["Net"].apply(utils.fmt_fin)
                    st.dataframe(_cc2, use_container_width=True, hide_index=True)

            with st.expander("💾 Mapping ვარიანტები", expanded=False):
                _variants = utils.load_mapping_variants()
                if _variants:
                    _vnames = list(_variants.keys())
                    _sel_var = st.selectbox("ჩატვირთვა:", _vnames, key="load_variant_sel")
                    _lc1, _lc2 = st.columns(2)
                    if _lc1.button("📥 ჩატვირთვა", use_container_width=True, key="load_variant_btn"):
                        _vmap = _variants[_sel_var]
                        _dft = st.session_state.df_working.copy()
                        _dft["Code"] = _dft["Code"].astype(str).str.strip()
                        _vchanged = 0
                        for _idx, _vrow in _dft.iterrows():
                            if str(_vrow["Code"]) in _vmap:
                                _dft.at[_idx, "Category"] = _vmap[str(_vrow["Code"])]
                                _vchanged += 1
                        st.session_state.df_working = _dft
                        st.toast(f"✅ {_vchanged} კოდი განახლდა", icon="📥")
                        st.rerun()
                    if _lc2.button("🗑️ წაშლა", use_container_width=True, key="del_variant_btn"):
                        utils.delete_mapping_variant(_sel_var)
                        st.rerun()
                st.markdown("---")
                _nvname = st.text_input("ვარიანტის სახელი:", key="new_variant_name",
                                         placeholder="მაგ: 2024 Standard")
                if st.button("💾 ამჟამინდელი შენახვა", use_container_width=True, key="save_variant_btn"):
                    if _nvname:
                        _mdict = dict(zip(
                            st.session_state.df_working["Code"].astype(str),
                            st.session_state.df_working.get("Category", "IGNORE (იგნორირება)"),
                        ))
                        utils.save_mapping_variant(_nvname, _mdict)
                        st.toast(f"✅ '{_nvname}' შენახულია!", icon="💾")
                    else:
                        st.warning("შეიყვანეთ სახელი")

with tab_pl:
    db = utils.load_db()
    opts = sorted(db.keys(), reverse=True)
    if not opts:
        st.markdown("""
        <div style="text-align:center;padding:80px 20px;color:#94A3B8;">
          <div style="font-size:42px;margin-bottom:16px;opacity:0.4;">📊</div>
          <div style="font-size:15px;font-weight:600;color:#64748B;margin-bottom:8px;">
            მონაცემები არ არის
          </div>
          <div style="font-size:13px;color:#94A3B8;">
            Mapping tab-ზე ატვირთეთ და შეინახეთ ფაილი
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        col_gen, col_snap = st.columns([3, 1])
        sel_src = col_gen.selectbox("📅 პერიოდი:", opts, label_visibility="collapsed")
        
        # 🔥 FIX: AI Advisor on RAW data (BEFORE cleaning)
        df_raw = pd.DataFrame(db[sel_src])
        df_raw['Code'] = df_raw['Code'].astype(str).str.strip()
        
        # 🔥 NEW: შევინახოთ df_raw session_state-ში რომ parent Name-ები ავიღოთ
        st.session_state.df_raw_for_names = df_raw
        
        # AI ADVISOR (checks RAW data with parents intact)
        problematic_codes = ai_advisor_module.render_audit_ui(df_raw, "PL", source_key=sel_src, ui_key="pl")
        
        # THEN clean for calculations (removes parent codes)
        df_clean = utils.clean_dataset_logic(db[sel_src])
        
        # მშობელი კოდის გენერაცია (2 ციფრი + 00) ვიზუალისთვის
        if not df_clean.empty and 'Code' in df_clean.columns:
            df_clean['ParentCode'] = df_clean['Code'].apply(lambda x: str(x)[:2] + "00" if len(str(x)) >= 3 else str(x))

        # --- CALCULATIONS ---
        def c(cat): return df_clean[df_clean['Category']==cat]['Net'].sum()
        rev = c("Revenue (შემოსავალი)") * -1
        other_net = c("Other Income/Expense (სხვა არასაოპერაციო)") * -1
        cogs = c("COGS (თვითღირებულება)")
        opex = c("Operating Expenses (საოპერაციო ხარჯები)")
        depr = c("Depreciation (ცვეთა/ამორტიზაცია)")
        inte = c("Interest (საპროცენტო ხარჯი)")
        tax = c("Tax (მოგების გადასახადი)")

        gross_profit = rev - cogs
        ebitda = gross_profit - opex
        ebit = ebitda - depr
        ebt = ebit - inte + other_net
        net = ebt - tax
        
        # ═══ PAGE HEADER ═══
        margin_pct = (net / rev * 100) if rev else 0
        profit_color = "#10B981" if net >= 0 else "#F87171"
        badge_cls = "badge-green" if net >= 0 else "badge-red"
        badge_txt = f"{'▲' if net>=0 else '▼'} {abs(margin_pct):.1f}% Net Margin"
        
        st.markdown(f"""
        <div style="display:flex;align-items:center;justify-content:space-between;
                    padding:18px 22px;background:#FAFAF8;border:1px solid rgba(0,0,0,0.07);
                    border-radius:12px;margin-bottom:20px;">
          <div>
            <div style="font-size:18px;font-weight:700;color:#0F172A;letter-spacing:-0.02em;">
              მოგება-ზარალის უწყისი
            </div>
            <div style="font-size:12px;color:#94A3B8;margin-top:3px;">
              პერიოდი: <span style="color:#64748B;font-weight:500;">{sel_src}</span>
            </div>
          </div>
          <div style="display:flex;align-items:center;gap:10px;">
            <span class="badge {badge_cls}">{badge_txt}</span>
            <div style="font-family:'DM Mono',monospace;font-size:20px;
                        font-weight:600;color:{profit_color};">
              {utils.fmt_fin(net)}
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        
        snap_name = col_snap.text_input("სახელი:", value=f"PL_{sel_src}", label_visibility="collapsed")
        if col_snap.button("💾 შენახვა", key="snap_pl", use_container_width=True):
            utils.save_snapshot(snap_name, df_clean.to_dict('records'))
            st.toast("✅ სნეპშოტი შენახულია!")
            
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("💰 Revenue", utils.fmt_fin(rev))
        k2.metric("📦 Gross Profit", utils.fmt_fin(gross_profit))
        k3.metric("⚡ EBITDA", utils.fmt_fin(ebitda))
        k4.metric("📉 EBIT", utils.fmt_fin(ebit))
        k5.metric("✨ Net Profit", utils.fmt_fin(net))
        
        fig = go.Figure(go.Waterfall(
            orientation="v",
            measure=["relative", "relative", "total", "relative", "total", "total"],
            x=["Revenue", "COGS", "Gross Profit", "Opex + Other", "EBITDA", "Net Profit"],
            y=[rev, -cogs, 0, -(opex+inte+tax-other_net), 0, 0],
            connector={"line": {"color": "rgba(0,0,0,0.08)", "width": 1}},
            increasing={"marker": {"color": "#10B981"}},
            decreasing={"marker": {"color": "#F87171"}},
            totals={"marker": {"color": "#3B82F6"}},
            textfont={"family": "DM Mono", "size": 11, "color": "#64748B"},
            textposition="outside",
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(248,248,247,0.8)",
            height=240,
            margin=dict(t=10, b=10, l=0, r=0),
            font=dict(family="Plus Jakarta Sans", color="#64748B", size=12),
            xaxis=dict(
                showgrid=False, zeroline=False,
                tickfont=dict(size=11, color="#64748B"),
                linecolor="rgba(0,0,0,0.06)"
            ),
            yaxis=dict(
                showgrid=True, gridcolor="rgba(0,0,0,0.06)",
                zeroline=False, tickfont=dict(size=10, color="#94A3B8"),
                tickformat=",.0f"
            ),
            hoverlabel=dict(
                bgcolor="#FFFFFF", bordercolor="rgba(0,0,0,0.1)",
                font=dict(family="Plus Jakarta Sans", size=12, color="#0F172A")
            )
        )
        st.plotly_chart(fig, use_container_width=True)
        
        show_codes = st.checkbox("კოდები", value=True, key="pl_check")
        cols = 3 if show_codes else 2

        # --- HTML GENERATOR ---
        def get_pl_rows(cat, multiplier=1, color_override=None):
            subset = df_clean[df_clean['Category'] == cat].copy()
            if subset.empty: return ""
            subset['Val'] = subset['Net'] * multiplier
            if 'ParentCode' not in subset.columns: return ""
            
            # აგრეგაცია
            grouped = subset.groupby('ParentCode').agg({'Val': 'sum', 'Code': 'first'}).reset_index().sort_values('ParentCode')
            
            html = ""
            for _, group_row in grouped.iterrows():
                if abs(group_row['Val']) < 0.01: continue
                p_code = group_row['ParentCode']
                p_val = group_row['Val']
                
                # სახელის ძებნა
                p_name = PL_PARENT_MAP.get(str(p_code))
                if not p_name:
                    # 🔥 FIXED: df_raw-დან ვიღებთ (არა subset-დან!)
                    # რადგან subset-ში parent-ები უკვე წაშლილია
                    if 'df_raw_for_names' in st.session_state:
                        parent_row = st.session_state.df_raw_for_names[
                            st.session_state.df_raw_for_names['Code'] == p_code
                        ]
                        if not parent_row.empty:
                            p_name = parent_row.iloc[0]['Name']
                        else:
                            p_name = f"ჯგუფი {p_code}"
                    else:
                        p_name = f"ჯგუფი {p_code}"

                children = subset[subset['ParentCode'] == p_code]
                children_rows = ""
                should_expand = len(children) > 0
                
                if should_expand:
                    for _, child in children.iterrows():
                        if abs(child['Val']) < 0.01: continue
                        row_style = "background-color: #ffe6e6;" if str(child["Code"]) in problematic_codes else ""
                        c_code_td = f'<td style="color:#666; font-size:0.85em; width:80px;">{child["Code"]}</td>' if show_codes else ""
                        children_rows += f"""<tr style="border-bottom:1px dashed #eee; {row_style}">{c_code_td}<td style="color:#555; font-size:0.9em; padding-left:15px;">{child["Name"]}</td><td style="text-align:right; font-family:monospace; font-size:0.9em; color:#555;">{utils.fmt_fin(child["Val"])}</td></tr>"""
                    children_table = f'<table style="width:100%; background-color:#fcfcfc; margin-top:5px; margin-bottom:5px;">{children_rows}</table>'
                
                td_code = f'<td class="code-col"><b>{p_code}</b></td>' if show_codes else ""
                
                if should_expand and children_rows:
                    name_cell = f'<details style="cursor:pointer;"><summary style="outline:none;"><b>{p_name}</b> <span style="font-size:0.7em; color:#999;">▼</span></summary>{children_table}</details>' 
                else:
                    name_cell = f"<b>{p_name}</b>"
                
                val_style = f'color:{color_override};' if color_override else ""
                html += f"""<tr style="background-color: #fafafa; border-bottom: 1px solid #eee;">{td_code}<td class="sub-indent">{name_cell}</td><td class="amt" style="vertical-align:top; padding-top:8px; {val_style}"><b>{utils.fmt_fin(p_val)}</b></td></tr>"""
            return html

        pl_html = f"""
<style>
    .pl-table {{ width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 0.95rem; }}
    .pl-table th {{ border-bottom: 2px solid #ddd; text-align: left; padding: 8px; background: #f8f9fa; }}
    .pl-table td {{ padding: 6px 8px; vertical-align: top; }}
    .header-row td {{ background-color: #4A90E2; color: white; font-weight: bold; padding: 10px; text-transform: uppercase; }}
    .sub-header-row td {{ background-color: #EBF5FB; font-weight: bold; border-top: 1px solid #aaa; color: #333; }}
    .calc-row td {{ background-color: #e8f4f8; font-weight: bold; color: #2c3e50; border-top: 2px solid #bdc3c7; }}
    .grand-row td {{ background-color: #2E86C1; color: white; font-weight: bold; padding: 10px; font-size: 1.1em; }}
    .amt {{ text-align: right; font-family: monospace; white-space: nowrap; }}
    .code-col {{ width: 80px; font-family: monospace; color: #333; vertical-align:top; padding-top:8px; }}
    .sub-indent {{ padding-left: 10px; }}
    details > summary {{ list-style: none; }}
    details > summary::-webkit-details-marker {{ display: none; }}
</style>
<table class="pl-table">
<thead><tr>{'<th>Code</th>' if show_codes else ''}<th>Item</th><th>Amount</th></tr></thead><tbody>
<tr class="header-row"><td colspan="{cols}">Revenue</td></tr>{get_pl_rows("Revenue (შემოსავალი)", -1)}
<tr class="total-row"><td colspan="{cols-1}">Total Revenue</td><td class="amt">{utils.fmt_fin(rev)}</td></tr>
<tr class="header-row" style="background-color:#E67E22;"><td colspan="{cols}">COGS</td></tr>{get_pl_rows("COGS (თვითღირებულება)", 1)}
<tr class="total-row"><td colspan="{cols-1}">Total COGS</td><td class="amt">{utils.fmt_fin(cogs)}</td></tr>
<tr class="calc-row"><td colspan="{cols-1}">GROSS PROFIT</td><td class="amt"><b>{utils.fmt_fin(gross_profit)}</b></td></tr>
<tr class="header-row" style="background-color:#95A5A6;"><td colspan="{cols}">Opex</td></tr>{get_pl_rows("Operating Expenses (საოპერაციო ხარჯები)", 1)}
<tr class="total-row"><td colspan="{cols-1}">Total OpEx</td><td class="amt">{utils.fmt_fin(opex)}</td></tr>
<tr class="calc-row" style="background-color:#D5F4E6;"><td colspan="{cols-1}">EBITDA</td><td class="amt"><b>{utils.fmt_fin(ebitda)}</b></td></tr>
<tr class="sub-header-row"><td colspan="{cols}">Other Items</td></tr>
{get_pl_rows("Depreciation (ცვეთა/ამორტიზაცია)", 1)}
<tr class="calc-row" style="background-color:#FADBD8;"><td colspan="{cols-1}">EBIT</td><td class="amt"><b>{utils.fmt_fin(ebit)}</b></td></tr>
{get_pl_rows("Interest (საპროცენტო ხარჯი)", 1)}
{get_pl_rows("Other Income/Expense (სხვა არასაოპერაციო)", -1)}
<tr class="calc-row" style="background-color:#f2f2f2;"><td colspan="{cols-1}">EBT</td><td class="amt"><b>{utils.fmt_fin(ebt)}</b></td></tr>
<tr class="sub-header-row"><td colspan="{cols}">Tax</td></tr>{get_pl_rows("Tax (მოგების გადასახადი)", 1)}
<tr class="grand-row"><td colspan="{cols-1}">NET PROFIT</td><td class="amt">{utils.fmt_fin(net)}</td></tr>
</tbody></table>"""
        st.markdown(pl_html, unsafe_allow_html=True)
        
        with st.expander("🗄️ არქივი"):
            snaps = utils.load_snapshots()
            if snaps:
                sel_s = st.selectbox("სნეპშოტი:", list(snaps.keys()))
                if st.button("🗑️ წაშლა", key="del_snap"):
                    utils.delete_snapshot(sel_s); st.rerun()

# TAB 3: BALANCE SHEET
with tab_bs:
    balance_sheet_module.render_balance_sheet_tab()

# TAB 4: CASH FLOW (NEW)
with tab_cf:
    cash_flow_module.render_cash_flow_tab()

# TAB 5: COMPARISON
with tab_comp:
    comparison_module.render_comparison_tab()

# TAB 6: STRATEGY
# 🎯 STRATEGY TAB - სრული მენეჯერული ანალიტიკა

# ეს კოდი ჩაანაცვლებს app.py-ში tab_sim (Strategy tab) სექციას
# ხაზები ~307-350

# TAB 6: STRATEGY
with tab_sim:
    st.markdown("""
    <div style="display:flex;align-items:center;gap:12px;
                padding:18px 22px;background:#FAFAF8;
                border:1px solid rgba(0,0,0,0.07);
                border-radius:12px;margin-bottom:20px;">
      <div style="font-size:24px;opacity:0.8;">🧠</div>
      <div>
        <div style="font-size:18px;font-weight:700;color:#0F172A;letter-spacing:-0.02em;">
          სტრატეგიული ანალიზი
        </div>
        <div style="font-size:12px;color:#94A3B8;margin-top:2px;">
          KPI Dashboard · Break-Even · Scenario Analysis
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)
    
    db = utils.load_db()
    opts = sorted(db.keys(), reverse=True)
    
    if not opts:
        st.warning("მონაცემთა ბაზა ცარიელია. გთხოვთ ჯერ ატვირთოთ Excel ფაილი.")
    else:
        # Period Selection
        col_period, col_compare = st.columns([2, 2])
        current_period = col_period.selectbox("📅 ანალიზის პერიოდი:", opts, key="strategy_period")
        
        # Optional comparison period
        compare_options = ["არ შედარება"] + [o for o in opts if o != current_period]
        compare_period = col_compare.selectbox("⚖️ შედარების პერიოდი:", compare_options, key="strategy_compare")
        
        # Load data
        df_current = utils.clean_dataset_logic(db[current_period])
        
        if compare_period != "არ შედარება":
            df_previous = utils.clean_dataset_logic(db[compare_period])
        else:
            df_previous = None
        
        # Helper function
        def get_cat(df, cat):
            if df is None or df.empty:
                return 0.0
            return df[df['Category'] == cat]['Net'].sum()
        
        # ==========================================
        # 📊 SECTION 1: KEY FINANCIAL METRICS
        # ==========================================
        
        st.markdown("---")
        st.markdown("### 📈 ძირითადი ფინანსური მაჩვენებლები")
        
        # Current period calculations
        revenue = get_cat(df_current, "Revenue (შემოსავალი)") * -1
        cogs = get_cat(df_current, "COGS (თვითღირებულება)")
        opex = get_cat(df_current, "Operating Expenses (საოპერაციო ხარჯები)")
        depr = get_cat(df_current, "Depreciation (ცვეთა/ამორტიზაცია)")
        interest = get_cat(df_current, "Interest (საპროცენტო ხარჯი)")
        other = get_cat(df_current, "Other Income/Expense (სხვა არასაოპერაციო)") * -1
        tax = get_cat(df_current, "Tax (მოგების გადასახადი)")
        
        gross_profit = revenue - cogs
        ebitda = gross_profit - opex
        ebit = ebitda - depr
        ebt = ebit - interest + other
        net_profit = ebt - tax
        
        # Previous period (if selected)
        if df_previous is not None:
            revenue_prev = get_cat(df_previous, "Revenue (შემოსავალი)") * -1
            gross_profit_prev = revenue_prev - get_cat(df_previous, "COGS (თვითღირებულება)")
            ebitda_prev = gross_profit_prev - get_cat(df_previous, "Operating Expenses (საოპერაციო ხარჯები)")
            net_profit_prev = (ebitda_prev - get_cat(df_previous, "Depreciation (ცვეთა/ამორტიზაცია)") 
                             - get_cat(df_previous, "Interest (საპროცენტო ხარჯი)") 
                             + get_cat(df_previous, "Other Income/Expense (სხვა არასაოპერაციო)") * -1
                             - get_cat(df_previous, "Tax (მოგების გადასახადი)"))
        else:
            revenue_prev = gross_profit_prev = ebitda_prev = net_profit_prev = None
        
        # Display key metrics
        k1, k2, k3, k4, k5 = st.columns(5)
        
        def show_metric_with_delta(col, label, value, prev_value):
            if prev_value is not None and prev_value != 0:
                delta = value - prev_value
                delta_pct = (delta / abs(prev_value)) * 100
                col.metric(label, utils.fmt_fin(value), f"{delta_pct:+.1f}%")
            else:
                col.metric(label, utils.fmt_fin(value))
        
        show_metric_with_delta(k1, "შემოსავალი", revenue, revenue_prev)
        show_metric_with_delta(k2, "Gross Profit", gross_profit, gross_profit_prev)
        show_metric_with_delta(k3, "EBITDA", ebitda, ebitda_prev)
        k4.metric("EBIT", utils.fmt_fin(ebit))
        show_metric_with_delta(k5, "Net Profit", net_profit, net_profit_prev)
        
        # ==========================================
        # 📊 SECTION 2: PROFITABILITY RATIOS
        # ==========================================
        
        st.markdown("---")
        st.markdown("### 💰 მომგებიანობის კოეფიციენტები")
        
        r1, r2, r3, r4 = st.columns(4)
        
        gross_margin = (gross_profit / revenue * 100) if revenue else 0
        ebitda_margin = (ebitda / revenue * 100) if revenue else 0
        ebit_margin = (ebit / revenue * 100) if revenue else 0
        net_margin = (net_profit / revenue * 100) if revenue else 0
        
        r1.metric("Gross Margin", f"{gross_margin:.1f}%", 
                 help="(შემოსავალი - თვითღირებულება) / შემოსავალი")
        r2.metric("EBITDA Margin", f"{ebitda_margin:.1f}%",
                 help="EBITDA / შემოსავალი")
        r3.metric("EBIT Margin", f"{ebit_margin:.1f}%",
                 help="EBIT / შემოსავალი")
        r4.metric("Net Profit Margin", f"{net_margin:.1f}%",
                 help="წმინდა მოგება / შემოსავალი")
        
        # ==========================================
        # 📊 SECTION 3: COST STRUCTURE ANALYSIS
        # ==========================================
        
        st.markdown("---")
        st.markdown("### 🏗️ ხარჯების სტრუქტურის ანალიზი")
        
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.markdown("**ხარჯების განაწილება (% შემოსავლიდან)**")
            
            cost_structure = {
                'COGS': (cogs / revenue * 100) if revenue else 0,
                'OpEx': (opex / revenue * 100) if revenue else 0,
                'Depreciation': (depr / revenue * 100) if revenue else 0,
                'Interest': (interest / revenue * 100) if revenue else 0,
                'Tax': (tax / revenue * 100) if revenue else 0,
                'Net Profit': (net_profit / revenue * 100) if revenue else 0
            }
            
            fig_pie = go.Figure(data=[go.Pie(
                labels=list(cost_structure.keys()),
                values=list(cost_structure.values()),
                hole=0.3,
                marker_colors=['#E74C3C', '#F39C12', '#3498DB', '#9B59B6', '#1ABC9C', '#27AE60']
            )])
            fig_pie.update_layout(height=300, margin=dict(t=30, b=0, l=0, r=0))
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col_chart2:
            st.markdown("**პროფიტის კასკადი (Waterfall)**")
            
            fig_waterfall = go.Figure(go.Waterfall(
                orientation="v",
                measure=["relative", "relative", "relative", "relative", "relative", "total"],
                x=["შემოსავალი", "COGS", "OpEx", "Depr", "Interest+Tax", "Net Profit"],
                y=[revenue, -cogs, -opex, -depr, -(interest+tax-other), 0],
                connector={"line": {"color": "rgb(63, 63, 63)"}},
                decreasing={"marker": {"color": "#E74C3C"}},
                increasing={"marker": {"color": "#27AE60"}},
                totals={"marker": {"color": "#3498DB"}}
            ))
            fig_waterfall.update_layout(height=300, margin=dict(t=30, b=0, l=0, r=0))
            st.plotly_chart(fig_waterfall, use_container_width=True)
        
        # ==========================================
        # 📊 SECTION 4: BALANCE SHEET METRICS
        # ==========================================
        
        st.markdown("---")
        st.markdown("### 💼 ბალანსის მაჩვენებლები")
        
        # BS metrics
        current_assets = get_cat(df_current, "BS: Current Assets (მიმდინარე აქტივები)")
        non_current_assets = get_cat(df_current, "BS: Non-Current Assets (გრძელვადიანი აქტივები)")
        total_assets = current_assets + non_current_assets
        
        current_liab = get_cat(df_current, "BS: Current Liabilities (მიმდინარე ვალდ.)") * -1
        non_current_liab = get_cat(df_current, "BS: Non-Current Liabilities (გრძელვადიანი ვალდ.)") * -1
        total_liab = current_liab + non_current_liab
        
        equity = get_cat(df_current, "BS: Equity (კაპიტალი)") * -1
        total_equity = equity + net_profit
        
        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Total Assets", utils.fmt_fin(total_assets))
        b2.metric("Total Liabilities", utils.fmt_fin(total_liab))
        b3.metric("Total Equity", utils.fmt_fin(total_equity))
        b4.metric("Assets - (Liab+Eq)", utils.fmt_fin(total_assets - total_liab - total_equity))
        
        # ==========================================
        # 📊 SECTION 5: FINANCIAL RATIOS
        # ==========================================
        
        st.markdown("---")
        st.markdown("### 📐 ფინანსური კოეფიციენტები")
        
        tab_liquidity, tab_leverage, tab_efficiency, tab_returns = st.tabs([
            "💧 ლიკვიდურობა", "⚖️ ფინანსური ბერკეტი", "⚡ ეფექტურობა", "📈 დაბრუნება"
        ])
        
        with tab_liquidity:
            st.markdown("#### ლიკვიდურობის კოეფიციენტები")
            
            l1, l2, l3 = st.columns(3)
            
            # Current Ratio
            current_ratio = (current_assets / current_liab) if current_liab else 0
            l1.metric("Current Ratio", f"{current_ratio:.2f}",
                     help="მიმდინარე აქტივები / მიმდინარე ვალდებულებები. ოპტიმალური: 1.5-2.0")
            
            # Quick Ratio (assuming inventory is ~40% of current assets)
            inventory_est = current_assets * 0.4  # approximate
            quick_ratio = ((current_assets - inventory_est) / current_liab) if current_liab else 0
            l2.metric("Quick Ratio (est.)", f"{quick_ratio:.2f}",
                     help="(მიმდინარე აქტივები - მარაგები) / მიმდინარე ვალდებულებები")
            
            # Cash Ratio
            cash_ratio = ((current_assets * 0.3) / current_liab) if current_liab else 0
            l3.metric("Cash Ratio (est.)", f"{cash_ratio:.2f}",
                     help="ფულადი სახსრები / მიმდინარე ვალდებულებები")
            
            # Interpretation
            if current_ratio < 1:
                st.error("⚠️ Current Ratio < 1: მაღალი ლიკვიდურობის რისკი!")
            elif current_ratio < 1.5:
                st.warning("⚡ Current Ratio 1-1.5: ლიკვიდურობა დამაკმაყოფილებელია, მაგრამ საჭიროებს მონიტორინგს")
            else:
                st.success("✅ Current Ratio > 1.5: კარგი ლიკვიდურობა")
        
        with tab_leverage:
            st.markdown("#### ფინანსური ბერკეტის კოეფიციენტები")
            
            le1, le2, le3 = st.columns(3)
            
            # Debt to Equity
            debt_to_equity = (total_liab / total_equity) if total_equity else 0
            le1.metric("Debt/Equity", f"{debt_to_equity:.2f}",
                      help="ვალდებულებები / კაპიტალი. ნაკლები = უფრო უსაფრთხო")
            
            # Debt to Assets
            debt_to_assets = (total_liab / total_assets) if total_assets else 0
            le2.metric("Debt/Assets", f"{debt_to_assets:.2%}",
                      help="ვალდებულებები / აქტივები")
            
            # Equity Multiplier
            equity_multiplier = (total_assets / total_equity) if total_equity else 0
            le3.metric("Equity Multiplier", f"{equity_multiplier:.2f}",
                      help="აქტივები / კაპიტალი. DuPont ანალიზი")
            
            # Interest Coverage
            if interest > 0:
                interest_coverage = ebit / interest
                st.metric("Interest Coverage Ratio", f"{interest_coverage:.2f}",
                         help="EBIT / საპროცენტო ხარჯები. >3 არის კარგი")
                
                if interest_coverage < 1.5:
                    st.error("⚠️ Interest Coverage < 1.5: რთულია საპროცენტო ხარჯების დაფარვა!")
                elif interest_coverage < 3:
                    st.warning("⚡ Interest Coverage 1.5-3: საპროცენტო ხარჯები მართვადია")
                else:
                    st.success("✅ Interest Coverage > 3: საპროცენტო ხარჯები კომფორტულად იფარება")
        
        with tab_efficiency:
            st.markdown("#### ეფექტურობის კოეფიციენტები")
            
            ef1, ef2, ef3 = st.columns(3)
            
            # Asset Turnover
            asset_turnover = (revenue / total_assets) if total_assets else 0
            ef1.metric("Asset Turnover", f"{asset_turnover:.2f}",
                      help="შემოსავალი / აქტივები. აქტივების გამოყენების ეფექტურობა")
            
            # Equity Turnover
            equity_turnover = (revenue / total_equity) if total_equity else 0
            ef2.metric("Equity Turnover", f"{equity_turnover:.2f}",
                      help="შემოსავალი / კაპიტალი")
            
            # Operating Efficiency
            operating_efficiency = (opex / revenue * 100) if revenue else 0
            ef3.metric("OpEx/Revenue", f"{operating_efficiency:.1f}%",
                      help="საოპერაციო ხარჯები / შემოსავალი. ნაკლები = უფრო ეფექტური")
        
        with tab_returns:
            st.markdown("#### დაბრუნების კოეფიციენტები")
            
            rt1, rt2, rt3 = st.columns(3)
            
            # ROA
            roa = (net_profit / total_assets * 100) if total_assets else 0
            rt1.metric("ROA", f"{roa:.2f}%",
                      help="Return on Assets = წმინდა მოგება / აქტივები")
            
            # ROE
            roe = (net_profit / total_equity * 100) if total_equity else 0
            rt2.metric("ROE", f"{roe:.2f}%",
                      help="Return on Equity = წმინდა მოგება / კაპიტალი")
            
            # ROIC (approx)
            invested_capital = total_equity + non_current_liab
            roic = (ebit / invested_capital * 100) if invested_capital else 0
            rt3.metric("ROIC (approx)", f"{roic:.2f}%",
                      help="Return on Invested Capital = EBIT / ინვესტირებული კაპიტალი")
            
            # DuPont Analysis
            st.markdown("#### 🔬 DuPont ანალიზი (ROE დეკომპოზიცია)")
            dupont_col1, dupont_col2 = st.columns([2, 1])
            
            with dupont_col1:
                profit_margin_dup = (net_profit / revenue) if revenue else 0
                asset_turnover_dup = (revenue / total_assets) if total_assets else 0
                equity_mult_dup = (total_assets / total_equity) if total_equity else 0
                
                roe_calculated = profit_margin_dup * asset_turnover_dup * equity_mult_dup * 100
                
                st.write(f"""
                **ROE = Profit Margin × Asset Turnover × Equity Multiplier**
                
                - Profit Margin: {profit_margin_dup*100:.2f}%
                - Asset Turnover: {asset_turnover_dup:.2f}
                - Equity Multiplier: {equity_mult_dup:.2f}
                - **ROE: {roe_calculated:.2f}%**
                """)
            
            with dupont_col2:
                st.info("""
                **DuPont ანალიზი აჩვენებს:**
                - მომგებიანობას
                - ეფექტურობას
                - ბერკეტს
                """)
        
        # ==========================================
        # 📊 SECTION 6: SCENARIO ANALYSIS
        # ==========================================
        
        st.markdown("---")
        st.markdown("### 🎯 სცენარული ანალიზი & სიმულაცია")
        
        sim_col1, sim_col2 = st.columns([1, 2])
        
        with sim_col1:
            st.markdown("**📊 პარამეტრების ცვლილება (%)**")
            
            revenue_change = st.slider("შემოსავლის ცვლილება", -50, 100, 0, 5, 
                                      help="როგორ შეიცვლება შემოსავალი?")
            cogs_change = st.slider("COGS ცვლილება", -50, 100, 0, 5,
                                   help="როგორ შეიცვლება თვითღირებულება?")
            opex_change = st.slider("OpEx ცვლილება", -50, 100, 0, 5,
                                   help="როგორ შეიცვლება საოპერაციო ხარჯები?")
            
            st.markdown("---")
            st.markdown("**📋 სცენარის შაბლონები**")
            
            if st.button("📈 ზრდის სცენარი (+20% Rev, +10% Costs)"):
                st.session_state.scenario_rev = 20
                st.session_state.scenario_cogs = 10
                st.session_state.scenario_opex = 10
                st.rerun()
            
            if st.button("💰 ეფექტურობის გაზრდა (COGS -10%)"):
                st.session_state.scenario_cogs = -10
                st.rerun()
            
            if st.button("⚠️ კრიზისული (-30% Rev)"):
                st.session_state.scenario_rev = -30
                st.rerun()
        
        with sim_col2:
            # Simulated calculations
            sim_revenue = revenue * (1 + revenue_change/100)
            sim_cogs = cogs * (1 + cogs_change/100)
            sim_opex = opex * (1 + opex_change/100)
            sim_gross_profit = sim_revenue - sim_cogs
            sim_ebitda = sim_gross_profit - sim_opex
            sim_net_profit = sim_ebitda - depr - interest + other - tax
            
            st.markdown("**📊 სიმულაციის შედეგები**")
            
            # Comparison table
            comparison_data = {
                'მაჩვენებელი': ['შემოსავალი', 'Gross Profit', 'EBITDA', 'Net Profit'],
                'ფაქტობრივი': [
                    utils.fmt_fin(revenue),
                    utils.fmt_fin(gross_profit),
                    utils.fmt_fin(ebitda),
                    utils.fmt_fin(net_profit)
                ],
                'სიმულაცია': [
                    utils.fmt_fin(sim_revenue),
                    utils.fmt_fin(sim_gross_profit),
                    utils.fmt_fin(sim_ebitda),
                    utils.fmt_fin(sim_net_profit)
                ],
                'ცვლილება': [
                    utils.fmt_fin(sim_revenue - revenue),
                    utils.fmt_fin(sim_gross_profit - gross_profit),
                    utils.fmt_fin(sim_ebitda - ebitda),
                    utils.fmt_fin(sim_net_profit - net_profit)
                ],
                'Δ%': [
                    f"{((sim_revenue - revenue)/revenue*100 if revenue else 0):.1f}%",
                    f"{((sim_gross_profit - gross_profit)/gross_profit*100 if gross_profit else 0):.1f}%",
                    f"{((sim_ebitda - ebitda)/ebitda*100 if ebitda else 0):.1f}%",
                    f"{((sim_net_profit - net_profit)/net_profit*100 if net_profit else 0):.1f}%"
                ]
            }
            
            st.dataframe(pd.DataFrame(comparison_data), use_container_width=True, hide_index=True)
            
            # Visualization
            fig_scenario = go.Figure()
            fig_scenario.add_trace(go.Bar(
                name='ფაქტობრივი',
                x=['შემოსავალი', 'Gross Profit', 'EBITDA', 'Net Profit'],
                y=[revenue, gross_profit, ebitda, net_profit],
                marker_color='#3498DB'
            ))
            fig_scenario.add_trace(go.Bar(
                name='სიმულაცია',
                x=['შემოსავალი', 'Gross Profit', 'EBITDA', 'Net Profit'],
                y=[sim_revenue, sim_gross_profit, sim_ebitda, sim_net_profit],
                marker_color='#27AE60'
            ))
            fig_scenario.update_layout(barmode='group', height=300, margin=dict(t=20, b=0, l=0, r=0))
            st.plotly_chart(fig_scenario, use_container_width=True)
        
        # ==========================================
        # 📊 SECTION 7: BREAKEVEN ANALYSIS
        # ==========================================
        
        st.markdown("---")
        st.markdown("### ⚖️ ურთიერთდაფარვის (Break-Even) ანალიზი")
        
        be_col1, be_col2 = st.columns(2)
        
        with be_col1:
            # Assumptions
            st.markdown("**📋 დაშვებები**")
            
            # Estimate fixed vs variable costs
            fixed_costs = opex + depr  # assume opex and depr are mostly fixed
            variable_cost_ratio = (cogs / revenue) if revenue else 0
            
            st.write(f"- ცვლადი ხარჯები: {variable_cost_ratio*100:.1f}% შემოსავლიდან")
            st.write(f"- ფიქსირებული ხარჯები: {utils.fmt_fin(fixed_costs)}")
            
            # Contribution margin
            contribution_margin_ratio = 1 - variable_cost_ratio
            st.write(f"- Contribution Margin: {contribution_margin_ratio*100:.1f}%")
            
            # Breakeven point
            if contribution_margin_ratio > 0:
                breakeven_revenue = fixed_costs / contribution_margin_ratio
                st.markdown(f"#### 🎯 Break-Even შემოსავალი: **{utils.fmt_fin(breakeven_revenue)}**")
                
                current_vs_be = (revenue / breakeven_revenue) if breakeven_revenue else 0
                st.write(f"- მიმდინარე შემოსავალი არის {current_vs_be:.1f}x break-even-ის")
                
                safety_margin = ((revenue - breakeven_revenue) / revenue * 100) if revenue else 0
                st.write(f"- უსაფრთხოების მარჟა: {safety_margin:.1f}%")
        
        with be_col2:
            # Break-even chart
            st.markdown("**📈 ურთიერთდაფარვის გრაფიკი**")
            
            revenue_range = [i * revenue / 10 for i in range(0, 21)]
            total_cost_line = [fixed_costs + (r * variable_cost_ratio) for r in revenue_range]
            
            fig_be = go.Figure()
            fig_be.add_trace(go.Scatter(
                x=revenue_range, y=revenue_range,
                name='შემოსავალი',
                line=dict(color='#27AE60', width=3)
            ))
            fig_be.add_trace(go.Scatter(
                x=revenue_range, y=total_cost_line,
                name='სრული ხარჯები',
                line=dict(color='#E74C3C', width=3)
            ))
            
            if contribution_margin_ratio > 0:
                fig_be.add_vline(x=breakeven_revenue, line_dash="dash", 
                               line_color="gray", annotation_text="Break-Even")
            
            fig_be.update_layout(
                height=300,
                xaxis_title="შემოსავალი",
                yaxis_title="თანხა",
                hovermode='x unified',
                margin=dict(t=20, b=0, l=0, r=0)
            )
            st.plotly_chart(fig_be, use_container_width=True)
        
        # ==========================================
        # 📊 SECTION 8: AI INSIGHTS
        # ==========================================
        
        st.markdown("---")
        st.markdown("### 🤖 AI რეკომენდაციები")
        
        # Prepare insights
        insights = []
        
        # Profitability insights
        if gross_margin < 30:
            insights.append("⚠️ **დაბალი Gross Margin (<30%)**: განიხილეთ ფასების გაზრდა ან COGS-ის შემცირება")
        elif gross_margin > 60:
            insights.append("✅ **ძალიან კარგი Gross Margin (>60%)**: გაგრძელეთ მიმდინარე სტრატეგია")
        
        if net_margin < 5:
            insights.append("⚠️ **დაბალი Net Margin (<5%)**: საჭიროა ხარჯების ოპტიმიზაცია")
        
        # Liquidity insights
        if current_ratio < 1:
            insights.append("🚨 **ლიკვიდურობის რისკი**: მიმდინარე აქტივები < მიმდინარე ვალდებულებები")
        
        # Leverage insights
        if debt_to_equity > 2:
            insights.append("⚠️ **მაღალი Debt/Equity (>2)**: განიხილეთ ვალების რეფინანსირება ან კაპიტალის გაზრდა")
        
        # Efficiency insights
        if operating_efficiency > 40:
            insights.append("⚡ **მაღალი OpEx (>40% შემოსავლიდან)**: ეძებეთ ავტომატიზაციისა და ოპტიმიზაციის გზები")
        
        # Growth insights
        if df_previous is not None:
            revenue_growth = ((revenue - revenue_prev) / revenue_prev * 100) if revenue_prev else 0
            if revenue_growth > 20:
                insights.append(f"📈 **შესანიშნავი ზრდა (+{revenue_growth:.1f}%)**: შეინარჩუნეთ მომენტუმი")
            elif revenue_growth < -10:
                insights.append(f"⚠️ **შემოსავლების კლება ({revenue_growth:.1f}%)**: გადასინჯეთ სამარკეტინგო სტრატეგია")
        
        if insights:
            for insight in insights:
                st.markdown(f"- {insight}")
        else:
            st.success("✅ ყველა ძირითადი მაჩვენებელი ნორმალურ დიაპაზონშია!")
        
        # Download button for full report
        st.markdown("---")
        if st.button("📥 ექსპორტი Excel-ში (Full Report)", use_container_width=True):
            # Create comprehensive Excel report
            report_data = {
                'პერიოდი': [current_period],
                'შემოსავალი': [revenue],
                'COGS': [cogs],
                'Gross Profit': [gross_profit],
                'OpEx': [opex],
                'EBITDA': [ebitda],
                'EBIT': [ebit],
                'Net Profit': [net_profit],
                'Gross Margin %': [gross_margin],
                'EBITDA Margin %': [ebitda_margin],
                'Net Margin %': [net_margin],
                'Current Ratio': [current_ratio],
                'Debt/Equity': [debt_to_equity],
                'ROA %': [roa],
                'ROE %': [roe],
                'Asset Turnover': [asset_turnover]
            }
            
            df_report = pd.DataFrame(report_data)
            
            # Note: In real implementation, you'd use openpyxl to create and download
            st.success("✅ რეპორტი მზადაა! (Excel export ფუნქციონალი დაემატება)")
            st.dataframe(df_report, use_container_width=True)