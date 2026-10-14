import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ppi import metrics
from ppi.components import card, chart, empty_state, kpi, kpi_row, learn, money, num, page_header, pct, section
from ppi.state import ctx
from ppi.theme import AQUA, BLUE, MUTED, SERIES, TEXT_2, VIOLET, YELLOW

c = ctx()
page_header("Technician Profitability", "Hours, efficiency, and the gross profit each technician produces versus what they're paid.", c.period_label, c.all.source)

tm = metrics.tech_metrics(c.cur)
if tm.empty:
    empty_state("Jobs & Labor Lines and Technician Timecards")
    st.stop()
tp = metrics.tech_metrics(c.prev)


def tot(df: pd.DataFrame) -> dict:
    if df.empty:
        return {k: float("nan") for k in ["billed", "eff", "prod", "prof", "gp", "gp_pct", "cb"]}
    b, w, a = df["hours_billed"].sum(), df["hours_worked"].sum(), df["hours_available"].sum()
    return {"billed": b, "eff": b / w if w else float("nan"), "prod": w / a if a else float("nan"),
            "prof": b / a if a else float("nan"), "gp": df["labor_gp"].sum(),
            "gp_pct": df["labor_gp"].sum() / df["labor_sales"].sum() if df["labor_sales"].sum() else float("nan"),
            "cb": df["comebacks"].sum() / df["ros"].sum() if df["ros"].sum() else float("nan")}


t, p = tot(tm), tot(tp)
d = metrics.pct_change
kpi_row([
    kpi("Hours Billed", num(t["billed"]), d(t["billed"], p["billed"]), variant="accent"),
    kpi("Shop Efficiency", pct(t["eff"], 0), t["eff"] - p["eff"], delta_is_points=True, foot="Billed ÷ worked"),
    kpi("Productivity", pct(t["prod"], 0), t["prod"] - p["prod"], delta_is_points=True, foot="Worked ÷ available"),
    kpi("Proficiency", pct(t["prof"], 0), t["prof"] - p["prof"], delta_is_points=True, foot="Billed ÷ available"),
    kpi("Labor Gross Profit", money(t["gp"]), d(t["gp"], p["gp"]), foot=f"{pct(t['gp_pct'])} of labor sales"),
    kpi("Comeback Rate", pct(t["cb"]), t["cb"] - p["cb"], good_when_up=False, delta_is_points=True),
])

section("Productivity triangle")
c1, c2 = st.columns([1.25, 1], gap="medium")
order = tm.sort_values("proficiency", ascending=False)["technician"].tolist()
with c1:
    with card("Efficiency · productivity · proficiency", "Dashed line = 100%. Above the line is better.", key="tri"):
        fig = go.Figure()
        for name, col, color in [("Efficiency", "efficiency", BLUE), ("Productivity", "productivity", AQUA), ("Proficiency", "proficiency", YELLOW)]:
            s = tm.set_index("technician").reindex(order)[col]
            fig.add_bar(x=order, y=s, name=name, marker_color=color,
                        hovertemplate=f"%{{x}}<br>{name} <b>%{{y:.0%}}</b><extra></extra>")
        fig.add_hline(y=1, line=dict(color=MUTED, width=1, dash="dash"))
        fig.update_layout(barmode="group", yaxis=dict(tickformat=".0%"))
        chart(fig, 340)
with c2:
    with card("Where labor dollars go", "Labor sales split into technician pay and labor gross profit", key="split"):
        s = tm.sort_values("labor_sales")
        fig = go.Figure()
        fig.add_bar(y=s["technician"], x=s["pay_cost"], name="Tech pay", orientation="h", marker_color="#2e3747",
                    marker_line=dict(color="#111722", width=2),
                    hovertemplate="%{y}<br>Pay <b>%{x:$,.0f}</b><extra></extra>")
        fig.add_bar(y=s["technician"], x=s["labor_gp"], name="Labor gross profit", orientation="h", marker_color=AQUA,
                    marker_line=dict(color="#111722", width=2), customdata=s["labor_gp_pct"],
                    text=[pct(v, 0) for v in s["labor_gp_pct"]], textposition="inside", insidetextanchor="end",
                    textfont=dict(color="#0a0e14", size=11),
                    hovertemplate="%{y}<br>Labor GP <b>%{x:$,.0f}</b> (%{customdata:.0%})<extra></extra>")
        fig.update_layout(barmode="stack", xaxis=dict(tickprefix="$", tickformat="~s", showgrid=True, gridcolor="#1f2733"),
                          yaxis=dict(showgrid=False))
        fig.update_traces(marker_cornerradius=0, selector=dict(type="bar"))
        chart(fig, 340)

section("Technician scorecard")
with card(None, key="scorecard"):
    cols = ["technician", "pay_type", "pay_rate", "hours_available", "hours_worked", "hours_billed", "efficiency",
            "productivity", "proficiency", "billed_per_day", "labor_sales", "pay_cost", "labor_gp", "labor_gp_pct", "elr",
            "comebacks", "comeback_rate"]
    st.dataframe(tm[cols], hide_index=True, width="stretch", column_config={
        "technician": st.column_config.TextColumn("Technician", pinned=True), "pay_type": "Pay plan",
        "pay_rate": st.column_config.NumberColumn("Rate", format="dollar"),
        "hours_available": st.column_config.NumberColumn("Avail hrs", format="%,.1f"),
        "hours_worked": st.column_config.NumberColumn("Worked hrs", format="%,.1f"),
        "hours_billed": st.column_config.NumberColumn("Billed hrs", format="%,.1f"),
        "efficiency": st.column_config.NumberColumn("Efficiency", format="percent"),
        "productivity": st.column_config.NumberColumn("Productivity", format="percent"),
        "proficiency": st.column_config.NumberColumn("Proficiency", format="percent"),
        "billed_per_day": st.column_config.NumberColumn("Billed hrs/day", format="%.1f"),
        "labor_sales": st.column_config.NumberColumn("Labor sales", format="dollar", step=1),
        "pay_cost": st.column_config.NumberColumn("Pay cost", format="dollar", step=1),
        "labor_gp": st.column_config.NumberColumn("Labor GP", format="dollar", step=1),
        "labor_gp_pct": st.column_config.NumberColumn("Labor GP %", format="percent"),
        "elr": st.column_config.NumberColumn("ELR", format="dollar"),
        "comebacks": st.column_config.NumberColumn("Comebacks", format="%d"),
        "comeback_rate": st.column_config.NumberColumn("Comeback %", format="percent"),
    })

section("Trend & drill-down")
t1, t2 = st.columns([1.3, 1], gap="medium")
with t1:
    with card("Billed hours per week", "By technician", key="weekly"):
        j = c.cur.jobs[c.cur.jobs["authorized"] & c.cur.jobs["technician"].notna()].merge(c.cur.ros[["ro_number", "posted_date"]], on="ro_number")
        wk = j.groupby([pd.Grouper(key="posted_date", freq="W-MON", label="left", closed="left"), "technician"])["hours_billed"].sum().reset_index()
        fig = go.Figure()
        all_techs = sorted(c.all.jobs["technician"].dropna().unique())  # color follows the tech, not their rank
        for tech in sorted(wk["technician"].unique()):
            s = wk[wk["technician"] == tech]
            fig.add_scatter(x=s["posted_date"], y=s["hours_billed"], mode="lines", name=tech,
                            line=dict(color=SERIES[all_techs.index(tech) % len(SERIES)]),
                            hovertemplate=f"{tech}<br>%{{x|Week of %b %d}}<br><b>%{{y:.1f}} hrs</b><extra></extra>")
        fig.update_layout(hovermode="x unified", yaxis_title="Billed hours")
        chart(fig, 330)
with t2:
    with card("Technician drill-down", key="drill"):
        tech = st.selectbox("Technician", order, label_visibility="collapsed")
        tj = c.cur.jobs[(c.cur.jobs["technician"] == tech) & c.cur.jobs["authorized"]]
        g = tj.groupby("category").agg(billed=("hours_billed", "sum"), worked=("hours_worked", "sum"), jobs=("job_id", "count"))
        g["eff"] = g["billed"] / g["worked"]
        g = g.sort_values("billed")
        colors = [AQUA if e >= 1 else VIOLET for e in g["eff"]]
        fig = go.Figure(go.Bar(x=g["billed"], y=g.index, orientation="h", marker_color=colors, customdata=g[["eff", "jobs"]],
                               text=[f"{e:.0%} eff" for e in g["eff"]], textposition="outside", cliponaxis=False,
                               textfont=dict(color=TEXT_2, size=11),
                               hovertemplate="%{y}<br>%{x:.1f} billed hrs · %{customdata[1]} jobs<br>Efficiency <b>%{customdata[0]:.0%}</b><extra></extra>"))
        fig.update_layout(xaxis=dict(title="Billed hours", range=[0, g["billed"].max() * 1.3 if len(g) else 1]))
        chart(fig, 285)
        st.caption("Billed hours by job category. Green = beats book time (≥100% efficiency), violet = slower than book.")

learn("Efficiency, productivity and proficiency explained", """
Three hour counts tell you almost everything about a technician:<br>
• <b>Available</b> — hours clocked in for the day (from timecards).<br>
• <b>Worked</b> — hours actually clocked onto repair orders.<br>
• <b>Billed</b> (flagged) — labor hours charged to the customer, usually from labor-guide book time.<br><br>
<b>Efficiency = billed ÷ worked.</b> 120% means a 1.0-hour job takes them 50 minutes. Low efficiency = skills, tools or comebacks.<br>
<b>Productivity = worked ÷ available.</b> How much of the day they're on cars. Low productivity is usually a
<i>shop</i> problem: waiting on parts, approvals, or not enough work dispatched.<br>
<b>Proficiency = billed ÷ available.</b> The bottom line — billed hours per hour you pay them to be there.<br><br>
<b>Pay cost:</b> flat-rate techs are paid per billed hour; hourly techs are paid for every available hour.
<b>Labor gross profit</b> = labor sales − pay cost (before payroll taxes and benefits).
""")
