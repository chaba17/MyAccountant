import streamlit as st
import pandas as pd
import utils 

def get_period_data(db, p_type, p_val):
    relevant_keys = []
    if p_type == 'Month':
        if p_val in db: relevant_keys = [p_val]
    elif p_type == 'Quarter':
        parts = p_val.split(' ')
        if len(parts) == 2:
            q, y = parts
            q_months = {'Q1':['01','02','03'], 'Q2':['04','05','06'], 'Q3':['07','08','09'], 'Q4':['10','11','12']}
            months = q_months.get(q, [])
            relevant_keys = [k for k in db.keys() if k.startswith(y) and k[5:7] in months]
    elif p_type == 'Year':
        relevant_keys = [k for k in db.keys() if k.startswith(p_val)]
        
    all_data = []
    for k in relevant_keys:
        all_data.extend(db[k])
    
    if not all_data: return pd.DataFrame()
    
    # ვიყენებთ clean logic-ს რომ მშობელი კოდები არ გაორმაგდეს
    df = utils.clean_dataset_logic(all_data)
    
    # ვაჯგუფებთ კოდის მიხედვით (თუ რამდენიმე თვეა გაერთიანებული)
    return df.groupby(['Code', 'Name', 'Category'])['Net'].sum().reset_index()

def render_comparison_tab():
    st.markdown("### ⚖️ პერიოდების შედარება")
    
    db = utils.load_db()
    if not db:
        st.warning("ბაზაში მონაცემები არ არის. გთხოვთ ჯერ შეინახოთ რეპორტები P&L ტაბიდან.")
        return

    all_months = sorted(db.keys(), reverse=True)
    years = sorted(list(set([m[:4] for m in all_months])), reverse=True)
    
    c1, c2 = st.columns([1, 3])
    with c1:
        p_type = st.selectbox("ტიპი:", ["Month", "Quarter", "Year"])
        options = []
        if p_type == "Month": options = all_months
        elif p_type == "Quarter": 
            for y in years: options.extend([f"Q4 {y}", f"Q3 {y}", f"Q2 {y}", f"Q1 {y}"])
        elif p_type == "Year": options = years
        if not options: options = ["N/A"]
        
    with c2:
        selected_periods = st.multiselect("აირჩიეთ პერიოდები:", options, default=options[:2] if len(options)>1 else options)

    if not selected_periods:
        st.info("აირჩიეთ მინიმუმ 1 პერიოდი.")
        return
    
    show_codes = st.checkbox("კოდების ჩვენება", value=True)

    # --- MATRIX GENERATION ---
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
        st.warning("მონაცემები არ მოიძებნა.")
        return

    # --- HTML BUILDER ---
    # Header
    header_html = f"<thead><tr>{'<th>Code</th>' if show_codes else ''}<th class='text-left'>Item Description</th>"
    for p in selected_periods:
        header_html += f"<th>{p}</th>"
    
    has_var = len(selected_periods) >= 2
    if has_var: header_html += "<th>Var (Diff)</th><th>Var %</th>"
    header_html += "</tr></thead>"

    def build_section_html(cat, multiplier=1):
        codes = [c for c, v in master_dict.items() if v['Category'] == cat]
        totals = {p: 0.0 for p in selected_periods}
        
        if not codes: return "", totals
        
        codes.sort()
        rows_html = ""
        
        for c in codes:
            item = master_dict[c]
            vals = [item.get(p, 0.0) * multiplier for p in selected_periods]
            if all(abs(v) < 0.01 for v in vals): continue
            
            for i, p in enumerate(selected_periods): totals[p] += vals[i]
            
            cells = ""
            for i, v in enumerate(vals):
                is_exp = cat.startswith(('COGS', 'Operating', 'Depreciation', 'Interest', 'Tax'))
                disp = -abs(v) if is_exp else v
                if cat.startswith('Revenue'): disp = abs(v)
                cls = "neg" if disp < 0 else "pos"
                style = "color:#666;" if i > 0 and cls=="pos" else ""
                cells += f"<td class='amt {cls}' style='{style}'>{utils.fmt_fin(disp)}</td>"
            
            var_html = ""
            if has_var:
                v1, v2 = vals[0], vals[1]
                diff = v1 - v2
                is_exp = cat.startswith(('COGS', 'Operating', 'Depreciation', 'Interest', 'Tax'))
                disp_diff = -diff if is_exp else diff
                
                vh = utils.fmt_var(disp_diff, is_exp)
                pct = (diff/abs(v2)*100) if v2!=0 else 0
                pcl = "var-neg" if (is_exp and diff>0) or (not is_exp and diff<0) else "var-pos"
                if abs(diff)<0.01: pcl=""
                var_html = f"<td class='amt'>{vh}</td><td class='amt {pcl}'>{pct:+.1f}%</td>"

            ctd = f"<td class='code-col'>{c}</td>" if show_codes else ""
            # NO INDENTATION HERE
            rows_html += f"<tr>{ctd}<td class='sub-indent'>{item['Name']}</td>{cells}{var_html}</tr>"

        # Total Row
        t_cells = ""
        for p in selected_periods:
            tv = totals[p]
            is_exp = cat.startswith(('COGS', 'Operating', 'Depreciation', 'Interest', 'Tax'))
            tdisp = -abs(tv) if is_exp else tv
            if cat.startswith('Revenue'): tdisp = abs(tv)
            tcls = "neg" if tdisp < 0 else "pos"
            t_cells += f"<td class='amt {tcls}'><b>{utils.fmt_fin(tdisp)}</b></td>"
        
        t_var_html = ""
        if has_var:
            tv1, tv2 = totals[selected_periods[0]], totals[selected_periods[1]]
            tdiff = tv1 - tv2
            is_exp = cat.startswith(('COGS', 'Operating', 'Depreciation', 'Interest', 'Tax'))
            tdisp_diff = -tdiff if is_exp else tdiff
            
            tvh = utils.fmt_var(tdisp_diff, is_exp)
            tpct = (tdiff/abs(tv2)*100) if tv2!=0 else 0
            tpcl = "var-neg" if (is_exp and tdiff>0) or (not is_exp and tdiff<0) else "var-pos"
            t_var_html = f"<td class='amt'><b>{tvh}</b></td><td class='amt {tpcl}'><b>{tpct:+.1f}%</b></td>"

        cols = (1 if show_codes else 0) + 1 + len(selected_periods) + (2 if has_var else 0)
        return f"""<tr class="header-row"><td colspan="{cols}">{cat}</td></tr>{rows_html}<tr class="total-row"><td colspan="{2 if show_codes else 1}">Total {cat.split(' ')[0]}</td>{t_cells}{t_var_html}</tr>""", totals

    # --- SECTIONS ---
    h1, t1 = build_section_html("Revenue (შემოსავალი)", -1)
    h2, t2 = build_section_html("COGS (თვითღირებულება)", 1)
    h3, t3 = build_section_html("Operating Expenses (საოპერაციო ხარჯები)", 1)
    h4, t4 = build_section_html("Depreciation (ცვეთა/ამორტიზაცია)", 1)
    h5, t5 = build_section_html("Interest (საპროცენტო ხარჯი)", 1)
    h6, t6 = build_section_html("Other Income/Expense (სხვა არასაოპერაციო)", -1)
    h7, t7 = build_section_html("Tax (მოგების გადასახადი)", 1)

    # --- SUMMARY ROWS ---
    def make_summary_row(label, p_list, func_val):
        cells = ""
        v1, v2 = 0, 0
        for i, p in enumerate(p_list):
            val = func_val(p)
            if i==0: v1=val
            if i==1: v2=val
            cells += f"<td class='amt'><b>{utils.fmt_fin(val)}</b></td>"
        
        vars = ""
        if has_var:
            d = v1 - v2
            pc = (d/abs(v2)*100) if v2!=0 else 0
            vh = utils.fmt_var(d)
            pcl = "var-pos" if d>0 else "var-neg"
            vars = f"<td class='amt'><b>{vh}</b></td><td class='amt {pcl}'><b>{pc:+.1f}%</b></td>"
        
        return f'<tr class="grand-row"><td colspan="{2 if show_codes else 1}">{label}</td>{cells}{vars}</tr>'

    def get_gross(p): return t1.get(p,0) - t2.get(p,0)
    def get_ebitda(p): return get_gross(p) - t3.get(p,0)
    def get_net(p): return (get_ebitda(p) - t4.get(p,0)) - t5.get(p,0) + t6.get(p,0) - t7.get(p,0)

    r_gross = make_summary_row("GROSS PROFIT", selected_periods, get_gross)
    r_ebitda = make_summary_row("EBITDA", selected_periods, get_ebitda)
    r_net = make_summary_row("NET PROFIT", selected_periods, get_net)

    # --- FINAL RENDER ---
    # აქაც არანაირი შეწევა!
    final_table = f"""
<table class="pl-table">
{header_html}
<tbody>
{h1} {h2} 
{r_gross}
{h3} 
{r_ebitda}
{h4} 
<tr class="grand-row" style="background-color:#546E7A"><td colspan="{2 if show_codes else 1}">EBIT</td></tr>
{h5} {h6} {h7}
{r_net}
</tbody>
</table>
"""
    st.markdown(final_table, unsafe_allow_html=True)