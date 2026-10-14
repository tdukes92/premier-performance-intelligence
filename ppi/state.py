"""Shared page context: the sidebar filters (built once in app.py) and the filtered data every page reads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import streamlit as st

from . import data as data_mod
from . import pricing
from .data import Filters, ShopData

PRESETS = ["Month to date", "Last 30 days", "Last 90 days", "Quarter to date", "Year to date", "Last 12 months", "Custom range"]


@dataclass(frozen=True)
class Context:
    all: ShopData        # everything loaded (incl. open ROs) - for WIP and long trends
    cur: ShopData        # posted ROs in the selected period
    prev: ShopData       # same-length period immediately before
    filters: Filters
    period_label: str


def _preset_range(preset: str, max_d: date) -> tuple[date, date]:
    end = max_d
    if preset == "Month to date":
        return end.replace(day=1), end
    if preset == "Last 30 days":
        return end - timedelta(days=29), end
    if preset == "Last 90 days":
        return end - timedelta(days=89), end
    if preset == "Quarter to date":
        return date(end.year, 3 * ((end.month - 1) // 3) + 1, 1), end
    if preset == "Year to date":
        return date(end.year, 1, 1), end
    return end - timedelta(days=364), end


def build_sidebar() -> Context:
    sb = st.sidebar
    imported = data_mod.imported_keys()
    sb.markdown('<div class="ppi-section" style="margin-top:0.4rem">Data source</div>', unsafe_allow_html=True)
    if imported:
        if "_force_source" in st.session_state:
            st.session_state["source"] = st.session_state.pop("_force_source")
        choice = sb.radio("Data source", ["Imported data", "Sample data"], label_visibility="collapsed", key="source")
        source = "imported" if choice == "Imported data" else "sample"
    else:
        sb.caption("Using fictional **sample data**. Import Tekmetric CSVs on the Data Import page.")
        source = "sample"
    data = data_mod.load(source)

    min_d, max_d = data_mod.date_bounds(data)
    sb.markdown('<div class="ppi-section">Filters</div>', unsafe_allow_html=True)
    preset = sb.selectbox("Period", PRESETS, index=2, key="preset")
    if preset == "Custom range":
        picked = sb.date_input("Date range", value=(max_d - timedelta(days=89), max_d), min_value=min_d, max_value=max_d, key="custom_range")
        if isinstance(picked, (tuple, list)):
            start, end = (picked[0], picked[-1]) if picked else (max_d, max_d)
        else:
            start = end = picked
    else:
        start, end = _preset_range(preset, max_d)
    start = max(start, min_d)

    advisors = sorted(a for a in data.ros["advisor"].dropna().unique())
    ctypes = sorted(c for c in data.ros["customer_type"].dropna().unique())
    sel_adv = sb.multiselect("Service advisor", advisors, placeholder="All advisors", key="f_adv")
    sel_ct = sb.multiselect("Customer type", ctypes, placeholder="All customer types", key="f_ct")

    f = Filters(start=start, end=end, advisors=tuple(sel_adv), customer_types=tuple(sel_ct))
    cur = data_mod.filter_data(data, f)
    prev = data_mod.filter_data(data, f.prior())
    label = f"{start:%b %d, %Y} – {end:%b %d, %Y}"
    sb.caption(f"Comparing to {f.prior().start:%b %d} – {f.prior().end:%b %d, %Y}. Sales are counted on the date an RO is posted (closed).")
    return Context(all=data, cur=cur, prev=prev, filters=f, period_label=label)


def ctx() -> Context:
    return st.session_state["_ctx"]


# --- Parts pricing settings (editable on the Parts page) ---------------------

def pricing_settings() -> dict:
    if "pricing" not in st.session_state:
        st.session_state["pricing"] = {
            "matrix": pricing.DEFAULT_MATRIX.copy(),
            "tire_margin": pricing.TIRE_TARGET_MARGIN,
            "tolerance": 0.03,
            "fleet_allowance": 0.06,
        }
    return st.session_state["pricing"]


def analyzed_parts(d: ShopData):
    s = pricing_settings()
    return pricing.analyze_parts(d.parts, d.ros, s["matrix"], s["tire_margin"], s["tolerance"], s["fleet_allowance"])
