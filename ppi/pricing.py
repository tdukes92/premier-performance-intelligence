"""Parts pricing matrix and margin-leakage detection.

A *parts matrix* is the shop's pricing rule: the cheaper the part, the higher
the margin it should carry. "Leakage" is the gross profit lost when a part is
sold for less than the matrix says it should be.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# (cost from, cost to, target gross margin) - margin = (price - cost) / price
DEFAULT_MATRIX = pd.DataFrame(
    {
        "cost_from": [0.0, 10.0, 25.0, 50.0, 100.0, 200.0, 400.0],
        "cost_to": [10.0, 25.0, 50.0, 100.0, 200.0, 400.0, float("inf")],
        "target_margin": [0.70, 0.62, 0.57, 0.52, 0.47, 0.42, 0.36],
    }
)
TIRE_TARGET_MARGIN = 0.25  # tires are priced competitively, so they get their own target


def target_margin(cost, category, matrix: pd.DataFrame = DEFAULT_MATRIX, tire_margin: float = TIRE_TARGET_MARGIN):
    """Target margin for scalar or array inputs."""
    cost_arr = np.atleast_1d(np.asarray(cost, dtype=float))
    cat_arr = np.atleast_1d(np.asarray(category, dtype=object))
    bounds = matrix["cost_from"].to_numpy()
    margins = matrix["target_margin"].to_numpy()
    idx = np.clip(np.searchsorted(bounds, cost_arr, side="right") - 1, 0, len(bounds) - 1)
    out = margins[idx]
    out = np.where(cat_arr == "Tires", tire_margin, out)
    return out if np.ndim(cost) else float(out[0])


def matrix_price(cost, category, matrix: pd.DataFrame = DEFAULT_MATRIX, tire_margin: float = TIRE_TARGET_MARGIN):
    m = target_margin(cost, category, matrix, tire_margin)
    return np.asarray(cost, dtype=float) / (1 - m) if np.ndim(cost) else float(cost) / (1 - m)


REASON_ORDER = ["Not charged ($0)", "Sold below cost", "Below matrix", "Comeback (no charge)", "On matrix"]
SEVERITY = {"Not charged ($0)": "Critical", "Sold below cost": "Critical", "Below matrix": "Warning",
            "Comeback (no charge)": "Info", "On matrix": "OK"}


def analyze_parts(parts: pd.DataFrame, ros: pd.DataFrame, matrix: pd.DataFrame = DEFAULT_MATRIX,
                  tire_margin: float = TIRE_TARGET_MARGIN, tolerance: float = 0.03,
                  fleet_allowance: float = 0.06) -> pd.DataFrame:
    """Add matrix targets, actual margin, leakage $ and an exception reason to every part line.

    tolerance:        how far under the matrix price a line can be before it is flagged (rounding etc.)
    fleet_allowance:  extra discount fleet accounts are allowed by agreement
    """
    if parts.empty:
        return parts.assign(ext_cost=[], ext_price=[], target_price=[], leakage=[], reason=[])
    ctx_cols = [c for c in ["ro_number", "advisor", "customer_type", "is_comeback", "closed_at", "customer_name"] if c in ros]
    df = parts.merge(ros[ctx_cols], on="ro_number", how="left")
    df["ext_cost"] = df["unit_cost"] * df["quantity"]
    df["ext_price"] = df["unit_price"] * df["quantity"]
    df["gross_profit"] = df["ext_price"] - df["ext_cost"]
    df["margin"] = np.where(df["ext_price"] > 0, df["gross_profit"] / df["ext_price"].where(df["ext_price"] > 0), np.nan)
    df["target_margin"] = target_margin(df["unit_cost"].to_numpy(), df["category"].fillna("").to_numpy(), matrix, tire_margin)
    df["target_unit_price"] = df["unit_cost"] / (1 - df["target_margin"])
    fleet = df.get("customer_type", pd.Series("", index=df.index)).fillna("").eq("Fleet")
    allowed = df["target_unit_price"] * (1 - tolerance - np.where(fleet, fleet_allowance, 0.0))
    df["target_price"] = df["target_unit_price"] * df["quantity"]
    df["pct_of_matrix"] = np.where(df["target_unit_price"] > 0, df["unit_price"] / df["target_unit_price"], np.nan)

    comeback = df.get("is_comeback", pd.Series(False, index=df.index)).fillna(False).astype(bool)
    reason = np.select(
        [comeback, (df["unit_price"] <= 0) & (df["unit_cost"] > 0), df["unit_price"] < df["unit_cost"], df["unit_price"] < allowed],
        ["Comeback (no charge)", "Not charged ($0)", "Sold below cost", "Below matrix"],
        default="On matrix",
    )
    df["reason"] = reason
    df["severity"] = df["reason"].map(SEVERITY)
    flagged = df["reason"].isin(["Not charged ($0)", "Sold below cost", "Below matrix"])
    df["leakage"] = np.where(flagged, (df["target_price"] - df["ext_price"]).clip(lower=0), 0.0)
    return df
