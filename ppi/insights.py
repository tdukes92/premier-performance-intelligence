"""Auto-generated, plain-English findings for the Executive Overview."""

from __future__ import annotations

import pandas as pd

from . import metrics
from .components import money, pct
from .state import Context, analyzed_parts


def generate(c: Context, max_items: int = 6) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    k, kp = metrics.kpis(c.cur), metrics.kpis(c.prev)

    # Gross profit margin movement
    gp_delta = k["gp_pct"] - kp["gp_pct"]
    if gp_delta == gp_delta and abs(gp_delta) >= 0.005:
        lvl = "good" if gp_delta > 0 else "serious"
        out.append((lvl, f"Gross profit margin {'up' if gp_delta > 0 else 'down'} {abs(gp_delta) * 100:.1f} pts",
                    f"{pct(k['gp_pct'])} this period vs {pct(kp['gp_pct'])} in the prior period."))

    # Parts leakage
    pa = analyzed_parts(c.cur)
    if not pa.empty:
        leak = pa["leakage"].sum()
        if leak > 0:
            by_adv = pa.groupby("advisor")["leakage"].sum().sort_values(ascending=False)
            top = by_adv.index[0] if len(by_adv) else "—"
            share = by_adv.iloc[0] / leak if len(by_adv) else 0
            n = int((pa["leakage"] > 0).sum())
            out.append(("critical" if leak > 0.01 * k["sales"] else "serious",
                        f"{money(leak)} in parts margin leakage",
                        f"{n:,} part lines sold under the pricing matrix. {top} accounts for {pct(share, 0)} of it — see Parts Profitability."))

    # Tech efficiency
    tm = metrics.tech_metrics(c.cur)
    if not tm.empty and tm["efficiency"].notna().any():
        low = tm.sort_values("efficiency").iloc[0]
        if low["efficiency"] < 0.9:
            lost = (low["hours_worked"] - low["hours_billed"]) * (k["elr"] if k["elr"] == k["elr"] else 0)
            out.append(("serious", f"{low['technician']} is running {pct(low['efficiency'], 0)} efficiency",
                        f"Worked {low['hours_worked']:,.0f} hrs to bill {low['hours_billed']:,.0f}. At the current effective labor rate that's ~{money(lost)} of unbilled time."))
        top = tm.sort_values("labor_gp", ascending=False).iloc[0]
        out.append(("good", f"{top['technician']} leads labor gross profit",
                    f"{money(top['labor_gp'])} labor GP on {top['hours_billed']:,.0f} billed hours ({pct(top['efficiency'], 0)} efficiency)."))

    # Discounts
    am = metrics.advisor_metrics(c.cur)
    if not am.empty and am["discount_pct"].notna().any():
        hi = am.sort_values("discount_pct", ascending=False).iloc[0]
        avg = am["discounts"].sum() / (am["sales"].sum() + am["discounts"].sum())
        if hi["discount_pct"] > 1.5 * avg and hi["discounts"] > 0:
            out.append(("warning", f"{hi['advisor']} discounts at {pct(hi['discount_pct'])} of sales",
                        f"Shop average is {pct(avg)}. {money(hi['discounts'])} given away this period."))

    # Car count
    cc = metrics.pct_change(k["car_count"], kp["car_count"])
    if cc == cc and abs(cc) >= 0.03:
        out.append(("good" if cc > 0 else "warning", f"Car count {'up' if cc > 0 else 'down'} {pct(abs(cc), 0)}",
                    f"{k['car_count']:,.0f} ROs posted vs {kp['car_count']:,.0f} in the prior period."))

    # Aging WIP
    wip = c.all.ros[c.all.ros["is_open"]]
    if not wip.empty:
        age = (pd.Timestamp.now() - wip["opened_at"]).dt.days
        old = int((age >= 3).sum())
        if old:
            out.append(("warning", f"{old} open RO{'s' if old != 1 else ''} older than 3 days",
                        f"{money(wip['total_sale'].sum())} of work in progress not yet invoiced — see Operational Insights."))

    order = {"critical": 0, "serious": 1, "warning": 2, "good": 3, "info": 4}
    return sorted(out, key=lambda x: order[x[0]])[:max_items]
