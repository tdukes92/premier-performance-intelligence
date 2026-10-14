"""Reusable UI pieces: formatters, page header, KPI tiles, cards, insight rows, learn boxes."""

from __future__ import annotations

import html
import math
from contextlib import contextmanager
import re

import plotly.graph_objects as go
import streamlit as st

from .theme import SURFACE, CRITICAL, GOOD, MUTED, PLOTLY_CONFIG, SERIOUS, WARNING



# --- Formatters -------------------------------------------------------------

def _nan(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def money(x, short: bool = True, decimals: int = 0) -> str:
    if _nan(x):
        return "—"
    sign = "-" if x < 0 else ""
    x = abs(x)
    if short and x >= 1_000_000:
        return f"{sign}${x / 1_000_000:.2f}M"
    if short and x >= 10_000:
        return f"{sign}${x / 1_000:.1f}K"
    return f"{sign}${x:,.{decimals}f}"


def pct(x, decimals: int = 1) -> str:
    return "—" if _nan(x) else f"{x * 100:.{decimals}f}%"


def num(x, decimals: int = 0) -> str:
    return "—" if _nan(x) else f"{x:,.{decimals}f}"


# --- Layout -----------------------------------------------------------------

def page_header(title: str, subtitle: str, period_label: str, source: str) -> None:
    badge = ('<span class="ppi-badge sample">● Sample data</span>' if source == "sample"
             else '<span class="ppi-badge live">● Imported data</span>')
    st.markdown(
        f"""<div style="display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:10px;margin-bottom:1.2rem">
        <div><div class="ppi-page-title">{html.escape(title)}</div><div class="ppi-page-sub">{html.escape(subtitle)}</div></div>
        <div><span class="ppi-badge">{html.escape(period_label)}</span>{badge}</div></div>""",
        unsafe_allow_html=True,
    )


def section(label: str) -> None:
    st.markdown(f'<div class="ppi-section">{html.escape(label)}</div>', unsafe_allow_html=True)


@contextmanager
def card(title: str | None = None, subtitle: str | None = None, key: str | None = None):
    key = key or re.sub(r"[^a-z0-9]+", "_", (title or subtitle or "x").lower()).strip("_")
    with st.container(key=f"card_{key}"):
        if title:
            st.markdown(f'<p class="ppi-card-title">{html.escape(title)}</p>', unsafe_allow_html=True)
        if subtitle:
            st.markdown(f'<p class="ppi-card-sub">{html.escape(subtitle)}</p>', unsafe_allow_html=True)
        yield


def chart(fig: go.Figure, height: int = 320, key: str | None = None) -> None:
    fig.update_layout(height=height, paper_bgcolor=SURFACE, plot_bgcolor=SURFACE)
    st.plotly_chart(fig, width="stretch", theme=None, config=PLOTLY_CONFIG, key=key)


def kpi(label: str, value: str, delta: float | None = None, *, good_when_up: bool = True,
        foot: str | None = None, delta_is_points: bool = False, variant: str = "") -> str:
    """Return HTML for one KPI tile. Deltas carry an arrow + text, never color alone."""
    delta_html = ""
    if delta is not None and not _nan(delta):
        up = delta >= 0
        good = up == good_when_up
        color = GOOD if good else CRITICAL
        if abs(delta) < 0.005:
            color, arrow = MUTED, "▬"
        else:
            arrow = "▲" if up else "▼"
        text = f"{abs(delta) * 100:.1f} pts" if delta_is_points else f"{abs(delta) * 100:.1f}%"
        delta_html = f'<div class="delta" style="color:{color}">{arrow} {text} <span class="vs">vs prior period</span></div>'
    foot_html = f'<div class="foot">{html.escape(foot) if foot else "&nbsp;"}</div>'
    return (f'<div class="ppi-kpi {variant}"><div class="label">{html.escape(label)}</div>'
            f'<div class="value">{html.escape(value)}</div>{delta_html}{foot_html}</div>')


def kpi_row(tiles: list[str]) -> None:
    cols = st.columns(len(tiles), gap="small")
    for c, t in zip(cols, tiles):
        c.markdown(t, unsafe_allow_html=True)


_LEVELS = {
    "critical": (CRITICAL, "✕", "Critical"),
    "serious": (SERIOUS, "!", "Attention"),
    "warning": (WARNING, "!", "Watch"),
    "good": (GOOD, "✓", "Win"),
    "info": ("#9085e9", "i", "Note"),
}


def insight(level: str, title: str, body: str) -> None:
    color, icon, tag = _LEVELS[level]
    st.markdown(
        f"""<div class="ppi-insight"><div class="icon" style="color:{color}">{icon}</div>
        <div><div class="title"><span class="tag" style="color:{color}">{tag}</span>{html.escape(title)}</div>
        <div class="body">{html.escape(body)}</div></div></div>""",
        unsafe_allow_html=True,
    )


def learn(title: str, body_html: str) -> None:
    """Collapsible plain-English explanation of a metric or concept."""
    with st.expander(f"📘  {title}"):
        st.markdown(f'<div class="ppi-learn">{body_html}</div>', unsafe_allow_html=True)


def empty_state(dataset_label: str) -> None:
    st.info(f"This view needs **{dataset_label}** data. Import it on the **Data Import** page, "
            "or switch the sidebar data source back to sample data.", icon="📥")
