import streamlit as st
import pandas as pd
import utils
import ai_advisor_module


def render_balance_sheet_tab():
    st.markdown("### Balance Sheet (IFRS)")

    db = utils.load_db()
    opts = sorted(db.keys(), reverse=True)
    if not opts:
        st.info("No data available. Upload and save data from the Mapping tab.")
        return

    sel_bs = st.selectbox("Period:", opts, key="bs_period")

    # Load raw data for AI advisor and names
    df_raw = pd.DataFrame(db[sel_bs])
    df_raw["Code"] = df_raw["Code"].astype(str).str.strip()
    if "Net" not in df_raw.columns:
        df_raw["Net"] = (
            pd.to_numeric(df_raw.get("Debit", 0), errors="coerce").fillna(0)
            - pd.to_numeric(df_raw.get("Credit", 0), errors="coerce").fillna(0)
        )

    # Get parent map for grouping
    parent_map = utils.get_parent_map(db[sel_bs])
    code_name = (
        df_raw.drop_duplicates("Code").set_index("Code")["Name"].to_dict()
        if "Name" in df_raw.columns
        else {}
    )

    # Clean data (leaf codes only)
    df_calc = utils.clean_dataset_logic(db[sel_bs])
    if df_calc.empty:
        st.warning("No data after cleaning.")
        return

    # AI Advisor
    problematic_codes = ai_advisor_module.render_audit_ui(df_calc, "BS", source_key=sel_bs)

    # Calculations using shared utility
    pl = utils.calc_pl_metrics(df_calc)
    bs = utils.calc_bs_metrics(df_calc, pl["net_profit"])
    check = bs["total_assets"] - bs["total_liab"] - bs["total_equity"]

    # KPI metrics
    k1, k2, k3 = st.columns(3)
    k1.metric("Total Assets", utils.fmt_fin(bs["total_assets"]))
    k2.metric("Equity + Liabilities", utils.fmt_fin(bs["total_liab"] + bs["total_equity"]))
    k3.metric(
        "Difference",
        utils.fmt_fin(check),
        delta_color="off" if abs(check) < 1 else "inverse",
    )
    if abs(check) > 0.1:
        st.error(f"Imbalance: {utils.fmt_fin(check)}")

    show_codes = st.checkbox("Show codes", value=True, key="bs_codes")
    cols = 3 if show_codes else 2

    # Build grouped rows HTML
    def get_bs_rows(cat, multiplier=1.0):
        subset = df_calc[df_calc["Category"] == cat].copy()
        if subset.empty:
            return ""
        subset["Val"] = subset["Net"] * multiplier

        # Group by parent
        groups = {}
        for _, row in subset.iterrows():
            code = row["Code"]
            if code in parent_map:
                p_code, p_name = parent_map[code]
            else:
                p_code, p_name = code, code_name.get(code, code)
            if p_code not in groups:
                groups[p_code] = {"name": p_name, "children": [], "total": 0}
            groups[p_code]["children"].append(row)
            groups[p_code]["total"] += row["Val"]

        html = ""
        for g_code in sorted(groups.keys()):
            g = groups[g_code]
            if abs(g["total"]) < 0.01:
                continue

            children_html = ""
            for ch in sorted(g["children"], key=lambda x: x["Code"]):
                if abs(ch["Val"]) < 0.01:
                    continue
                err = "background:#FEF2F2;" if str(ch["Code"]) in problematic_codes else ""
                code_td = f'<td class="code-col">{ch["Code"]}</td>' if show_codes else ""
                children_html += (
                    f'<tr style="{err}">'
                    f"{code_td}"
                    f'<td class="indent" style="color:var(--text-secondary);font-size:0.85rem;">{ch["Name"]}</td>'
                    f'<td class="amt">{utils.fmt_fin(ch["Val"])}</td></tr>'
                )

            code_td = f'<td class="code-col"><b>{g_code}</b></td>' if show_codes else ""
            if children_html:
                inner = f'<table class="child-table">{children_html}</table>'
                name_cell = f'<details><summary><b>{g["name"]}</b></summary>{inner}</details>'
            else:
                name_cell = f'<b>{g["name"]}</b>'

            html += (
                f'<tr style="background:var(--bg-subtle);">'
                f"{code_td}"
                f"<td>{name_cell}</td>"
                f'<td class="amt" style="vertical-align:top;padding-top:10px;"><b>{utils.fmt_fin(g["total"])}</b></td></tr>'
            )
        return html

    # Build the full table
    bs_html = f"""
<table class="fin-table">
<thead><tr>{"<th>Code</th>" if show_codes else ""}<th>Description</th><th class="text-right">Amount (GEL)</th></tr></thead>
<tbody>
<tr class="section-row"><td colspan="{cols}">ASSETS</td></tr>
<tr class="subtotal-row"><td colspan="{cols}">Non-Current Assets</td></tr>
{get_bs_rows("BS: Non-Current Assets (გრძელვადიანი აქტივები)", 1)}
<tr class="subtotal-row"><td colspan="{cols - 1}">Total Non-Current Assets</td>
    <td class="amt"><b>{utils.fmt_fin(bs['nc_assets'])}</b></td></tr>
<tr class="subtotal-row"><td colspan="{cols}">Current Assets</td></tr>
{get_bs_rows("BS: Current Assets (მიმდინარე აქტივები)", 1)}
<tr class="subtotal-row"><td colspan="{cols - 1}">Total Current Assets</td>
    <td class="amt"><b>{utils.fmt_fin(bs['c_assets'])}</b></td></tr>
<tr class="grand-row"><td colspan="{cols - 1}">TOTAL ASSETS</td>
    <td class="amt">{utils.fmt_fin(bs['total_assets'])}</td></tr>

<tr class="section-row"><td colspan="{cols}">EQUITY & LIABILITIES</td></tr>
<tr class="subtotal-row"><td colspan="{cols}">Equity</td></tr>
{get_bs_rows("BS: Equity (კაპიტალი)", -1)}
<tr>{"<td></td>" if show_codes else ""}
    <td style="font-style:italic;padding:10px;color:var(--text-secondary);">Period Net Profit / (Loss)</td>
    <td class="amt" style="padding:10px;">{utils.fmt_fin(pl['net_profit'])}</td></tr>
<tr class="subtotal-row"><td colspan="{cols - 1}">Total Equity</td>
    <td class="amt"><b>{utils.fmt_fin(bs['total_equity'])}</b></td></tr>
<tr class="subtotal-row"><td colspan="{cols}">Non-Current Liabilities</td></tr>
{get_bs_rows("BS: Non-Current Liabilities (გრძელვადიანი ვალდ.)", -1)}
<tr class="subtotal-row"><td colspan="{cols - 1}">Total Non-Current Liabilities</td>
    <td class="amt"><b>{utils.fmt_fin(bs['nc_liab'])}</b></td></tr>
<tr class="subtotal-row"><td colspan="{cols}">Current Liabilities</td></tr>
{get_bs_rows("BS: Current Liabilities (მიმდინარე ვალდ.)", -1)}
<tr class="subtotal-row"><td colspan="{cols - 1}">Total Current Liabilities</td>
    <td class="amt"><b>{utils.fmt_fin(bs['c_liab'])}</b></td></tr>
<tr class="grand-row"><td colspan="{cols - 1}">TOTAL EQUITY & LIABILITIES</td>
    <td class="amt">{utils.fmt_fin(bs['total_liab'] + bs['total_equity'])}</td></tr>
</tbody></table>
"""
    st.markdown(bs_html, unsafe_allow_html=True)
