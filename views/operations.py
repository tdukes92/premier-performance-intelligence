import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ppi import metrics
from ppi.components import card, chart, empty_state, kpi, kpi_row, learn, money, num, page_header, pct, section
from ppi.state import ctx
from ppi.theme import AQUA, BLUE, MUTED, ORANGE, SEQUENTIAL_BLUE, TEXT_2, VIOLET

c = ctx()
page_header("Operational Insights", "Workflow, capacity, work in progress and follow-up opportunities.", c.period_label, c.all.source)

r = c.cur.ros
if r.empty:
    empty_state("Repair Orders")
    st.stop()

now = pd.Timestamp.now()
wip = c.all.ros[c.all.ros["is_open"]].copy()
wip["days_open"] = (now - wip["opened_at"]).dt.total_seconds() / 86400
k, kp = metrics.kpis(c.cur), metrics.kpis(c.prev)
waiter = r["waiter"].mean() if r["waiter"].any() else float("nan")
same_day = (r["cycle_days"] < 1).mean()
p_same = (c.prev.ros["cycle_days"] < 1).mean() if len(c.prev.ros) else float("nan")

kpi_row([
    kpi("Open ROs (WIP)", num(len(wip)), foot=f"{money(wip['total_sale'].sum())} not yet invoiced", variant="accent"),
    kpi("Avg Cycle Time", f"{k['avg_cycle_days']:.1f} days", metrics.pct_change(k["avg_cycle_days"], kp["avg_cycle_days"]),
        good_when_up=False, foot="Opened → posted"),
    kpi("Same-Day Completion", pct(same_day, 0), same_day - p_same, delta_is_points=True),
    kpi("Comeback Rate", pct(k["comeback_rate"]), k["comeback_rate"] - kp["comeback_rate"], good_when_up=False, delta_is_points=True),
    kpi("Waiters", pct(waiter, 0), foot="Customers who waited on-site"),
])

section("Capacity & flow")
o1, o2 = st.columns([1.35, 1], gap="medium")
with o1:
    with card("When cars arrive", "ROs opened by weekday and hour — staff the counter and dispatch accordingly", key="heat"):
        h = r.assign(dow=r["opened_at"].dt.dayofweek, hour=r["opened_at"].dt.hour)
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        hours = list(range(int(h["hour"].min()), int(h["hour"].max()) + 1))
        pv = h.pivot_table(index="dow", columns="hour", values="ro_number", aggfunc="count").reindex(index=range(7), columns=hours).fillna(0)
        pv = pv.loc[pv.sum(axis=1) > 0]
        n_weeks = max(1, c.filters.days / 7)
        z = pv.to_numpy() / n_weeks
        fig = go.Figure(go.Heatmap(
            z=z, x=[f"{hh % 12 or 12}{'a' if hh < 12 else 'p'}" for hh in hours], y=[days[i] for i in pv.index],
            colorscale=[[i / (len(SEQUENTIAL_BLUE) - 1), col] for i, col in enumerate(SEQUENTIAL_BLUE)],
            xgap=2, ygap=2, colorbar=dict(title=dict(text="ROs/wk", font=dict(color=MUTED, size=11)), tickfont=dict(color=MUTED), thickness=10),
            hovertemplate="%{y} %{x}<br><b>%{z:.1f} ROs</b> per week<extra></extra>",
        ))
        fig.update_layout(yaxis=dict(autorange="reversed", showgrid=False), xaxis=dict(showgrid=False))
        chart(fig, 300)
with o2:
    with card("Cycle time", "Share of ROs by days from open to posted", key="cycle"):
        b = pd.cut(r["cycle_days"], [-0.01, 1, 2, 4, 7, 1e9], labels=["Same day", "1 day", "2–3 days", "4–6 days", "7+ days"])
        dist = b.value_counts(normalize=True).reindex(b.cat.categories).fillna(0)
        fig = go.Figure(go.Bar(x=list(dist.index), y=dist.values, marker_color=BLUE, text=[pct(v, 0) for v in dist.values],
                               textposition="outside", cliponaxis=False, textfont=dict(color=TEXT_2),
                               hovertemplate="%{x}: <b>%{y:.1%}</b> of ROs<extra></extra>"))
        fig.update_layout(yaxis=dict(visible=False, range=[0, dist.max() * 1.25]))
        chart(fig, 300)

section("Work in progress")
with card(f"Open repair orders · {len(wip)}", "Oldest first — anything over 3 days needs a status update to the customer", key="wip"):
    if wip.empty:
        st.caption("No open ROs.")
    else:
        wip["status"] = np.select([wip["days_open"] >= 5, wip["days_open"] >= 3], ["🔴 5+ days", "🟠 3–4 days"], "🟢 On track")
        st.dataframe(wip.sort_values("days_open", ascending=False)[
            ["status", "ro_number", "opened_at", "days_open", "advisor", "customer_name", "vehicle_make", "total_sale"]],
            hide_index=True, width="stretch", height=min(380, 40 + 35 * len(wip)), column_config={
                "status": "Status", "ro_number": "RO #", "opened_at": st.column_config.DatetimeColumn("Opened", format="MMM D, h:mm a"),
                "days_open": st.column_config.NumberColumn("Days open", format="%.1f"), "advisor": "Advisor",
                "customer_name": "Customer", "vehicle_make": "Make", "total_sale": st.column_config.NumberColumn("RO value", format="dollar"),
            })

section("Opportunities")
p1, p2 = st.columns(2, gap="medium")
with p1:
    with card("Declined work by category", "Recommended but not approved — your follow-up call list", key="declined"):
        jobs = c.cur.jobs
        if jobs.empty:
            empty_state("Jobs & Labor Lines")
        else:
            dec = jobs[~jobs["authorized"]].groupby("category").agg(value=("job_total", "sum"), jobs=("job_id", "count")).sort_values("value")
            fig = go.Figure(go.Bar(x=dec["value"], y=dec.index, orientation="h", marker_color=VIOLET, customdata=dec["jobs"],
                                   text=[f"{money(v)} · {n} jobs" for v, n in zip(dec["value"], dec["jobs"])], textposition="outside",
                                   cliponaxis=False, textfont=dict(color=TEXT_2, size=11),
                                   hovertemplate="%{y}<br><b>%{x:$,.0f}</b> declined on %{customdata} jobs<extra></extra>"))
            fig.update_layout(xaxis=dict(visible=False, range=[0, dec["value"].max() * 1.5 if len(dec) else 1]))
            chart(fig, 360)
            # Follow-up list
            dj = jobs[~jobs["authorized"]].merge(r[["ro_number", "posted_date", "customer_name", "advisor", "vehicle_make"]], on="ro_number")
            st.download_button("Download declined-work follow-up list (CSV)",
                               dj.sort_values("job_total", ascending=False)[["posted_date", "ro_number", "customer_name", "vehicle_make", "advisor", "job_name", "category", "job_total"]].to_csv(index=False).encode(),
                               file_name="declined_work_followup.csv", mime="text/csv")
with p2:
    with card("Comebacks by job category", "Comeback ROs, by the category of the redone job", key="cb"):
        cb_ros = r[r["is_comeback"]]
        if cb_ros.empty or c.cur.jobs.empty:
            st.caption("No comebacks in this period. 🎉")
        else:
            cbj = c.cur.jobs[c.cur.jobs["ro_number"].isin(cb_ros["ro_number"])]
            cnt = cbj.groupby("category")["ro_number"].nunique().sort_values()
            fig = go.Figure(go.Bar(x=cnt.values, y=cnt.index, orientation="h", marker_color=ORANGE, text=cnt.values,
                                   textposition="outside", cliponaxis=False, textfont=dict(color=TEXT_2),
                                   hovertemplate="%{y}: <b>%{x}</b> comebacks<extra></extra>"))
            fig.update_layout(xaxis=dict(visible=False, range=[0, cnt.max() * 1.3]))
            chart(fig, 230)
            st.caption(f"Comebacks cost {money(-cb_ros['gross_profit'].sum(), short=False)} in unpaid labor and parts this period.")

section("Customer & vehicle mix")
v1, v2 = st.columns(2, gap="medium")
with v1:
    with card("Car count & ARO by make", "Top 10 makes by visits", key="makes"):
        mk = r.groupby("vehicle_make").agg(ros=("ro_number", "count"), aro=("total_sale", "mean")).sort_values("ros", ascending=False).head(10)
        mk = mk.sort_values("ros")
        fig = go.Figure(go.Bar(x=mk["ros"], y=mk.index, orientation="h", marker_color=AQUA, customdata=mk["aro"],
                               text=[f"{n} · ARO {money(a)}" for n, a in zip(mk["ros"], mk["aro"])], textposition="outside",
                               cliponaxis=False, textfont=dict(color=TEXT_2, size=11),
                               hovertemplate="%{y}<br><b>%{x}</b> ROs · ARO %{customdata:$,.0f}<extra></extra>"))
        fig.update_layout(xaxis=dict(visible=False, range=[0, mk["ros"].max() * 1.55]))
        chart(fig, 340)
with v2:
    with card("ARO by vehicle age", "Older vehicles need more work — and are often your best customers", key="age"):
        ref_year = r["posted_date"].dt.year.max()
        age = (ref_year - r["vehicle_year"]).where(r["vehicle_year"] > 1900)
        bucket = pd.cut(age, [-1, 3, 6, 10, 15, 100], labels=["0–3 yrs", "4–6 yrs", "7–10 yrs", "11–15 yrs", "16+ yrs"])
        ag = r.assign(bucket=bucket).dropna(subset=["bucket"]).groupby("bucket", observed=False).agg(
            aro=("total_sale", "mean"), ros=("ro_number", "count"))
        fig = go.Figure(go.Bar(x=list(ag.index.astype(str)), y=ag["aro"], marker_color=BLUE, customdata=ag["ros"],
                               text=[money(v) for v in ag["aro"]], textposition="outside", cliponaxis=False, textfont=dict(color=TEXT_2),
                               hovertemplate="%{x}<br>ARO <b>%{y:$,.0f}</b> · %{customdata} ROs<extra></extra>"))
        fig.update_layout(yaxis=dict(visible=False, range=[0, ag["aro"].max() * 1.25]))
        chart(fig, 340)

learn("Operational metrics explained", """
<b>Cycle time</b> — days from RO creation to posting. Long cycle times tie up bays and delay cash.<br>
<b>WIP</b> (work in progress) — ROs opened but not yet invoiced. Aging WIP is usually waiting on parts,
approval, or a sublet — and customers waiting for updates.<br>
<b>Comebacks</b> — vehicles returned to fix work already done. Each costs labor and parts at no charge and
risks the customer relationship.<br>
<b>Declined work</b> — recommended repairs the customer said no to. A structured follow-up call or text
within 30–90 days typically recovers a meaningful share of it.
""")
