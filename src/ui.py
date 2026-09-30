"""
Reusable UI building blocks — the liquid-glass design system. Built once,
used by every page, so the app reads as one product. All colors/logo paths
come from constants.py (ARCHITECTURE.md: branding stays centralized).
"""
from __future__ import annotations

import base64
import math
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from constants import (
    APP_NAME, APP_TAGLINE, APP_VERSION, GOLD, GOLD_LIGHT, GOLD_DARK, GOLD_SOFT,
    OBSIDIAN, OBSIDIAN_2, GLASS_BG, GLASS_BG_STRONG, GLASS_BORDER, GLASS_BORDER_GOLD,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_ON_GOLD, LOGO_HERO, LOGO_ICON, SIDEBAR_BG,
    GRID_LINE, ZERO_LINE, PAGE_BG, TRACK_BG,
    STATUS_COLORS, COLOR_NEUTRAL, COLOR_WARNING, efficiency_color,
    OBSIDIAN_DARK, OBSIDIAN_2_DARK, GLASS_BG_DARK, GLASS_BG_STRONG_DARK, GLASS_BORDER_DARK,
    TEXT_PRIMARY_DARK, TEXT_SECONDARY_DARK, SIDEBAR_BG_DARK, GRID_LINE_DARK, ZERO_LINE_DARK,
    PAGE_BG_DARK, TRACK_BG_DARK,
    OBSIDIAN_LIGHT, OBSIDIAN_2_LIGHT, GLASS_BG_LIGHT, GLASS_BG_STRONG_LIGHT, GLASS_BORDER_LIGHT,
    TEXT_PRIMARY_LIGHT, TEXT_SECONDARY_LIGHT, SIDEBAR_BG_LIGHT, GRID_LINE_LIGHT, ZERO_LINE_LIGHT,
    PAGE_BG_LIGHT, TRACK_BG_LIGHT,
)


_UNSET = object()


def _apply_theme():
    """Switch the app between dark (default) and light by reassigning THIS
    MODULE's own OBSIDIAN/GLASS_*/TEXT_PRIMARY/TEXT_SECONDARY names —
    everything else (gold accents, status colors, TEXT_ON_GOLD,
    GLASS_BORDER_GOLD) stays fixed in both themes, per user's explicit
    "maintain all other color" request (2026-09-26). Only ui.py reads these
    neutrals directly (confirmed via grep — every page only imports
    TEXT_ON_GOLD/status colors, which don't change), so mutating ui.py's
    own globals here is enough; no page needs to know theming exists.
    Called once per script run, from inject_global_css() — the single
    choke point app.py calls before any page renders — so every function
    below sees the right colors for the rest of that run.
    """
    global OBSIDIAN, OBSIDIAN_2, GLASS_BG, GLASS_BG_STRONG, GLASS_BORDER, TEXT_PRIMARY, TEXT_SECONDARY
    global SIDEBAR_BG, GRID_LINE, ZERO_LINE, PAGE_BG, TRACK_BG
    if st.session_state.get("bi_theme") == "light":
        OBSIDIAN, OBSIDIAN_2 = OBSIDIAN_LIGHT, OBSIDIAN_2_LIGHT
        GLASS_BG, GLASS_BG_STRONG, GLASS_BORDER = GLASS_BG_LIGHT, GLASS_BG_STRONG_LIGHT, GLASS_BORDER_LIGHT
        TEXT_PRIMARY, TEXT_SECONDARY = TEXT_PRIMARY_LIGHT, TEXT_SECONDARY_LIGHT
        SIDEBAR_BG = SIDEBAR_BG_LIGHT
        GRID_LINE, ZERO_LINE = GRID_LINE_LIGHT, ZERO_LINE_LIGHT
        PAGE_BG = PAGE_BG_LIGHT
        TRACK_BG = TRACK_BG_LIGHT
    else:
        OBSIDIAN, OBSIDIAN_2 = OBSIDIAN_DARK, OBSIDIAN_2_DARK
        GLASS_BG, GLASS_BG_STRONG, GLASS_BORDER = GLASS_BG_DARK, GLASS_BG_STRONG_DARK, GLASS_BORDER_DARK
        TEXT_PRIMARY, TEXT_SECONDARY = TEXT_PRIMARY_DARK, TEXT_SECONDARY_DARK
        SIDEBAR_BG = SIDEBAR_BG_DARK
        GRID_LINE, ZERO_LINE = GRID_LINE_DARK, ZERO_LINE_DARK
        PAGE_BG = PAGE_BG_DARK
        TRACK_BG = TRACK_BG_DARK


def theme_toggle():
    """Sidebar light/dark switch — sets session_state["bi_theme"] and
    reruns so _apply_theme() (called from inject_global_css() on the next
    run) picks it up. Call from app.py, before inject_global_css()."""
    is_light = st.sidebar.toggle(
        "☀️ Light theme", value=st.session_state.get("bi_theme") == "light", key="bi_theme_toggle",
    )
    st.session_state["bi_theme"] = "light" if is_light else "dark"


def persisted_default(key: str, fallback):
    """Read a widget's last value from a shadow "persist" key that
    survives page navigation, falling back to `fallback` on first use.

    Root cause confirmed 2026-09-23: Streamlit clears a widget's own
    session_state[key] when switching between st.navigation pages, even
    with an explicit `key=` set — a widget's returned value is NOT durable
    across page navigation on its own, only plain session_state entries
    assigned directly in code are (e.g. weekly_workbook_bytes). So every
    filter/sort widget that should survive navigating away and back stores
    its value under a SEPARATE `_persist_<key>` entry via `persist()`
    below, and reads that (not the widget's own key) for its `default`/
    `index` on the next run.
    """
    val = st.session_state.get(f"_persist_{key}", _UNSET)
    return fallback if val is _UNSET else val


def persist(key: str, value):
    """Save a widget's current value to its shadow persist key — call
    once right after creating the widget, every run. See
    persisted_default() for why this indirection exists."""
    st.session_state[f"_persist_{key}"] = value


def persisted_index(key: str, options: list, fallback_index: int = 0) -> int:
    """Like persisted_default(), but for selectbox/radio widgets, which
    take an `index` into `options` rather than a `default` value. Falls
    back to `fallback_index` on first use or if the persisted value has
    dropped out of `options` (e.g. a week no longer offering it)."""
    val = st.session_state.get(f"_persist_{key}", _UNSET)
    if val is _UNSET or val not in options:
        return fallback_index
    return options.index(val)


def _img_data_uri(path: str) -> str:
    p = Path(path)
    mime = "image/svg+xml" if p.suffix == ".svg" else "image/png"
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


# --------------------------------------------------------------------------
# Global CSS — liquid glass design language, applied once per page
# --------------------------------------------------------------------------

def inject_global_css():
    _apply_theme()
    st.markdown(
        """
        <link rel="stylesheet"
              href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,400,0..1,0" />
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <style>
        .bi-icon {{
            font-family: 'Material Symbols Outlined';
            font-weight: normal;
            font-style: normal;
            line-height: 1;
            letter-spacing: normal;
            text-transform: none;
            display: inline-block;
            white-space: nowrap;
            word-wrap: normal;
            direction: ltr;
            -webkit-font-smoothing: antialiased;
        }}
        html, body, .stApp {{
            background: {PAGE_BG} !important;
            color: {TEXT_PRIMARY};
        }}
        [data-testid="stAppViewContainer"] {{ background: transparent; }}
        [data-testid="stHeader"] {{ background: transparent; }}
        [data-testid="stToolbar"] {{ background: transparent; }}

        h1, h2, h3, h4, h5, h6 {{ color: {TEXT_PRIMARY} !important; font-weight: 600 !important; letter-spacing: -0.01em; }}
        p, span, label, .stMarkdown, div {{ color: {TEXT_PRIMARY}; }}
        [data-testid="stCaptionContainer"], .stCaption, small {{ color: {TEXT_SECONDARY} !important; }}

        /* ---------------- Sidebar: frosted glass panel ---------------- */
        [data-testid="stSidebar"] {{
            background: {SIDEBAR_BG};
            backdrop-filter: blur(28px) saturate(150%);
            -webkit-backdrop-filter: blur(28px) saturate(150%);
            border-right: 1px solid {GLASS_BORDER};
        }}
        [data-testid="stSidebarNav"] a, [data-testid="stSidebarNavLink"] {{
            border-radius: 14px !important;
            margin: 2px 8px !important;
            transition: all 0.18s ease;
        }}
        [data-testid="stSidebarNav"] a:hover {{
            background: {GOLD_SOFT} !important;
            transform: translateX(2px);
        }}
        [data-testid="stSidebarNav"] a[aria-current="page"] {{
            background: linear-gradient(90deg, {GOLD_SOFT}, transparent) !important;
            border-left: 2px solid {GOLD};
            box-shadow: 0 0 18px rgba(252,202,4,0.15);
        }}

        /* ---------------- Native Streamlit chrome (popovers, dropdowns,
           tooltips, dialogs) ----------------
           These render through a portal (#stFloatingOverlayPortal) using
           Streamlit's OWN base theme (.streamlit/config.toml, fixed to
           dark) rather than our custom classes above — our theme toggle
           doesn't reach them on its own, so they stayed hard-coded dark
           even after switching to light (bug caught 2026-09-26). Inline
           styles Streamlit sets via JS can still be beaten by an
           `!important` rule in a stylesheet, which is what these do. */
        [data-testid="stPopoverBody"], [data-baseweb="popover"],
        [data-baseweb="menu"], ul[role="listbox"],
        [data-testid="stTooltipContent"], [role="tooltip"],
        [data-testid="stDialog"] [role="dialog"] {{
            background-color: {OBSIDIAN_2} !important;
            color: {TEXT_PRIMARY} !important;
            border-color: {GLASS_BORDER} !important;
        }}
        [data-testid="stPopoverBody"] *, [data-baseweb="menu"] *, ul[role="listbox"] * {{
            color: {TEXT_PRIMARY} !important;
        }}
        /* The popover's own TRIGGER button (data-testid="stPopoverButton")
           is a separate element from stButton/stDownloadButton/
           stFormSubmitButton above — same gold-pill treatment as every
           other button in the app, added here since it didn't match those
           selectors and was left hard-coded dark (bug caught 2026-09-26). */
        [data-testid="stPopoverButton"] {{
            background: linear-gradient(135deg, {GOLD_LIGHT}, {GOLD} 55%, {GOLD_DARK}) !important;
            color: {TEXT_ON_GOLD} !important;
            border: none !important;
            border-radius: 999px !important;
            box-shadow: 0 4px 18px rgba(252,202,4,0.22), 0 1px 0 rgba(255,255,255,0.25) inset;
        }}
        [data-testid="stPopoverButton"] * {{
            color: {TEXT_ON_GOLD} !important;
        }}

        /* ---------------- Buttons: pill, gold gradient, glow on hover ---------------- */
        [data-testid="stButton"] button, [data-testid="stDownloadButton"] button,
        [data-testid="stFormSubmitButton"] button {{
            background: linear-gradient(135deg, {GOLD_LIGHT}, {GOLD} 55%, {GOLD_DARK});
            color: {TEXT_ON_GOLD} !important;
            border: none;
            border-radius: 999px;
            font-weight: 600;
            padding: 0.5rem 1.4rem;
            box-shadow: 0 4px 18px rgba(252,202,4,0.22), 0 1px 0 rgba(255,255,255,0.25) inset;
            transition: transform 0.16s ease, box-shadow 0.16s ease;
        }}
        [data-testid="stButton"] button:hover, [data-testid="stDownloadButton"] button:hover,
        [data-testid="stFormSubmitButton"] button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 26px rgba(252,202,4,0.32), 0 1px 0 rgba(255,255,255,0.3) inset;
        }}

        /* ---------------- Inputs, selects, uploader: glass surfaces ---------------- */
        [data-testid="stFileUploaderDropzone"], [data-testid="stFileUploader"] section {{
            background: {GLASS_BG} !important;
            border: 1.5px dashed {GLASS_BORDER_GOLD} !important;
            border-radius: 20px !important;
            backdrop-filter: blur(20px) saturate(140%);
        }}
        [data-baseweb="select"] > div, .stTextInput input, .stNumberInput input,
        [data-testid="stMultiSelect"] > div,
        [data-testid="stSelectbox"] [role="group"], [data-testid="stMultiSelect"] [role="group"] {{
            background: {GLASS_BG} !important;
            border: 1px solid {GLASS_BORDER} !important;
            border-radius: 14px !important;
            color: {TEXT_PRIMARY} !important;
        }}
        [data-baseweb="select"] > div:focus-within,
        [data-testid="stSelectbox"] [role="group"]:focus-within,
        [data-testid="stMultiSelect"] [role="group"]:focus-within {{
            border-color: {GOLD} !important;
            box-shadow: 0 0 0 3px {GOLD_SOFT} !important;
        }}
        /* React-Aria ComboBox/select input + its dropdown listbox — a
           different DOM structure from the older [data-baseweb="select"]
           this app was originally styled for (Streamlit version upgrade);
           the old selector above silently matched nothing, and it stayed
           unnoticed in dark mode since Streamlit's own native dark
           default happened to blend in — only became visible as a bug
           once the light theme (2026-09-26) needed it to actually flip. */
        [data-testid="stSelectbox"] input, [data-testid="stMultiSelect"] input {{
            background: transparent !important;
            color: {TEXT_PRIMARY} !important;
        }}
        [data-testid="stSelectbox"] [role="listbox"], [data-testid="stMultiSelect"] [role="listbox"] {{
            background-color: {OBSIDIAN_2} !important;
            border: 1px solid {GLASS_BORDER} !important;
            color: {TEXT_PRIMARY} !important;
        }}
        [data-testid="stSelectbox"] [role="option"], [data-testid="stMultiSelect"] [role="option"] {{
            color: {TEXT_PRIMARY} !important;
        }}
        /* The dropdown's actual opaque background lives on
           [data-testid="stSelectboxVirtualDropdown"] — a DIFFERENT
           element from [role="listbox"] above, and rendered in a portal
           OUTSIDE [data-testid="stSelectbox"] entirely (confirmed
           2026-09-28 by walking the live DOM's parent chain), so neither
           of the two selectors above ever actually matched it. Its
           hard-coded dark background/light text is what made the
           dropdown look broken/unreadable in light theme. */
        [data-testid="stSelectboxVirtualDropdown"] {{
            background-color: {OBSIDIAN_2} !important;
            border: 1px solid {GLASS_BORDER} !important;
        }}
        [data-testid="stSelectboxVirtualDropdown"] [role="option"] {{
            color: {TEXT_PRIMARY} !important;
        }}
        /* The multiselect widget's own dropdown portal is a DIFFERENT
           element with a DIFFERENT testid ("stMultiSelectDropdown", no
           "Virtual") from the plain selectbox's ("stSelectboxVirtualDropdown"
           above) — confirmed 2026-09-28 by inspecting the live DOM; the
           selectbox fix alone did not cover it, same hard-coded dark
           background bug. */
        [data-testid="stMultiSelectDropdown"] {{
            background-color: {OBSIDIAN_2} !important;
            border: 1px solid {GLASS_BORDER} !important;
            color: {TEXT_PRIMARY} !important;
        }}
        [data-testid="stMultiSelectDropdown"] [role="option"] {{
            color: {TEXT_PRIMARY} !important;
        }}

        /* ---------------- Alerts: glass with colored left border ---------------- */
        [data-testid="stAlert"] {{
            background: {GLASS_BG_STRONG} !important;
            backdrop-filter: blur(20px) saturate(140%);
            border: 1px solid {GLASS_BORDER} !important;
            border-radius: 18px !important;
            box-shadow: 0 8px 30px rgba(0,0,0,0.35);
        }}

        /* ---------------- Metrics ---------------- */
        [data-testid="stMetric"] {{
            background: {GLASS_BG} !important;
            border: 1px solid {GLASS_BORDER} !important;
            border-radius: 20px !important;
            padding: 14px 18px !important;
            backdrop-filter: blur(20px) saturate(140%);
        }}
        [data-testid="stMetricValue"] {{ color: {TEXT_PRIMARY} !important; }}
        [data-testid="stMetricLabel"] {{ color: {TEXT_SECONDARY} !important; }}

        /* ---------------- DataFrame / tables ---------------- */
        [data-testid="stDataFrame"], [data-testid="stTable"] {{
            border-radius: 18px !important;
            overflow: hidden;
            border: 1px solid {GLASS_BORDER} !important;
        }}

        /* ---------------- Expander ---------------- */
        [data-testid="stExpander"] {{
            background: {GLASS_BG} !important;
            border: 1px solid {GLASS_BORDER} !important;
            border-radius: 18px !important;
            backdrop-filter: blur(20px) saturate(140%);
        }}

        /* ---------------- Radio / checkbox accent ---------------- */
        [data-testid="stRadio"] label span:first-child,
        [data-testid="stCheckbox"] label span:first-child {{
            accent-color: {GOLD};
        }}

        /* ---------------- Our own glass utility classes ---------------- */
        .bi-glass-card {{
            background: {GLASS_BG};
            border: 1px solid {GLASS_BORDER};
            border-radius: 24px;
            padding: 1.4rem 1.6rem;
            backdrop-filter: blur(24px) saturate(150%);
            -webkit-backdrop-filter: blur(24px) saturate(150%);
            box-shadow: 0 10px 40px rgba(0,0,0,0.35), 0 1px 0 rgba(255,255,255,0.06) inset;
            transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
        }}
        .bi-glass-card:hover {{
            transform: translateY(-3px);
            border-color: {GLASS_BORDER_GOLD};
            box-shadow: 0 16px 50px rgba(0,0,0,0.45), 0 0 0 1px rgba(252,202,4,0.08);
        }}
        .bi-pill {{
            display: inline-flex; align-items: center; gap: 6px;
            padding: 4px 14px; border-radius: 999px; font-size: 12px; font-weight: 600;
            border: 1px solid {GLASS_BORDER};
        }}
        .bi-nav-card-icon {{
            display: flex; align-items: center; justify-content: center;
            width: 52px; height: 52px; border-radius: 16px; flex-shrink: 0;
            background: {GLASS_BG};
            border: 1px solid {GLASS_BORDER};
            transition: background 0.18s ease, box-shadow 0.18s ease;
        }}
        .bi-nav-card-icon .bi-icon {{
            font-size: 28px !important; color: {GOLD} !important;
        }}

        /* ---------------- Glass container (non-HTML content) ----------------
           ui.kpi_cards() glass-wraps plain HTML by putting the .bi-glass-card
           class directly on a markdown div. That doesn't work for content
           Streamlit renders as its own component (e.g. a Plotly chart), so
           ui.glass_container() instead puts the SAME visual treatment on the
           st.container(key=...) wrapper div itself — any key prefixed
           "bi_glass_" gets it, so a chart-based card and an HTML kpi_cards()
           card can sit side by side looking identical (2026-09-23). */
        div[class*="st-key-bi_glass_"] {{
            background: {GLASS_BG};
            border: 1px solid {GLASS_BORDER};
            border-radius: 24px;
            padding: 1rem 1.3rem 0.6rem;
            backdrop-filter: blur(24px) saturate(150%);
            -webkit-backdrop-filter: blur(24px) saturate(150%);
            box-shadow: 0 10px 40px rgba(0,0,0,0.35), 0 1px 0 rgba(255,255,255,0.06) inset;
            transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
            min-height: 108px;
            height: 100%;
            box-sizing: border-box;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        div[class*="st-key-bi_glass_"]:hover {{
            transform: translateY(-3px);
            border-color: {GLASS_BORDER_GOLD};
            box-shadow: 0 16px 50px rgba(0,0,0,0.45), 0 0 0 1px rgba(252,202,4,0.08);
        }}
        /* Force the whole Streamlit wrapper chain (column -> vertical block
           -> layout wrapper) to stretch to full height, not just size to
           its own content — otherwise align-items:stretch on the outer
           st.columns() row has nothing to act on, and two glass cards with
           different content (plain text vs. a Plotly chart) end up
           different heights (2026-09-23). */
        div[data-testid="stColumn"]:has(> div div[class*="st-key-bi_glass_"]),
        div[data-testid="stColumn"]:has(> div div[class*="st-key-bi_pill_"]) {{
            display: flex;
        }}
        div[data-testid="stColumn"]:has(> div div[class*="st-key-bi_glass_"]) > div,
        div[data-testid="stColumn"]:has(> div div[class*="st-key-bi_glass_"]) [data-testid="stVerticalBlock"],
        div[data-testid="stColumn"]:has(> div div[class*="st-key-bi_glass_"]) [data-testid="stLayoutWrapper"],
        div[data-testid="stColumn"]:has(> div div[class*="st-key-bi_pill_"]) > div,
        div[data-testid="stColumn"]:has(> div div[class*="st-key-bi_pill_"]) [data-testid="stVerticalBlock"],
        div[data-testid="stColumn"]:has(> div div[class*="st-key-bi_pill_"]) [data-testid="stLayoutWrapper"] {{
            height: 100%;
        }}
        div[class*="st-key-bi_glass_"], div[class*="st-key-bi_pill_"] {{
            align-self: stretch;
        }}

        /* ---------------- Gold pill card (KPI cards, "look like our
           buttons" — 2026-09-23) ----------------
           Same warm gold gradient/glow/pill-radius as ui.py's own button
           CSS above, applied to a glass_container-style wrapper instead of
           a <button> — for KPI cards the user wants visually matching the
           "Download table as CSV" pill buttons rather than the neutral
           dark glass-card look. Any key prefixed "bi_pill_" gets it. */
        div[class*="st-key-bi_pill_"] {{
            background: linear-gradient(135deg, {GOLD_LIGHT}, {GOLD} 55%, {GOLD_DARK});
            border: none;
            border-radius: 999px;
            padding: 1rem 1.6rem;
            box-shadow: 0 4px 18px rgba(252,202,4,0.22), 0 1px 0 rgba(255,255,255,0.25) inset;
            transition: transform 0.16s ease, box-shadow 0.16s ease;
            min-height: 108px;
            box-sizing: border-box;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        div[class*="st-key-bi_pill_"]:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 26px rgba(252,202,4,0.32), 0 1px 0 rgba(255,255,255,0.3) inset;
        }}

        /* ---------------- Teacup gauge hover tooltip ----------------
           See ui.teacup_gauge_html() — one small custom tooltip per
           machine-line gauge (Production vs Available, Machines, Shifts
           Worked). Defined once here rather than per-card, since the
           same 28-card grid would otherwise repeat this rule 28 times. */
        .bi-teacup-tooltip {{
            position: absolute;
            bottom: 108%;
            left: 50%;
            transform: translateX(-50%);
            background: {OBSIDIAN_2};
            border: 1px solid {GLASS_BORDER_GOLD};
            border-radius: 10px;
            padding: 0.55rem 0.8rem;
            font-size: 12px;
            line-height: 1.5;
            white-space: nowrap;
            color: {TEXT_PRIMARY};
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.15s ease;
            box-shadow: 0 10px 30px rgba(0,0,0,0.45);
            z-index: 20;
        }}
        .bi-teacup-gauge:hover .bi-teacup-tooltip {{
            opacity: 1;
        }}

        /* ---------------- Clickable nav cards: invisible button overlay ----------------
           See ui.nav_card() — the visible card is plain HTML; a same-size,
           fully transparent st.button sits on top of it (via a keyed
           container) and does the actual navigation through
           st.switch_page(), which preserves session state. A raw <a href>
           does NOT (confirmed bug, 2026-09-21) — Streamlit only does
           client-side routing for its own nav widgets. */
        div[class*="st-key-navcard_"] {{
            position: relative;
            cursor: pointer;
        }}
        div[class*="st-key-navcard_"]:hover .bi-nav-card-icon {{
            background: {GOLD_SOFT};
            box-shadow: 0 0 20px rgba(252,202,4,0.25);
        }}
        div[class*="st-key-navcard_"]:hover .bi-glass-card {{
            transform: translateY(-3px);
            border-color: {GLASS_BORDER_GOLD};
            box-shadow: 0 16px 50px rgba(0,0,0,0.45), 0 0 0 1px rgba(252,202,4,0.08);
        }}
        /* The immediate parent (stElementContainer) is the one Streamlit
           sizes to width:fit-content for a bare button — override IT, not
           just the stButton div inside it, or the click target stays tiny. */
        div[class*="st-key-navcard_"] [data-testid="stElementContainer"]:has([data-testid="stButton"]) {{
            position: absolute !important; inset: 0 !important;
            width: 100% !important; height: 100% !important; margin: 0 !important; z-index: 5 !important;
        }}
        div[class*="st-key-navcard_"] [data-testid="stButton"] {{
            position: absolute !important; inset: 0 !important;
            width: 100% !important; height: 100% !important; margin: 0 !important;
        }}
        div[class*="st-key-navcard_"] [data-testid="stButton"] button {{
            width: 100% !important; height: 100% !important; opacity: 0; cursor: pointer;
            background: transparent !important; box-shadow: none !important; border: none !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------
# Header / hero
# --------------------------------------------------------------------------

def render_header(subtitle: str | None = None):
    """Compact header used on every non-Overview page."""
    logo_uri = _img_data_uri(LOGO_ICON)
    st.markdown(
        f"""
        <div class="bi-glass-card" style="display:flex;align-items:center;justify-content:space-between;
                    gap:16px;margin-bottom:1.6rem;padding:1rem 1.4rem;">
            <div style="display:flex;align-items:center;gap:14px;">
                <img src="{logo_uri}" style="height:44px;width:44px;border-radius:12px;object-fit:cover;" />
                <div>
                    <div style="font-size:20px;font-weight:700;color:{TEXT_PRIMARY};line-height:1.15;">
                        {APP_NAME}
                    </div>
                    {f'<div style="font-size:13px;color:{TEXT_SECONDARY};margin-top:1px;">{subtitle}</div>' if subtitle else ''}
                </div>
            </div>
            <span class="bi-pill" style="color:{GOLD};border-color:{GLASS_BORDER_GOLD};background:{GOLD_SOFT};">
                {APP_VERSION}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_brand():
    """Mini logo + app name + version pill, relocated via JS into
    Streamlit's native stSidebarHeader slot — the strip above the page
    nav, next to the collapse control.

    st.markdown strips <script> tags (dangerouslySetInnerHTML never
    executes them), so this uses st.components.v1.html — a real iframe
    where scripts DO run — and reaches into the parent document to move
    a purpose-built element into place. Guarded so a rerun doesn't stack
    duplicates.
    """
    import streamlit.components.v1 as components

    logo_uri = _img_data_uri(LOGO_ICON)
    components.html(
        f"""
        <script>
        (function() {{
            const doc = window.parent.document;
            let brand = doc.getElementById('bi-sidebar-brand');
            if (!brand) {{
                brand = doc.createElement('div');
                brand.id = 'bi-sidebar-brand';
                brand.style.cssText = 'display:flex;align-items:center;gap:9px;width:100%;';
                brand.innerHTML = `
                    <img src="{logo_uri}" style="height:30px;width:30px;border-radius:8px;object-fit:cover;flex-shrink:0;" />
                    <div style="font-size:13px;font-weight:700;color:{TEXT_PRIMARY};line-height:1.2;flex:1;
                                white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                        {APP_NAME}
                    </div>
                    <span class="bi-pill" style="color:{GOLD};border-color:{GLASS_BORDER_GOLD};background:{GOLD_SOFT};
                                font-size:10px;padding:2px 9px;flex-shrink:0;border-radius:999px;border-style:solid;border-width:1px;">
                        {APP_VERSION}
                    </span>
                `;
            }}
            const header = doc.querySelector('[data-testid="stSidebarHeader"]');
            if (header) {{
                header.style.height = 'auto';
                header.style.paddingBottom = '6px';
                if (!header.contains(brand)) {{
                    header.insertBefore(brand, header.firstChild);
                }}
            }}
        }})();
        </script>
        """,
        height=0,
    )


def render_hero():
    """Hero section — Overview page only. Logo left, name/tagline/badge beside it."""
    logo_uri = _img_data_uri(LOGO_HERO)
    st.markdown(
        f"""
        <div class="bi-glass-card" style="display:flex;align-items:center;gap:24px;
                    padding:1.4rem 1.8rem;margin-bottom:1.8rem;
                    background: radial-gradient(500px 220px at 0% 0%, rgba(252,202,4,0.10), transparent 65%),
                                {GLASS_BG};">
            <img src="{logo_uri}" style="height:72px;width:auto;border-radius:14px;
                        box-shadow:0 8px 26px rgba(0,0,0,0.5);flex-shrink:0;" />
            <div>
                <div style="font-size:26px;font-weight:700;color:{TEXT_PRIMARY};letter-spacing:-0.02em;
                            line-height:1.2;">
                    {APP_NAME}
                </div>
                <div style="font-size:14px;color:{TEXT_SECONDARY};margin-top:2px;">
                    {APP_TAGLINE}
                </div>
                <div style="margin-top:8px;">
                    <span class="bi-pill" style="color:{GOLD};border-color:{GLASS_BORDER_GOLD};background:{GOLD_SOFT};">
                        ● Live workbook analysis &nbsp;·&nbsp; {APP_VERSION}
                    </span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------
# Cards / badges
# --------------------------------------------------------------------------

def nav_card(icon: str, title: str, description: str, page_path: str, key: str):
    """Clickable glass card that navigates to another page of this app —
    bigger icon beside the name, description beneath.

    `icon` is a Material Symbols ligature name (e.g. "precision_manufacturing",
    same set used by st.Page's :material/...: icons). `page_path` is the
    same path string used to register the page in app.py's st.navigation
    (e.g. "pages/2_machine_capacity.py") — passed straight to
    st.switch_page(), which is a real (session-preserving) Streamlit
    rerun, not a browser navigation.

    Bug found 2026-09-21: an earlier version used a raw `<a href="...">`
    wrapping the card. Streamlit does NOT intercept arbitrary anchor tags
    for client-side routing (only its own st.page_link / sidebar nav do
    that) — clicking it triggered a full browser reload and silently
    dropped the uploaded workbook from session_state. Fixed by rendering
    the card as plain HTML (non-interactive) and overlaying an invisible,
    full-size st.button on top of it via CSS, wired to st.switch_page().
    """
    with st.container(key=f"navcard_{key}"):
        st.markdown(
            f"""
            <div class="bi-glass-card bi-nav-card">
                <div style="display:flex;align-items:center;gap:14px;">
                    <div class="bi-nav-card-icon">
                        <span class="bi-icon" translate="no">{icon}</span>
                    </div>
                    <div style="font-size:18px;font-weight:600;color:{TEXT_PRIMARY};">{title}</div>
                </div>
                <div style="font-size:13px;color:{TEXT_SECONDARY};margin-top:12px;line-height:1.5;">
                    {description}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        clicked = st.button("Open", key=f"navbtn_{key}")
    if clicked:
        st.switch_page(page_path)


def status_badge(status: str) -> str:
    color = STATUS_COLORS.get(status, COLOR_NEUTRAL)
    return (
        f'<span class="bi-pill" style="color:{color};border-color:{color}55;'
        f'background:{color}1F;white-space:nowrap;">{status}</span>'
    )


def kpi_cards(metrics: dict[str, str], highlight: set[str] | frozenset[str] = frozenset()):
    """Row of KPI cards, one per (label, value) pair, all in the same
    st.columns() row so they align and size together. `highlight` (a set
    of labels) renders those specific cards as a small, round,
    gold-highlighted pill instead of the default glass card — for a
    derived/secondary KPI that should read as a quick highlight without
    breaking out of the row (confirmed by user 2026-09-29, Fulfillment
    page's Overall Fulfillment %)."""
    cols = st.columns(len(metrics))
    for col, (label, value) in zip(cols, metrics.items()):
        with col:
            if label in highlight:
                st.markdown(
                    f"""
                    <div class="bi-glass-card" style="padding:1.1rem 1.3rem;border-radius:999px;
                                background:{GOLD_SOFT};border-color:{GLASS_BORDER_GOLD};text-align:center;">
                        <div style="font-size:12px;color:{GOLD};text-transform:uppercase;
                                    letter-spacing:0.04em;font-weight:700;">{label}</div>
                        <div style="font-size:26px;font-weight:700;color:{GOLD};margin-top:4px;">{value}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""
                    <div class="bi-glass-card" style="padding:1.1rem 1.3rem;">
                        <div style="font-size:12px;color:{TEXT_SECONDARY};text-transform:uppercase;
                                    letter-spacing:0.04em;">{label}</div>
                        <div style="font-size:26px;font-weight:700;color:{TEXT_PRIMARY};margin-top:4px;">{value}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def glass_container(key: str):
    """A st.container whose own div is styled as a glass card (translucent
    blur, rounded corners, matching .bi-glass-card) — use this instead of
    kpi_cards() when the card holds something Streamlit renders as its own
    component (e.g. a Plotly chart) rather than plain HTML, so the two
    kinds of card look identical side by side. Pair with metric_label()
    for the same uppercase label typography kpi_cards() uses internally.
    """
    return st.container(key=f"bi_glass_{key}")


def gold_pill_container(key: str):
    """Like glass_container(), but styled as a warm gold-gradient pill
    card matching the site's own buttons (same gradient/glow/pill-radius
    as "Download table as CSV" etc.) — confirmed by user 2026-09-23 for
    the Overview page's KPI cards. Pair with metric_label(dark=True) for
    label text with enough contrast on the gold background."""
    return st.container(key=f"bi_pill_{key}")


def metric_label(text: str, dark: bool = False, center: bool = False):
    """Small uppercase label matching kpi_cards()'s internal typography —
    put at the top of a glass_container() when its content isn't plain
    HTML kpi_cards() could render the label+value for directly.

    `dark=True` swaps to a dark-on-gold color for use inside a
    gold_pill_container(), where the light TEXT_SECONDARY default has no
    contrast against the gold background. `center=True` centers the text
    horizontally instead of the default left alignment; it also nudges
    the label up slightly (negative margin-top) since gold_pill_container
    vertically centers its whole label+content block and a centered title
    otherwise sits a bit low/cramped against the value below it
    (confirmed by user 2026-09-29)."""
    color = f"{TEXT_ON_GOLD}99" if dark else TEXT_SECONDARY
    text_align = "center" if center else "left"
    margin_top = "-10px" if center else "0"
    st.markdown(
        f'<div style="font-size:12px;color:{color};text-transform:uppercase;'
        f'letter-spacing:0.04em;text-align:{text_align};margin-top:{margin_top};">{text}</div>',
        unsafe_allow_html=True,
    )


def tea_brewing_loader(message: str = "Brewing your dashboard…"):
    """CSS-only steaming-teacup loading animation, on-brand for a tea
    company's dashboard — replaces the default Streamlit spinner during
    a page's actual analysis/load step (confirmed by user 2026-09-24).

    Returns the st.empty() placeholder holding it — call `.empty()` on
    the result once the real work is done to clear it:

        loader = ui.tea_brewing_loader("Brewing your dashboard…")
        result = _load_dashboard(raw_bytes, supplement_bytes)  # the slow part
        loader.empty()

    Pair with `@st.cache_data(show_spinner=False)` on the wrapped
    function so Streamlit's own spinner text doesn't also show — on a
    cache hit (same inputs, already computed) the call returns instantly
    and this loader barely flashes, which is the intended behavior: it's
    only visible during genuine analysis time, not every rerun.
    """
    placeholder = st.empty()
    placeholder.markdown(
        f"""
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                    padding:3rem 0;gap:1rem;">
            <div style="position:relative;width:70px;height:70px;">
                <div style="position:absolute;bottom:38px;left:16px;width:4px;height:18px;
                            background:rgba(245,241,232,0.55);border-radius:4px;
                            animation:bi-steam-rise 1.8s ease-in-out infinite;animation-delay:0s;"></div>
                <div style="position:absolute;bottom:38px;left:30px;width:4px;height:18px;
                            background:rgba(245,241,232,0.55);border-radius:4px;
                            animation:bi-steam-rise 1.8s ease-in-out infinite;animation-delay:0.4s;"></div>
                <div style="position:absolute;bottom:38px;left:44px;width:4px;height:18px;
                            background:rgba(245,241,232,0.55);border-radius:4px;
                            animation:bi-steam-rise 1.8s ease-in-out infinite;animation-delay:0.8s;"></div>
                <div style="position:absolute;bottom:0;left:10px;width:50px;height:35px;
                            background:linear-gradient(135deg,{GOLD_LIGHT},{GOLD} 55%,{GOLD_DARK});
                            border-radius:0 0 18px 18px;
                            box-shadow:0 4px 18px rgba(252,202,4,0.28),0 1px 0 rgba(255,255,255,0.25) inset;"></div>
                <div style="position:absolute;bottom:8px;right:0px;width:16px;height:16px;
                            border:4px solid {GOLD};border-left:none;border-radius:0 50% 50% 0;"></div>
            </div>
            <div style="color:{TEXT_SECONDARY};font-size:14px;letter-spacing:0.02em;">{message}</div>
        </div>
        <style>
        @keyframes bi-steam-rise {{
            0%   {{ opacity:0; transform:translateY(0) translateX(0) scaleY(0.6); }}
            30%  {{ opacity:0.85; }}
            100% {{ opacity:0; transform:translateY(-26px) translateX(4px) scaleY(1.4); }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    return placeholder


# --------------------------------------------------------------------------
# Charts — dark, glass-compatible styling
# --------------------------------------------------------------------------

def plotly_chart(fig: go.Figure, **kwargs):
    """Thin wrapper around st.plotly_chart that always passes theme=None.

    Bug caught 2026-09-26 (theme toggle): st.plotly_chart's DEFAULT
    theme="streamlit" makes Streamlit override a figure's own
    layout.font.color with ITS OWN native theme color (from
    .streamlit/config.toml, fixed dark) — every chart's axis/tick text
    stayed a light color even after our figures were built with the
    correct (now dark-on-light) TEXT_PRIMARY. theme=None tells Streamlit
    to render the figure exactly as we built it. Use this instead of
    st.plotly_chart everywhere in the app so no call site can forget it.
    """
    return st.plotly_chart(fig, theme=None, **kwargs)

def _plot_layout() -> dict:
    """Built fresh on every call (not a frozen module-level dict) so it
    always reflects the CURRENT theme — TEXT_PRIMARY/GRID_LINE/ZERO_LINE
    are reassigned by _apply_theme() at runtime; a dict built once at
    import time would permanently bake in whatever theme was active the
    first time ui.py was imported (2026-09-26 theme-toggle fix)."""
    return dict(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT_PRIMARY),
        xaxis=dict(gridcolor=GRID_LINE, zerolinecolor=ZERO_LINE),
        yaxis=dict(gridcolor=GRID_LINE, zerolinecolor=ZERO_LINE),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )


def style_fig(fig: go.Figure) -> go.Figure:
    fig.update_layout(**_plot_layout())
    return fig


def bullet_chart(rows: list[dict], show_capacity: bool = True, show_plan: bool = True) -> go.Figure:
    """rows: [{name, capacity, plan, production, status, color, hover_note}, ...]

    `capacity` is the bar's normalization scale — the value that maps to a
    full-width (100%) track. Set `show_capacity=True` only when it's a real,
    meaningful figure (e.g. machine Total Available Tbgs); the Machine
    Capacity page does this. Set `show_capacity=False` when `capacity` is
    just an internal scaling helper with no real-world meaning (e.g. the
    Fulfillment page's max(Plan, Produced) padding) — this hides the
    "Capacity" row from the hover tooltip and the axis title, so the chart
    never implies a number that doesn't exist. (Bug found 2026-09-21: the
    Fulfillment page was labeling its scaling helper as "Capacity" in the
    tooltip, which read as real machine capacity but wasn't.)

    `show_plan` (default True) — set False for a pure Capacity-vs-Production
    comparison with no Plan involved at all: drops the Plan marker line drawn
    on the bar AND the "Plan" row from the hover tooltip. Confirmed by user
    2026-09-23: the Machine Capacity page's Performance Comparison charts
    compare Capacity (Tbgs) against Production (Tbgs) only — Plan there
    would be Booked Week Plan, which is a different unit (CFC) and not part
    of what that chart is showing.

    `color` (optional, hex string) — confirmed 2026-09-22: this colors the
    HOVER TOOLTIP BOX for that row, not the bar itself (bar fill always
    stays the normal status/gold color). Used e.g. for the SKU
    over-production explanation (green/red/grey hover box), which is a
    property of "what does this number mean," not "how full is this bar."
    (Corrected from an earlier version that mistakenly recolored the bar.)
    `hover_note` (optional string, may contain "<br>") is appended to that
    row's tooltip verbatim — used to explain *why* the hover box is
    colored the way it is, right where the color is seen.
    """
    names = [r["name"] for r in rows]
    # Floored to a small minimum visible width (1.5%) — a literal 0
    # production (not uncommon for the worst-ranked rows in a Bottom 5
    # chart) renders as a genuine 0px-wide bar, which is visually
    # indistinguishable from the chart having failed to render at all
    # (bug caught 2026-09-26). The floor makes "this SKU/line produced
    # nothing" a small but visible sliver instead of nothing on screen —
    # same floor pattern already used for zero-flow Sankey links
    # (sku_machine_sankey). Real nonzero values are unaffected unless
    # they'd already round to an imperceptible sliver.
    prod_pct = [max(min(r["production"] / r["capacity"] * 100, 100), 1.5) if r["capacity"] else 1.5 for r in rows]
    plan_pct = [min(r["plan"] / r["capacity"] * 100, 100) if r["capacity"] else 0 for r in rows]
    colors = [STATUS_COLORS.get(r.get("status"), GOLD) for r in rows]
    notes = [r.get("hover_note", "") for r in rows]
    hover_bg = [r.get("color") or OBSIDIAN_2 for r in rows]
    hover_font = [TEXT_ON_GOLD if r.get("color") else TEXT_PRIMARY for r in rows]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[100] * len(rows), y=names, orientation="h",
        marker=dict(color=TRACK_BG), showlegend=False, hoverinfo="skip",
        width=0.5,
    ))
    if show_capacity and show_plan:
        customdata = [[r["capacity"], r["production"], r["plan"], n] for r, n in zip(rows, notes)]
        hovertemplate = (
            "<b>%{y}</b><br>"
            "Capacity: %{customdata[0]:,.0f}<br>"
            "Production: %{customdata[1]:,.0f}<br>"
            "Plan: %{customdata[2]:,.0f}"
            "%{customdata[3]}<extra></extra>"
        )
    elif show_capacity and not show_plan:
        customdata = [[r["capacity"], r["production"], n] for r, n in zip(rows, notes)]
        hovertemplate = (
            "<b>%{y}</b><br>"
            "Capacity: %{customdata[0]:,.0f}<br>"
            "Production: %{customdata[1]:,.0f}"
            "%{customdata[2]}<extra></extra>"
        )
    elif not show_capacity and show_plan:
        customdata = [[r["production"], r["plan"], n] for r, n in zip(rows, notes)]
        hovertemplate = (
            "<b>%{y}</b><br>"
            "Production: %{customdata[0]:,.0f}<br>"
            "Plan: %{customdata[1]:,.0f}"
            "%{customdata[2]}<extra></extra>"
        )
    else:
        customdata = [[r["production"], n] for r, n in zip(rows, notes)]
        hovertemplate = (
            "<b>%{y}</b><br>"
            "Production: %{customdata[0]:,.0f}"
            "%{customdata[1]}<extra></extra>"
        )
    fig.add_trace(go.Bar(
        x=prod_pct, y=names, orientation="h",
        marker=dict(color=colors), showlegend=False, width=0.5,
        customdata=customdata,
        hovertemplate=hovertemplate,
        hoverlabel=dict(bgcolor=hover_bg, font=dict(color=hover_font)),
    ))
    if show_plan:
        fig.add_trace(go.Scatter(
            x=plan_pct, y=names, mode="markers",
            marker=dict(symbol="line-ns", size=18, line=dict(width=3, color=TEXT_PRIMARY)),
            showlegend=False,
            customdata=[[r["plan"]] for r in rows],
            hovertemplate="Plan: %{customdata[0]:,.0f}<extra></extra>",
        ))
    # Left margin sized explicitly from the longest label in THIS chart,
    # with real padding baked in — not left to Plotly's own automargin.
    # History (bug caught 2026-09-26, each step verified by measuring the
    # actual rendered SVG geometry, not just eyeballing a screenshot):
    # `l=10` alone clipped long names (up to 40 chars, see _sku_row()'s
    # truncation) down to their last couple of characters. `automargin`
    # fixed the clipping but sizes the margin to fit the text EXACTLY, so
    # the label ran right up against the bars with a ~1px gap — unreadably
    # tight. Padding the label text itself (plain spaces, then
    # non-breaking spaces) turned out not to help either: Plotly.js (and
    # JS's own String.trim(), which its tick-label code appears to use)
    # strips ALL Unicode space separators, non-breaking included, so any
    # trailing "space-like" character got silently removed again. An
    # explicit margin — a real gap between plot area and container edge —
    # is the only thing that reliably measured a nonzero, visible gap.
    # `yaxis.automargin` must stay OFF: it re-shrinks whatever margin.l is
    # given back down to the tightest fit (re-verified 2026-09-26 — with
    # automargin still on, this exact left_margin calculation measured the
    # same ~1px gap as before, since automargin overwrote it every render).
    # Sized from actual measured text width (~7.3px/char at this font
    # size, confirmed 2026-09-26 by reading a rendered label's real
    # bounding box) plus the ticklabelstandoff gap below, with only a
    # small safety buffer — not padded generously the way an earlier
    # version was, which made the label column consume more than half the
    # chart's width and left the bars looking squeezed off to one side
    # instead of flush with the "Top 5/Bottom 5" heading above them (bug
    # caught 2026-09-26).
    max_name_len = max((len(n) for n in names), default=0)
    left_margin = min(max(max_name_len * 7.3 + 10 + 8, 40), 260)
    fig.update_layout(
        # `+120` (was `+80`) gives the extra `b=45` bottom margin below
        # room to come out of newly-added height rather than the bars'
        # own space, so increasing the bottom margin doesn't squash the
        # bars shorter.
        barmode="overlay", height=max(300, 40 * len(rows) + 120),
        # `r=28` (was 10) gives the "100" tick label room to render
        # without its text overflowing past the plot's right edge into
        # whatever sits beside it (e.g. the neighboring Top5/Bottom5
        # column) — same bug/verification pass as the left-margin fix.
        # `b=45` (was 10) — the x-axis tick labels ("0"/"50"/"100") AND
        # the axis title ("Relative to Plan/Produced") both need to
        # render below the bars; 10px wasn't enough room for either,
        # so they rendered past the chart's own bottom edge and
        # overlapped whatever Streamlit content came right after it on
        # the page (bug caught 2026-09-28).
        margin=dict(l=left_margin, r=28, t=10, b=45),
        # `showgrid=False` on both axes — confirmed by user 2026-09-26,
        # this chart reads better as clean bars with no vertical/
        # horizontal gridlines. `ticklabelstandoff` genuinely shifts the
        # y-axis label away from the axis (unlike padding margin.l alone,
        # which only gives the label MORE ROOM to render without clipping
        # — extra margin.l beyond what the text needs doesn't turn into a
        # gap, Plotly just left-pads the unused space; confirmed
        # 2026-09-26 by reading the rendered figure's actual layout.margin
        # off the live Plotly object). It only works with automargin OFF —
        # automargin fights it and resets any gap back to ~1px.
        xaxis=dict(
            title="% of capacity" if show_capacity else "Relative to Plan/Produced",
            range=[0, 105], showgrid=False, zeroline=False,
        ),
        yaxis=dict(ticklabelstandoff=10, showgrid=False, zeroline=False),
    )
    return style_fig(fig)


def format_indian_compact(value: float) -> str:
    """Abbreviate a number into Indian Lakh/Crore notation, spelled out —
    e.g. 4,933,271 -> "49 Lakhs", 123,400,000 -> "12.3 Crores" — for a
    widget's on-screen display where the full exact figure belongs in a
    hover tooltip instead (confirmed by user 2026-09-23, spelled-out unit
    confirmed 2026-09-24). Automatically rolls over to the next unit as a
    value grows (Lakh -> Crore), not fixed to whatever unit it started at.
    Falls back to a plain comma-grouped number below 1 lakh, where the
    abbreviation wouldn't save any space. Singular "Lakh"/"Crore" only
    when the rounded amount is exactly 1, plural otherwise.

    Rounding edge case (caught 2026-09-24): rounding to whole Lakhs can
    push a value that's just under 1 Crore up to "100 Lakhs" — which
    reads as a full Crore but is labeled Lakhs. Checked for explicitly
    below rather than trusting the raw magnitude>=1_00_00_000 threshold
    alone.
    """
    magnitude = abs(value)
    if magnitude >= 1_00_00_000:
        crores = value / 1_00_00_000
        unit = "Crore" if round(crores, 1) == 1 else "Crores"
        return f"{crores:.1f} {unit}"
    if magnitude >= 1_00_000:
        lakhs = round(value / 1_00_000)
        if abs(lakhs) >= 100:
            crores = value / 1_00_00_000
            unit = "Crore" if round(crores, 1) == 1 else "Crores"
            return f"{crores:.1f} {unit}"
        unit = "Lakh" if abs(lakhs) == 1 else "Lakhs"
        return f"{lakhs:.0f} {unit}"
    return f"{value:,.0f}"


def _compact_metric_fig(display_text: str, hover_html: str, text_color: str) -> go.Figure:
    """Shared shell for a big-number card whose exact value(s) are only a
    hover away — an invisible full-card bar carries the hover, a single
    text annotation carries the display. Used by ratio_card() and
    run_rate_card(); meant to sit inside a glass_container()/
    gold_pill_container() with a metric_label() above it.
    """
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[1], y=[""], orientation="h",
        marker=dict(color="rgba(0,0,0,0)"), showlegend=False, width=1.6,
        hovertemplate=hover_html + "<extra></extra>",
        hoverlabel=dict(bgcolor=OBSIDIAN_2, font=dict(color=TEXT_PRIMARY)),
    ))
    fig.update_layout(
        height=54,
        margin=dict(l=0, r=0, t=4, b=0),
        xaxis=dict(visible=False, range=[0, 1], fixedrange=True),
        yaxis=dict(visible=False, fixedrange=True),
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        annotations=[dict(
            text=display_text,
            x=0, y=0.5, xref="paper", yref="paper", showarrow=False,
            font=dict(size=26, color=text_color),
            xanchor="left",
        )],
    )
    return fig


def ratio_card(
    pct: float | None, produced: float, plan: float, text_color: str | None = None,
    last_week_plan: float | None = None,
) -> go.Figure:
    """Overall Fulfillment % widget — the big % is the display, the raw
    figures behind it are a hover away instead of separate KPI cards
    (2026-09-23). Meant to sit inside a ui.glass_container() (with a
    ui.metric_label() above it for the title) so it visually matches a
    kpi_cards() card exactly — this figure itself is fully transparent
    (no visible fill of its own, just a wide invisible bar for the hover
    hit-area) so the container's own background/border/blur is what's
    actually seen.

    `text_color` overrides the default efficiency-band color for the big
    percentage — pass this (e.g. TEXT_ON_GOLD) when the card sits on a
    gold_pill_container(), where green/yellow/red would clash with or
    disappear into the gold background.

    `pct` is Total Produced / (This Week Plan + Last Week Uncommitted
    Plan) — confirmed by user 2026-09-29 that this combined figure (not
    Produced / This Week Plan alone) is the one the big % should show.
    Hover shows the three raw values behind it (Total Produced, Last
    Week Uncommitted Plan, This Week Plan) with no percentage repeated
    (confirmed by user 2026-09-29 — the % is already the headline).
    """
    display_pct = pct if pct is not None else 0.0
    color = text_color or (efficiency_color(display_pct) if pct is not None else COLOR_NEUTRAL)
    hover_lines = [f"Total Produced: {produced:,.0f}"]
    if last_week_plan is not None:
        hover_lines.append(f"Last Week Uncommitted Plan: {last_week_plan:,.0f}")
    hover_lines.append(f"This Week Plan: {plan:,.0f}")
    hover_html = "<br>".join(hover_lines)
    return _compact_metric_fig(f"{display_pct:.1f}%" if pct is not None else "N/A", hover_html, color)


def run_rate_card(
    run_rate: float, prev_run_rate: float | None, text_color: str,
    required_run_rate: float | None = None,
):
    """Weekly Run Rate KPI — big centered Actual number with a small
    status chip underneath showing the Required target and the
    shortfall/on-track state ("Option 4" of 5 mockups shown to the user
    2026-09-29, chosen over a two-equal-numbers layout and a comparison
    bar — both rejected as not neat enough). Abbreviated to Indian
    Lakh/Crore notation (confirmed 2026-09-23); the exact figures are a
    native browser tooltip (title attribute) on the big number and the
    chip. Renders directly via st.markdown, so call this in place (no
    ui.plotly_chart() wrapper — it isn't a go.Figure).

    `required_run_rate` (optional) is the flat daily target (Booked Week
    Plan / 6, CFC->Tbgs converted) for the same week Run Rate is anchored
    to. Omit it to fall back to just the big Actual number (no chip —
    there's nothing to compare against).
    """
    delta_html = ""
    if prev_run_rate:
        delta_pct = (run_rate - prev_run_rate) / prev_run_rate * 100
        arrow = "▲" if delta_pct >= 0 else "▼"
        delta_html = (
            f'<div style="font-size:11px;color:{text_color}99;margin-top:4px;" '
            f'title="Previous week: {prev_run_rate:,.0f} Tbgs/day">{arrow} {abs(delta_pct):.1f}% vs last week</div>'
        )

    chip_html = ""
    if required_run_rate is not None:
        of_target_pct = (run_rate / required_run_rate * 100) if required_run_rate else 0
        if of_target_pct >= 100:
            chip_text = f"✓ On track — {of_target_pct:.0f}% of target"
        else:
            chip_text = f"⚠ Need {format_indian_compact(required_run_rate)} — {100 - of_target_pct:.0f}% short"
        chip_html = (
            '<div style="display:inline-flex;align-items:center;gap:6px;margin-top:8px;'
            f'background:{text_color}1F;border-radius:999px;padding:5px 14px;font-size:12px;font-weight:700;color:{text_color};" '
            f'title="Required: {required_run_rate:,.0f} Tbgs/day">{chip_text}</div>'
        )

    # Every tag's opening stays on ONE line (no attribute wrapped onto the
    # next) and the whole thing is built with no embedded newlines —
    # Streamlit's react-markdown HTML-block detection silently fails and
    # falls back to showing raw text once a tag's attributes span two
    # source lines (bug hit and isolated 2026-09-29 building this exact
    # card), unlike kpi_cards()'s plain multi-line triple-quoted HTML
    # where every tag opens and closes on its own line.
    st.markdown(
        '<div style="text-align:center;">'
        f'<div style="font-size:34px;font-weight:800;color:{text_color};line-height:1;" title="Exact: {run_rate:,.0f} Tbgs/day">{format_indian_compact(run_rate)}</div>'
        f'{delta_html}'
        f'{chip_html}'
        '</div>',
        unsafe_allow_html=True,
    )


def big_stat_with_chip(value: float, chip_text: str | None, text_color: str, exact_suffix: str = ""):
    """Single big centered number (Indian Lakh/Crore notation) with an
    optional small status chip underneath — the single-value counterpart
    to run_rate_card()'s "Option 4" layout, for a KPI pill that has just
    one figure to show rather than an Actual/Required pair (confirmed by
    user 2026-09-29 for the Overview page's Targeted Tbgs pill). Renders
    directly via st.markdown; call in place (no ui.plotly_chart()
    wrapper — it isn't a go.Figure)."""
    chip_html = ""
    if chip_text:
        chip_html = (
            '<div style="display:inline-flex;align-items:center;gap:6px;margin-top:8px;'
            f'background:{text_color}1F;border-radius:999px;padding:5px 14px;font-size:12px;font-weight:700;color:{text_color};">{chip_text}</div>'
        )
    st.markdown(
        '<div style="text-align:center;">'
        f'<div style="font-size:34px;font-weight:800;color:{text_color};line-height:1;" title="Exact: {value:,.0f}{exact_suffix}">{format_indian_compact(value)}</div>'
        f'{chip_html}'
        '</div>',
        unsafe_allow_html=True,
    )


def gauge_chart(label: str, value: float) -> go.Figure:
    """Compact radial gauge for one machine line's Efficiency % — used in
    the Overview page's small-multiple grid (one per machine line).

    Bands match constants.efficiency_color() (Green >50%, Yellow 20-50%,
    Red <20%) for both the bar color and the background step zones, so a
    gauge reads with the same color language as every efficiency-colored
    cell elsewhere in the app. Value is clamped to [0, 100] for display —
    a line running above 100% still shows a full bar rather than
    overflowing the gauge, same clamping bullet_chart already does.
    """
    display_value = max(0.0, min(value, 100.0))
    color = efficiency_color(value)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=display_value,
        number=dict(suffix="%", font=dict(size=20, color=TEXT_PRIMARY)),
        title=dict(text=label, font=dict(size=11, color=TEXT_SECONDARY)),
        gauge=dict(
            axis=dict(range=[0, 100], tickwidth=0, showticklabels=False),
            bar=dict(color=color, thickness=0.35),
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            steps=[
                dict(range=[0, 20], color="rgba(255,107,107,0.14)"),
                dict(range=[20, 50], color="rgba(255,194,75,0.14)"),
                dict(range=[50, 100], color="rgba(61,220,132,0.14)"),
            ],
        ),
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT_PRIMARY),
        height=170,
        margin=dict(l=24, r=24, t=44, b=10),
    )
    return fig


def teacup_gauge_html(
    label: str, value: float, produced: float | None = None, available: float | None = None,
    machines: int | None = None, shifts_worked: float | None = None,
    fulfillment_pct: float | None = None,
) -> str:
    """Alternate, tea-themed style for one machine line's Efficiency %
    gauge — a circular gold progress ring around a small teacup icon,
    referencing a photoreal "tea level" gauge image the user shared
    2026-09-24 (visual inspiration only, not a pixel copy — this is pure
    CSS/SVG so all ~28 machine-line cards on the Overview grid stay
    lightweight; no per-card raster image).

    Same color bands and clamping as gauge_chart() (Green >50%, Yellow
    20-50%, Red <20%, value clamped to [0, 100] for display) — this is a
    reskin of the same data, not a different calculation. Returns raw
    HTML for st.markdown(..., unsafe_allow_html=True); each card is
    self-contained (no shared ids/keyframes), so it's safe to call in a
    loop.

    The optional `produced`/`available`/`machines`/`shifts_worked`/
    `fulfillment_pct` args (all already present in status_df — no extra
    computation) drive a hover tooltip (confirmed by user 2026-09-24): raw
    Production vs Available Tbgs, machine count, shifts worked, and that
    line's Fulfillment % — turns a bare "%" into "how much, out of how
    much, from how many machines/shifts, and did it meet plan". Omit any
    of them to leave that line out of the tooltip; `fulfillment_pct` may
    also be NaN (a line with no plan data) — shown as "N/A".
    """
    display_value = max(0.0, min(value, 100.0))
    color = efficiency_color(value)
    radius = 68
    circumference = 2 * math.pi * radius
    offset = circumference * (1 - display_value / 100)

    tooltip_lines = []
    if produced is not None and available is not None:
        tooltip_lines.append(f"Production: {produced:,.0f} / {available:,.0f} Tbgs")
    if machines is not None:
        tooltip_lines.append(f"Machines: {machines:.0f}" if isinstance(machines, float) else f"Machines: {machines}")
    if shifts_worked is not None:
        tooltip_lines.append(f"Shifts Worked: {shifts_worked:,.0f}")
    if fulfillment_pct is not None:
        fulfillment_text = f"{fulfillment_pct:.1f}%" if fulfillment_pct == fulfillment_pct else "N/A"
        tooltip_lines.append(f"Fulfillment: {fulfillment_text}")
    tooltip_html = "<br>".join(tooltip_lines)
    tooltip_div = f'<div class="bi-teacup-tooltip">{tooltip_html}</div>' if tooltip_html else ""

    return f"""
    <div class="bi-teacup-gauge" style="position:relative;display:flex;flex-direction:column;
                align-items:center;gap:0.35rem;padding:0.4rem 0;">
        {tooltip_div}
        <div style="font-size:11px;color:{TEXT_SECONDARY};text-transform:uppercase;
                    letter-spacing:0.04em;text-align:center;">{label}</div>
        <div style="position:relative;width:160px;height:160px;">
            <svg width="160" height="160" viewBox="0 0 160 160" style="transform:rotate(-90deg);">
                <circle cx="80" cy="80" r="{radius}" fill="none"
                        stroke="rgba(245,241,232,0.08)" stroke-width="10" />
                <circle cx="80" cy="80" r="{radius}" fill="none"
                        stroke="{color}" stroke-width="10" stroke-linecap="round"
                        stroke-dasharray="{circumference:.2f}"
                        stroke-dashoffset="{offset:.2f}" />
            </svg>
            <div style="position:absolute;inset:0;display:flex;flex-direction:column;
                        align-items:center;justify-content:center;gap:0.3rem;">
                <div style="position:relative;width:40px;height:26px;">
                    <div style="position:absolute;bottom:0;left:6px;width:28px;height:18px;
                                background:linear-gradient(135deg,{GOLD_LIGHT},{GOLD} 55%,{GOLD_DARK});
                                border-radius:0 0 9px 9px;
                                box-shadow:0 2px 10px rgba(252,202,4,0.22),0 1px 0 rgba(255,255,255,0.25) inset;"></div>
                    <div style="position:absolute;bottom:3px;right:-1px;width:9px;height:9px;
                                border:3px solid {GOLD};border-left:none;border-radius:0 50% 50% 0;"></div>
                </div>
                <div style="font-size:22px;font-weight:700;color:{TEXT_PRIMARY};">{display_value:.1f}%</div>
            </div>
        </div>
    </div>
    """


def funnel_chart(funnel: dict, title: str = "") -> go.Figure:
    fig = go.Figure(go.Funnel(
        y=list(funnel.keys()),
        x=list(funnel.values()),
        textinfo="value+percent initial",
        marker=dict(color=[GOLD_DARK, GOLD, GOLD_LIGHT]),
        connector=dict(line=dict(color=GLASS_BORDER, width=1)),
    ))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=30 if title else 10, b=10), title=title)
    return style_fig(fig)


def sankey_chart(df, source_col: str, target_col: str, value_col: str, source_prefix: str = "", target_prefix: str = "") -> go.Figure:
    """Generic two-column Sankey: one flow per (source, target) row, width
    = value. `source_prefix`/`target_prefix` disambiguate labels that could
    collide between the two columns (e.g. a machine number that happens to
    match a product name) without cluttering the visible node label.
    """
    sources = sorted(df[source_col].unique())
    targets = sorted(df[target_col].unique())
    source_labels = [f"{source_prefix}{s}" for s in sources]
    target_labels = [f"{target_prefix}{t}" for t in targets]
    labels = source_labels + target_labels
    source_idx = {s: i for i, s in enumerate(sources)}
    target_idx = {t: i + len(sources) for i, t in enumerate(targets)}

    link_colors = [GOLD_SOFT] * len(df)
    node_colors = [GOLD] * len(sources) + [GLASS_BG_STRONG] * len(targets)

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            label=labels,
            color=node_colors,
            pad=14, thickness=16,
            line=dict(color=GLASS_BORDER, width=0.5),
        ),
        link=dict(
            source=[source_idx[s] for s in df[source_col]],
            target=[target_idx[t] for t in df[target_col]],
            value=df[value_col].tolist(),
            color=link_colors,
            hovertemplate="%{source.label} → %{target.label}<br>%{value:,.0f}<extra></extra>",
        ),
        textfont=dict(color=TEXT_PRIMARY, size=12),
    ))
    fig.update_layout(
        height=max(360, 26 * len(labels) + 60),
        margin=dict(l=10, r=10, t=10, b=10),
    )
    return style_fig(fig)


def sku_machine_sankey(df) -> go.Figure:
    """Item -> Machine Line Sankey showing EVERY assigned machine line, not
    just the ones with output (confirmed by user 2026-09-22). `df` needs
    columns Item, Machine Line, Booked Week Plan, Produced (see
    fulfillment.sku_machine_line_flows).

    A Produced=0 flow would be visually invisible at its real width, so it
    gets a small visible floor instead — but the floor is never the number
    shown on hover, which always reflects the real figures:
      - Produced > 0                -> hover shows Produced (gold link)
      - Produced == 0, Booked > 0   -> hover shows Booked, labeled "not yet
                                        produced" (amber link)
      - Produced == 0, Booked == 0  -> hover shows 0 plainly, nothing to
                                        explain (neutral gray link)
    """
    sources = sorted(df["Item"].unique())
    targets = sorted(df["Machine Line"].unique())
    labels = sources + targets
    source_idx = {s: i for i, s in enumerate(sources)}
    target_idx = {t: i + len(sources) for i, t in enumerate(targets)}

    real_produced = df.loc[df["Produced"] > 0, "Produced"]
    floor = max(real_produced.max() * 0.03, 1) if not real_produced.empty else 1

    values, colors, hover_text = [], [], []
    for _, r in df.iterrows():
        if r["Produced"] > 0:
            values.append(r["Produced"])
            colors.append(GOLD_SOFT)
            hover_text.append(f"Produced: {r['Produced']:,.0f}")
        elif r["Booked Week Plan"] > 0:
            values.append(floor)
            colors.append(f"{COLOR_WARNING}55")
            hover_text.append(f"Booked: {r['Booked Week Plan']:,.0f} (not yet produced)")
        else:
            values.append(floor)
            colors.append(f"{COLOR_NEUTRAL}33")
            hover_text.append("Produced: 0")

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            label=labels,
            color=[GOLD] * len(sources) + [GLASS_BG_STRONG] * len(targets),
            pad=14, thickness=16,
            line=dict(color=GLASS_BORDER, width=0.5),
        ),
        link=dict(
            source=[source_idx[s] for s in df["Item"]],
            target=[target_idx[t] for t in df["Machine Line"]],
            value=values,
            color=colors,
            customdata=hover_text,
            hovertemplate="%{source.label} → %{target.label}<br>%{customdata}<extra></extra>",
        ),
        textfont=dict(color=TEXT_PRIMARY, size=12),
    ))
    fig.update_layout(
        height=max(360, 26 * len(labels) + 60),
        margin=dict(l=10, r=10, t=10, b=10),
    )
    return style_fig(fig)


def blocked_state(message: str):
    st.info(message)
