"""Loading, cleaning, enrichment and filtering of the four core tables."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from . import sample_data
from .schema import DATASETS, Dataset

ROOT = Path(__file__).resolve().parent.parent
IMPORT_DIR = ROOT / "data" / "imported"

TRUE_WORDS = {"true", "t", "yes", "y", "1", "approved", "authorized", "sold", "x", "comeback"}


@dataclass(frozen=True)
class ShopData:
    ros: pd.DataFrame
    jobs: pd.DataFrame
    parts: pd.DataFrame
    timecards: pd.DataFrame
    source: str  # "sample" | "imported"

    def has(self, key: str) -> bool:
        return not getattr(self, {"repair_orders": "ros"}.get(key, key)).empty


# --- Type coercion (shared by sample + imports) -----------------------------

def _to_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return s.astype("string").str.strip().str.lower().isin(TRUE_WORDS).astype(bool)


def _to_float(s: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(s):
        return s.astype(float)
    cleaned = s.astype("string").str.replace(r"[\$,\s]", "", regex=True).str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    return pd.to_numeric(cleaned, errors="coerce")


def coerce(df: pd.DataFrame, dataset: Dataset) -> pd.DataFrame:
    """Give every canonical column the right type, adding missing optional columns with safe defaults."""
    df = df.copy()
    for col in dataset.columns:
        if col.name not in df.columns:
            df[col.name] = {"float": 0.0, "bool": False, "date": pd.NaT}.get(col.dtype, None)
        s = df[col.name]
        if col.dtype == "float":
            df[col.name] = _to_float(s).fillna(0.0)
        elif col.dtype == "bool":
            df[col.name] = _to_bool(s.fillna(False))
        elif col.dtype == "date":
            df[col.name] = pd.to_datetime(s, errors="coerce", format="mixed") if not pd.api.types.is_datetime64_any_dtype(s) else s
        else:
            df[col.name] = s.astype(object).map(lambda v: None if pd.isna(v) or str(v).strip() == "" else str(v).strip())
    return df


# --- Enrichment -------------------------------------------------------------

def enrich_ros(ros: pd.DataFrame) -> pd.DataFrame:
    df = ros.copy()
    df["customer_type"] = df["customer_type"].fillna("Retail")
    df["total_sale"] = df["labor_sale"] + df["parts_sale"] + df["sublet_sale"] + df["fees"] - df["discount"]
    df["total_cost"] = df["labor_cost"] + df["parts_cost"] + df["sublet_cost"]
    df["gross_profit"] = df["total_sale"] - df["total_cost"]
    df["gp_pct"] = np.where(df["total_sale"] > 0, df["gross_profit"] / df["total_sale"].where(df["total_sale"] > 0), np.nan)
    df["is_open"] = df["closed_at"].isna()
    df["posted_date"] = df["closed_at"].dt.normalize()
    df["cycle_days"] = (df["closed_at"] - df["opened_at"]).dt.total_seconds() / 86400
    return df


def _finalize(raw: dict[str, pd.DataFrame], source: str) -> ShopData:
    frames = {}
    for key, ds in DATASETS.items():
        df = raw.get(key)
        frames[key] = coerce(df, ds) if df is not None and not df.empty else coerce(pd.DataFrame(columns=[c.name for c in ds.columns]), ds)
    ros = enrich_ros(frames["repair_orders"])
    jobs = frames["jobs"]
    if jobs["job_id"].isna().any():
        jobs["job_id"] = jobs["job_id"].fillna(pd.Series(jobs["ro_number"].astype(str) + "-" + (jobs.groupby("ro_number").cumcount() + 1).astype(str), index=jobs.index))
    return ShopData(ros=ros, jobs=jobs, parts=frames["parts"], timecards=frames["timecards"], source=source)


@st.cache_data(show_spinner="Generating sample shop data…")
def _sample(end: date) -> dict[str, pd.DataFrame]:
    return sample_data.generate(end=end)


def imported_keys() -> list[str]:
    return [k for k in DATASETS if (IMPORT_DIR / f"{k}.csv").exists()]


@st.cache_data(show_spinner="Loading imported data…")
def _imported(stamp: tuple) -> dict[str, pd.DataFrame]:
    return {k: pd.read_csv(IMPORT_DIR / f"{k}.csv", dtype=str) for k in imported_keys()}


def load(source: str) -> ShopData:
    if source == "imported" and imported_keys():
        stamp = tuple((k, (IMPORT_DIR / f"{k}.csv").stat().st_mtime) for k in imported_keys())
        return _finalize(_imported(stamp), "imported")
    return _finalize(_sample(date.today()), "sample")


def save_import(key: str, df: pd.DataFrame) -> Path:
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = IMPORT_DIR / f"{key}.csv"
    df.to_csv(path, index=False)
    st.cache_data.clear()
    return path


def delete_import(key: str) -> None:
    (IMPORT_DIR / f"{key}.csv").unlink(missing_ok=True)
    st.cache_data.clear()


# --- Filtering --------------------------------------------------------------

@dataclass(frozen=True)
class Filters:
    start: date
    end: date
    advisors: tuple[str, ...] = ()
    customer_types: tuple[str, ...] = ()

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def prior(self) -> "Filters":
        """The equal-length period immediately before this one (for comparisons)."""
        return replace(self, start=self.start - timedelta(days=self.days), end=self.start - timedelta(days=1))


def filter_data(data: ShopData, f: Filters) -> ShopData:
    """Posted (closed) ROs in the period, plus their jobs and parts. Open ROs are kept for WIP views."""
    ros = data.ros
    mask = ros["posted_date"].between(pd.Timestamp(f.start), pd.Timestamp(f.end))
    if f.advisors:
        mask &= ros["advisor"].isin(f.advisors)
    if f.customer_types:
        mask &= ros["customer_type"].isin(f.customer_types)
    posted = ros[mask]
    keep = set(posted["ro_number"])
    tc = data.timecards
    tc = tc[tc["date"].between(pd.Timestamp(f.start), pd.Timestamp(f.end))]
    return ShopData(
        ros=posted,
        jobs=data.jobs[data.jobs["ro_number"].isin(keep)],
        parts=data.parts[data.parts["ro_number"].isin(keep)],
        timecards=tc,
        source=data.source,
    )


def date_bounds(data: ShopData) -> tuple[date, date]:
    dates = pd.concat([data.ros["posted_date"].dropna(), data.ros["opened_at"].dropna()])
    if dates.empty:
        today = date.today()
        return today - timedelta(days=365), today
    return dates.min().date(), dates.max().date()
