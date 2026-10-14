"""Premier Performance Intelligence - entry point.

Run locally with:   streamlit run app.py
"""

from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).parent / "assets"

st.set_page_config(
    page_title="Premier Performance Intelligence",
    page_icon=str(ASSETS / "icon.svg"),
    layout="wide",
    initial_sidebar_state="expanded",
)

from ppi import theme  # noqa: E402  (registers the Plotly template on import)
from ppi.state import build_sidebar  # noqa: E402

theme.inject_css()
st.logo(str(ASSETS / "logo.svg"), size="large", icon_image=str(ASSETS / "icon.svg"))

pages = {
    "Dashboard": [
        st.Page("views/executive.py", title="Executive Overview", icon=":material/space_dashboard:", default=True),
        st.Page("views/parts.py", title="Parts Profitability", icon=":material/settings:"),
        st.Page("views/techs.py", title="Technician Profitability", icon=":material/build:"),
        st.Page("views/advisors.py", title="Service Advisors", icon=":material/support_agent:"),
        st.Page("views/ros.py", title="RO Profitability", icon=":material/receipt_long:"),
        st.Page("views/operations.py", title="Operational Insights", icon=":material/insights:"),
    ],
    "Data": [
        st.Page("views/data_import.py", title="Data Import", icon=":material/upload_file:"),
    ],
}
nav = st.navigation(pages)
st.session_state["_ctx"] = build_sidebar()
nav.run()
