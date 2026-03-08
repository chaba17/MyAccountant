"""
balance_sheet_module.py — FinSuite Pro

ჯგუფება ლოგიკა (ყველა DB-ზე — ახალი და ძველი):
  1. DB-ის კოდებზე ვამოვლენთ მშობლებს (3 წესი, app.py-ის იდენტური)
  2. მშობლები = IGNORE display-ში (კატეგ. მიუხედავად)
  3. leaf კოდები ჯამდება; display-ში ჯგუფდება IGNORE მშობლის Name-ის ქვეშ
"""

import streamlit as st
import pandas as pd
from collections import defaultdict
import utils
import ai_advisor_module


# ── იგივე 3 წესი, რაც app.py smart_map-ში ──────────────────────────────────
def _detect_parents(df: pd.DataFrame) -> set:
    """
    3 წესი:
    1. Space: "3131 0513" → parent "3131"
    2. Same Net, pure numeric → smaller number = parent
    3. Net = sum of same-first-digit family → parent
    """
    nets = df.groupby("Code")["Net"].sum().to_dict()
    all_codes = list(df["Code"].unique())
    pure = [c for c in all_codes if " " not in c]
    parents = set()

    # Rule 1
    for c in all_codes:
        if " " in c:
            p = c.split(" ")[0]
            if p in set(all_codes):
                parents.add(p)

    # Rule 2
    for a in pure:
        na = nets.get(a, 0)
        if abs(na) < 0.01:
            continue
        for b in pure:
            if a == b:
                continue
            if abs(nets.get(b, 0) - na) < 0.05:
                try:
                    if int(a) < int(b):
                        parents.add(a)
                except ValueError:
                    pass

    # Rule 3 (after rule 2)
    remaining = [c for c in pure if c not in parents]
    fams = defaultdict(list)
    for c in remaining:
        fams[c[0]].append(c)
    for members in fams.values():
        if len(members) < 2:
            continue
        for x in members:
            nx = nets.get(x, 0)
            if abs(nx) < 0.01:
                continue
            others = [c for c in members if c != x]
            if abs(sum(nets.get(c, 0) for c in others) - nx) < 0.05:
                parents.add(x)

    return parents


def render_balance_sheet_tab():
    st.markdown("### ⚖️ ბალანსის უწყისი (IFRS)")

    db = utils.load_db()
    opts = sorted(db.keys(), reverse=True)
    if not opts:
        st.warning("ბაზა ცარიელია.")
        return

    c_sel, _ = st.columns([2, 2])
    sel_bs = c_sel.selectbox("პერიოდი:", opts)

    df_raw = pd.DataFrame(db[sel_bs])
    df_raw["Code"] = df_raw["Code"].astype(str).str.strip()
    if "Net" not in df_raw.columns:
        df_raw["Net"] = (pd.to_numeric(df_raw.get("Debit", 0), errors="coerce").fillna(0)
                         - pd.to_numeric(df_raw.get("Credit", 0), errors="coerce").fillna(0))

    # ── მშობელი კოდების გამოვლენა (ყველა DB-ზე მუშაობს) ──
    parents = _detect_parents(df_raw)

    # ── მშობელი → IGNORE; leaf → ინახება კატეგ. ──
    code_name = df_raw.drop_duplicates("Code").set_index("Code")["Name"].to_dict() \
                if "Name" in df_raw.columns else {}

    # df_calc: მხოლოდ leaf კოდები (მშობლების გარეშე)
    df_calc = df_raw[~df_raw["Code"].isin(parents)].copy()
    if df_calc.empty:
        st.warning("მონაცემები ცარიელია.")
        return

    # ── ჯგუფის სათაური: მშობლის Name სვეტი ──
    def find_group(code: str):
        """leaf კოდის ყველაზე ახლო მშობელი IGNORE-ებიდან → (parent_code, parent_name)"""
        own_name = code_name.get(code, code)

        # Rule 1: space — "3131 0513" → "3131"
        if " " in code:
            p = code.split(" ")[0]
            if p in parents:
                return p, code_name.get(p, p)
            return p, code_name.get(p, p)

        # Rule 2: nearest parent in same first-digit family
        # "nearest" = largest numeric value that is still < this code AND is in parents
        best = None
        for p in parents:
            if " " in p:
                continue
            if len(p) >= 1 and p[0] == code[0]:
                try:
                    if int(p) < int(code):
                        if best is None or int(p) > int(best):
                            best = p
                except ValueError:
                    pass

        if best:
            return best, code_name.get(best, best)

        return code, own_name

    # AI Advisor (df_calc-ზე — leaf კოდები)
    problematic_codes = ai_advisor_module.render_audit_ui(df_calc, "BS", source_key=sel_bs)

    # ── კალკულაციები ──
    def c(cat):
        return df_calc[df_calc["Category"] == cat]["Net"].sum()

    rev       = c("Revenue (შემოსავალი)") * -1
    other_pl  = c("Other Income/Expense (სხვა არასაოპერაციო)") * -1
    cogs      = c("COGS (თვითღირებულება)")
    opex      = c("Operating Expenses (საოპერაციო ხარჯები)")
    depr      = c("Depreciation (ცვეთა/ამორტიზაცია)")
    inte      = c("Interest (საპროცენტო ხარჯი)")
    tax       = c("Tax (მოგების გადასახადი)")
    net_profit_val = (rev + other_pl) - (cogs + opex + depr + inte + tax)

    nc_assets    = c("BS: Non-Current Assets (გრძელვადიანი აქტივები)")
    c_assets_val = c("BS: Current Assets (მიმდინარე აქტივები)")
    total_assets = nc_assets + c_assets_val

    nc_liab    = c("BS: Non-Current Liabilities (გრძელვადიანი ვალდ.)") * -1
    c_liab_val = c("BS: Current Liabilities (მიმდინარე ვალდ.)") * -1
    total_liab = nc_liab + c_liab_val

    equity_base       = c("BS: Equity (კაპიტალი)") * -1
    total_equity      = equity_base + net_profit_val
    total_liab_equity = total_liab + total_equity
    check             = total_assets - total_liab_equity

    k1, k2, k3 = st.columns(3)
    k1.metric("სულ აქტივები",        utils.fmt_fin(total_assets))
    k2.metric("სულ კაპიტ. + ვალდ.", utils.fmt_fin(total_liab_equity))
    k3.metric("საკონტროლო სხვაობა", utils.fmt_fin(check),
              delta_color="off" if abs(check) < 1 else "inverse")
    if abs(check) > 0.1:
        st.error(f"🔴 დისბალანსი: {utils.fmt_fin(check)}")

    show_codes = st.checkbox("კოდების ჩვენება", value=True, key="bs_code_check")
    cols = 3 if show_codes else 2

    def get_bs_rows(cat: str, multiplier: float = 1.0) -> str:
        subset = df_calc[df_calc["Category"] == cat].copy()
        if subset.empty:
            return ""
        subset["Val"] = subset["Net"] * multiplier
        subset["GCode"] = subset["Code"].apply(lambda c: find_group(c)[0])
        subset["GName"] = subset["Code"].apply(lambda c: find_group(c)[1])

        html = ""
        for g_code, grp in subset.groupby("GCode", sort=True):
            g_total = grp["Val"].sum()
            if abs(g_total) < 0.01:
                continue
            g_name = grp["GName"].iloc[0]

            child_html = ""
            for _, ch in grp.sort_values("Code").iterrows():
                if abs(ch["Val"]) < 0.01:
                    continue
                err_style = "background:#ffe6e6;" if str(ch["Code"]) in problematic_codes else ""
                code_td = (f'<td style="color:#666;font-size:.85em;width:90px;">{ch["Code"]}</td>'
                           if show_codes else "")
                child_html += (
                    f'<tr style="border-bottom:1px dashed #eee;{err_style}">'
                    f'{code_td}'
                    f'<td style="color:#555;font-size:.9em;padding-left:20px;">{ch["Name"]}</td>'
                    f'<td style="text-align:right;font-family:monospace;font-size:.9em;">'
                    f'{utils.fmt_fin(ch["Val"])}</td></tr>'
                )

            if child_html:
                inner = f'<table style="width:100%;background:#fcfcfc;margin:4px 0;">{child_html}</table>'
                name_cell = (
                    f'<details style="cursor:pointer;">'
                    f'<summary style="outline:none;list-style:none;">'
                    f'<b>{g_name}</b>'
                    f'<span style="font-size:.7em;color:#999;margin-left:6px;">▼</span>'
                    f'</summary>{inner}</details>'
                )
            else:
                name_cell = f"<b>{g_name}</b>"

            code_td_p = f'<td class="code-col"><b>{g_code}</b></td>' if show_codes else ""
            html += (
                f'<tr style="background:#fafafa;border-bottom:1px solid #eee;">'
                f'{code_td_p}'
                f'<td class="sub-indent">{name_cell}</td>'
                f'<td class="amt" style="vertical-align:top;padding-top:8px;">'
                f'<b>{utils.fmt_fin(g_total)}</b></td></tr>'
            )
        return html

    bs_html = f"""
<style>
.pl-table{{width:100%;border-collapse:collapse;font-family:sans-serif;font-size:.95rem;}}
.pl-table th{{border-bottom:2px solid #ddd;text-align:left;padding:8px;background:#f8f9fa;}}
.pl-table td{{padding:6px 8px;vertical-align:top;}}
.header-row td{{background:#4A90E2;color:white;font-weight:bold;padding:10px;text-transform:uppercase;}}
.total-row td{{background:#EBF5FB;font-weight:bold;border-top:1px solid #aaa;color:#333;}}
.grand-row td{{background:#2E86C1;color:white;font-weight:bold;padding:10px;font-size:1.1em;}}
.amt{{text-align:right;font-family:monospace;white-space:nowrap;}}
.code-col{{width:90px;font-family:monospace;color:#333;vertical-align:top;padding-top:8px;}}
.sub-indent{{padding-left:10px;}}
details>summary{{list-style:none;}}
details>summary::-webkit-details-marker{{display:none;}}
</style>
<table class="pl-table">
<thead><tr>{'<th>კოდი</th>' if show_codes else ''}<th>დასახელება</th><th>თანხა (GEL)</th></tr></thead>
<tbody>
<tr class="header-row"><td colspan="{cols}">აქტივები (ASSETS)</td></tr>
<tr class="total-row"><td colspan="{cols}">გრძელვადიანი აქტივები</td></tr>
{get_bs_rows("BS: Non-Current Assets (გრძელვადიანი აქტივები)", 1)}
<tr class="total-row"><td colspan="{cols-1}">სულ გრძელვადიანი აქტივები</td>
  <td class="amt"><b>{utils.fmt_fin(nc_assets)}</b></td></tr>
<tr class="total-row"><td colspan="{cols}">მიმდინარე აქტივები</td></tr>
{get_bs_rows("BS: Current Assets (მიმდინარე აქტივები)", 1)}
<tr class="total-row"><td colspan="{cols-1}">სულ მიმდინარე აქტივები</td>
  <td class="amt"><b>{utils.fmt_fin(c_assets_val)}</b></td></tr>
<tr class="grand-row"><td colspan="{cols-1}">სულ აქტივები</td>
  <td class="amt">{utils.fmt_fin(total_assets)}</td></tr>
<tr class="header-row"><td colspan="{cols}">კაპიტალი და ვალდებულებები</td></tr>
<tr class="total-row"><td colspan="{cols}">კაპიტალი</td></tr>
{get_bs_rows("BS: Equity (კაპიტალი)", -1)}
<tr>{'<td></td>' if show_codes else ''}
  <td style="font-style:italic;padding:10px;">პერიოდის მოგება/ზარალი</td>
  <td class="amt" style="padding:10px;">{utils.fmt_fin(net_profit_val)}</td></tr>
<tr class="total-row"><td colspan="{cols-1}">სულ კაპიტალი</td>
  <td class="amt"><b>{utils.fmt_fin(total_equity)}</b></td></tr>
<tr class="total-row"><td colspan="{cols}">გრძელვადიანი ვალდებულებები</td></tr>
{get_bs_rows("BS: Non-Current Liabilities (გრძელვადიანი ვალდ.)", -1)}
<tr class="total-row"><td colspan="{cols-1}">სულ გრძელვადიანი ვალდ.</td>
  <td class="amt"><b>{utils.fmt_fin(nc_liab)}</b></td></tr>
<tr class="total-row"><td colspan="{cols}">მიმდინარე ვალდებულებები</td></tr>
{get_bs_rows("BS: Current Liabilities (მიმდინარე ვალდ.)", -1)}
<tr class="total-row"><td colspan="{cols-1}">სულ მიმდინარე ვალდ.</td>
  <td class="amt"><b>{utils.fmt_fin(c_liab_val)}</b></td></tr>
<tr class="grand-row"><td colspan="{cols-1}">სულ კაპიტალი და ვალდებულებები</td>
  <td class="amt">{utils.fmt_fin(total_liab_equity)}</td></tr>
</tbody></table>
"""
    st.markdown(bs_html, unsafe_allow_html=True)


if __name__ == "__main__":
    render_balance_sheet_tab()