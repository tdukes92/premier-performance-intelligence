"""Business metrics. Each function takes already-filtered tables and returns plain numbers or DataFrames.

Definitions follow common automotive-repair industry usage; see the "How it's calculated"
notes on each page for plain-English explanations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import ShopData


def _div(a, b):
    return float(a) / float(b) if b else float("nan")


def kpis(d: ShopData) -> dict[str, float]:
    r = d.ros
    paid = r[r["total_sale"] > 0]
    billed = d.jobs["hours_billed"].sum() if not d.jobs.empty else float("nan")
    return {
        "sales": r["total_sale"].sum(),
        "gross_profit": r["gross_profit"].sum(),
        "gp_pct": _div(r["gross_profit"].sum(), r["total_sale"].sum()),
        "car_count": float(len(r)),
        "aro": _div(paid["total_sale"].sum(), len(paid)),
        "labor_sales": r["labor_sale"].sum(),
        "parts_sales": r["parts_sale"].sum(),
        "labor_gp_pct": _div(r["labor_sale"].sum() - r["labor_cost"].sum(), r["labor_sale"].sum()),
        "parts_gp_pct": _div(r["parts_sale"].sum() - r["parts_cost"].sum(), r["parts_sale"].sum()),
        "elr": _div(r["labor_sale"].sum(), billed) if billed == billed else float("nan"),
        "hours_billed": billed,
        "hours_per_ro": _div(billed, len(r)) if billed == billed else float("nan"),
        "discounts": r["discount"].sum(),
        "comeback_rate": _div(r["is_comeback"].sum(), len(r)),
        "avg_cycle_days": r["cycle_days"].mean() if len(r) else float("nan"),
    }


def pct_change(cur: float, prev: float) -> float:
    if prev in (0, None) or prev != prev or cur != cur:
        return float("nan")
    return (cur - prev) / abs(prev)


def trend(ros: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Sales / GP / car count per period. freq: 'D', 'W', or 'M'."""
    if ros.empty:
        return pd.DataFrame(columns=["period", "sales", "gross_profit", "car_count", "aro", "gp_pct"])
    rule = {"D": "D", "W": "W-MON", "M": "MS"}[freq]
    g = ros.set_index("posted_date").resample(rule, label="left", closed="left")
    out = pd.DataFrame({
        "sales": g["total_sale"].sum(),
        "gross_profit": g["gross_profit"].sum(),
        "labor_sale": g["labor_sale"].sum(),
        "parts_sale": g["parts_sale"].sum(),
        "car_count": g["ro_number"].count(),
    }).reset_index(names="period")
    out["aro"] = out["sales"] / out["car_count"].replace(0, np.nan)
    out["gp_pct"] = out["gross_profit"] / out["sales"].replace(0, np.nan)
    return out


def sales_mix(ros: pd.DataFrame) -> pd.DataFrame:
    rows = [
        ("Labor", ros["labor_sale"].sum(), ros["labor_cost"].sum()),
        ("Parts", ros["parts_sale"].sum(), ros["parts_cost"].sum()),
        ("Sublet", ros["sublet_sale"].sum(), ros["sublet_cost"].sum()),
        ("Fees", ros["fees"].sum(), 0.0),
    ]
    df = pd.DataFrame(rows, columns=["type", "sales", "cost"])
    df["gross_profit"] = df["sales"] - df["cost"]
    df["gp_pct"] = df["gross_profit"] / df["sales"].replace(0, np.nan)
    df["share"] = df["sales"] / df["sales"].sum()
    return df


def tech_metrics(d: ShopData, all_ros: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per-technician hours, productivity triangle, labor $, pay cost and comebacks.

    Efficiency  = billed hours / worked hours      (how fast vs. book time)
    Productivity= worked hours / available hours   (how much of the day is on cars)
    Proficiency = billed hours / available hours   (the combined result)
    """
    jobs = d.jobs[d.jobs["authorized"] & d.jobs["technician"].notna()]
    if jobs.empty and d.timecards.empty:
        return pd.DataFrame()
    j = jobs.groupby("technician").agg(
        hours_billed=("hours_billed", "sum"), hours_worked=("hours_worked", "sum"),
        labor_sales=("labor_sale", "sum"), jobs=("job_id", "count"), ros=("ro_number", "nunique"),
    )
    tc = d.timecards.copy()
    if not tc.empty:
        tc["pay_type"] = tc["pay_type"].fillna("Hourly")
        t = tc.groupby("technician").agg(
            hours_available=("hours_available", "sum"), days=("date", "nunique"),
            pay_type=("pay_type", "last"), pay_rate=("pay_rate", "last"),
        )
        out = j.join(t, how="outer")
    else:
        out = j.assign(hours_available=np.nan, days=np.nan, pay_type="Unknown", pay_rate=np.nan)
    out = out.fillna({"hours_billed": 0, "hours_worked": 0, "labor_sales": 0, "jobs": 0, "ros": 0})
    flat = out["pay_type"].astype(str).str.lower().str.startswith("flat")
    out["pay_cost"] = np.where(flat, out["hours_billed"], out["hours_available"]) * out["pay_rate"]
    out["labor_gp"] = out["labor_sales"] - out["pay_cost"]
    out["labor_gp_pct"] = out["labor_gp"] / out["labor_sales"].replace(0, np.nan)
    out["efficiency"] = out["hours_billed"] / out["hours_worked"].replace(0, np.nan)
    out["productivity"] = out["hours_worked"] / out["hours_available"].replace(0, np.nan)
    out["proficiency"] = out["hours_billed"] / out["hours_available"].replace(0, np.nan)
    out["elr"] = out["labor_sales"] / out["hours_billed"].replace(0, np.nan)
    out["billed_per_day"] = out["hours_billed"] / out["days"].replace(0, np.nan)

    # Comebacks: comeback ROs in the period, attributed to the tech on that RO's job.
    cb_ros = set(d.ros.loc[d.ros["is_comeback"], "ro_number"])
    cb = jobs[jobs["ro_number"].isin(cb_ros)].groupby("technician")["ro_number"].nunique()
    out["comebacks"] = cb.reindex(out.index).fillna(0)
    out["comeback_rate"] = out["comebacks"] / out["ros"].replace(0, np.nan)
    return out.reset_index(names="technician").sort_values("labor_gp", ascending=False)


def advisor_metrics(d: ShopData, parts_analyzed: pd.DataFrame | None = None) -> pd.DataFrame:
    r = d.ros
    if r.empty:
        return pd.DataFrame()
    g = r.groupby("advisor").agg(
        ros=("ro_number", "count"), sales=("total_sale", "sum"), gross_profit=("gross_profit", "sum"),
        labor_sales=("labor_sale", "sum"), parts_sales=("parts_sale", "sum"), discounts=("discount", "sum"),
        comebacks=("is_comeback", "sum"),
    )
    g["gp_pct"] = g["gross_profit"] / g["sales"].replace(0, np.nan)
    g["aro"] = g["sales"] / g["ros"]
    g["discount_pct"] = g["discounts"] / (g["sales"] + g["discounts"]).replace(0, np.nan)
    if not d.jobs.empty:
        jj = d.jobs.merge(r[["ro_number", "advisor"]], on="ro_number")
        jj["authorized_total"] = jj["job_total"].where(jj["authorized"], 0.0)
        jg = jj.groupby("advisor").agg(
            presented=("job_total", "sum"),
            authorized=("authorized_total", "sum"),
            jobs_presented=("job_id", "count"), jobs_authorized=("authorized", "sum"),
            hours_billed=("hours_billed", "sum"),
        )
        g = g.join(jg)
        g["close_rate"] = g["authorized"] / g["presented"].replace(0, np.nan)
        g["job_close_rate"] = g["jobs_authorized"] / g["jobs_presented"].replace(0, np.nan)
        g["declined_value"] = g["presented"] - g["authorized"]
        g["hours_per_ro"] = g["hours_billed"] / g["ros"]
        g["elr"] = g["labor_sales"] / g["hours_billed"].replace(0, np.nan)
    if parts_analyzed is not None and not parts_analyzed.empty:
        g["parts_leakage"] = parts_analyzed.groupby("advisor")["leakage"].sum().reindex(g.index).fillna(0)
    return g.reset_index().sort_values("gross_profit", ascending=False)
