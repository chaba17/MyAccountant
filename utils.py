import streamlit as st
import pandas as pd
import json
import os

# --- Configuration ---
HISTORY_FILE = 'financial_history_db.json'
SNAPSHOTS_FILE = 'pl_reports_archive.json'
VARIANTS_FILE = 'mapping_variants.json'

MAPPING_OPTIONS = [
    "Revenue (შემოსავალი)", "COGS (თვითღირებულება)", "Operating Expenses (საოპერაციო ხარჯები)",
    "Depreciation (ცვეთა/ამორტიზაცია)", "Interest (საპროცენტო ხარჯი)", "Tax (მოგების გადასახადი)",
    "Other Income/Expense (სხვა არასაოპერაციო)",
    "BS: Non-Current Assets (გრძელვადიანი აქტივები)",
    "BS: Current Assets (მიმდინარე აქტივები)",
    "BS: Equity (კაპიტალი)",
    "BS: Non-Current Liabilities (გრძელვადიანი ვალდ.)",
    "BS: Current Liabilities (მიმდინარე ვალდ.)",
    "IGNORE (იგნორირება)"
]

# --- Modern Design System ---
STYLES = """
<style>
:root {
    --primary: #2563EB;
    --primary-light: #EFF6FF;
    --success: #059669;
    --success-light: #ECFDF5;
    --danger: #DC2626;
    --danger-light: #FEF2F2;
    --warning: #D97706;
    --warning-light: #FFFBEB;
    --text-primary: #0F172A;
    --text-secondary: #475569;
    --text-muted: #94A3B8;
    --border: #E2E8F0;
    --bg-subtle: #F8FAFC;
    --surface: #FFFFFF;
}

/* Global typography */
.stApp { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }

/* Financial tables */
.fin-table { width:100%; border-collapse:collapse; font-size:0.9rem; }
.fin-table th { padding:10px 12px; text-align:left; font-size:0.75rem; font-weight:600;
    text-transform:uppercase; letter-spacing:0.05em; color:var(--text-muted);
    border-bottom:2px solid var(--border); background:var(--bg-subtle); }
.fin-table th.text-right { text-align:right; }
.fin-table td { padding:8px 12px; border-bottom:1px solid #F1F5F9; }
.fin-table .amt { text-align:right; font-family:'JetBrains Mono','Fira Code',monospace;
    font-size:0.875rem; font-weight:500; }
.fin-table .neg { color:var(--danger); }
.fin-table .pos { color:var(--text-primary); }
.fin-table .var-pos { color:var(--success); font-weight:600; }
.fin-table .var-neg { color:var(--danger); font-weight:600; }

/* Row types */
.fin-table .section-row td { background:var(--primary); color:white; font-weight:600;
    padding:10px 12px; font-size:0.85rem; text-transform:uppercase; letter-spacing:0.03em; }
.fin-table .subtotal-row td { background:var(--bg-subtle); font-weight:600;
    border-top:1px solid var(--border); color:var(--text-primary); }
.fin-table .calc-row td { background:var(--primary-light); font-weight:700;
    border-top:2px solid var(--primary); color:var(--primary); }
.fin-table .grand-row td { background:var(--text-primary); color:white; font-weight:700;
    padding:12px; font-size:1rem; }
.fin-table .grand-row .amt { color:white; }

/* Code column */
.fin-table .code-col { color:var(--text-muted); font-size:0.8rem; width:70px;
    font-family:monospace; font-weight:500; }
.fin-table .indent { padding-left:20px; }

/* Expandable groups */
.fin-table details>summary { list-style:none; cursor:pointer; }
.fin-table details>summary::-webkit-details-marker { display:none; }
.fin-table details summary::after { content:" ▸"; font-size:0.7em; color:var(--text-muted); }
.fin-table details[open] summary::after { content:" ▾"; }

/* Cards */
.metric-card { background:var(--surface); padding:16px; border-radius:10px;
    border:1px solid var(--border); }
.metric-card .label { font-size:0.75rem; color:var(--text-muted); font-weight:500;
    text-transform:uppercase; letter-spacing:0.05em; }
.metric-card .value { font-size:1.5rem; font-weight:700; color:var(--text-primary);
    font-family:'JetBrains Mono',monospace; margin-top:4px; }

/* Badge */
.badge { display:inline-block; padding:3px 10px; border-radius:99px; font-size:0.75rem; font-weight:600; }
.badge-green { background:var(--success-light); color:var(--success); }
.badge-red { background:var(--danger-light); color:var(--danger); }
.badge-blue { background:var(--primary-light); color:var(--primary); }
.badge-yellow { background:var(--warning-light); color:var(--warning); }

/* Progress bars */
.progress-track { background:#F1F5F9; border-radius:99px; height:6px; }
.progress-fill { border-radius:99px; height:6px; transition:width 0.3s; }

/* Clean expander styling */
.fin-table .child-table { width:100%; margin:4px 0; background:#FAFBFC; }
.fin-table .child-table td { padding:4px 12px; border-bottom:1px dashed #F1F5F9;
    font-size:0.85rem; color:var(--text-secondary); }

/* Hide Streamlit footer only */
footer {visibility: hidden;}
</style>
"""

# --- Cached DB operations ---
@st.cache_data(ttl=2)
def load_db():
    if not os.path.exists(HISTORY_FILE): return {}
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for key in data:
                for row in data[key]:
                    row['Code'] = str(row['Code']).strip()
            return data
    except: return {}

def save_to_db(date_key, data):
    for row in data:
        row['Code'] = str(row['Code']).strip()
    db = load_db()
    db[date_key] = data
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=4, ensure_ascii=False)
    load_db.clear()

def delete_from_db(date_key):
    db = load_db()
    if date_key in db:
        del db[date_key]
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=4, ensure_ascii=False)
        load_db.clear()
        return True
    return False

@st.cache_data(ttl=2)
def load_snapshots():
    if not os.path.exists(SNAPSHOTS_FILE): return {}
    try:
        with open(SNAPSHOTS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {}

def save_snapshot(report_name, data):
    snaps = load_snapshots()
    snaps[report_name] = data
    with open(SNAPSHOTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(snaps, f, indent=4, ensure_ascii=False)
    load_snapshots.clear()

def delete_snapshot(report_name):
    snaps = load_snapshots()
    if report_name in snaps:
        del snaps[report_name]
        with open(SNAPSHOTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(snaps, f, indent=4, ensure_ascii=False)
        load_snapshots.clear()
        return True
    return False

@st.cache_data(ttl=2)
def load_mapping_variants():
    if not os.path.exists(VARIANTS_FILE): return {}
    try:
        with open(VARIANTS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {}

def save_mapping_variant(name, mapping_dict):
    variants = load_mapping_variants()
    str_mapping = {str(k).strip(): v for k, v in mapping_dict.items()}
    variants[name] = str_mapping
    with open(VARIANTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(variants, f, indent=4, ensure_ascii=False)
    load_mapping_variants.clear()

def delete_mapping_variant(name):
    variants = load_mapping_variants()
    if name in variants:
        del variants[name]
        with open(VARIANTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(variants, f, indent=4, ensure_ascii=False)
        load_mapping_variants.clear()
        return True
    return False

# --- Formatting ---
def fmt_fin(val):
    if val is None: return ""
    s = "{:,.2f}".format(abs(val))
    if val < 0: return f"({s})"
    return s

def fmt_var(val, is_expense=False):
    if abs(val) < 1: return "-"
    is_good = val > 0 if not is_expense else val < 0
    arrow = "↑" if val > 0 else "↓"
    cls = "var-pos" if is_good else "var-neg"
    return f'<span class="{cls}">{arrow} {fmt_fin(val)}</span>'

# --- Shared P&L Metrics Calculator ---
def calc_pl_metrics(df_clean):
    """Calculate all P&L metrics from a cleaned DataFrame. Returns dict."""
    def c(cat): return df_clean[df_clean['Category']==cat]['Net'].sum()
    rev = c("Revenue (შემოსავალი)") * -1
    other_net = c("Other Income/Expense (სხვა არასაოპერაციო)") * -1
    cogs = c("COGS (თვითღირებულება)")
    opex = c("Operating Expenses (საოპერაციო ხარჯები)")
    depr = c("Depreciation (ცვეთა/ამორტიზაცია)")
    inte = c("Interest (საპროცენტო ხარჯი)")
    tax = c("Tax (მოგების გადასახადი)")
    gross = rev - cogs
    ebitda = gross - opex
    ebit = ebitda - depr
    ebt = ebit - inte + other_net
    net = ebt - tax
    return dict(revenue=rev, cogs=cogs, opex=opex, depr=depr, interest=inte,
                tax=tax, other=other_net, gross_profit=gross, ebitda=ebitda,
                ebit=ebit, ebt=ebt, net_profit=net)

# --- Shared BS Metrics Calculator ---
def calc_bs_metrics(df_clean, net_profit=0):
    """Calculate all Balance Sheet metrics from a cleaned DataFrame. Returns dict."""
    def c(cat): return df_clean[df_clean['Category']==cat]['Net'].sum()
    nc_assets = c("BS: Non-Current Assets (გრძელვადიანი აქტივები)")
    c_assets = c("BS: Current Assets (მიმდინარე აქტივები)")
    total_assets = nc_assets + c_assets
    nc_liab = c("BS: Non-Current Liabilities (გრძელვადიანი ვალდ.)") * -1
    c_liab = c("BS: Current Liabilities (მიმდინარე ვალდ.)") * -1
    total_liab = nc_liab + c_liab
    equity_base = c("BS: Equity (კაპიტალი)") * -1
    total_equity = equity_base + net_profit
    return dict(nc_assets=nc_assets, c_assets=c_assets, total_assets=total_assets,
                nc_liab=nc_liab, c_liab=c_liab, total_liab=total_liab,
                equity_base=equity_base, total_equity=total_equity)

# ===================================================================
# HIERARCHY LOGIC  --  parent detection + grouping
# ===================================================================
#
# Georgian accounting system code hierarchy types:
#
#  TYPE A -- SPACE PREFIX:
#    "1210" -> "1210 6"  (space separator = sub-analytic)
#    "3131" -> "3131 0513"
#    Rule: B.startswith(A + ' ')
#
#  TYPE B -- NUMERIC PREFIX:
#    "11" -> "1110"  (B[:len(A)] == A)
#    "1610" -> "1610 00002"
#    Rule: ' ' not in A AND len(A) < len(B) AND B[:len(A)] == A
#
#  TYPE C -- NET DUPLICATE (same net, different code):
#    6000 Net == 6100 Net  ->  6000 higher-level summary, must be removed
#    6100 Net == 6112+6113+6114  ->  6100 summary, must be removed
#    Rule: detected via net equality + net-sum matching
#
# CLEAN rule:  remove TYPE A+B+C parents from summation
# GROUP rule:  each leaf displays under its nearest parent (any type)
# ===================================================================

def _is_prefix_parent(a: str, b: str) -> bool:
    """True if a is a TYPE A or TYPE B parent of b."""
    if a == b:
        return False
    if b.startswith(a + ' '):          # TYPE A: space separator
        return True
    if ' ' not in a and len(a) < len(b) and b[:len(a)] == a:  # TYPE B: numeric
        return True
    return False


def _build_prefix_parents(all_codes):
    """Set of all codes that have at least one prefix-child."""
    parents = set()
    for a in all_codes:
        for b in all_codes:
            if _is_prefix_parent(a, b):
                parents.add(a)
                break
    return parents


def _build_net_dupes(all_codes, nets, prefix_parents):
    """
    TYPE C: net-duplicate codes that are NOT prefix-parents.
    Two sub-rules:
      C1 -- same absolute net, numerically smaller code = higher summary
      C2 -- code net = sum of same first-digit family members
    """
    from collections import defaultdict
    dupes = set()
    tol = 0.05

    # C1: exact same net -> smaller numeric = dupe
    net_groups = defaultdict(list)
    for c in all_codes:
        n = nets.get(c, 0.0)
        if abs(n) < 0.01:
            continue
        net_groups[round(abs(n), 4)].append(c)

    for key, group in net_groups.items():
        if len(group) < 2:
            continue
        def _sk(c):
            seg = c.split(' ')[0]
            try:
                return (len(seg), int(seg))
            except ValueError:
                return (len(seg), 0)
        grp = sorted(group, key=_sk)
        # all but the deepest/largest are higher-level summaries -> dupes
        for c in grp[:-1]:
            dupes.add(c)

    # C2: net = sum of same-first-digit family
    # try prefix lengths 1, 2, 3 so we catch both 6000=sum(6xxx) and 6100=sum(611x)
    for pfx_len in [1, 2, 3]:
        fam = defaultdict(list)
        for c in all_codes:
            if c not in prefix_parents and c not in dupes and ' ' not in c:
                fam[c[:pfx_len]].append(c)
        for f, members in fam.items():
            if len(members) < 2:
                continue
            for x in members:
                if x in dupes:
                    continue
                nx = nets.get(x, 0.0)
                if abs(nx) < 0.01:
                    continue
                others = [c for c in members if c != x and c not in dupes]
                if not others:
                    continue
                # only flag if others cover a meaningful portion of x's net
                if sum(abs(nets.get(c, 0.0)) for c in others) < abs(nx) * 0.5:
                    continue
                if abs(sum(nets.get(c, 0.0) for c in others) - nx) < tol:
                    dupes.add(x)

    return dupes


def clean_dataset_logic(data_list):
    """
    Removes parent codes -- only leaf codes remain.
    Used for P&L, BS, CF calculations so amounts are not double-counted.
    """
    if not data_list:
        return pd.DataFrame()

    df = pd.DataFrame(data_list)
    df["Code"] = df["Code"].astype(str).str.strip()

    if "Net" not in df.columns:
        df["Net"] = (pd.to_numeric(df.get("Debit", 0), errors="coerce").fillna(0)
                     - pd.to_numeric(df.get("Credit", 0), errors="coerce").fillna(0))

    all_codes = list(df["Code"].unique())
    nets = df.groupby("Code")["Net"].sum().to_dict()

    prefix_parents = _build_prefix_parents(all_codes)
    net_dupes = _build_net_dupes(all_codes, nets, prefix_parents)
    remove = prefix_parents | net_dupes

    return pd.DataFrame([r for _, r in df.iterrows() if r["Code"] not in remove])


def get_parent_map(data_list):
    """
    {leaf_code: (parent_code, parent_name)} -- for balance_sheet_module.

    For each leaf code, finds the nearest (longest) parent:
    1. prefix-parent (TYPE A/B) -- priority
    2. net-dupe parent (TYPE C) -- fallback (6112 -> 6100)
    parent_name = Name column recorded in DB
    """
    if not data_list:
        return {}

    df = pd.DataFrame(data_list)
    df["Code"] = df["Code"].astype(str).str.strip()
    code_name = (df.drop_duplicates("Code").set_index("Code")["Name"].to_dict()
                 if "Name" in df.columns else {})

    all_codes = list(df["Code"].unique())

    if "Net" not in df.columns:
        df["Net"] = (pd.to_numeric(df.get("Debit", 0), errors="coerce").fillna(0)
                     - pd.to_numeric(df.get("Credit", 0), errors="coerce").fillna(0))
    nets = df.groupby("Code")["Net"].sum().to_dict()

    prefix_parents = _build_prefix_parents(all_codes)
    net_dupes = _build_net_dupes(all_codes, nets, prefix_parents)
    all_parent_codes = prefix_parents | net_dupes

    result = {}
    for leaf in all_codes:
        if leaf in all_parent_codes:
            continue  # parents don't need a parent entry

        # 1. nearest prefix-parent
        best = None
        for p in prefix_parents:
            if _is_prefix_parent(p, leaf):
                if best is None or len(p) > len(best):
                    best = p

        # 2. net-dupe parent: find net-dupe in same first-digit family
        #    whose net is >= leaf net (i.e. it's a higher-level summary)
        if best is None:
            net_leaf = abs(nets.get(leaf, 0.0))
            candidates = [
                p for p in net_dupes
                if ' ' not in p
                and len(p) >= 1 and len(leaf) >= 1
                and p[0] == leaf[0]
                and abs(nets.get(p, 0.0)) >= net_leaf - 0.05
            ]
            if candidates:
                # pick the one with largest numeric value = most specific
                def _sk2(c):
                    try:
                        return (len(c), int(c))
                    except ValueError:
                        return (len(c), 0)
                best = sorted(candidates, key=_sk2)[-1]

        if best:
            result[leaf] = (best, code_name.get(best, best))

    return result
