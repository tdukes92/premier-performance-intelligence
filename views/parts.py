import numpy as np
import plotly.graph_objects as go
import streamlit as st

from ppi.components import card, chart, empty_state, kpi, kpi_row, learn, money, num, page_header, pct
from ppi.state import analyzed_parts, ctx, pricing_settings
from ppi.theme import AQUA, BLUE, CRITICAL, MUTED, SERIOUS, TEXT_2, WARNING

c = ctx()
page_header("Parts Profitability", "Parts margin by category, vendor and price tier — and where margin is leaking.", c.period_label, c.all.source)

if c.cur.parts.empty:
    empty_state("Parts Lines")
    st.stop()

pa = analyzed_parts(c.cur)
pp = analyzed_parts(c.prev)
sold = pa[pa["reason"] != "Comeback (no charge)"]
sales, gp = sold["ext_price"].sum(), sold["gross_profit"].sum()
p_sales, p_gp = pp["ext_price"].sum(), pp["gross_profit"].sum()
leak, p_leak = pa["leakage"].sum(), pp["leakage"].sum() if not pp.empty else float("nan")
exc = pa[pa["leakage"] > 0]
potential_gp_pct = (gp + leak) / (sales + leak) if sales + leak else float("nan")

kpi_row([
    kpi("Parts Sales", money(sales), (sales - p_sales) / p_sales if p_sales else None, variant="accent"),
    kpi("Parts Gross Profit", money(gp), (gp - p_gp) / p_gp if p_gp else None),
    kpi("Parts GP %", pct(gp / sales if sales else float("nan")), (gp / sales - p_gp / p_sales) if sales and p_sales else None,
        delta_is_points=True, foot=f"At matrix: {pct(potential_gp_pct)}"),
    kpi("Margin Leakage", money(leak), (leak - p_leak) / p_leak if p_leak else None, good_when_up=False, variant="alert",
        foot=f"{pct(leak / gp if gp else float('nan'))} of parts GP"),
    kpi("Exception Lines", num(len(exc)), foot=f"of {len(pa):,} part lines ({pct(len(exc) / len(pa) if len(pa) else 0)})"),
])

tab_exc, tab_break, tab_matrix = st.tabs(["⚠  Margin Leakage Exceptions", "Profitability Breakdown", "Pricing Matrix & Rules"])

# --- Exception report ---------------------------------------------------------
with tab_exc:
    st.write("")
    f1, f2, f3, f4 = st.columns([2, 1.1, 1.1, 0.8])
    reasons = f1.multiselect("Exception type", ["Not charged ($0)", "Sold below cost", "Below matrix"],
                             default=["Not charged ($0)", "Sold below cost", "Below matrix"])
    advs = f2.multiselect("Advisor", sorted(exc["advisor"].dropna().unique()), placeholder="All advisors")
    cats = f3.multiselect("Part category", sorted(exc["category"].dropna().unique()), placeholder="All categories")
    min_leak = f4.number_input("Min leakage $", min_value=0.0, value=0.0, step=5.0)

    view = exc[exc["reason"].isin(reasons) & (exc["leakage"] >= min_leak)]
    if advs:
        view = view[view["advisor"].isin(advs)]
    if cats:
        view = view[view["category"].isin(cats)]

    r1, r2, r3 = st.columns(3, gap="medium")
    reason_color = {"Not charged ($0)": CRITICAL, "Sold below cost": SERIOUS, "Below matrix": WARNING}
    with r1:
        with card("Leakage by exception type", key="leak_reason"):
            g = view.groupby("reason").agg(leakage=("leakage", "sum"), lines=("leakage", "size")).reindex(list(reason_color)).dropna()
            fig = go.Figure(go.Bar(x=g["leakage"], y=g.index, orientation="h",
                                   marker_color=[reason_color[r] for r in g.index], customdata=g["lines"],
                                   text=[f"{money(v)} · {int(n)} lines" for v, n in zip(g["leakage"], g["lines"])],
                                   textposition="outside", cliponaxis=False, textfont=dict(color=TEXT_2),
                                   hovertemplate="%{y}<br><b>%{x:$,.0f}</b> on %{customdata} lines<extra></extra>"))
            fig.update_layout(xaxis=dict(visible=False, range=[0, max(1, g["leakage"].max()) * 2.1]), yaxis=dict(autorange="reversed"))
            chart(fig, 200)
    with r2:
        with card("Leakage by advisor", key="leak_adv"):
            g = view.groupby("advisor")["leakage"].sum().sort_values()
            fig = go.Figure(go.Bar(x=g.values, y=g.index, orientation="h", marker_color=BLUE,
                                   text=[money(v) for v in g.values], textposition="outside", cliponaxis=False,
                                   textfont=dict(color=TEXT_2), hovertemplate="%{y}: <b>%{x:$,.0f}</b><extra></extra>"))
            fig.update_layout(xaxis=dict(visible=False, range=[0, max(1, g.max() if len(g) else 1) * 1.35]))
            chart(fig, 200)
    with r3:
        with card("Leakage by part category", key="leak_cat"):
            g = view.groupby("category")["leakage"].sum().sort_values().tail(7)
            fig = go.Figure(go.Bar(x=g.values, y=g.index, orientation="h", marker_color=BLUE,
                                   text=[money(v) for v in g.values], textposition="outside", cliponaxis=False,
                                   textfont=dict(color=TEXT_2), hovertemplate="%{y}: <b>%{x:$,.0f}</b><extra></extra>"))
            fig.update_layout(xaxis=dict(visible=False, range=[0, max(1, g.max() if len(g) else 1) * 1.35]))
            chart(fig, 200)

    with card("Exception detail", f"{len(view):,} part lines · {money(view['leakage'].sum(), short=False)} lost gross profit · sorted by largest leakage"):
        table = view.sort_values("leakage", ascending=False)[[
            "severity", "reason", "closed_at", "ro_number", "advisor", "customer_name", "description", "category",
            "vendor", "quantity", "unit_cost", "unit_price", "target_unit_price", "pct_of_matrix", "margin", "target_margin", "leakage",
        ]].rename(columns={"closed_at": "posted"})
        table["severity"] = table["severity"].map({"Critical": "🔴 Critical", "Warning": "🟠 Warning"}).fillna(table["severity"])
        st.dataframe(
            table, hide_index=True, width="stretch", height=440,
            column_config={
                "severity": st.column_config.TextColumn("Severity", width="small"),
                "reason": "Exception",
                "posted": st.column_config.DateColumn("Posted", format="MMM D, YYYY"),
                "ro_number": "RO #", "advisor": "Advisor", "customer_name": "Customer", "description": "Part",
                "category": "Category", "vendor": "Vendor",
                "quantity": st.column_config.NumberColumn("Qty", format="%.0f"),
                "unit_cost": st.column_config.NumberColumn("Unit cost", format="dollar"),
                "unit_price": st.column_config.NumberColumn("Sold @", format="dollar"),
                "target_unit_price": st.column_config.NumberColumn("Matrix @", format="dollar"),
                "pct_of_matrix": st.column_config.ProgressColumn("% of matrix", format="percent", min_value=0, max_value=1),
                "margin": st.column_config.NumberColumn("Margin", format="percent"),
                "target_margin": st.column_config.NumberColumn("Target", format="percent"),
                "leakage": st.column_config.NumberColumn("Leakage", format="dollar"),
            },
        )
        st.download_button("Download exception report (CSV)", table.to_csv(index=False).encode(),
                           file_name=f"parts_margin_exceptions_{c.filters.start}_{c.filters.end}.csv", mime="text/csv")

    learn("How the margin leakage report works", """
<b>Your pricing matrix</b> says what margin each part should carry based on its cost (cheap parts carry higher margin).
For every part line we compute the <b>matrix price</b> = cost ÷ (1 − target margin).<br><br>
A line is flagged when it is sold for less than the matrix price minus a small <b>tolerance</b> (default 3%, for rounding).
Fleet accounts get an extra <b>fleet allowance</b> (default 6%) because they usually have negotiated pricing.<br><br>
<b>Exception types</b>, most serious first:<br>
• <b>Not charged ($0)</b> — the part has a cost but was given away. Often a missed line on the invoice.<br>
• <b>Sold below cost</b> — the shop lost money on the part itself.<br>
• <b>Below matrix</b> — profitable, but someone overrode the price. Usually discounting or price-matching.<br><br>
<b>Leakage $</b> = (matrix price − actual price) × quantity: the gross profit the shop would have made at matrix.
Comeback/no-charge ROs are excluded because giving those parts away is intentional. Adjust all rules on the
<b>Pricing Matrix & Rules</b> tab.
""")

# --- Breakdown --------------------------------------------------------------------
with tab_break:
    st.write("")
    b1, b2 = st.columns([1.2, 1], gap="medium")
    with b1:
        with card("Margin by category: actual vs. target", "Dot = actual GP %, tick = blended matrix target", key="cat_margin"):
            g = sold.groupby("category").agg(sales=("ext_price", "sum"), gp=("gross_profit", "sum"),
                                             target_gp=("target_price", "sum"), cost=("ext_cost", "sum"))
            g["gp_pct"] = g["gp"] / g["sales"]
            g["target_pct"] = (g["target_gp"] - g["cost"]) / g["target_gp"]
            g = g.sort_values("sales")
            fig = go.Figure()
            for cat, row in g.iterrows():
                fig.add_shape(type="line", x0=row["gp_pct"], x1=row["target_pct"], y0=cat, y1=cat, line=dict(color=MUTED, width=2))
            fig.add_scatter(x=g["target_pct"], y=g.index, mode="markers", name="Matrix target",
                            marker=dict(symbol="line-ns", size=16, line=dict(width=3, color=TEXT_2)),
                            hovertemplate="%{y}<br>Target <b>%{x:.1%}</b><extra></extra>")
            fig.add_scatter(x=g["gp_pct"], y=g.index, mode="markers", name="Actual GP %",
                            marker=dict(size=12, color=AQUA, line=dict(width=2, color="#111722")), customdata=g["sales"],
                            hovertemplate="%{y}<br>Actual <b>%{x:.1%}</b><br>Sales %{customdata:$,.0f}<extra></extra>")
            fig.update_layout(xaxis=dict(tickformat=".0%", showgrid=True, gridcolor="#1f2733"), yaxis=dict(showgrid=False))
            chart(fig, 360)
    with b2:
        with card("Sales & gross profit by category", key="cat_table"):
            t = g.sort_values("sales", ascending=False).reset_index()[["category", "sales", "gp", "gp_pct", "target_pct"]]
            t["share"] = t["sales"] / t["sales"].sum()
            st.dataframe(t, hide_index=True, width="stretch", height=360, column_config={
                "category": "Category",
                "sales": st.column_config.NumberColumn("Sales", format="dollar", step=1),
                "gp": st.column_config.NumberColumn("Gross profit", format="dollar", step=1),
                "gp_pct": st.column_config.NumberColumn("GP %", format="percent"),
                "target_pct": st.column_config.NumberColumn("Target", format="percent"),
                "share": st.column_config.ProgressColumn("Share of sales", format="percent", min_value=0, max_value=1),
            })

    b3, b4 = st.columns(2, gap="medium")
    with b3:
        with card("Margin by cost tier", "Actual GP % for each matrix tier vs. its target", key="tier"):
            s = pricing_settings()
            m = s["matrix"].reset_index(drop=True)
            nt = sold[sold["category"] != "Tires"].copy()
            nt["tier"] = np.clip(np.searchsorted(m["cost_from"].to_numpy(), nt["unit_cost"].to_numpy(), side="right") - 1, 0, len(m) - 1)
            tg = nt.groupby("tier").agg(sales=("ext_price", "sum"), gp=("gross_profit", "sum")).reindex(range(len(m))).fillna(0)
            labels = [f"${a:,.0f}–{'∞' if np.isinf(b) else f'${b:,.0f}'}" for a, b in zip(m["cost_from"], m["cost_to"])]
            actual = (tg["gp"] / tg["sales"].replace(0, np.nan)).to_numpy()
            fig = go.Figure()
            fig.add_bar(x=labels, y=m["target_margin"], name="Target", marker_color="#2e3747",
                        hovertemplate="%{x}<br>Target <b>%{y:.0%}</b><extra></extra>")
            fig.add_bar(x=labels, y=actual, name="Actual", marker_color=BLUE,
                        hovertemplate="%{x}<br>Actual <b>%{y:.1%}</b><extra></extra>")
            fig.update_layout(barmode="group", yaxis=dict(tickformat=".0%"), xaxis_title="Unit cost tier")
            chart(fig, 300)
    with b4:
        with card("Vendor scorecard", "Parts sold by supplier", key="vendor"):
            v = sold.groupby("vendor").agg(lines=("ext_price", "size"), cost=("ext_cost", "sum"), sales=("ext_price", "sum"),
                                           gp=("gross_profit", "sum"), leakage=("leakage", "sum")).sort_values("sales", ascending=False)
            v["gp_pct"] = v["gp"] / v["sales"]
            st.dataframe(v.reset_index(), hide_index=True, width="stretch", height=300, column_config={
                "vendor": "Vendor", "lines": st.column_config.NumberColumn("Lines", format="%,d"),
                "cost": st.column_config.NumberColumn("Purchases", format="dollar", step=1),
                "sales": st.column_config.NumberColumn("Sales", format="dollar", step=1),
                "gp": st.column_config.NumberColumn("GP", format="dollar", step=1),
                "gp_pct": st.column_config.NumberColumn("GP %", format="percent"),
                "leakage": st.column_config.NumberColumn("Leakage", format="dollar", step=1),
            })

    with card("Top parts by gross profit", key="top_parts"):
        tp = sold.groupby(["description", "category"]).agg(qty=("quantity", "sum"), sales=("ext_price", "sum"),
                                                           gp=("gross_profit", "sum")).reset_index()
        tp["gp_pct"] = tp["gp"] / tp["sales"]
        tp = tp.sort_values("gp", ascending=False).head(15)
        st.dataframe(tp, hide_index=True, width="stretch", column_config={
            "description": "Part", "category": "Category", "qty": st.column_config.NumberColumn("Qty", format="%,.0f"),
            "sales": st.column_config.NumberColumn("Sales", format="dollar", step=1),
            "gp": st.column_config.ProgressColumn("Gross profit", format="dollar", step=1, min_value=0, max_value=float(tp["gp"].max())),
            "gp_pct": st.column_config.NumberColumn("GP %", format="percent"),
        })

# --- Matrix -------------------------------------------------------------------
with tab_matrix:
    st.write("")
    s = pricing_settings()
    m1, m2 = st.columns([1.3, 1], gap="large")
    with m1:
        st.markdown("##### Parts pricing matrix")
        st.caption("Edit to match your shop's matrix in Tekmetric. Target margin is gross margin: (price − cost) ÷ price.")
        edit = s["matrix"].copy()
        edit["target_margin"] = (edit["target_margin"] * 100).round(1)
        edit["markup"] = (1 / (1 - edit["target_margin"] / 100)).round(2)
        edited = st.data_editor(
            edit, hide_index=True, width="stretch", num_rows="dynamic", key="matrix_editor",
            column_config={
                "cost_from": st.column_config.NumberColumn("Cost from ($)", format="dollar", min_value=0),
                "cost_to": st.column_config.NumberColumn("Cost to ($)", format="dollar", disabled=True,
                                                         help="Calculated from the next row's 'cost from'."),
                "target_margin": st.column_config.NumberColumn("Target margin %", format="%.1f%%", min_value=0, max_value=95),
                "markup": st.column_config.NumberColumn("= Cost multiplier", format="%.2fx", disabled=True),
            },
        )
    with m2:
        st.markdown("##### Exception rules")
        tire = st.slider("Tire target margin", 0, 50, int(round(s["tire_margin"] * 100)), format="%d%%",
                         help="Tires are priced competitively, so they use one flat target instead of the matrix.")
        tol = st.slider("Tolerance before flagging", 0, 15, int(round(s["tolerance"] * 100)), format="%d%%",
                        help="A part can be this far under the matrix price without being flagged (rounding, price ending in .99).")
        fleet = st.slider("Fleet pricing allowance", 0, 25, int(round(s["fleet_allowance"] * 100)), format="%d%%",
                          help="Additional discount fleet customers are allowed by agreement.")
        b_apply, b_reset = st.columns(2)
        if b_apply.button("Apply changes", type="primary", width="stretch"):
            new = edited.dropna(subset=["cost_from", "target_margin"]).sort_values("cost_from").reset_index(drop=True)
            new["cost_to"] = list(new["cost_from"].iloc[1:]) + [float("inf")]
            new["target_margin"] = new["target_margin"] / 100
            s.update(matrix=new[["cost_from", "cost_to", "target_margin"]], tire_margin=tire / 100,
                     tolerance=tol / 100, fleet_allowance=fleet / 100)
            st.rerun()
        if b_reset.button("Reset to defaults", width="stretch"):
            del st.session_state["pricing"]
            st.rerun()
        st.caption("Changes apply for this browser session across all pages.")

    learn("What is a parts matrix, and why use one?", """
Most shops don't price every part by hand. A <b>matrix</b> sets the margin automatically by the part's cost:
a $4 oil filter might carry 70% margin (sell ~$13) while a $450 compressor carries 36% (sell ~$700).
Customers rarely notice margin on small parts, and big-ticket parts stay competitive.<br><br>
<b>Margin vs. markup:</b> a 50% <i>margin</i> is the same as a 2.0× <i>multiplier</i> (100% markup).
The "cost multiplier" column shows the equivalent multiplier so you can match what's in Tekmetric.
""")
