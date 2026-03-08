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
import auth

# ── Page Config ──
st.set_page_config(page_title="FinSuite Pro", layout="wide", initial_sidebar_state="expanded")
st.markdown(utils.STYLES, unsafe_allow_html=True)

# ── Authentication Gate ──
if not auth.login_page():
    st.stop()

# ── Plotly Theme ──
import plotly.io as pio
pio.templates["finsuite"] = go.layout.Template(
    layout=dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(248,250,252,0.8)",
        font=dict(family="Inter, -apple-system, sans-serif", color="#475569", size=12),
        colorway=["#2563EB", "#059669", "#D97706", "#7C3AED", "#DC2626", "#0891B2", "#4F46E5"],
        xaxis=dict(showgrid=False, zeroline=False, linecolor="rgba(0,0,0,0.06)",
                   tickfont=dict(size=11, color="#64748B")),
        yaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.05)", zeroline=False,
                   tickfont=dict(size=11, color="#64748B")),
        legend=dict(bgcolor="rgba(255,255,255,0.96)", bordercolor="rgba(0,0,0,0.06)",
                    borderwidth=1, font=dict(size=12, color="#475569")),
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="rgba(0,0,0,0.1)",
                        font=dict(family="Inter", size=12, color="#0F172A")),
        margin=dict(t=30, b=30, l=10, r=10),
    )
)
pio.templates.default = "finsuite"

# ── Sidebar ──
_display = st.session_state.get('display_name', 'User')
_role_badge = ' (Admin)' if st.session_state.get('user_role') == 'admin' else ''
st.sidebar.markdown(f"""
<div style="padding:4px 0 18px 0;border-bottom:1px solid #E2E8F0;margin-bottom:18px;">
  <div style="font-size:17px;font-weight:700;color:#0F172A;letter-spacing:-0.02em;">
    FinSuite Pro
  </div>
  <div style="font-size:11px;color:#94A3B8;margin-top:2px;">Financial Analysis Platform</div>
  <div style="font-size:12px;color:#475569;margin-top:8px;">
    Signed in as <b>{_display}</b>{_role_badge}
  </div>
</div>
""", unsafe_allow_html=True)
if st.sidebar.button("Sign Out", use_container_width=True, key="btn_signout"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# P&L parent name mapping
PL_PARENT_MAP = {
    '6100': 'Operating Revenue',
    '6200': 'Other Revenue',
    '7100': 'Materials & COGS',
    '7200': 'Direct Labor',
    '7300': 'Sales & Marketing',
    '7400': 'Administrative Expenses',
    '8100': 'Interest Expenses',
    '9100': 'Income Tax',
}

st.sidebar.markdown("""
<div style="font-size:11px;font-weight:600;color:#94A3B8;
            text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px;">
  Upload Data
</div>
""", unsafe_allow_html=True)

# File upload state
if 'upload_key' not in st.session_state:
    st.session_state.upload_key = 0

uploaded_file = st.sidebar.file_uploader(
    "Upload Excel",
    type=["xlsx"],
    key=f"file_uploader_{st.session_state.upload_key}",
)

if 'df_working' not in st.session_state:
    st.session_state.df_working = None

# ── File Processing ──
if uploaded_file and st.session_state.df_working is None:
    file_size_mb = uploaded_file.size / (1024 * 1024)
    if file_size_mb > 50:
        st.error(f"File too large ({file_size_mb:.1f}MB). Maximum is 50MB.")
        st.stop()

    try:
        df = pd.read_excel(uploaded_file)
        df.columns = [str(c).strip() for c in df.columns]

        # Check if first row is header
        first_row = df.iloc[0].fillna('').astype(str).str.lower().tolist()
        header_kw = ['code', 'account', 'ანალიტიკ', 'კოდ', 'debit', 'დებეტ',
                     'credit', 'კრედიტ', 'name', 'სახელ', 'balance', 'ნაშთ']
        if any(kw in ' '.join(first_row) for kw in header_kw):
            df.columns = df.iloc[0].fillna('').astype(str).str.strip()
            df = df.iloc[1:].reset_index(drop=True)

        # Auto-detect columns
        def _find_col(df, keywords):
            for col in df.columns:
                if any(kw in str(col).lower() for kw in keywords):
                    return col
            for col in df.columns:
                sample = df[col].dropna().astype(str).head(10)
                if sample.str.match(r'^\d{3,6}').mean() > 0.5:
                    return col
            return None

        code_col = _find_col(df, ['code', 'კოდ', 'account', 'ანალიტიკ', 'acct', '#'])
        name_col = _find_col(df, ['name', 'სახელ', 'დასახელ', 'description', 'title', 'наим'])
        debit_col = _find_col(df, ['debit', 'დებეტ', 'debet', 'db'])
        credit_col = _find_col(df, ['credit', 'კრედიტ', 'cr'])
        balance_col = _find_col(df, ['balance', 'ნაშთ', 'net', 'სალდო', 'amount', 'თანხ'])

        # Fallback to positional
        cols = list(df.columns)
        if code_col is None and len(cols) >= 1: code_col = cols[0]
        if name_col is None and len(cols) >= 2: name_col = cols[1]
        if debit_col is None and len(cols) >= 3: debit_col = cols[2]
        if credit_col is None and len(cols) >= 4: credit_col = cols[3]

        # Rename
        rename_map = {}
        if code_col: rename_map[code_col] = 'Code'
        if name_col and name_col != code_col: rename_map[name_col] = 'Name'
        if debit_col and debit_col not in rename_map: rename_map[debit_col] = 'Debit'
        if credit_col and credit_col not in rename_map: rename_map[credit_col] = 'Credit'
        if balance_col and balance_col not in rename_map: rename_map[balance_col] = 'Balance'
        df.rename(columns=rename_map, inplace=True)

        # Ensure required columns
        if 'Code' not in df.columns:
            raise ValueError("Could not find Code column. Check your Excel file.")
        if 'Name' not in df.columns:
            df['Name'] = df['Code']
        if 'Debit' not in df.columns and 'Credit' not in df.columns:
            if 'Balance' in df.columns:
                df['Debit'] = pd.to_numeric(df['Balance'], errors='coerce').clip(lower=0).fillna(0)
                df['Credit'] = pd.to_numeric(df['Balance'], errors='coerce').clip(upper=0).abs().fillna(0)
            else:
                df['Debit'] = 0
                df['Credit'] = 0
        if 'Debit' not in df.columns: df['Debit'] = 0
        if 'Credit' not in df.columns: df['Credit'] = 0

        # Clean
        df = df[df['Code'].notna()].copy()
        df = df[df['Code'].astype(str).str.strip() != ''].copy()
        df = df[df['Code'].astype(str).str.match(r'^\d', na=False)].copy()
        df['Code'] = df['Code'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        df['Name'] = df['Name'].fillna('').astype(str)
        df['Debit'] = pd.to_numeric(df['Debit'], errors='coerce').fillna(0)
        df['Credit'] = pd.to_numeric(df['Credit'], errors='coerce').fillna(0)
        df['Net'] = df['Debit'] - df['Credit']

        if df.empty:
            raise ValueError("No valid account codes found in the file.")

        st.sidebar.success(f"Loaded {len(df):,} rows")

    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        st.stop()

    # ── Hierarchy detection & Category assignment ──
    import json as _json
    import os as _os
    from collections import defaultdict as _ddict

    _nets = df.groupby("Code")["Net"].sum().to_dict()
    _all = list(df["Code"].unique())
    _pure = [c for c in _all if ' ' not in c]
    _parents = set()

    # Rule 1: space separator
    for _c in _all:
        if ' ' in _c:
            _p = _c.split(' ')[0]
            if _p in set(_all):
                _parents.add(_p)

    # Rule 2: same net, pure numeric -> smaller = parent
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

    # Rule 3: net = sum of family
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

    # Load mapping memory
    _mem_file = "mapping_memory.json"
    _memory_map = {}
    if _os.path.exists(_mem_file):
        try:
            with open(_mem_file, "r", encoding="utf-8") as _f:
                _memory_map = _json.load(_f)
        except Exception:
            _memory_map = {}

    def smart_map(row):
        code = str(row["Code"]).strip()
        name = str(row.get("Name", ""))
        if code in _parents:
            return "IGNORE (იგნორირება)"
        if code in _memory_map:
            return _memory_map[code]
        return ai_advisor_module.smart_suggest(code, name)

    df["Category"] = df.apply(smart_map, axis=1)
    st.session_state.df_working = df

df_final = st.session_state.df_working

# ════════════════════════════════════════════
#  TABS
# ════════════════════════════════════════════
_tab_names = ["Mapping", "P&L", "Balance Sheet", "Cash Flow", "Comparison", "Strategy"]
if st.session_state.get('user_role') == 'admin':
    _tab_names.append("Admin")
    tab_map, tab_pl, tab_bs, tab_cf, tab_comp, tab_sim, tab_admin = st.tabs(_tab_names)
else:
    tab_map, tab_pl, tab_bs, tab_cf, tab_comp, tab_sim = st.tabs(_tab_names)

# ─────────────────────────────────────────
# TAB 1: MAPPING
# ─────────────────────────────────────────
with tab_map:
    if df_final is None:
        db = utils.load_db()
        db_keys = sorted(db.keys(), reverse=True)

        if not db_keys:
            # Empty state
            st.markdown("""
<div style="text-align:center;padding:80px 20px;">
  <div style="font-size:48px;margin-bottom:16px;opacity:0.6;">&#128202;</div>
  <h2 style="color:#0F172A;margin-bottom:8px;font-size:22px;">Welcome to FinSuite Pro</h2>
  <p style="color:#64748B;font-size:14px;max-width:400px;margin:0 auto;">
    Upload an Excel trial balance from the sidebar to start your financial analysis.
  </p>
  <div style="display:flex;justify-content:center;gap:40px;margin-top:28px;">
    <div style="text-align:center;color:#64748B;font-size:13px;">
      <div style="background:#2563EB;color:white;width:30px;height:30px;border-radius:50%;
                  display:flex;align-items:center;justify-content:center;font-weight:700;
                  margin:0 auto 8px;">1</div>Upload Excel</div>
    <div style="text-align:center;color:#64748B;font-size:13px;">
      <div style="background:#2563EB;color:white;width:30px;height:30px;border-radius:50%;
                  display:flex;align-items:center;justify-content:center;font-weight:700;
                  margin:0 auto 8px;">2</div>Review Mapping</div>
    <div style="text-align:center;color:#64748B;font-size:13px;">
      <div style="background:#2563EB;color:white;width:30px;height:30px;border-radius:50%;
                  display:flex;align-items:center;justify-content:center;font-weight:700;
                  margin:0 auto 8px;">3</div>Save & Analyze</div>
  </div>
</div>""", unsafe_allow_html=True)

        else:
            # Saved periods manager
            st.markdown("#### Saved Periods")

            _std_cats = [c for c in utils.MAPPING_OPTIONS if c != "IGNORE (იგნორირება)"]
            grid_cols = st.columns(min(4, len(db_keys)))
            for _i, _k in enumerate(db_keys):
                _df_k = pd.DataFrame(db[_k])
                _n_total = len(_df_k)
                _n_mapped = len(_df_k[_df_k["Category"].isin(_std_cats)]) if "Category" in _df_k.columns else 0
                _pct = _n_mapped / _n_total * 100 if _n_total else 0
                _net = _df_k["Net"].sum() if "Net" in _df_k.columns else 0
                _color = "#059669" if _pct == 100 else ("#D97706" if _pct > 70 else "#DC2626")
                with grid_cols[_i % min(4, len(db_keys))]:
                    st.markdown(f"""
<div style="border:1px solid #E2E8F0;border-radius:10px;padding:14px;margin-bottom:10px;background:white;">
  <div style="font-weight:700;font-size:14px;color:#0F172A;">{_k}</div>
  <div style="font-size:12px;color:#64748B;margin:4px 0;">{_n_total} codes</div>
  <div style="background:#F1F5F9;border-radius:99px;height:5px;margin:8px 0;">
    <div style="background:{_color};width:{_pct:.0f}%;height:5px;border-radius:99px;"></div>
  </div>
  <div style="font-size:11px;color:{_color};font-weight:600;">{_pct:.0f}% mapped</div>
</div>""", unsafe_allow_html=True)

            st.markdown("---")

            _c_sel, _c_edit, _c_del = st.columns([3, 1, 1])
            _selected_period = _c_sel.selectbox("Select period:", db_keys, key="mgr_period",
                                                 label_visibility="collapsed")

            if _c_edit.button("Edit", type="primary", use_container_width=True, key="btn_edit"):
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

            if _c_del.button("Delete", use_container_width=True, key="btn_del"):
                st.session_state.delete_confirm_period = _selected_period

            if st.session_state.delete_confirm_period == _selected_period:
                st.error(f"Delete **{_selected_period}** permanently?")
                _dc1, _dc2, _dc3 = st.columns([1, 1, 3])
                if _dc1.button("Yes, delete", type="primary", key="btn_confirm_del"):
                    utils.delete_from_db(_selected_period)
                    st.session_state.delete_confirm_period = None
                    st.toast(f"{_selected_period} deleted")
                    st.rerun()
                if _dc2.button("Cancel", key="btn_cancel_del"):
                    st.session_state.delete_confirm_period = None
                    st.rerun()

            # Detail panel
            st.markdown(f"#### {_selected_period} — Details")
            _df_sel = pd.DataFrame(db[_selected_period])
            if "Code" in _df_sel.columns:
                _df_sel["Code"] = _df_sel["Code"].astype(str).str.strip()
            _n_total2 = len(_df_sel)
            _n_mapped2 = len(_df_sel[_df_sel["Category"].isin(_std_cats)]) if "Category" in _df_sel.columns else 0
            _n_ignore2 = len(_df_sel[_df_sel["Category"] == "IGNORE (იგნორირება)"]) if "Category" in _df_sel.columns else 0
            _net2 = _df_sel["Net"].sum() if "Net" in _df_sel.columns else 0

            _s1, _s2, _s3, _s4 = st.columns(4)
            _s1.metric("Total Codes", _n_total2)
            _s2.metric("Mapped", _n_mapped2)
            _s3.metric("Unmapped", _n_total2 - _n_mapped2 - _n_ignore2)
            _s4.metric("Total Net", utils.fmt_fin(_net2))

            if "Category" in _df_sel.columns:
                with st.expander("Category Distribution", expanded=False):
                    _cc = _df_sel["Category"].value_counts().reset_index()
                    _cc.columns = ["Category", "Count"]
                    if "Net" in _df_sel.columns:
                        _nc = _df_sel.groupby("Category")["Net"].sum().reset_index()
                        _nc.columns = ["Category", "Total Net"]
                        _cc = _cc.merge(_nc, on="Category", how="left")
                        _cc["Total Net"] = _cc["Total Net"].apply(utils.fmt_fin)
                    st.dataframe(_cc, use_container_width=True, hide_index=True)

    # ── Mapping Editor ──
    else:
        if "editing_period_key" not in st.session_state:
            st.session_state.editing_period_key = None

        _is_edit = bool(st.session_state.editing_period_key)
        _edit_label = f" — Editing: {st.session_state.editing_period_key}" if _is_edit else ""

        st.markdown(f"#### Category Mapping{_edit_label}")

        df_w = st.session_state.df_working
        _std_cats2 = [c for c in utils.MAPPING_OPTIONS if c != "IGNORE (იგნორირება)"]
        _total = len(df_w)
        _mapped = len(df_w[df_w["Category"].isin(_std_cats2)]) if "Category" in df_w.columns else 0
        _ignore = len(df_w[df_w["Category"] == "IGNORE (იგნორირება)"]) if "Category" in df_w.columns else 0
        _unmap = _total - _mapped - _ignore
        _pct2 = _mapped / _total * 100 if _total else 0

        _mc1, _mc2, _mc3, _mc4 = st.columns(4)
        _mc1.metric("Total", _total)
        _mc2.metric("Mapped", f"{_mapped} ({_pct2:.0f}%)")
        _mc3.metric("Unmapped", _unmap)
        _mc4.metric("Ignored", _ignore)
        st.progress(_pct2 / 100)
        st.markdown("---")

        _col_main, _col_side = st.columns([3, 1])

        with _col_main:
            _fc1, _fc2, _fc3 = st.columns([2, 2, 1])
            _search_q = _fc1.text_input("Search", placeholder="Code or name...", key="map_search")
            _filter_cat = _fc2.selectbox("Filter by category",
                                          ["All"] + utils.MAPPING_OPTIONS, key="map_filter")
            _show_unmap = _fc3.checkbox("Unmapped only", key="map_unmap")

            _fdf = df_w.copy()
            if _search_q:
                _fdf = _fdf[
                    _fdf["Code"].astype(str).str.contains(_search_q, case=False, na=False) |
                    _fdf["Name"].astype(str).str.contains(_search_q, case=False, na=False)
                ]
            if _filter_cat != "All":
                _fdf = _fdf[_fdf["Category"] == _filter_cat]
            if _show_unmap:
                _fdf = _fdf[~_fdf["Category"].isin(_std_cats2 + ["IGNORE (იგნორირება)"])]

            st.caption(f"Showing **{len(_fdf)}** / {_total}")

            _display_df = _fdf[["Code", "Name", "Net", "Category"]].copy()
            _edited_df = st.data_editor(
                _display_df,
                column_config={
                    "Category": st.column_config.SelectboxColumn(
                        "Category", options=utils.MAPPING_OPTIONS, width="large", required=True),
                    "Code": st.column_config.TextColumn("Code", width="small"),
                    "Name": st.column_config.TextColumn("Name", width="medium"),
                    "Net": st.column_config.NumberColumn("Net", format="%.2f", width="small"),
                },
                use_container_width=True, height=440, hide_index=True, key="map_editor",
            )

            if not _edited_df.equals(_display_df):
                for _, _row in _edited_df.iterrows():
                    _mask = st.session_state.df_working["Code"] == _row["Code"]
                    if _mask.any():
                        st.session_state.df_working.loc[_mask, "Category"] = _row["Category"]

            st.markdown("---")

            # Save / Clear
            _sc1, _sc2, _sc3 = st.columns([2, 1, 1])
            _default_date = datetime.now()
            if _is_edit:
                try:
                    _default_date = datetime.strptime(st.session_state.editing_period_key, "%Y-%m")
                except Exception:
                    pass
            _save_date = _sc1.date_input("Save period", _default_date, key="map_date")

            if _sc2.button("Save", type="primary", use_container_width=True, key="map_save"):
                _date_key = _save_date.strftime("%Y-%m")
                _old_key = st.session_state.get("editing_period_key")
                if _old_key and _old_key != _date_key:
                    utils.delete_from_db(_old_key)
                utils.save_to_db(_date_key, st.session_state.df_working.to_dict("records"))
                st.session_state.df_working = None
                st.session_state.editing_period_key = None
                st.session_state.upload_key = st.session_state.get("upload_key", 0) + 1
                st.toast(f"{_date_key} saved!")
                st.rerun()

            if _sc3.button("Clear", use_container_width=True, key="map_clear"):
                st.session_state.df_working = None
                st.session_state.editing_period_key = None
                st.session_state.upload_key = st.session_state.get("upload_key", 0) + 1
                st.rerun()

        with _col_side:
            st.markdown("##### Tools")

            with st.expander("Bulk Actions", expanded=True):
                _bulk_prefix = st.text_input("Prefix (e.g. 71, 74)", key="bulk_pfx",
                                              placeholder="Code prefix")
                _bulk_cat = st.selectbox("Category", utils.MAPPING_OPTIONS, key="bulk_cat")
                if st.button("Apply", key="bulk_apply", use_container_width=True, type="primary"):
                    if _bulk_prefix:
                        _bmask = st.session_state.df_working["Code"].astype(str).str.startswith(_bulk_prefix)
                        _bcnt = _bmask.sum()
                        if _bcnt > 0:
                            st.session_state.df_working.loc[_bmask, "Category"] = _bulk_cat
                            st.toast(f"{_bcnt} codes updated")
                            st.rerun()
                        else:
                            st.warning(f"No codes start with '{_bulk_prefix}'")

                st.markdown("---")
                st.caption("Quick Presets:")
                _presets = [
                    ("71/72 > COGS", [("71", "COGS (თვითღირებულება)"), ("72", "COGS (თვითღირებულება)")]),
                    ("74 > OpEx", [("74", "Operating Expenses (საოპერაციო ხარჯები)")]),
                    ("6x > Revenue", [("6", "Revenue (შემოსავალი)")]),
                    ("1x > Current Assets", [("11", "BS: Current Assets (მიმდინარე აქტივები)"),
                                              ("12", "BS: Current Assets (მიმდინარე აქტივები)")]),
                ]
                for _lbl, _rules in _presets:
                    if st.button(_lbl, key=f"preset_{_lbl}", use_container_width=True):
                        _tc = 0
                        for _pfx, _cat in _rules:
                            _pm = st.session_state.df_working["Code"].astype(str).str.startswith(_pfx)
                            st.session_state.df_working.loc[_pm, "Category"] = _cat
                            _tc += _pm.sum()
                        st.toast(f"{_tc} codes updated")
                        st.rerun()

            with st.expander("Category Stats", expanded=False):
                if "Category" in st.session_state.df_working.columns:
                    _cc2 = st.session_state.df_working["Category"].value_counts().reset_index()
                    _cc2.columns = ["Category", "Codes"]
                    if "Net" in st.session_state.df_working.columns:
                        _nc2 = st.session_state.df_working.groupby("Category")["Net"].sum().reset_index()
                        _nc2.columns = ["Category", "Net"]
                        _cc2 = _cc2.merge(_nc2, on="Category", how="left")
                        _cc2["Net"] = _cc2["Net"].apply(utils.fmt_fin)
                    st.dataframe(_cc2, use_container_width=True, hide_index=True)

            with st.expander("Mapping Variants", expanded=False):
                _variants = utils.load_mapping_variants()
                if _variants:
                    _vnames = list(_variants.keys())
                    _sel_var = st.selectbox("Load variant:", _vnames, key="load_var")
                    _lc1, _lc2 = st.columns(2)
                    if _lc1.button("Load", use_container_width=True, key="load_var_btn"):
                        _vmap = _variants[_sel_var]
                        _dft = st.session_state.df_working.copy()
                        _dft["Code"] = _dft["Code"].astype(str).str.strip()
                        _vc = 0
                        for _idx, _vrow in _dft.iterrows():
                            if str(_vrow["Code"]) in _vmap:
                                _dft.at[_idx, "Category"] = _vmap[str(_vrow["Code"])]
                                _vc += 1
                        st.session_state.df_working = _dft
                        st.toast(f"{_vc} codes updated")
                        st.rerun()
                    if _lc2.button("Delete", use_container_width=True, key="del_var_btn"):
                        utils.delete_mapping_variant(_sel_var)
                        st.rerun()
                st.markdown("---")
                _nvname = st.text_input("Variant name:", key="new_var_name",
                                         placeholder="e.g. 2024 Standard")
                if st.button("Save Current", use_container_width=True, key="save_var_btn"):
                    if _nvname:
                        _mdict = dict(zip(
                            st.session_state.df_working["Code"].astype(str),
                            st.session_state.df_working.get("Category", "IGNORE (იგნორირება)"),
                        ))
                        utils.save_mapping_variant(_nvname, _mdict)
                        st.toast(f"'{_nvname}' saved!")
                    else:
                        st.warning("Enter a name")

# ─────────────────────────────────────────
# TAB 2: P&L
# ─────────────────────────────────────────
with tab_pl:
    db = utils.load_db()
    opts = sorted(db.keys(), reverse=True)
    if not opts:
        st.markdown("""
<div style="text-align:center;padding:80px 20px;color:#94A3B8;">
  <div style="font-size:40px;margin-bottom:16px;opacity:0.4;">&#128202;</div>
  <div style="font-size:15px;font-weight:600;color:#64748B;">No data yet</div>
  <div style="font-size:13px;color:#94A3B8;">Upload and save data from the Mapping tab</div>
</div>""", unsafe_allow_html=True)
    else:
        col_gen, col_snap = st.columns([3, 1])
        sel_src = col_gen.selectbox("Period:", opts, label_visibility="collapsed", key="pl_period")

        # Raw data for AI advisor and parent names
        df_raw = pd.DataFrame(db[sel_src])
        df_raw['Code'] = df_raw['Code'].astype(str).str.strip()
        st.session_state.df_raw_for_names = df_raw

        # AI Advisor
        problematic_codes = ai_advisor_module.render_audit_ui(df_raw, "PL", source_key=sel_src, ui_key="pl")

        # Clean data
        df_clean = utils.clean_dataset_logic(db[sel_src])
        if not df_clean.empty and 'Code' in df_clean.columns:
            df_clean['ParentCode'] = df_clean['Code'].apply(
                lambda x: str(x)[:2] + "00" if len(str(x)) >= 3 else str(x))

        # Calculations
        m = utils.calc_pl_metrics(df_clean)
        rev, cogs, opex = m['revenue'], m['cogs'], m['opex']
        depr, inte, tax = m['depr'], m['interest'], m['tax']
        other_net = m['other']
        gross_profit, ebitda, ebit, ebt, net = m['gross_profit'], m['ebitda'], m['ebit'], m['ebt'], m['net_profit']

        # Header
        margin_pct = (net / rev * 100) if rev else 0
        profit_color = "#059669" if net >= 0 else "#DC2626"
        badge_cls = "badge-green" if net >= 0 else "badge-red"
        badge_txt = f"{'▲' if net >= 0 else '▼'} {abs(margin_pct):.1f}% Net Margin"

        st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;
            padding:16px 20px;background:#F8FAFC;border:1px solid #E2E8F0;
            border-radius:10px;margin-bottom:18px;">
  <div>
    <div style="font-size:17px;font-weight:700;color:#0F172A;">Profit & Loss Statement</div>
    <div style="font-size:12px;color:#94A3B8;margin-top:2px;">Period: {sel_src}</div>
  </div>
  <div style="display:flex;align-items:center;gap:10px;">
    <span class="badge {badge_cls}">{badge_txt}</span>
    <div style="font-family:monospace;font-size:20px;font-weight:600;color:{profit_color};">
      {utils.fmt_fin(net)}
    </div>
  </div>
</div>""", unsafe_allow_html=True)

        snap_name = col_snap.text_input("Snapshot:", value=f"PL_{sel_src}", label_visibility="collapsed")
        if col_snap.button("Save Snapshot", key="snap_pl", use_container_width=True):
            utils.save_snapshot(snap_name, df_clean.to_dict('records'))
            st.toast("Snapshot saved!")

        # KPI row
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Revenue", utils.fmt_fin(rev))
        k2.metric("Gross Profit", utils.fmt_fin(gross_profit))
        k3.metric("EBITDA", utils.fmt_fin(ebitda))
        k4.metric("EBIT", utils.fmt_fin(ebit))
        k5.metric("Net Profit", utils.fmt_fin(net))

        # Waterfall chart
        fig = go.Figure(go.Waterfall(
            orientation="v",
            measure=["relative", "relative", "total", "relative", "total", "total"],
            x=["Revenue", "COGS", "Gross Profit", "Opex + Other", "EBITDA", "Net Profit"],
            y=[rev, -cogs, 0, -(opex + inte + tax - other_net), 0, 0],
            connector={"line": {"color": "rgba(0,0,0,0.06)", "width": 1}},
            increasing={"marker": {"color": "#059669"}},
            decreasing={"marker": {"color": "#DC2626"}},
            totals={"marker": {"color": "#2563EB"}},
            textposition="outside",
            textfont=dict(size=11, color="#64748B"),
        ))
        fig.update_layout(height=240, margin=dict(t=10, b=10, l=0, r=0),
                          paper_bgcolor="rgba(0,0,0,0)",
                          plot_bgcolor="rgba(248,250,252,0.8)",
                          yaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.05)",
                                     tickformat=",.0f"),
                          xaxis=dict(showgrid=False))
        st.plotly_chart(fig, use_container_width=True)

        show_codes = st.checkbox("Show codes", value=True, key="pl_codes")
        cols = 3 if show_codes else 2

        # P&L row builder
        def get_pl_rows(cat, multiplier=1):
            subset = df_clean[df_clean['Category'] == cat].copy()
            if subset.empty or 'ParentCode' not in subset.columns:
                return ""
            subset['Val'] = subset['Net'] * multiplier
            grouped = subset.groupby('ParentCode').agg({'Val': 'sum', 'Code': 'first'}).reset_index().sort_values('ParentCode')

            html = ""
            for _, group_row in grouped.iterrows():
                if abs(group_row['Val']) < 0.01:
                    continue
                p_code = group_row['ParentCode']
                p_val = group_row['Val']

                # Find parent name
                p_name = PL_PARENT_MAP.get(str(p_code))
                if not p_name and 'df_raw_for_names' in st.session_state:
                    parent_row = st.session_state.df_raw_for_names[
                        st.session_state.df_raw_for_names['Code'] == p_code]
                    p_name = parent_row.iloc[0]['Name'] if not parent_row.empty else f"Group {p_code}"
                elif not p_name:
                    p_name = f"Group {p_code}"

                children = subset[subset['ParentCode'] == p_code]
                children_rows = ""
                for _, child in children.iterrows():
                    if abs(child['Val']) < 0.01:
                        continue
                    err = "background:#FEF2F2;" if str(child["Code"]) in problematic_codes else ""
                    c_td = f'<td class="code-col">{child["Code"]}</td>' if show_codes else ""
                    children_rows += (
                        f'<tr style="{err}">{c_td}'
                        f'<td class="indent" style="color:var(--text-secondary);font-size:0.85rem;">{child["Name"]}</td>'
                        f'<td class="amt" style="font-size:0.85rem;">{utils.fmt_fin(child["Val"])}</td></tr>'
                    )

                td_code = f'<td class="code-col"><b>{p_code}</b></td>' if show_codes else ""
                if children_rows:
                    inner = f'<table class="child-table">{children_rows}</table>'
                    name_cell = f'<details><summary><b>{p_name}</b></summary>{inner}</details>'
                else:
                    name_cell = f"<b>{p_name}</b>"

                html += (
                    f'<tr style="background:var(--bg-subtle);">'
                    f'{td_code}<td>{name_cell}</td>'
                    f'<td class="amt" style="vertical-align:top;padding-top:8px;"><b>{utils.fmt_fin(p_val)}</b></td></tr>'
                )
            return html

        # Build P&L table
        pl_html = f"""
<table class="fin-table">
<thead><tr>{'<th>Code</th>' if show_codes else ''}<th>Item</th><th class="text-right">Amount</th></tr></thead>
<tbody>
<tr class="section-row"><td colspan="{cols}">Revenue</td></tr>
{get_pl_rows("Revenue (შემოსავალი)", -1)}
<tr class="subtotal-row"><td colspan="{cols-1}">Total Revenue</td><td class="amt"><b>{utils.fmt_fin(rev)}</b></td></tr>

<tr class="section-row" style="background:#D97706;"><td colspan="{cols}">Cost of Goods Sold</td></tr>
{get_pl_rows("COGS (თვითღირებულება)", 1)}
<tr class="subtotal-row"><td colspan="{cols-1}">Total COGS</td><td class="amt"><b>{utils.fmt_fin(cogs)}</b></td></tr>
<tr class="calc-row"><td colspan="{cols-1}">GROSS PROFIT</td><td class="amt"><b>{utils.fmt_fin(gross_profit)}</b></td></tr>

<tr class="section-row" style="background:#64748B;"><td colspan="{cols}">Operating Expenses</td></tr>
{get_pl_rows("Operating Expenses (საოპერაციო ხარჯები)", 1)}
<tr class="subtotal-row"><td colspan="{cols-1}">Total OpEx</td><td class="amt"><b>{utils.fmt_fin(opex)}</b></td></tr>
<tr class="calc-row" style="background:#ECFDF5;"><td colspan="{cols-1}" style="color:#059669;">EBITDA</td><td class="amt" style="color:#059669;"><b>{utils.fmt_fin(ebitda)}</b></td></tr>

<tr class="subtotal-row"><td colspan="{cols}">Other Items</td></tr>
{get_pl_rows("Depreciation (ცვეთა/ამორტიზაცია)", 1)}
<tr class="calc-row" style="background:#FEF2F2;"><td colspan="{cols-1}" style="color:#DC2626;">EBIT</td><td class="amt" style="color:#DC2626;"><b>{utils.fmt_fin(ebit)}</b></td></tr>
{get_pl_rows("Interest (საპროცენტო ხარჯი)", 1)}
{get_pl_rows("Other Income/Expense (სხვა არასაოპერაციო)", -1)}
<tr class="calc-row"><td colspan="{cols-1}">EBT</td><td class="amt"><b>{utils.fmt_fin(ebt)}</b></td></tr>
<tr class="subtotal-row"><td colspan="{cols}">Tax</td></tr>
{get_pl_rows("Tax (მოგების გადასახადი)", 1)}
<tr class="grand-row"><td colspan="{cols-1}">NET PROFIT</td><td class="amt">{utils.fmt_fin(net)}</td></tr>
</tbody></table>"""
        st.markdown(pl_html, unsafe_allow_html=True)

        with st.expander("Snapshots Archive"):
            snaps = utils.load_snapshots()
            if snaps:
                sel_s = st.selectbox("Snapshot:", list(snaps.keys()))
                if st.button("Delete", key="del_snap"):
                    utils.delete_snapshot(sel_s)
                    st.rerun()

# ─────────────────────────────────────────
# TAB 3: BALANCE SHEET
# ─────────────────────────────────────────
with tab_bs:
    balance_sheet_module.render_balance_sheet_tab()

# ─────────────────────────────────────────
# TAB 4: CASH FLOW
# ─────────────────────────────────────────
with tab_cf:
    cash_flow_module.render_cash_flow_tab()

# ─────────────────────────────────────────
# TAB 5: COMPARISON
# ─────────────────────────────────────────
with tab_comp:
    comparison_module.render_comparison_tab()

# ─────────────────────────────────────────
# TAB 6: STRATEGY
# ─────────────────────────────────────────
with tab_sim:
    st.markdown("### Strategic Analysis")

    db = utils.load_db()
    opts = sorted(db.keys(), reverse=True)

    if not opts:
        st.info("No data available. Upload and save data first.")
    else:
        col_period, col_compare = st.columns([2, 2])
        current_period = col_period.selectbox("Analysis period:", opts, key="strat_period")
        compare_options = ["None"] + [o for o in opts if o != current_period]
        compare_period = col_compare.selectbox("Compare with:", compare_options, key="strat_compare")

        df_current = utils.clean_dataset_logic(db[current_period])
        m = utils.calc_pl_metrics(df_current)
        bs = utils.calc_bs_metrics(df_current, m['net_profit'])

        df_previous = None
        m_prev = None
        if compare_period != "None":
            df_previous = utils.clean_dataset_logic(db[compare_period])
            m_prev = utils.calc_pl_metrics(df_previous)

        # Key Metrics
        st.markdown("---")
        st.markdown("##### Key Financial Metrics")

        k1, k2, k3, k4, k5 = st.columns(5)

        def show_delta(col, label, val, prev_val):
            if prev_val is not None and prev_val != 0:
                delta_pct = (val - prev_val) / abs(prev_val) * 100
                col.metric(label, utils.fmt_fin(val), f"{delta_pct:+.1f}%")
            else:
                col.metric(label, utils.fmt_fin(val))

        show_delta(k1, "Revenue", m['revenue'], m_prev['revenue'] if m_prev else None)
        show_delta(k2, "Gross Profit", m['gross_profit'], m_prev['gross_profit'] if m_prev else None)
        show_delta(k3, "EBITDA", m['ebitda'], m_prev['ebitda'] if m_prev else None)
        k4.metric("EBIT", utils.fmt_fin(m['ebit']))
        show_delta(k5, "Net Profit", m['net_profit'], m_prev['net_profit'] if m_prev else None)

        # Profitability Ratios
        st.markdown("---")
        st.markdown("##### Profitability Ratios")

        rev = m['revenue']
        gross_margin = (m['gross_profit'] / rev * 100) if rev else 0
        ebitda_margin = (m['ebitda'] / rev * 100) if rev else 0
        ebit_margin = (m['ebit'] / rev * 100) if rev else 0
        net_margin = (m['net_profit'] / rev * 100) if rev else 0

        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Gross Margin", f"{gross_margin:.1f}%")
        r2.metric("EBITDA Margin", f"{ebitda_margin:.1f}%")
        r3.metric("EBIT Margin", f"{ebit_margin:.1f}%")
        r4.metric("Net Margin", f"{net_margin:.1f}%")

        # Cost Structure
        st.markdown("---")
        st.markdown("##### Cost Structure")

        col_c1, col_c2 = st.columns(2)

        with col_c1:
            cost_data = {
                'COGS': (m['cogs'] / rev * 100) if rev else 0,
                'OpEx': (m['opex'] / rev * 100) if rev else 0,
                'Depreciation': (m['depr'] / rev * 100) if rev else 0,
                'Interest': (m['interest'] / rev * 100) if rev else 0,
                'Tax': (m['tax'] / rev * 100) if rev else 0,
                'Net Profit': (m['net_profit'] / rev * 100) if rev else 0,
            }
            fig_pie = go.Figure(data=[go.Pie(
                labels=list(cost_data.keys()),
                values=list(cost_data.values()),
                hole=0.35,
                marker_colors=['#DC2626', '#D97706', '#2563EB', '#7C3AED', '#0891B2', '#059669']
            )])
            fig_pie.update_layout(height=300, margin=dict(t=10, b=0, l=0, r=0))
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_c2:
            fig_wf = go.Figure(go.Waterfall(
                orientation="v",
                measure=["relative", "relative", "relative", "relative", "relative", "total"],
                x=["Revenue", "COGS", "OpEx", "Depr", "Interest+Tax", "Net Profit"],
                y=[rev, -m['cogs'], -m['opex'], -m['depr'], -(m['interest'] + m['tax'] - m['other']), 0],
                connector={"line": {"color": "rgba(0,0,0,0.08)"}},
                decreasing={"marker": {"color": "#DC2626"}},
                increasing={"marker": {"color": "#059669"}},
                totals={"marker": {"color": "#2563EB"}},
            ))
            fig_wf.update_layout(height=300, margin=dict(t=10, b=0, l=0, r=0))
            st.plotly_chart(fig_wf, use_container_width=True)

        # Balance Sheet & Ratios
        st.markdown("---")
        st.markdown("##### Balance Sheet & Ratios")

        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Total Assets", utils.fmt_fin(bs['total_assets']))
        b2.metric("Total Liabilities", utils.fmt_fin(bs['total_liab']))
        b3.metric("Total Equity", utils.fmt_fin(bs['total_equity']))
        b4.metric("Balance Check", utils.fmt_fin(bs['total_assets'] - bs['total_liab'] - bs['total_equity']))

        tab_liq, tab_lev, tab_eff, tab_ret = st.tabs([
            "Liquidity", "Leverage", "Efficiency", "Returns"
        ])

        with tab_liq:
            l1, l2 = st.columns(2)
            current_ratio = (bs['c_assets'] / bs['c_liab']) if bs['c_liab'] else 0
            l1.metric("Current Ratio", f"{current_ratio:.2f}",
                      help="Current Assets / Current Liabilities. Target: 1.5-2.0")
            working_capital = bs['c_assets'] - bs['c_liab']
            l2.metric("Working Capital", utils.fmt_fin(working_capital))

            if current_ratio < 1:
                st.error("Current Ratio < 1: High liquidity risk")
            elif current_ratio < 1.5:
                st.warning("Current Ratio 1-1.5: Adequate but needs monitoring")
            else:
                st.success("Current Ratio > 1.5: Good liquidity")

        with tab_lev:
            le1, le2, le3 = st.columns(3)
            d2e = (bs['total_liab'] / bs['total_equity']) if bs['total_equity'] else 0
            d2a = (bs['total_liab'] / bs['total_assets']) if bs['total_assets'] else 0
            eq_mult = (bs['total_assets'] / bs['total_equity']) if bs['total_equity'] else 0
            le1.metric("Debt/Equity", f"{d2e:.2f}")
            le2.metric("Debt/Assets", f"{d2a:.2%}")
            le3.metric("Equity Multiplier", f"{eq_mult:.2f}")

            if m['interest'] > 0:
                ic = m['ebit'] / m['interest']
                st.metric("Interest Coverage", f"{ic:.2f}")
                if ic < 1.5:
                    st.error("Interest Coverage < 1.5: Difficulty covering interest")
                elif ic < 3:
                    st.warning("Interest Coverage 1.5-3: Manageable")
                else:
                    st.success("Interest Coverage > 3: Comfortable")

        with tab_eff:
            ef1, ef2, ef3 = st.columns(3)
            at = (rev / bs['total_assets']) if bs['total_assets'] else 0
            et = (rev / bs['total_equity']) if bs['total_equity'] else 0
            opex_ratio = (m['opex'] / rev * 100) if rev else 0
            ef1.metric("Asset Turnover", f"{at:.2f}")
            ef2.metric("Equity Turnover", f"{et:.2f}")
            ef3.metric("OpEx/Revenue", f"{opex_ratio:.1f}%")

        with tab_ret:
            rt1, rt2, rt3 = st.columns(3)
            roa = (m['net_profit'] / bs['total_assets'] * 100) if bs['total_assets'] else 0
            roe = (m['net_profit'] / bs['total_equity'] * 100) if bs['total_equity'] else 0
            ic_val = bs['total_equity'] + bs['nc_liab']
            roic = (m['ebit'] / ic_val * 100) if ic_val else 0
            rt1.metric("ROA", f"{roa:.2f}%")
            rt2.metric("ROE", f"{roe:.2f}%")
            rt3.metric("ROIC", f"{roic:.2f}%")

            # DuPont
            st.markdown("##### DuPont Analysis (ROE Decomposition)")
            pm = (m['net_profit'] / rev) if rev else 0
            at_dup = (rev / bs['total_assets']) if bs['total_assets'] else 0
            em_dup = (bs['total_assets'] / bs['total_equity']) if bs['total_equity'] else 0
            roe_calc = pm * at_dup * em_dup * 100
            st.markdown(f"""
**ROE = Profit Margin x Asset Turnover x Equity Multiplier**
- Profit Margin: {pm*100:.2f}%
- Asset Turnover: {at_dup:.2f}
- Equity Multiplier: {em_dup:.2f}
- **ROE: {roe_calc:.2f}%**
""")

        # Scenario Analysis
        st.markdown("---")
        st.markdown("##### Scenario Analysis")

        sim1, sim2 = st.columns([1, 2])

        with sim1:
            rev_chg = st.slider("Revenue change %", -50, 100, 0, 5)
            cogs_chg = st.slider("COGS change %", -50, 100, 0, 5)
            opex_chg = st.slider("OpEx change %", -50, 100, 0, 5)

        with sim2:
            s_rev = m['revenue'] * (1 + rev_chg / 100)
            s_cogs = m['cogs'] * (1 + cogs_chg / 100)
            s_opex = m['opex'] * (1 + opex_chg / 100)
            s_gross = s_rev - s_cogs
            s_ebitda = s_gross - s_opex
            s_net = s_ebitda - m['depr'] - m['interest'] + m['other'] - m['tax']

            sim_data = pd.DataFrame({
                'Metric': ['Revenue', 'Gross Profit', 'EBITDA', 'Net Profit'],
                'Actual': [utils.fmt_fin(m['revenue']), utils.fmt_fin(m['gross_profit']),
                          utils.fmt_fin(m['ebitda']), utils.fmt_fin(m['net_profit'])],
                'Simulated': [utils.fmt_fin(s_rev), utils.fmt_fin(s_gross),
                             utils.fmt_fin(s_ebitda), utils.fmt_fin(s_net)],
                'Change': [utils.fmt_fin(s_rev - m['revenue']),
                          utils.fmt_fin(s_gross - m['gross_profit']),
                          utils.fmt_fin(s_ebitda - m['ebitda']),
                          utils.fmt_fin(s_net - m['net_profit'])],
            })
            st.dataframe(sim_data, use_container_width=True, hide_index=True)

            fig_sim = go.Figure()
            fig_sim.add_trace(go.Bar(
                name='Actual', x=['Revenue', 'Gross', 'EBITDA', 'Net'],
                y=[m['revenue'], m['gross_profit'], m['ebitda'], m['net_profit']],
                marker_color='#2563EB'))
            fig_sim.add_trace(go.Bar(
                name='Simulated', x=['Revenue', 'Gross', 'EBITDA', 'Net'],
                y=[s_rev, s_gross, s_ebitda, s_net],
                marker_color='#059669'))
            fig_sim.update_layout(barmode='group', height=280, margin=dict(t=10, b=0, l=0, r=0))
            st.plotly_chart(fig_sim, use_container_width=True)

        # Break-Even
        st.markdown("---")
        st.markdown("##### Break-Even Analysis")

        be1, be2 = st.columns(2)

        with be1:
            fixed_costs = m['opex'] + m['depr']
            var_ratio = (m['cogs'] / rev) if rev else 0
            cm_ratio = 1 - var_ratio

            st.write(f"- Variable cost ratio: {var_ratio*100:.1f}%")
            st.write(f"- Fixed costs: {utils.fmt_fin(fixed_costs)}")
            st.write(f"- Contribution margin: {cm_ratio*100:.1f}%")

            if cm_ratio > 0:
                be_rev = fixed_costs / cm_ratio
                st.markdown(f"**Break-Even Revenue: {utils.fmt_fin(be_rev)}**")
                be_mult = (rev / be_rev) if be_rev else 0
                safety = ((rev - be_rev) / rev * 100) if rev else 0
                st.write(f"- Current = {be_mult:.1f}x break-even")
                st.write(f"- Safety margin: {safety:.1f}%")

        with be2:
            if cm_ratio > 0:
                rev_range = [i * rev / 10 for i in range(0, 21)]
                cost_line = [fixed_costs + (r * var_ratio) for r in rev_range]

                fig_be = go.Figure()
                fig_be.add_trace(go.Scatter(x=rev_range, y=rev_range, name='Revenue',
                                           line=dict(color='#059669', width=2)))
                fig_be.add_trace(go.Scatter(x=rev_range, y=cost_line, name='Total Cost',
                                           line=dict(color='#DC2626', width=2)))
                fig_be.add_vline(x=be_rev, line_dash="dash", line_color="#94A3B8",
                                annotation_text="Break-Even")
                fig_be.update_layout(height=280, margin=dict(t=10, b=0, l=0, r=0),
                                    xaxis_title="Revenue", yaxis_title="Amount",
                                    hovermode='x unified')
                st.plotly_chart(fig_be, use_container_width=True)

        # AI Insights
        st.markdown("---")
        st.markdown("##### Insights")

        insights = []
        if gross_margin < 30:
            insights.append("Low Gross Margin (<30%): Consider pricing or COGS reduction")
        elif gross_margin > 60:
            insights.append("Strong Gross Margin (>60%): Maintain current strategy")
        if net_margin < 5:
            insights.append("Low Net Margin (<5%): Optimize costs")
        if current_ratio < 1:
            insights.append("Liquidity risk: Current Assets < Current Liabilities")
        if d2e > 2:
            insights.append("High Debt/Equity (>2): Consider refinancing or capital raise")
        if opex_ratio > 40:
            insights.append("High OpEx (>40% of Revenue): Look for automation opportunities")
        if m_prev:
            rev_growth = ((m['revenue'] - m_prev['revenue']) / m_prev['revenue'] * 100) if m_prev['revenue'] else 0
            if rev_growth > 20:
                insights.append(f"Excellent growth (+{rev_growth:.1f}%)")
            elif rev_growth < -10:
                insights.append(f"Revenue decline ({rev_growth:.1f}%): Review strategy")

        if insights:
            for ins in insights:
                st.markdown(f"- {ins}")
        else:
            st.success("All key metrics are within normal range.")

# ─────────────────────────────────────────
# TAB 7: ADMIN (admin only)
# ─────────────────────────────────────────
if st.session_state.get('user_role') == 'admin':
    with tab_admin:
        auth.render_admin_panel()
