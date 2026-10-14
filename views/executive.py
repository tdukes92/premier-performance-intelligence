import plotly.graph_objects as go
import streamlit as st

from ppi import insights, metrics
from ppi.components import card, chart, empty_state, insight, kpi, kpi_row, learn, money, num, page_header, pct, section
from ppi.state import analyzed_parts, ctx
from ppi.theme import AQUA, BLUE, ORANGE, TEXT_2, YELLOW

c = ctx()
page_header("Executive Overview", "How the shop is performing, what changed, and where to look next.", c.period_label, c.all.source)

if c.cur.ros.empty:
    empty_state("Repair Orders")
    st.stop()

k, kp = metrics.kpis(c.cur), metrics.kpis(c.prev)
pa = analyzed_parts(c.cur)
leak = pa["leakage"].sum() if not pa.empty else float("nan")
leak_prev = analyzed_parts(c.prev)["leakage"].sum() if not c.prev.parts.empty else float("nan")
d = metrics.pct_change

kpi_row([
    kpi("Total Sales", money(k["sales"]), d(k["sales"], kp["sales"]), variant="accent"),
    kpi("Gross Profit", money(k["gross_profit"]), d(k["gross_profit"], kp["gross_profit"])),
    kpi("Gross Profit %", pct(k["gp_pct"]), k["gp_pct"] - kp["gp_pct"], delta_is_points=True),
    kpi("Car Count", num(k["car_count"]), d(k["car_count"], kp["car_count"]), foot="Posted repair orders"),
    kpi("Avg Repair Order", money(k["aro"], short=False), d(k["aro"], kp["aro"])),
])
st.write("")
kpi_row([
    kpi("Effective Labor Rate", money(k["elr"], short=False, decimals=2), d(k["elr"], kp["elr"]), foot="Labor $ ÷ billed hours"),
    kpi("Labor GP %", pct(k["labor_gp_pct"]), k["labor_gp_pct"] - kp["labor_gp_pct"], delta_is_points=True),
    kpi("Parts GP %", pct(k["parts_gp_pct"]), k["parts_gp_pct"] - kp["parts_gp_pct"], delta_is_points=True),
    kpi("Hours per RO", num(k["hours_per_ro"], 2), d(k["hours_per_ro"], kp["hours_per_ro"])),
    kpi("Parts Margin Leakage", money(leak), d(leak, leak_prev), good_when_up=False, variant="alert",
        foot="GP lost below matrix"),
])

section("Trend")
days = c.filters.days
freq = "D" if days <= 35 else "W" if days <= 190 else "M"
tr = metrics.trend(c.cur.ros, freq)
grain = {"D": "day", "W": "week", "M": "month"}[freq]

left, right = st.columns([1.75, 1], gap="medium")
with left:
    with card("Sales & gross profit", f"Per {grain}, posted ROs"):
        fig = go.Figure()
        fig.add_bar(x=tr["period"], y=tr["sales"], name="Sales", marker_color=BLUE,
                    hovertemplate="%{x|%b %d, %Y}<br>Sales <b>%{y:$,.0f}</b><extra></extra>")
        fig.add_bar(x=tr["period"], y=tr["gross_profit"], name="Gross profit", marker_color=AQUA,
                    hovertemplate="%{x|%b %d, %Y}<br>Gross profit <b>%{y:$,.0f}</b><extra></extra>")
        fig.update_layout(barmode="group", yaxis_tickprefix="$", yaxis_tickformat="~s", hovermode="x unified")
        chart(fig, 340)
with right:
    with card("Key insights", "Generated from this period's data"):
        items = insights.generate(c)
        if not items:
            st.caption("Nothing unusual this period.")
        for lvl, title, body in items:
            insight(lvl, title, body)

c1, c2, c3 = st.columns(3, gap="medium")
with c1:
    with card("Sales mix", "Share of sales and gross profit % by type"):
        mix = metrics.sales_mix(c.cur.ros)
        mix = mix[mix["sales"] > 0].sort_values("sales")
        fig = go.Figure(go.Bar(
            x=mix["sales"], y=mix["type"], orientation="h", marker_color=BLUE,
            text=[f"{money(s)} · {pct(g, 0)} GP" for s, g in zip(mix["sales"], mix["gp_pct"])],
            textposition="outside", textfont=dict(color=TEXT_2, size=11), cliponaxis=False,
            hovertemplate="%{y}: <b>%{x:$,.0f}</b><extra></extra>",
        ))
        fig.update_layout(xaxis=dict(visible=False, range=[0, mix["sales"].max() * 1.6]), yaxis=dict(showgrid=False), margin=dict(r=10))
        chart(fig, 250)
with c2:
    with card("Gross profit % trend", f"Per {grain}"):
        fig = go.Figure(go.Scatter(x=tr["period"], y=tr["gp_pct"], mode="lines", line=dict(color=AQUA, width=2),
                                   fill="tozeroy", fillcolor="rgba(25,158,112,0.10)",
                                   hovertemplate="%{x|%b %d, %Y}<br>GP <b>%{y:.1%}</b><extra></extra>"))
        lo = max(0, tr["gp_pct"].min() - 0.05) if tr["gp_pct"].notna().any() else 0
        fig.update_layout(yaxis=dict(tickformat=".0%", range=[lo, min(1, tr["gp_pct"].max() + 0.03)]))
        chart(fig, 250)
with c3:
    with card("Car count & ARO", f"ROs per {grain} (bars) · average RO $ shown in hover"):
        fig = go.Figure(go.Bar(x=tr["period"], y=tr["car_count"], marker_color=ORANGE, customdata=tr["aro"],
                               hovertemplate="%{x|%b %d, %Y}<br>Car count <b>%{y}</b><br>ARO <b>%{customdata:$,.0f}</b><extra></extra>"))
        chart(fig, 250)

section("Who drove the period")
a1, a2 = st.columns(2, gap="medium")
with a1:
    with card("Gross profit by service advisor"):
        am = metrics.advisor_metrics(c.cur).sort_values("gross_profit")
        fig = go.Figure(go.Bar(x=am["gross_profit"], y=am["advisor"], orientation="h", marker_color=BLUE,
                               text=[money(v) for v in am["gross_profit"]], textposition="outside", cliponaxis=False,
                               textfont=dict(color=TEXT_2), hovertemplate="%{y}: <b>%{x:$,.0f}</b><extra></extra>"))
        fig.update_layout(xaxis=dict(visible=False, range=[0, am["gross_profit"].max() * 1.25]))
        chart(fig, 230)
with a2:
    with card("Labor gross profit by technician"):
        tm = metrics.tech_metrics(c.cur)
        if tm.empty:
            empty_state("Jobs & Labor Lines")
        else:
            tm = tm.sort_values("labor_gp")
            fig = go.Figure(go.Bar(x=tm["labor_gp"], y=tm["technician"], orientation="h", marker_color=YELLOW,
                                   text=[money(v) for v in tm["labor_gp"]], textposition="outside", cliponaxis=False,
                                   textfont=dict(color=TEXT_2), hovertemplate="%{y}: <b>%{x:$,.0f}</b><extra></extra>"))
            fig.update_layout(xaxis=dict(visible=False, range=[0, tm["labor_gp"].max() * 1.25]))
            chart(fig, 230)

learn("How these numbers are calculated", """
<b>Total sales</b> = labor + parts + sublet + fees − discounts on ROs <i>posted</i> (closed) in the period.<br>
<b>Gross profit</b> = sales − (technician labor cost + parts cost + sublet cost). <b>GP %</b> = gross profit ÷ sales.
Healthy independent shops typically target roughly 55–65% overall.<br>
<b>Car count</b> = number of posted ROs. <b>ARO</b> (average repair order) = sales ÷ ROs with a sale.<br>
<b>Effective labor rate (ELR)</b> = labor sales ÷ billed hours. Compare it to your posted door rate — the gap is
discounting, fleet pricing and goodwill.<br>
<b>Parts margin leakage</b> = gross profit lost on parts priced below your pricing matrix (details on Parts Profitability).<br>
Every arrow compares to the same number of days immediately before the selected period.
""")
