import pandas as pd
import json
import os

# --- კონფიგურაცია ---
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

# --- სტილები ---
STYLES = """
<style>
    .pl-table {width: 100%; border-collapse: collapse; font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px;}
    .pl-table th {background-color: #EBF5FB; padding: 10px; text-align: right; border-bottom: 2px solid #AED6F1; color: #154360;}
    .pl-table th.text-left {text-align: left;}
    .pl-table td {padding: 7px 10px; border-bottom: 1px solid #f0f0f0;}
    
    .amt {text-align: right; font-family: 'Consolas', monospace; font-weight: 600;}
    .neg {color: #C0392B;} 
    .pos {color: #000;}
    .var-pos {color: #27AE60; font-weight: bold;} 
    .var-neg {color: #C0392B; font-weight: bold;}
    
    .header-row {background-color: #F4F6F7; font-weight: bold; color: #2C3E50; text-transform: uppercase; border-top: 1px solid #ccc;}
    .total-row {background-color: #EAEDED; font-weight: bold; border-top: 1px solid #999; color: #2C3E50;}
    .grand-row {background-color: #2C3E50; color: white !important; font-weight: bold; font-size: 15px;}
    .grand-row .amt {color: white !important;}
    
    .code-col {color: #888; font-size: 11px; width: 60px; font-weight: bold;}
    .sub-indent {padding-left: 15px;}
    
    .kpi-card {background-color: #ffffff; padding: 15px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: center;}
    .sim-card {padding: 20px; background-color: #f8f9fa; border-radius: 10px; border-left: 5px solid #F39C12; margin-bottom: 20px;}
</style>
"""

# --- ბაზის ფუნქციები ---
def load_db():
    if not os.path.exists(HISTORY_FILE): return {}
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # იძულებითი სტრინგად კონვერტაცია ჩატვირთვისას
            for key in data:
                for row in data[key]:
                    row['Code'] = str(row['Code']).strip()
            return data
    except: return {}

def save_to_db(date_key, data):
    # იძულებითი სტრინგად კონვერტაცია შენახვისას
    for row in data:
        row['Code'] = str(row['Code']).strip()
    db = load_db()
    db[date_key] = data
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=4, ensure_ascii=False)

def delete_from_db(date_key):
    db = load_db()
    if date_key in db:
        del db[date_key]
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=4, ensure_ascii=False)
        return True
    return False

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

def delete_snapshot(report_name):
    snaps = load_snapshots()
    if report_name in snaps:
        del snaps[report_name]
        with open(SNAPSHOTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(snaps, f, indent=4, ensure_ascii=False)
        return True
    return False

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

def delete_mapping_variant(name):
    variants = load_mapping_variants()
    if name in variants:
        del variants[name]
        with open(VARIANTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(variants, f, indent=4, ensure_ascii=False)
        return True
    return False

# --- ფორმატირება ---
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

# ═══════════════════════════════════════════════════════════════
# HIERARCHY LOGIC  —  parent detection + grouping
# ═══════════════════════════════════════════════════════════════
#
# ქართულ ბუღ. სისტემაში კოდების ორი სახის hierarchy:
#
#  TYPE A — SPACE PREFIX:
#    "1210" -> "1210 6"  (space separator = sub-analytic)
#    "3131" -> "3131 0513"
#    წესი: B.startswith(A + ' ')
#
#  TYPE B — NUMERIC PREFIX:
#    "11" -> "1110"  (B[:len(A)] == A)
#    "1610" -> "1610 00002"
#    წესი: ' ' not in A AND len(A) < len(B) AND B[:len(A)] == A
#
#  TYPE C — NET DUPLICATE (same net, different code):
#    6000 Net == 6100 Net  →  6000 higher-level summary, must be removed
#    6100 Net == 6112+6113+6114  →  6100 summary, must be removed
#    წესი: detected via net equality + net-sum matching
#
# CLEAN rule:  remove TYPE A+B+C parents from summation
# GROUP rule:  each leaf displays under its nearest parent (any type)
# ═══════════════════════════════════════════════════════════════

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
      C1 — same absolute net, numerically smaller code = higher summary
      C2 — code net = sum of same first-digit family members
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
    შლის მშობელ კოდებს — რჩება მხოლოდ leaf (ფოთოლი) კოდები.
    გამოიყენება P&L, BS, CF კალკულაციებისთვის — თანხა არ გაორმაგდება.
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
    {leaf_code: (parent_code, parent_name)} — balance_sheet_module-ისთვის.

    თითოეული leaf კოდისთვის პოულობს ყველაზე ახლო (longest) მშობელს:
    1. prefix-parent (TYPE A/B) — პრიორიტეტი
    2. net-dupe parent (TYPE C) — fallback (6112 -> 6100 'საოპერაციო შემოსავლები')
    parent_name = DB-ში ჩაწერილი Name სვეტი
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