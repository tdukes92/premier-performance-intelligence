import html
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ppi import metrics
from ppi import reviews as rv
from ppi.components import card, chart, insight, kpi, kpi_row, learn, num, page_header, pct, section
from ppi.state import ctx
from ppi.theme import AQUA, MUTED, RED, SERIES, STAR, SURFACE, TEXT_2

c = ctx()
page_header("Customer Reputation & Reviews", "Ratings, review volume, response status and what customers are saying — every platform in one place.",
            c.period_label, "sample")

all_reviews = rv.load(date.today())
cur = rv.in_period(all_reviews, c.filters.start, c.filters.end)
prev = rv.in_period(all_reviews, c.filters.prior().start, c.filters.prior().end)
s, sp = rv.summary(cur), rv.summary(prev)
now = pd.Timestamp.now()
open_alerts = rv.alerts(all_reviews, now)
platforms = [p for p in rv.PLATFORMS if p in set(all_reviews["platform"])] + sorted(set(all_reviews["platform"]) - set(rv.PLATFORMS))
pcolor = {p: SERIES[i % len(SERIES)] for i, p in enumerate(platforms)}  # color follows the platform

if c.filters.advisors or c.filters.customer_types:
    st.caption("ℹ️ Advisor and customer-type filters don't apply to reviews — only the period does.")


def stars(rating: float) -> str:
    full = int(round(rating)) if rating == rating else 0
    return f'<span class="ppi-stars">{"★" * full}<span class="off">{"★" * (5 - full)}</span></span>'


def hours_label(h: float) -> str:
    return "—" if h != h else f"{h:.0f} hrs" if h < 48 else f"{h / 24:.1f} days"


kpi_row([
    kpi("Average Rating", f"{s['avg_rating']:.2f} ★" if s["count"] else "—", foot=(f"Prior period {sp['avg_rating']:.2f} ★" if sp["count"] else "All platforms"), variant="accent"),
    kpi("New Reviews", num(s["count"]), metrics.pct_change(s["count"], sp["count"])),
    kpi("4–5 Star Share", pct(s["pct_positive"], 0), s["pct_positive"] - sp["pct_positive"], delta_is_points=True),
    kpi("Response Rate", pct(s["response_rate"], 0), s["response_rate"] - sp["response_rate"], delta_is_points=True,
        foot=f"Negative reviews: {pct(s['negative_response_rate'], 0)}"),
    kpi("Median Response Time", hours_label(s["median_response_hours"]),
        metrics.pct_change(s["median_response_hours"], sp["median_response_hours"]), good_when_up=False),
    kpi("Open Negative Alerts", num(int((open_alerts["rating"] <= rv.NEGATIVE_MAX).sum())), variant="alert",
        foot=f"{int((open_alerts['severity'] == 'critical').sum())} past {rv.RESPONSE_SLA_HOURS}h without a reply"),
])

# --- Executive summary + alerts ------------------------------------------------------
section("Executive summary")
comp = rv.theme_table(cur, prev, "complaint")
praise = rv.theme_table(cur, prev, "compliment")
staff_names = sorted({n.split()[0] for n in pd.concat([c.all.ros["advisor"], c.all.jobs["technician"]]).dropna().unique()})
staff = rv.staff_mentions(cur, staff_names)

left, right = st.columns([1.35, 1], gap="medium")
with left:
    with card("What customers are saying", "Generated from the review text for this period", key="rev_summary"):
        if cur.empty:
            st.caption("No reviews in this period.")
        else:
            e = html.escape
            by_plat = cur.groupby("platform")["rating"].agg(["mean", "count"])
            low_plat = by_plat[by_plat["count"] >= 3]["mean"].idxmin() if (by_plat["count"] >= 3).any() else None
            delta = s["avg_rating"] - sp["avg_rating"] if sp["count"] else float("nan")
            trend_txt = "" if delta != delta else (f", {'up' if delta >= 0 else 'down'} {abs(delta):.2f} from {sp['avg_rating']:.2f} ★ in the prior period")
            paras = [f"<p>Across <b>{int(s['count'])} reviews</b> on {cur['platform'].nunique()} platforms, customers rated the shop "
                     f"<b>{s['avg_rating']:.2f} ★</b>{trend_txt}. <b>{pct(s['pct_positive'], 0)}</b> were 4–5 stars and "
                     f"<b>{int(s['negatives'])}</b> were 1–2 stars.</p>"]
            top_p = praise[praise["mentions"] > 0].head(3)
            if len(top_p):
                items = ", ".join(f"<b>{e(t.lower())}</b> ({pct(sh, 0)} of reviews)" for t, sh in zip(top_p["theme"], top_p["share"]))
                staff_txt = ""
                good_staff = staff[staff["avg_rating"] >= 4]
                if len(good_staff):
                    g = good_staff.iloc[0]
                    staff_txt = f" <b>{e(g['name'])}</b> is the most-praised team member by name ({int(g['mentions'])} mentions, avg {g['avg_rating']:.1f} ★)."
                paras.append(f"<p>👍 <b>Compliments:</b> customers most often praise {items}.{staff_txt}</p>")
            top_c = comp[comp["mentions"] > 0]
            if len(top_c):
                t0 = top_c.iloc[0]
                rising = top_c.sort_values("change_pts", ascending=False).iloc[0]
                rise_txt = (f" <b>{e(rising['theme'])}</b> is rising fastest — mentioned in {pct(rising['share'], 0)} of reviews vs "
                            f"{pct(rising['prev_share'], 0)} in the prior period." if rising["change_pts"] > 0.01 else "")
                paras.append(f"<p>👎 <b>Complaints:</b> the top issue is <b>{e(t0['theme'].lower())}</b> ({int(t0['mentions'])} mentions, "
                             f"those reviews average {t0['avg_rating']:.1f} ★).{rise_txt}</p>")
            bad_staff = staff[staff["negative"] > 0].sort_values("negative", ascending=False)
            actions = []
            n_crit = int((open_alerts["severity"] == "critical").sum())
            if n_crit:
                actions.append(f"reply to the <b>{n_crit}</b> negative review{'s' if n_crit != 1 else ''} waiting more than {rv.RESPONSE_SLA_HOURS} hours")
            if low_plat and by_plat.loc[low_plat, "mean"] < s["avg_rating"] - 0.15:
                actions.append(f"look at <b>{e(low_plat)}</b>, the lowest-rated platform ({by_plat.loc[low_plat, 'mean']:.2f} ★)")
            if len(bad_staff):
                b = bad_staff.iloc[0]
                actions.append(f"coach on the {int(b['negative'])} negative review{'s' if b['negative'] != 1 else ''} naming <b>{e(b['name'])}</b>")
            if actions:
                paras.append("<p>🎯 <b>Next steps:</b> " + "; ".join(actions) + ".</p>")
            st.markdown(f'<div class="ppi-summary">{"".join(paras)}</div>', unsafe_allow_html=True)

with right:
    with card(f"Negative review alerts · {len(open_alerts)}", f"Unanswered reviews of 3★ or less, all dates. Goal: reply within {rv.RESPONSE_SLA_HOURS} hours.", key="rev_alerts"):
        if open_alerts.empty:
            insight("good", "All caught up", "Every 1–3 star review has a response.")
        for _, a in open_alerts.head(3).iterrows():
            snippet = a["text"] if len(a["text"]) <= 110 else a["text"][:107].rsplit(" ", 1)[0] + "…"
            insight(a["severity"], f"{a['rating']}★ on {a['platform']} · {a['reviewer']} · {hours_label(a['age_hours'])} unanswered", snippet)
        if len(open_alerts) > 3:
            st.caption(f"+ {len(open_alerts) - 3} more — filter the review feed below by “Awaiting response”.")

t1, t2 = st.columns(2, gap="medium")


def theme_chart(tbl: pd.DataFrame, color: str, key: str):
    t = tbl[tbl["mentions"] > 0].sort_values("mentions")
    if t.empty:
        st.caption("No mentions this period.")
        return
    labels = [f"{int(m)} · {'▲' if ch > 0.005 else '▼' if ch < -0.005 else '▬'} {abs(ch) * 100:.0f} pts" for m, ch in zip(t["mentions"], t["change_pts"])]
    fig = go.Figure(go.Bar(x=t["mentions"], y=t["theme"], orientation="h", marker_color=color, text=labels, textposition="outside",
                           cliponaxis=False, textfont=dict(color=TEXT_2, size=11), customdata=t[["share", "avg_rating", "prev_share"]],
                           hovertemplate="%{y}<br><b>%{x} mentions</b> (%{customdata[0]:.0%} of reviews)<br>"
                                         "Avg rating %{customdata[1]:.1f} ★<br>Prior period %{customdata[2]:.0%} of reviews<extra></extra>"))
    fig.update_layout(xaxis=dict(visible=False, range=[0, t["mentions"].max() * 1.5]))
    chart(fig, 300, key=key)


with t1:
    with card("Complaint themes", "Mentions this period · change in share of reviews vs prior period", key="rev_complaints"):
        theme_chart(comp, RED, "complaints_chart")
with t2:
    with card("Compliment themes", "Mentions this period · change in share of reviews vs prior period", key="rev_compliments"):
        theme_chart(praise, AQUA, "compliments_chart")

# --- Ratings by platform -----------------------------------------------------------
section("Ratings by platform")
tiles = []
allt = all_reviews[all_reviews["posted_date"] <= pd.Timestamp(c.filters.end)]
for p in ["All platforms", *platforms]:
    pc = cur if p == "All platforms" else cur[cur["platform"] == p]
    pa = allt if p == "All platforms" else allt[allt["platform"] == p]
    dot = "" if p == "All platforms" else f'<span class="dot" style="background:{pcolor[p]}"></span>'
    rating = pc["rating"].mean() if len(pc) else float("nan")
    tiles.append(
        f'<div class="ppi-plat"><div class="name">{dot}{html.escape(p)}</div>'
        f'<div class="big">{"—" if rating != rating else f"{rating:.2f}"}</div>{stars(rating)}'
        f'<div class="meta">{len(pc)} reviews this period · {pct(pc["responded"].mean() if len(pc) else float("nan"), 0)} answered</div>'
        f'<div class="meta">Lifetime {pa["rating"].mean():.2f} ★ · {len(pa):,} reviews</div></div>'
    )
kpi_row(tiles)

# --- Volume & rating over time ------------------------------------------------------------
section("Trends")
days = c.filters.days
freq = "W-MON" if days <= 190 else "MS"
grain = "week" if freq == "W-MON" else "month"
v1, v2 = st.columns([1.35, 1], gap="medium")
with v1:
    with card("Review volume", f"New reviews per {grain}, by platform", key="rev_volume"):
        g = cur.groupby([pd.Grouper(key="posted_date", freq=freq, label="left", closed="left"), "platform"]).size().unstack(fill_value=0)
        fig = go.Figure()
        for p in platforms:
            if p in g:
                fig.add_bar(x=g.index, y=g[p], name=p, marker=dict(color=pcolor[p], line=dict(color=SURFACE, width=2), cornerradius=0),
                            hovertemplate=f"{p}<br>%{{x|%b %d, %Y}}: <b>%{{y}}</b> reviews<extra></extra>")
        fig.update_layout(barmode="stack", hovermode="x unified", yaxis_title="Reviews", legend=dict(traceorder="normal"))
        chart(fig, 300)
with v2:
    with card("Average rating trend", "All platforms · rolling 30-day average (smooths out slow weeks)", key="rev_rating_trend"):
        daily = all_reviews.groupby("posted_date")["rating"].agg(["sum", "count"]).asfreq("D", fill_value=0)
        roll = daily.rolling(30, min_periods=1).sum()
        t = pd.DataFrame({"avg": roll["sum"] / roll["count"].replace(0, float("nan")), "n": roll["count"]})
        t = t.loc[pd.Timestamp(c.filters.start):pd.Timestamp(c.filters.end)].reset_index(names="day")
        fig = go.Figure(go.Scatter(x=t["day"], y=t["avg"], mode="lines", line=dict(color=STAR, width=2), customdata=t["n"],
                                   hovertemplate="30 days to %{x|%b %d, %Y}<br><b>%{y:.2f} ★</b> from %{customdata:.0f} reviews<extra></extra>"))
        lo = max(1, min(4.0, t["avg"].min() - 0.2)) if t["avg"].notna().any() else 1
        fig.update_layout(yaxis=dict(range=[lo, 5.0], title="Stars"))
        chart(fig, 300)

d1, d2 = st.columns(2, gap="medium")
with d1:
    with card("Star distribution", "This period", key="rev_dist"):
        dist = cur["rating"].value_counts().reindex([5, 4, 3, 2, 1], fill_value=0)
        share = dist / max(dist.sum(), 1)
        fig = go.Figure(go.Bar(x=dist.values, y=[f"{i} ★" for i in dist.index], orientation="h", marker_color=STAR,
                               text=[f"{v} · {sh:.0%}" for v, sh in zip(dist.values, share)], textposition="outside", cliponaxis=False,
                               textfont=dict(color=TEXT_2), hovertemplate="%{y}: <b>%{x}</b> reviews<extra></extra>"))
        fig.update_layout(yaxis=dict(autorange="reversed"), xaxis=dict(visible=False, range=[0, max(1, dist.max()) * 1.35]))
        chart(fig, 260)
with d2:
    with card("Response status by platform", "This period", key="rev_response"):
        rs = cur.groupby("platform")["responded"].agg(answered="sum", total="count").reindex(platforms).fillna(0)
        rs["waiting"] = rs["total"] - rs["answered"]
        fig = go.Figure()
        fig.add_bar(y=rs.index, x=rs["answered"], name="Responded", orientation="h", marker=dict(color=AQUA, line=dict(color=SURFACE, width=2), cornerradius=0),
                    hovertemplate="%{y}: <b>%{x}</b> responded<extra></extra>")
        fig.add_bar(y=rs.index, x=rs["waiting"], name="Awaiting response", orientation="h",
                    marker=dict(color="#3a4252", line=dict(color=SURFACE, width=2), cornerradius=0),
                    text=[pct(a / t, 0) + " answered" if t else "" for a, t in zip(rs["answered"], rs["total"])], textposition="outside",
                    cliponaxis=False, textfont=dict(color=TEXT_2, size=11), hovertemplate="%{y}: <b>%{x}</b> awaiting<extra></extra>")
        fig.update_layout(barmode="stack", legend=dict(traceorder="normal"), yaxis=dict(autorange="reversed"), xaxis=dict(visible=False, range=[0, max(1, rs["total"].max()) * 1.45]))
        chart(fig, 260)

# --- Review feed ------------------------------------------------------------------------
section("Recent reviews")
with card(None, key="rev_feed"):
    f1, f2, f3, f4, f5 = st.columns([1.3, 1, 1.1, 1.4, 0.7])
    sel_p = f1.multiselect("Platform", platforms, placeholder="All platforms")
    sel_r = f2.multiselect("Stars", [5, 4, 3, 2, 1], format_func=lambda x: f"{x} ★", placeholder="All ratings")
    sel_s = f3.selectbox("Response", ["All", "Awaiting response", "Responded"])
    sel_t = f4.selectbox("Theme", ["All themes", *rv.COMPLAINTS, *rv.COMPLIMENTS])
    limit = f5.selectbox("Show", [10, 25, 50], index=0)
    feed = cur.sort_values("posted_at", ascending=False)
    if sel_p:
        feed = feed[feed["platform"].isin(sel_p)]
    if sel_r:
        feed = feed[feed["rating"].isin(sel_r)]
    if sel_s != "All":
        feed = feed[feed["responded"] == (sel_s == "Responded")]
    if sel_t != "All themes":
        feed = feed[feed["themes"].map(lambda ts: sel_t in ts)]
    st.caption(f"{len(feed):,} reviews match · showing the newest {min(limit, len(feed))}")
    for _, r in feed.head(limit).iterrows():
        chips = "".join(f'<span class="ppi-chip pos">{html.escape(t)}</span>' for t in r["compliments"])
        chips += "".join(f'<span class="ppi-chip neg">{html.escape(t)}</span>' for t in r["complaints"])
        if r["responded"]:
            status = f'<span class="ppi-chip pos">✓ Responded in {hours_label(r["response_hours"])}</span>'
            reply = f'<div class="reply">↳ <b>Owner response:</b> {html.escape(r["response_text"] or "")}</div>'
        else:
            age = (now - r["posted_at"]).total_seconds() / 3600
            status = f'<span class="ppi-chip neg">● Awaiting response · {hours_label(age)}</span>' if r["rating"] <= 3 else \
                     f'<span class="ppi-chip">○ No response yet · {hours_label(age)}</span>'
            reply = ""
        st.markdown(
            f'<div class="ppi-review{" neg" if r["is_negative"] else ""}"><div class="head">'
            f'<div><span class="who">{html.escape(r["reviewer"])}</span> &nbsp;{stars(r["rating"])}</div>'
            f'<div class="when"><span class="dot" style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{pcolor.get(r["platform"], MUTED)}"></span> '
            f'{html.escape(r["platform"])} · {r["posted_at"]:%b %d, %Y}</div></div>'
            f'<div class="text">{html.escape(r["text"])}</div>{chips}{status}{reply}</div>',
            unsafe_allow_html=True,
        )
    export = feed.assign(themes=feed["themes"].map(", ".join))[["posted_at", "platform", "reviewer", "rating", "text", "themes", "responded", "responded_at", "response_text"]]
    st.download_button("Download these reviews (CSV)", export.to_csv(index=False).encode(), file_name="reviews.csv", mime="text/csv")

learn("How reviews are analyzed — and how other platforms will plug in", f"""
<b>One table for every platform.</b> Each review is stored with its platform, date, star rating, text and response status, so
Google, Yelp, Facebook, RepairPal or any future source all feed the same charts. This page currently shows <b>fictional sample
reviews</b>.<br><br>
<b>Themes</b> come from keyword rules applied to the review text (e.g. “never called”, “no updates” → <i>Poor communication</i>).
Rules live in <code>ppi/reviews.py</code> and are easy to extend. A review can match several themes, and a 4★ review can still
contain a complaint. <b>Change</b> on the theme charts is the shift in the share of reviews mentioning that theme versus the prior period.<br><br>
<b>Alerts</b> list every 1–3★ review with no owner reply, regardless of date. Red = 1–2★ older than {rv.RESPONSE_SLA_HOURS} hours.
A prompt, polite public reply matters: future customers read the response as much as the complaint.<br><br>
<b>Connecting real platforms later:</b> each platform has different rules for how much review data a business can pull. Google
Business Profile lets verified owners list and reply to their reviews via its API; Facebook exposes Page recommendations through
the Graph API; Yelp's public API returns only a few review excerpts, so full Yelp history usually comes from exports or a
reputation-management tool. Check each platform's current terms before connecting — they change.
""")
