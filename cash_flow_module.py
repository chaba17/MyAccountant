import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import utils
import ai_advisor_module

def render_cash_flow_tab():
    st.markdown("### 🌊 ფულადი ნაკადების მოძრაობის უწყისი (Indirect Method)")
    
    db = utils.load_db()
    opts = sorted(db.keys(), reverse=True)
    
    if not opts:
        st.warning("მონაცემთა ბაზა ცარიელია. გთხოვთ ატვირთოთ ფაილები.")
        return

    c1, c2 = st.columns(2)
    curr_period = c1.selectbox("მიმდინარე პერიოდი (Current):", opts, key="cf_curr")
    
    remaining_opts = [x for x in opts if x != curr_period]
    prev_period = c2.selectbox("წინა პერიოდი (Previous):", ["- საწყისი ნაშთი 0 -"] + remaining_opts, key="cf_prev")

    df_curr = utils.clean_dataset_logic(db[curr_period])
    
    if prev_period != "- საწყისი ნაშთი 0 -":
        df_prev = utils.clean_dataset_logic(db[prev_period])
    else:
        df_prev = pd.DataFrame(columns=['Category', 'Net'])

    # ==========================================
    # 🤖 AI ADVISOR (Cash Flow Health)
    # ==========================================
    # აქ ვამატებთ ui_key="cf"-ს, რათა არ მოხდეს კონფლიქტი სხვა ტაბებთან
    ai_advisor_module.render_audit_ui(df_curr, "BS", source_key=curr_period, ui_key="cf")

    # --- დამხმარე ფუნქცია ---
    def get_val(df, cat):
        if df.empty or 'Category' not in df.columns: return 0.0
        return df[df['Category'] == cat]['Net'].sum()

    # ==========================================
    # 🧮 CASH FLOW ENGINE (CALCULATIONS)
    # ==========================================

    # 1. საოპერაციო საქმიანობა (CFO)
    rev = get_val(df_curr, "Revenue (შემოსავალი)") * -1
    other = get_val(df_curr, "Other Income/Expense (სხვა არასაოპერაციო)") * -1
    cogs = get_val(df_curr, "COGS (თვითღირებულება)")
    opex = get_val(df_curr, "Operating Expenses (საოპერაციო ხარჯები)")
    depr = get_val(df_curr, "Depreciation (ცვეთა/ამორტიზაცია)")
    inte = get_val(df_curr, "Interest (საპროცენტო ხარჯი)")
    tax = get_val(df_curr, "Tax (მოგების გადასახადი)")
    
    net_profit = (rev + other) - (cogs + opex + depr + inte + tax)

    adj_non_cash = depr 

    # Working Capital Changes
    ca_curr = get_val(df_curr, "BS: Current Assets (მიმდინარე აქტივები)")
    ca_prev = get_val(df_prev, "BS: Current Assets (მიმდინარე აქტივები)")
    change_receivables = ca_prev - ca_curr 

    cl_curr = get_val(df_curr, "BS: Current Liabilities (მიმდინარე ვალდ.)")
    cl_prev = get_val(df_prev, "BS: Current Liabilities (მიმდინარე ვალდ.)")
    change_payables = (cl_curr * -1) - (cl_prev * -1)

    cfo = net_profit + adj_non_cash + change_receivables + change_payables

    # 2. საინვესტიციო საქმიანობა (CFI)
    nca_curr = get_val(df_curr, "BS: Non-Current Assets (გრძელვადიანი აქტივები)")
    nca_prev = get_val(df_prev, "BS: Non-Current Assets (გრძელვადიანი აქტივები)")
    cfi = nca_prev - nca_curr

    # 3. ფინანსური საქმიანობა (CFF)
    ncl_curr = get_val(df_curr, "BS: Non-Current Liabilities (გრძელვადიანი ვალდ.)") * -1
    ncl_prev = get_val(df_prev, "BS: Non-Current Liabilities (გრძელვადიანი ვალდ.)") * -1
    change_debt = ncl_curr - ncl_prev

    eq_curr = get_val(df_curr, "BS: Equity (კაპიტალი)") * -1
    eq_prev = get_val(df_prev, "BS: Equity (კაპიტალი)") * -1
    
    change_equity_total = eq_curr - eq_prev
    change_equity_clean = change_equity_total - net_profit
    
    cff = change_debt + change_equity_clean

    # 4. ჯამური ცვლილება
    net_cash_change = cfo + cfi + cff

    # ==========================================
    # 📊 VISUALIZATION
    # ==========================================
    
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("საოპერაციო (CFO)", utils.fmt_fin(cfo))
    k2.metric("საინვესტიციო (CFI)", utils.fmt_fin(cfi))
    k3.metric("ფინანსური (CFF)", utils.fmt_fin(cff))
    k4.metric("წმინდა ცვლილება", utils.fmt_fin(net_cash_change), delta_color="normal")

    st.markdown("---")

    col_chart, col_table = st.columns([3, 2])
    
    with col_chart:
        st.subheader("ვიზუალიზაცია (Waterfall)")
        fig = go.Figure(go.Waterfall(
            name = "Cash Flow", orientation = "v",
            measure = ["relative", "relative", "relative", "relative", "total", "relative", "relative", "total"],
            x = ["წმინდა მოგება", "+ ცვეთა", "Δ საბრუნავი კაპიტალი", "Δ მიმდ. ვალდებულებები", "CFO (ჯამი)", "CFI (ინვესტიცია)", "CFF (ფინანსური)", "სულ ცვლილება"],
            textposition = "outside",
            y = [net_profit, adj_non_cash, change_receivables, change_payables, 0, cfi, cff, 0],
            connector = {"line":{"color":"rgb(63, 63, 63)"}},
            decreasing = {"marker":{"color":"#E74C3C"}},
            increasing = {"marker":{"color":"#2ECC71"}},
            totals = {"marker":{"color":"#3498DB"}}
        ))
        fig.update_layout(title = "მოგების ტრანსფორმაცია ფულად ნაკადში", showlegend = False)
        st.plotly_chart(fig, use_container_width=True)

    with col_table:
        st.subheader("დეტალური რეპორტი")
        html = f"""
        <style>
            .cf-table {{ width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 0.9rem; }}
            .cf-table td {{ padding: 8px; border-bottom: 1px solid #eee; }}
            .cf-head {{ background-color: #f8f9fa; font-weight: bold; color: #333; }}
            .cf-sub {{ padding-left: 20px; color: #555; }}
            .cf-res {{ font-weight: bold; background-color: #eaf2f8; }}
            .cf-num {{ text-align: right; font-family: monospace; }}
        </style>
        <table class="cf-table">
            <tr class="cf-head"><td colspan="2">Operating Activities</td></tr>
            <tr><td class="cf-sub">Net Profit</td><td class="cf-num">{utils.fmt_fin(net_profit)}</td></tr>
            <tr><td class="cf-sub">+ Depreciation</td><td class="cf-num">{utils.fmt_fin(adj_non_cash)}</td></tr>
            <tr><td class="cf-sub">Δ Working Capital (Assets)</td><td class="cf-num">{utils.fmt_fin(change_receivables)}</td></tr>
            <tr><td class="cf-sub">Δ Working Capital (Liabs)</td><td class="cf-num">{utils.fmt_fin(change_payables)}</td></tr>
            <tr class="cf-res"><td>Net Cash from Operating</td><td class="cf-num">{utils.fmt_fin(cfo)}</td></tr>
            <tr class="cf-head"><td colspan="2" style="padding-top:10px;">Investing Activities</td></tr>
            <tr><td class="cf-sub">Δ Fixed Assets (Capex)</td><td class="cf-num">{utils.fmt_fin(cfi)}</td></tr>
            <tr class="cf-res"><td>Net Cash from Investing</td><td class="cf-num">{utils.fmt_fin(cfi)}</td></tr>
            <tr class="cf-head"><td colspan="2" style="padding-top:10px;">Financing Activities</td></tr>
            <tr><td class="cf-sub">Δ Long Term Debt</td><td class="cf-num">{utils.fmt_fin(change_debt)}</td></tr>
            <tr><td class="cf-sub">Δ Equity (Net of Profit)</td><td class="cf-num">{utils.fmt_fin(change_equity_clean)}</td></tr>
            <tr class="cf-res"><td>Net Cash from Financing</td><td class="cf-num">{utils.fmt_fin(cff)}</td></tr>
            <tr style="background-color: #2c3e50; color: white; font-weight: bold; font-size: 1.1em;">
                <td style="padding: 10px;">NET CASH CHANGE</td>
                <td style="padding: 10px; text-align: right;">{utils.fmt_fin(net_cash_change)}</td>
            </tr>
        </table>
        """
        st.markdown(html, unsafe_allow_html=True)

if __name__ == "__main__":
    render_cash_flow_tab()