"""Visual system: colors, global CSS, and the Plotly chart template.

Every color the app uses is defined here so the look can be changed in one place.
The categorical palette was validated for color-vision deficiency against the
card surface (#111722) - keep the order; it is what keeps adjacent series distinct.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# --- Surfaces & ink ---------------------------------------------------------
PAGE = "#0a0e14"
SURFACE = "#111722"
SURFACE_2 = "#161d2a"
BORDER = "rgba(255,255,255,0.08)"
TEXT = "#e8ecf2"
TEXT_2 = "#a9b1be"
MUTED = "#7d8594"
GRID = "#1f2733"
BASELINE = "#2e3747"

# --- Categorical series (fixed order, never cycled) --------------------------
SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = SERIES

# Sequential (one hue, dark surface -> bright) for heatmaps.
SEQUENTIAL_BLUE = ["#13243d", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#b7d3f6"]

# --- Status (reserved: never used as a series color) -------------------------
GOOD = "#0ca30c"
WARNING = "#fab219"
SERIOUS = "#ec835a"
CRITICAL = "#d03b3b"

FONT = "Inter, system-ui, -apple-system, 'Segoe UI', sans-serif"


def _register_plotly_template() -> None:
    axis = dict(
        showgrid=False,
        zeroline=False,
        linecolor=BASELINE,
        tickcolor=BASELINE,
        ticks="",
        tickfont=dict(color=MUTED, size=11),
        title=dict(font=dict(color=MUTED, size=11)),
        automargin=True,
    )
    template = go.layout.Template(
        layout=go.Layout(
            font=dict(family=FONT, color=TEXT_2, size=12),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            colorway=SERIES,
            margin=dict(l=8, r=8, t=8, b=8),
            xaxis=axis,
            yaxis={**axis, "showgrid": True, "gridcolor": GRID, "gridwidth": 1},
            hoverlabel=dict(bgcolor="#1b2331", bordercolor=BASELINE, font=dict(family=FONT, color=TEXT, size=12)),
            hovermode="closest",
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                font=dict(color=TEXT_2, size=11), bgcolor="rgba(0,0,0,0)", title=dict(text=""),
            ),
            bargap=0.28,
            bargroupgap=0.08,
        )
    )
    # Thin, rounded bar ends and 2px lines by default.
    template.data.bar = [go.Bar(marker=dict(cornerradius=4, line=dict(width=0)))]
    template.data.scatter = [go.Scatter(line=dict(width=2), marker=dict(size=8))]
    pio.templates["ppi_dark"] = template
    pio.templates.default = "ppi_dark"


_register_plotly_template()

PLOTLY_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"], "displayModeBar": "hover"}

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stApp, .stMarkdown, button, input, textarea, select {{
  font-family: {FONT};
}}
.stApp {{ background: {PAGE}; }}
.block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1480px; }}
footer, #MainMenu {{ visibility: hidden; }}
[data-testid="stHeader"] {{ background: transparent; }}

/* Sidebar */
section[data-testid="stSidebar"] {{ background: #0d121b; border-right: 1px solid {BORDER}; }}
section[data-testid="stSidebar"] .stMarkdown p {{ color: {TEXT_2}; }}

/* Typography */
h1, h2, h3, h4 {{ color: {TEXT}; letter-spacing: -0.01em; }}
.ppi-page-title {{ font-size: 1.9rem; font-weight: 700; color: {TEXT}; margin: 0; line-height: 1.2; }}
.ppi-page-sub {{ color: {MUTED}; font-size: 0.92rem; margin-top: 0.3rem; }}
.ppi-badge {{
  display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 0.75rem; font-weight: 600;
  background: {SURFACE_2}; color: {TEXT_2}; border: 1px solid {BORDER}; margin-left: 6px; white-space: nowrap;
}}
.ppi-badge.sample {{ color: {WARNING}; border-color: rgba(250,178,25,0.35); }}
.ppi-badge.live {{ color: {GOOD}; border-color: rgba(12,163,12,0.4); }}
.ppi-section {{ font-size: 0.78rem; font-weight: 600; letter-spacing: 0.09em; text-transform: uppercase;
  color: {MUTED}; margin: 1.6rem 0 0.6rem 0; }}
.ppi-card-title {{ font-size: 0.98rem; font-weight: 600; color: {TEXT}; margin: 0; }}
.ppi-card-sub {{ font-size: 0.8rem; color: {MUTED}; margin: 2px 0 6px 0; }}

/* Cards: any st.container(key="card...") */
[class*="st-key-card"] {{
  background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px; padding: 18px 18px 10px 18px;
}}

/* KPI tiles */
.ppi-kpi {{
  background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px; padding: 16px 18px 14px 18px;
  height: 100%; min-height: 150px;
}}
.ppi-kpi .label {{ font-size: 0.72rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: {MUTED}; }}
.ppi-kpi .value {{ font-size: 1.75rem; font-weight: 700; color: {TEXT}; margin-top: 6px; line-height: 1.15; }}
.ppi-kpi .delta {{ font-size: 0.8rem; font-weight: 600; margin-top: 8px; }}
.ppi-kpi .delta .vs {{ color: {MUTED}; font-weight: 500; }}
.ppi-kpi .foot {{ font-size: 0.78rem; color: {MUTED}; margin-top: 8px; }}
.ppi-kpi.accent {{ border-left: 3px solid {BLUE}; }}
.ppi-kpi.alert {{ border-left: 3px solid {CRITICAL}; }}

/* Insight / alert rows */
.ppi-insight {{
  display: flex; gap: 12px; align-items: flex-start; padding: 12px 14px; border-radius: 10px;
  background: {SURFACE_2}; border: 1px solid {BORDER}; margin-bottom: 8px;
}}
.ppi-insight .icon {{ font-size: 0.95rem; line-height: 1.35rem; font-weight: 700; min-width: 20px; text-align: center; }}
.ppi-insight .title {{ color: {TEXT}; font-weight: 600; font-size: 0.9rem; }}
.ppi-insight .body {{ color: {TEXT_2}; font-size: 0.84rem; margin-top: 2px; }}
.ppi-insight .tag {{ font-size: 0.68rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; margin-right: 6px; }}

/* Learn boxes */
.ppi-learn {{ border-left: 3px solid {VIOLET}; background: rgba(144,133,233,0.07); padding: 10px 14px;
  border-radius: 6px; color: {TEXT_2}; font-size: 0.86rem; margin: 6px 0 10px 0; }}
.ppi-learn b {{ color: {TEXT}; }}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid {BORDER}; }}
.stTabs [data-baseweb="tab"] {{ color: {MUTED}; font-weight: 600; padding: 8px 14px; }}
.stTabs [aria-selected="true"] {{ color: {TEXT}; }}

/* Charts: let the card surface show through */
[data-testid="stPlotlyChart"] .main-svg {{ background: transparent !important; }}

/* Dataframes */
[data-testid="stDataFrame"] {{ border: 1px solid {BORDER}; border-radius: 10px; }}

/* Buttons */
.stDownloadButton button, .stButton button {{ border-radius: 8px; font-weight: 600; }}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
