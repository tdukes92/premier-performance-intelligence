import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ppi import metrics
from ppi.components import card, chart, empty_state, insight, kpi, learn, money, num, page_header, pct, section
from ppi.state import analyzed_parts, ctx
from ppi.theme import SERIES, TEXT_2

c = ctx()
page_header("Service Advisor Performance", "Sales, close rate, ticket size and the margin each advisor protects or gives away.", c.period_label, c.all.source)

if c.cur.ros.empty:
    empty_state("Repair Orders")
    st.stop()

am = metrics.advisor_metrics(c.cur, analyzed_parts(c.cur))
ap = metrics.advisor_metrics(c.prev, analyzed_parts(c.prev))
all_adv = sorted(c.all.ros["advisor"].dropna().unique())
color = {a: SERIES[i % len(SERIES)] for i, a in enumerate(all_adv)}  # color follows the advisor

section("Advisor cards")
cols = st.columns(len(am), gap="small") if len(am) <= 4 else st.columns(4, gap="small")
prev_idx = ap.set_index("advisor") if not ap.empty else None
for i, (_, r) in enumerate(am.iterrows()):
    prev = prev_idx.loc[r["advisor"]] if prev_idx is not None and r["advisor"] in prev_idx.index else None
    with cols[i % len(cols)]:
        st.markdown(kpi(r["advisor"], money(r["gross_profit"]),
                        metrics.pct_change(r["gross_profit"], prev["gross_profit"]) if prev is not None else None,
                        foot=f"{num(r['ros'])} ROs · ARO {money(r['aro'], short=False)} · Close {pct(r.get('close_rate'), 0)} · GP {pct(r['gp_pct'], 0)}"),
                    unsafe_allow_html=True)

section("Comparisons")
has_jobs = "close_rate" in am


def hbar(df, col, fmt, title, sub, key, better="high"):
    with card(title, sub, key=key):
        s = df.sort_values(col)
        fig = go.Figure(go.Bar(x=s[col], y=s["advisor"], orientation="h", marker_color=[color[a] for a in s["advisor"]],
                               text=[fmt(v) for v in s[col]], textposition="outside", cliponaxis=False,
                               textfont=dict(color=TEXT_2), hovertemplate="%{y}: <b>%{text}</b><extra></extra>"))
        mx = s[col].max() if len(s) and s[col].max() == s[col].max() else 1
        fig.update_layout(xaxis=dict(visible=False, range=[0, mx * 1.35]))
        chart(fig, 200)


r1 = st.columns(3, gap="medium")
with r1[0]:
    hbar(am, "aro", lambda v: money(v, short=False), "Average repair order", "Sales ÷ ROs", "aro")
with r1[1]:
    if has_jobs:
        hbar(am, "close_rate", lambda v: pct(v, 0), "Close rate ($)", "Authorized $ ÷ presented $", "close")
    else:
        empty_state("Jobs & Labor Lines")
with r1[2]:
    hbar(am, "gp_pct", lambda v: pct(v, 1), "Gross profit %", "Gross profit ÷ sales", "gp")
r2 = st.columns(3, gap="medium")
with r2[0]:
    hbar(am, "discount_pct", lambda v: pct(v, 1), "Discount rate", "Discounts ÷ sales before discount (lower is better)", "disc")
with r2[1]:
    if has_jobs:
        hbar(am, "hours_per_ro", lambda v: f"{v:.2f} hrs", "Billed hours per RO", "Labor hours sold per ticket", "hpr")
with r2[2]:
    if "parts_leakage" in am:
        hbar(am, "parts_leakage", money, "Parts margin leakage", "GP lost to under-matrix parts pricing (lower is better)", "leak")

section("Trend")
with card("Gross profit per week by advisor", key="adv_trend"):
    r = c.cur.ros
    wk = r.groupby([pd.Grouper(key="posted_date", freq="W-MON", label="left", closed="left"), "advisor"])["gross_profit"].sum().reset_index()
    fig = go.Figure()
    for a in sorted(wk["advisor"].unique()):
        s = wk[wk["advisor"] == a]
        fig.add_scatter(x=s["posted_date"], y=s["gross_profit"], mode="lines", name=a, line=dict(color=color[a]),
                        hovertemplate=f"{a}<br>%{{x|Week of %b %d}}<br><b>%{{y:$,.0f}}</b><extra></extra>")
    fig.update_layout(hovermode="x unified", yaxis=dict(tickprefix="$", tickformat="~s"))
    chart(fig, 300)

section("Scorecard")
with card(None, key="adv_table"):
    show = [c_ for c_ in ["advisor", "ros", "sales", "gross_profit", "gp_pct", "aro", "close_rate", "job_close_rate",
                          "declined_value", "hours_per_ro", "elr", "discounts", "discount_pct", "parts_leakage", "comebacks"] if c_ in am]
    st.dataframe(am[show], hide_index=True, width="stretch", column_config={
        "advisor": "Advisor", "ros": st.column_config.NumberColumn("ROs", format="%,d"),
        "sales": st.column_config.NumberColumn("Sales", format="dollar", step=1),
        "gross_profit": st.column_config.NumberColumn("Gross profit", format="dollar", step=1),
        "gp_pct": st.column_config.NumberColumn("GP %", format="percent"),
        "aro": st.column_config.NumberColumn("ARO", format="dollar", step=1),
        "close_rate": st.column_config.NumberColumn("Close $ %", format="percent"),
        "job_close_rate": st.column_config.NumberColumn("Close job %", format="percent"),
        "declined_value": st.column_config.NumberColumn("Declined $", format="dollar", step=1),
        "hours_per_ro": st.column_config.NumberColumn("Hrs/RO", format="%.2f"),
        "elr": st.column_config.NumberColumn("ELR", format="dollar"),
        "discounts": st.column_config.NumberColumn("Discounts", format="dollar", step=1),
        "discount_pct": st.column_config.NumberColumn("Disc %", format="percent"),
        "parts_leakage": st.column_config.NumberColumn("Parts leakage", format="dollar", step=1),
        "comebacks": st.column_config.NumberColumn("Comebacks", format="%d"),
    })

if has_jobs and am["declined_value"].sum() > 0:
    top = am.sort_values("declined_value", ascending=False).iloc[0]
    insight("info", f"{money(am['declined_value'].sum())} of recommended work was declined this period",
            f"{top['advisor']} has the most declined work ({money(top['declined_value'])}). "
            "Declined jobs are your best follow-up list — see Operational Insights for the top declined services.")

learn("Advisor metrics explained", """
<b>ARO</b> — average repair order: sales ÷ number of ROs. Driven by inspections and how well work is presented.<br>
<b>Close rate ($)</b> — dollars the customer approved ÷ dollars presented (including recommendations). Most shops
land between 50% and 70%. <b>Close job %</b> is the same idea counted in jobs instead of dollars.<br>
<b>Hours per RO</b> — billed labor hours per ticket; the best single predictor of tech paychecks and shop profit.<br>
<b>Discount rate</b> — discounts ÷ what sales would have been without them.<br>
<b>Parts leakage</b> — margin lost to parts sold under the pricing matrix on that advisor's ROs.
""")
