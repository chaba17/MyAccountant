import streamlit as st
import pandas as pd
import utils


def get_period_data(db, p_type, p_val):
    relevant_keys = []
    if p_type == 'Month':
        if p_val in db:
            relevant_keys = [p_val]
    elif p_type == 'Quarter':
        parts = p_val.split(' ')
        if len(parts) == 2:
            q, y = parts
            q_months = {'Q1': ['01','02','03'], 'Q2': ['04','05','06'],
                        'Q3': ['07','08','09'], 'Q4': ['10','11','12']}
            months = q_months.get(q, [])
            relevant_keys = [k for k in db.keys() if k.startswith(y) and k[5:7] in months]
    elif p_type == 'Year':
        relevant_keys = [k for k in db.keys() if k.startswith(p_val)]

    all_data = []
    for k in relevant_keys:
        all_data.extend(db[k])

    if not all_data:
        return pd.DataFrame()

    df = utils.clean_dataset_logic(all_data)
    return df.groupby(['Code', 'Name', 'Category'])['Net'].sum().reset_index()


def render_comparison_tab():
    st.markdown("### Period Comparison")

    db = utils.load_db()
    if not db:
        st.info("No data available. Save reports from the Mapping tab first.")
        return

    all_months = sorted(db.keys(), reverse=True)
    years = sorted(list(set([m[:4] for m in all_months])), reverse=True)

    c1, c2 = st.columns([1, 3])
    with c1:
        p_type = st.selectbox("Type:", ["Month", "Quarter", "Year"], key="comp_type")
        options = []
        if p_type == "Month":
            options = all_months
        elif p_type == "Quarter":
            for y in years:
                options.extend([f"Q4 {y}", f"Q3 {y}", f"Q2 {y}", f"Q1 {y}"])
        elif p_type == "Year":
            options = years
        if not options:
            options = ["N/A"]

    with c2:
        selected_periods = st.multiselect(
            "Select periods:", options,
            default=options[:2] if len(options) > 1 else options,
            key="comp_periods"
        )

    if not selected_periods:
        st.info("Select at least 1 period.")
        return

    show_codes = st.checkbox("Show codes", value=True, key="comp_codes")

    # Build master data
    master_dict = {}
    for p in selected_periods:
        df_p = get_period_data(db, p_type, p)
        if not df_p.empty:
            for _, row in df_p.iterrows():
                code = str(row['Code'])
                if code not in master_dict:
                    master_dict[code] = {'Name': row['Name'], 'Category': row['Category']}
                master_dict[code][p] = row['Net']

    if not master_dict:
        st.warning("No data found for selected periods.")
        return

    # HTML builder
    has_var = len(selected_periods) >= 2
    num_cols = (1 if show_codes else 0) + 1 + len(selected_periods) + (2 if has_var else 0)

    header_html = f"<thead><tr>{'<th>Code</th>' if show_codes else ''}<th>Description</th>"
    for p in selected_periods:
        header_html += f"<th class='text-right'>{p}</th>"
    if has_var:
        header_html += "<th class='text-right'>Variance</th><th class='text-right'>Var %</th>"
    header_html += "</tr></thead>"

    def build_section(cat, multiplier=1):
        codes = [c for c, v in master_dict.items() if v['Category'] == cat]
        totals = {p: 0.0 for p in selected_periods}

        if not codes:
            return "", totals

        codes.sort()
        rows_html = ""
        is_exp = cat.startswith(('COGS', 'Operating', 'Depreciation', 'Interest', 'Tax'))

        for c in codes:
            item = master_dict[c]
            vals = [item.get(p, 0.0) * multiplier for p in selected_periods]
            if all(abs(v) < 0.01 for v in vals):
                continue

            for i, p in enumerate(selected_periods):
                totals[p] += vals[i]

            cells = ""
            for v in vals:
                disp = -abs(v) if is_exp else (abs(v) if cat.startswith('Revenue') else v)
                cls = "neg" if disp < 0 else "pos"
                cells += f"<td class='amt {cls}'>{utils.fmt_fin(disp)}</td>"

            var_html = ""
            if has_var:
                v1, v2 = vals[0], vals[1]
                diff = v1 - v2
                disp_diff = -diff if is_exp else diff
                vh = utils.fmt_var(disp_diff, is_exp)
                pct = (diff / abs(v2) * 100) if v2 != 0 else 0
                pcl = "var-neg" if (is_exp and diff > 0) or (not is_exp and diff < 0) else "var-pos"
                if abs(diff) < 0.01:
                    pcl = ""
                var_html = f"<td class='amt'>{vh}</td><td class='amt {pcl}'>{pct:+.1f}%</td>"

            code_td = f"<td class='code-col'>{c}</td>" if show_codes else ""
            rows_html += f"<tr>{code_td}<td class='indent'>{item['Name']}</td>{cells}{var_html}</tr>"

        # Total row
        t_cells = ""
        for p in selected_periods:
            tv = totals[p]
            tdisp = -abs(tv) if is_exp else (abs(tv) if cat.startswith('Revenue') else tv)
            tcls = "neg" if tdisp < 0 else "pos"
            t_cells += f"<td class='amt {tcls}'><b>{utils.fmt_fin(tdisp)}</b></td>"

        t_var = ""
        if has_var:
            tv1, tv2 = totals[selected_periods[0]], totals[selected_periods[1]]
            td = tv1 - tv2
            tdd = -td if is_exp else td
            tvh = utils.fmt_var(tdd, is_exp)
            tpct = (td / abs(tv2) * 100) if tv2 != 0 else 0
            tpcl = "var-neg" if (is_exp and td > 0) or (not is_exp and td < 0) else "var-pos"
            t_var = f"<td class='amt'><b>{tvh}</b></td><td class='amt {tpcl}'><b>{tpct:+.1f}%</b></td>"

        section_label = cat.split('(')[0].strip()
        section = (
            f'<tr class="section-row"><td colspan="{num_cols}">{cat}</td></tr>'
            f'{rows_html}'
            f'<tr class="subtotal-row"><td colspan="{2 if show_codes else 1}">Total {section_label}</td>{t_cells}{t_var}</tr>'
        )
        return section, totals

    # Build all sections
    h1, t1 = build_section("Revenue (შემოსავალი)", -1)
    h2, t2 = build_section("COGS (თვითღირებულება)", 1)
    h3, t3 = build_section("Operating Expenses (საოპერაციო ხარჯები)", 1)
    h4, t4 = build_section("Depreciation (ცვეთა/ამორტიზაცია)", 1)
    h5, t5 = build_section("Interest (საპროცენტო ხარჯი)", 1)
    h6, t6 = build_section("Other Income/Expense (სხვა არასაოპერაციო)", -1)
    h7, t7 = build_section("Tax (მოგების გადასახადი)", 1)

    # Summary rows
    def summary_row(label, calc_fn):
        cells = ""
        v1, v2 = 0, 0
        for i, p in enumerate(selected_periods):
            val = calc_fn(p)
            if i == 0: v1 = val
            if i == 1: v2 = val
            cells += f"<td class='amt'><b>{utils.fmt_fin(val)}</b></td>"

        var_html = ""
        if has_var:
            d = v1 - v2
            pc = (d / abs(v2) * 100) if v2 != 0 else 0
            vh = utils.fmt_var(d)
            pcl = "var-pos" if d > 0 else "var-neg"
            var_html = f"<td class='amt'><b>{vh}</b></td><td class='amt {pcl}'><b>{pc:+.1f}%</b></td>"

        return f'<tr class="grand-row"><td colspan="{2 if show_codes else 1}">{label}</td>{cells}{var_html}</tr>'

    def get_gross(p): return t1.get(p, 0) - t2.get(p, 0)
    def get_ebitda(p): return get_gross(p) - t3.get(p, 0)
    def get_net(p): return get_ebitda(p) - t4.get(p, 0) - t5.get(p, 0) + t6.get(p, 0) - t7.get(p, 0)

    table = f"""
<table class="fin-table">
{header_html}
<tbody>
{h1}{h2}
{summary_row("GROSS PROFIT", get_gross)}
{h3}
{summary_row("EBITDA", get_ebitda)}
{h4}
{h5}{h6}{h7}
{summary_row("NET PROFIT", get_net)}
</tbody>
</table>
"""
    st.markdown(table, unsafe_allow_html=True)
