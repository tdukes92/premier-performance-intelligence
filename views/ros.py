import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ppi import metrics
from ppi.components import card, chart, empty_state, kpi, kpi_row, learn, money, num, page_header, pct, section
from ppi.state import analyzed_parts, ctx
from ppi.theme import AQUA, BLUE, CRITICAL, GOOD, MUTED, ORANGE, SURFACE, TEXT_2, YELLOW

c = ctx()
page_header("RO Profitability", "Which repair orders and job types make money — and which ones don't.", c.period_label, c.all.source)

r = c.cur.ros
if r.empty:
    empty_state("Repair Orders")
    st.stop()

target = st.session_state.get("ro_target", 0.50)
paid = r[r["total_sale"] > 0]
below = paid[paid["gp_pct"] < target]
neg = r[r["gross_profit"] < 0]
k, kp = metrics.kpis(c.cur), metrics.kpis(c.prev)

kpi_row([
    kpi("Posted ROs", num(len(r)), metrics.pct_change(len(r), len(c.prev.ros)), variant="accent"),
    kpi("Avg GP per RO", money(r["gross_profit"].mean(), short=False),
        metrics.pct_change(r["gross_profit"].mean(), c.prev.ros["gross_profit"].mean() if len(c.prev.ros) else float("nan"))),
    kpi("Median RO GP %", pct(paid["gp_pct"].median()), foot="Half of ROs are above this"),
    kpi(f"ROs Under {target:.0%} GP", num(len(below)), foot=f"{pct(len(below) / len(paid) if len(paid) else 0)} of paid ROs", good_when_up=False),
    kpi("Losing ROs", num(len(neg)), foot=f"{money(neg['gross_profit'].sum())} total loss (incl. comebacks)", variant="alert"),
])

section("Distribution")
d1, d2 = st.columns([1, 1.2], gap="medium")
with d1:
    with card("RO gross profit % distribution", "Number of ROs in each 5-point GP band", key="hist"):
        vals = paid["gp_pct"].clip(-0.2, 1.0)
        bins = np.arange(-0.2, 1.0001, 0.05)
        counts, edges = np.histogram(vals, bins=bins)
        mids = (edges[:-1] + edges[1:]) / 2
        colors = [CRITICAL if m < 0 else ORANGE if m < target else BLUE for m in mids]
        fig = go.Figure(go.Bar(x=mids, y=counts, width=0.045, marker_color=colors,
                               customdata=np.stack([edges[:-1], edges[1:]], axis=1),
                               hovertemplate="GP %{customdata[0]:.0%}–%{customdata[1]:.0%}<br><b>%{y} ROs</b><extra></extra>"))
        fig.add_vline(x=target, line=dict(color=MUTED, dash="dash", width=1),
                      annotation_text=f"Target {target:.0%}", annotation_font_color=TEXT_2, annotation_position="top left")
        fig.update_layout(xaxis=dict(tickformat=".0%"), yaxis_title="ROs", bargap=0)
        chart(fig, 320)
with d2:
    with card("RO size vs. margin", "Each dot is a repair order", key="scatter"):
        types = sorted(c.all.ros["customer_type"].dropna().unique())
        palette = {t: col for t, col in zip(types, [BLUE, ORANGE, AQUA])}
        fig = go.Figure()
        for t in types:
            s = paid[paid["customer_type"] == t]
            if s.empty:
                continue
            fig.add_scatter(x=s["total_sale"], y=s["gp_pct"], mode="markers", name=t,
                            marker=dict(size=7, color=palette.get(t, MUTED), opacity=0.65, line=dict(width=1, color=SURFACE)),
                            customdata=np.stack([s["ro_number"], s["advisor"], s["gross_profit"]], axis=1),
                            hovertemplate="RO %{customdata[0]} · %{customdata[1]}<br>Sale <b>%{x:$,.0f}</b><br>GP %{customdata[2]:$,.0f} (<b>%{y:.0%}</b>)<extra></extra>")
        fig.add_hline(y=target, line=dict(color=MUTED, dash="dash", width=1))
        fig.update_layout(xaxis=dict(type="log", title="RO total (log scale)", tickvals=[50, 100, 250, 500, 1000, 2500, 5000, 10000], ticktext=["$50", "$100", "$250", "$500", "$1K", "$2.5K", "$5K", "$10K"], showgrid=True, gridcolor="#1f2733"),
                          yaxis=dict(tickformat=".0%", range=[-0.2, 1]))
        chart(fig, 320)

section("By job type")
jobs = c.cur.jobs[c.cur.jobs["authorized"]].copy()
if jobs.empty:
    empty_state("Jobs & Labor Lines")
else:
    # Job-level gross profit: labor sale - tech pay + parts GP on that job.
    tc = c.all.timecards
    rates = tc.sort_values("date").groupby("technician")[["pay_type", "pay_rate"]].last() if not tc.empty else pd.DataFrame(columns=["pay_type", "pay_rate"])
    jobs = jobs.join(rates, on="technician")
    flat = jobs["pay_type"].fillna("").str.lower().str.startswith("flat")
    jobs["labor_cost"] = np.where(flat, jobs["hours_billed"], jobs["hours_worked"]) * jobs["pay_rate"].fillna(0)
    pa = analyzed_parts(c.cur)
    pj = pa.groupby("job_id").agg(parts_sale=("ext_price", "sum"), parts_gp=("gross_profit", "sum")) if not pa.empty else pd.DataFrame(columns=["parts_sale", "parts_gp"])
    jobs = jobs.join(pj, on="job_id").fillna({"parts_sale": 0, "parts_gp": 0})
    jobs["sales"] = jobs["labor_sale"] + jobs["parts_sale"]
    jobs["gp"] = jobs["labor_sale"] - jobs["labor_cost"] + jobs["parts_gp"]
    g = jobs.groupby("category").agg(jobs=("job_id", "count"), sales=("sales", "sum"), gp=("gp", "sum"),
                                     labor=("labor_sale", "sum"), parts=("parts_sale", "sum"), hours=("hours_billed", "sum"))
    g["gp_pct"] = g["gp"] / g["sales"].replace(0, np.nan)
    g["gp_per_job"] = g["gp"] / g["jobs"]
    g["gp_per_hour"] = g["gp"] / g["hours"].replace(0, np.nan)

    j1, j2 = st.columns([1.2, 1], gap="medium")
    with j1:
        with card("Gross profit by job category", "Labor + parts on authorized jobs", key="jobcat"):
            s = g.sort_values("gp")
            fig = go.Figure(go.Bar(x=s["gp"], y=s.index, orientation="h", marker_color=AQUA, customdata=s[["gp_pct", "jobs"]],
                                   text=[f"{money(v)} · {pct(p, 0)}" for v, p in zip(s["gp"], s["gp_pct"])],
                                   textposition="outside", cliponaxis=False, textfont=dict(color=TEXT_2, size=11),
                                   hovertemplate="%{y}<br>GP <b>%{x:$,.0f}</b> (%{customdata[0]:.0%})<br>%{customdata[1]} jobs<extra></extra>"))
            fig.update_layout(xaxis=dict(visible=False, range=[0, s["gp"].max() * 1.4]))
            chart(fig, 380)
    with j2:
        with card("Profit per billed hour", "Gross profit ÷ labor hours — which work pays best for bay time", key="gph"):
            s = g.dropna(subset=["gp_per_hour"]).sort_values("gp_per_hour")
            fig = go.Figure(go.Bar(x=s["gp_per_hour"], y=s.index, orientation="h", marker_color=YELLOW,
                                   text=[money(v, short=False) for v in s["gp_per_hour"]], textposition="outside", cliponaxis=False,
                                   textfont=dict(color=TEXT_2, size=11), hovertemplate="%{y}<br><b>%{x:$,.0f}</b> GP per hour<extra></extra>"))
            fig.update_layout(xaxis=dict(visible=False, range=[0, s["gp_per_hour"].max() * 1.3]))
            chart(fig, 380)

section("Low-profit RO review")
with card(None, key="lowro"):
    f1, f2, f3 = st.columns([1, 1, 2])
    new_target = f1.slider("GP % target", 20, 80, int(target * 100), step=5, format="%d%%")
    if new_target / 100 != target:
        st.session_state["ro_target"] = new_target / 100
        st.rerun()
    include_cb = f2.toggle("Include comebacks", value=False)
    review = r[(r["gp_pct"] < target) | (r["gross_profit"] < 0)]
    if not include_cb:
        review = review[~review["is_comeback"]]
    review = review.sort_values("gross_profit")
    f3.markdown(f"<div style='padding-top:1.9rem;color:{TEXT_2}'>{len(review):,} ROs below target · "
                f"{money((target * review['total_sale'] - review['gross_profit']).clip(lower=0).sum())} GP short of target</div>",
                unsafe_allow_html=True)
    cols = ["ro_number", "posted_date", "advisor", "customer_name", "customer_type", "vehicle_make", "labor_sale", "parts_sale",
            "discount", "total_sale", "total_cost", "gross_profit", "gp_pct", "is_comeback"]
    st.dataframe(review[cols], hide_index=True, width="stretch", height=380, column_config={
        "ro_number": "RO #", "posted_date": st.column_config.DateColumn("Posted", format="MMM D, YYYY"),
        "advisor": "Advisor", "customer_name": "Customer", "customer_type": "Type", "vehicle_make": "Make",
        "labor_sale": st.column_config.NumberColumn("Labor", format="dollar"),
        "parts_sale": st.column_config.NumberColumn("Parts", format="dollar"),
        "discount": st.column_config.NumberColumn("Discount", format="dollar"),
        "total_sale": st.column_config.NumberColumn("Total", format="dollar"),
        "total_cost": st.column_config.NumberColumn("Cost", format="dollar"),
        "gross_profit": st.column_config.NumberColumn("GP", format="dollar"),
        "gp_pct": st.column_config.NumberColumn("GP %", format="percent"),
        "is_comeback": st.column_config.CheckboxColumn("Comeback"),
    })
    st.download_button("Download (CSV)", review[cols].to_csv(index=False).encode(), file_name="low_profit_ros.csv", mime="text/csv")

section("RO inspector")
with card(None, key="inspector"):
    default = review["ro_number"].iloc[0] if len(review) else r["ro_number"].iloc[0]
    ro_list = r.sort_values("posted_date", ascending=False)["ro_number"].tolist()
    ro_id = st.selectbox("Look up an RO", ro_list, index=ro_list.index(default), help="Type to search by RO number")
    ro = r[r["ro_number"] == ro_id].iloc[0]
    i1, i2 = st.columns([1.1, 1], gap="medium")
    with i1:
        steps = [("Labor", ro["labor_sale"]), ("Parts", ro["parts_sale"]), ("Sublet", ro["sublet_sale"]), ("Fees", ro["fees"]),
                 ("Discount", -ro["discount"]), ("Labor cost", -ro["labor_cost"]), ("Parts cost", -ro["parts_cost"]),
                 ("Sublet cost", -ro["sublet_cost"])]
        steps = [(n, v) for n, v in steps if abs(v) > 0.005]
        fig = go.Figure(go.Waterfall(
            x=[n for n, _ in steps] + ["Gross profit"], y=[v for _, v in steps] + [ro["gross_profit"]],
            measure=["relative"] * len(steps) + ["total"],
            increasing=dict(marker=dict(color=BLUE)), decreasing=dict(marker=dict(color=ORANGE)),
            totals=dict(marker=dict(color=GOOD if ro["gross_profit"] >= 0 else CRITICAL)),
            connector=dict(line=dict(color="#2e3747", width=1)),
            text=[money(v, short=False) for _, v in steps] + [money(ro["gross_profit"], short=False)], textposition="outside",
            textfont=dict(color=TEXT_2, size=11), hovertemplate="%{x}: <b>%{y:$,.2f}</b><extra></extra>",
        ))
        fig.update_layout(yaxis=dict(tickprefix="$", tickformat="~s"), showlegend=False)
        st.markdown(f"**RO {ro_id}** · {ro['customer_name']} · {ro['vehicle_year']:.0f} {ro['vehicle_make']} · {ro['advisor']} · "
                    f"GP **{pct(ro['gp_pct'])}**" + (" · 🔁 comeback" if ro["is_comeback"] else ""))
        chart(fig, 300, key="waterfall")
    with i2:
        rj = c.cur.jobs[c.cur.jobs["ro_number"] == ro_id][["job_name", "category", "technician", "authorized", "hours_billed", "labor_sale", "job_total"]]
        st.markdown("**Jobs**")
        st.dataframe(rj, hide_index=True, width="stretch", column_config={
            "job_name": "Job", "category": "Category", "technician": "Tech",
            "authorized": st.column_config.CheckboxColumn("Sold"), "hours_billed": st.column_config.NumberColumn("Hrs", format="%.1f"),
            "labor_sale": st.column_config.NumberColumn("Labor", format="dollar"),
            "job_total": st.column_config.NumberColumn("Quoted", format="dollar"),
        })
        rp = analyzed_parts(c.cur)
        rp = rp[rp["ro_number"] == ro_id][["description", "quantity", "unit_cost", "unit_price", "target_unit_price", "reason"]] if not rp.empty else rp
        st.markdown("**Parts**")
        st.dataframe(rp, hide_index=True, width="stretch", column_config={
            "description": "Part", "quantity": st.column_config.NumberColumn("Qty", format="%.0f"),
            "unit_cost": st.column_config.NumberColumn("Cost", format="dollar"),
            "unit_price": st.column_config.NumberColumn("Sold @", format="dollar"),
            "target_unit_price": st.column_config.NumberColumn("Matrix @", format="dollar"), "reason": "Pricing check",
        })

learn("Reading RO profitability", """
<b>RO gross profit</b> = everything the customer paid (labor, parts, sublet, fees, minus discounts) minus what it cost
the shop (technician pay for the hours on the RO, parts cost, sublet cost).<br><br>
<b>Why look at individual ROs?</b> Shop-wide averages hide problems. A handful of ROs written at 20% GP — usually from
heavy discounting, a big under-priced part, or a comeback — can drag the month down. Use the review table and the
inspector to find the cause, then fix the process (price override approvals, matrix, discount policy).<br><br>
<b>Profit per billed hour</b> shows which work earns the most for the bay time it uses. High-GP-per-hour work is what to
promote in inspections and marketing.
""")
