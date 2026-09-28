import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from constants import APP_NAME, APP_VERSION, LOGO_ICON  # noqa: E402
from ui import inject_global_css, render_sidebar_brand, theme_toggle  # noqa: E402

st.set_page_config(
    page_title=APP_NAME,
    page_icon=LOGO_ICON,
    layout="wide",
)
# Must run before inject_global_css() so a just-clicked toggle takes effect
# in the SAME rerun, not one run later (2026-09-26 theme-toggle feature).
theme_toggle()
inject_global_css()
render_sidebar_brand()

pg = st.navigation([
    st.Page("pages/1_overview.py", title="Overview", icon=":material/home:"),
    st.Page("pages/2_machine_capacity.py", title="Machine Capacity", icon=":material/precision_manufacturing:"),
    st.Page("pages/3_fulfillment.py", title="Fulfillment", icon=":material/inventory_2:"),
    st.Page("pages/4_flow_explorer.py", title="Flow Explorer", icon=":material/hub:"),
])
pg.run()
