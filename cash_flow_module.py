import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import utils
import ai_advisor_module


def render_cash_flow_tab():
    st.markdown("### Cash Flow Statement (Indirect Method)")

    db = utils.load_db()
    opts = sorted(db.keys(), reverse=True)

    if not opts:
        st.info("No data available. Upload and save data from the Mapping tab.")
        return

    c1, c2 = st.columns(2)
    curr_period = c1.selectbox("Current Period:", opts, key="cf_curr")
    remaining = [x for x in opts if x != curr_period]
    prev_period = c2.selectbox("Previous Period:", ["- Opening balance 0 -"] + remaining, key="cf_prev")

    df_curr = utils.clean_dataset_logic(db[curr_period])

    if prev_period != "- Opening balance 0 -":
        df_prev = utils.clean_dataset_logic(db[prev_period])
    else:
        df_prev = pd.DataFrame(columns=['Category', 'Net'])

    # AI Advisor
    ai_advisor_module.render_audit_ui(df_curr, "BS", source_key=curr_period, ui_key="cf")

    # Helper
    def get_val(df, cat):
        if df.empty or 'Category' not in df.columns:
            return 0.0
        return df[df['Category'] == cat]['Net'].sum()

    # === CALCULATIONS ===

    # Operating Activities (CFO)
    pl = utils.calc_pl_metrics(df_curr)
    net_profit = pl['net_profit']
    adj_non_cash = pl['depr']

    # Working Capital Changes
    ca_curr = get_val(df_curr, "BS: Current Assets (მიმდინარე აქტივები)")
    ca_prev = get_val(df_prev, "BS: Current Assets (მიმდინარე აქტივები)")
    change_working_assets = ca_prev - ca_curr

    cl_curr = get_val(df_curr, "BS: Current Liabilities (მიმდინარე ვალდ.)") * -1
    cl_prev = get_val(df_prev, "BS: Current Liabilities (მიმდინარე ვალდ.)") * -1
    change_working_liabs = cl_curr - cl_prev

    cfo = net_profit + adj_non_cash + change_working_assets + change_working_liabs

    # Investing Activities (CFI)
    nca_curr = get_val(df_curr, "BS: Non-Current Assets (გრძელვადიანი აქტივები)")
    nca_prev = get_val(df_prev, "BS: Non-Current Assets (გრძელვადიანი აქტივები)")
    cfi = nca_prev - nca_curr

    # Financing Activities (CFF)
    ncl_curr = get_val(df_curr, "BS: Non-Current Liabilities (გრძელვადიანი ვალდ.)") * -1
    ncl_prev = get_val(df_prev, "BS: Non-Current Liabilities (გრძელვადიანი ვალდ.)") * -1
    change_debt = ncl_curr - ncl_prev

    eq_curr = get_val(df_curr, "BS: Equity (კაპიტალი)") * -1
    eq_prev = get_val(df_prev, "BS: Equity (კაპიტალი)") * -1
    change_equity_clean = (eq_curr - eq_prev) - net_profit

    cff = change_debt + change_equity_clean
    net_cash_change = cfo + cfi + cff

    # === KPI METRICS ===
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Operating (CFO)", utils.fmt_fin(cfo))
    k2.metric("Investing (CFI)", utils.fmt_fin(cfi))
    k3.metric("Financing (CFF)", utils.fmt_fin(cff))
    k4.metric("Net Change", utils.fmt_fin(net_cash_change))

    st.markdown("---")

    col_chart, col_table = st.columns([3, 2])

    with col_chart:
        fig = go.Figure(go.Waterfall(
            name="Cash Flow",
            orientation="v",
            measure=["relative", "relative", "relative", "relative", "total",
                     "relative", "relative", "total"],
            x=["Net Profit", "+ Depreciation", "Working Capital", "Current Liabilities",
               "CFO", "CFI (Investing)", "CFF (Financing)", "Net Change"],
            y=[net_profit, adj_non_cash, change_working_assets, change_working_liabs,
               0, cfi, cff, 0],
            textposition="outside",
            connector={"line": {"color": "rgba(0,0,0,0.1)", "width": 1}},
            decreasing={"marker": {"color": "#DC2626"}},
            increasing={"marker": {"color": "#059669"}},
            totals={"marker": {"color": "#2563EB"}},
        ))
        fig.update_layout(
            title="Profit to Cash Flow Transformation",
            showlegend=False,
            height=380,
            margin=dict(t=40, b=20, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(248,250,252,0.8)",
            font=dict(family="Inter, sans-serif", color="#475569", size=12),
            yaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.05)", tickformat=",.0f"),
            xaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_table:
        html = f"""
<table class="fin-table">
<tbody>
<tr class="section-row"><td colspan="2">Operating Activities</td></tr>
<tr><td class="indent">Net Profit</td><td class="amt">{utils.fmt_fin(net_profit)}</td></tr>
<tr><td class="indent">+ Depreciation & Amortization</td><td class="amt">{utils.fmt_fin(adj_non_cash)}</td></tr>
<tr><td class="indent">Change in Working Capital (Assets)</td><td class="amt">{utils.fmt_fin(change_working_assets)}</td></tr>
<tr><td class="indent">Change in Working Capital (Liabilities)</td><td class="amt">{utils.fmt_fin(change_working_liabs)}</td></tr>
<tr class="calc-row"><td>Net Cash from Operations</td><td class="amt">{utils.fmt_fin(cfo)}</td></tr>

<tr class="section-row"><td colspan="2">Investing Activities</td></tr>
<tr><td class="indent">Change in Fixed Assets (CapEx)</td><td class="amt">{utils.fmt_fin(cfi)}</td></tr>
<tr class="calc-row"><td>Net Cash from Investing</td><td class="amt">{utils.fmt_fin(cfi)}</td></tr>

<tr class="section-row"><td colspan="2">Financing Activities</td></tr>
<tr><td class="indent">Change in Long-Term Debt</td><td class="amt">{utils.fmt_fin(change_debt)}</td></tr>
<tr><td class="indent">Change in Equity (excl. Profit)</td><td class="amt">{utils.fmt_fin(change_equity_clean)}</td></tr>
<tr class="calc-row"><td>Net Cash from Financing</td><td class="amt">{utils.fmt_fin(cff)}</td></tr>

<tr class="grand-row"><td>NET CASH CHANGE</td><td class="amt">{utils.fmt_fin(net_cash_change)}</td></tr>
</tbody>
</table>
"""
        st.markdown(html, unsafe_allow_html=True)
