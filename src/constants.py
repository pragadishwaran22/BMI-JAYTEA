"""
Centralized branding + theme. Colors, logo paths, and version live here
only — change the product's look by editing this file alone, nothing else.
Palette sampled directly from the JAY logo (assets/logo_hero.png).
"""

APP_NAME = "Benchmark Intelligence"
APP_SHORT_NAME = "BI"
APP_TAGLINE = "Manufacturing performance, decoded."
APP_VERSION = "v1.0"

# --------------------------------------------------------------------------
# Brand palette — sampled from the logo; edit here to re-theme everywhere
# --------------------------------------------------------------------------
GOLD = "#FCCA04"          # primary accent, sampled from logo ring
GOLD_LIGHT = "#FFE066"
GOLD_DARK = "#8A6200"
GOLD_SOFT = "rgba(252, 202, 4, 0.16)"   # tinted fills/borders

# Dark theme (the app's original/default look) — kept under _DARK names so
# ui.py can switch to the _LIGHT set below at runtime (theme toggle, added
# 2026-09-26) while every OTHER color (gold accents, status colors) stays
# exactly the same in both themes, per user's explicit "maintain all other
# color" request.
OBSIDIAN_DARK = "#0A0A0C"       # page background
OBSIDIAN_2_DARK = "#151518"     # secondary surface
GLASS_BG_DARK = "rgba(255, 255, 255, 0.055)"
GLASS_BG_STRONG_DARK = "rgba(255, 255, 255, 0.09)"
GLASS_BORDER_DARK = "rgba(255, 255, 255, 0.12)"
TEXT_PRIMARY_DARK = "#F5F1E8"    # warm white
TEXT_SECONDARY_DARK = "#ABA89F"  # muted silver
GRID_LINE_DARK = "rgba(255, 255, 255, 0.08)"     # Plotly chart gridlines
ZERO_LINE_DARK = "rgba(255, 255, 255, 0.12)"     # Plotly chart zero-line/axis
TRACK_BG_DARK = "rgba(255, 255, 255, 0.16)"      # bullet_chart's 0-100% background track

# Light theme — glossy gold/yellow-into-white (user request 2026-09-26,
# superseding an earlier light-grey-metallic attempt). Flat fallbacks
# (OBSIDIAN_LIGHT/OBSIDIAN_2_LIGHT, used wherever a solid color is needed —
# popovers, tooltips) are white/pale-gold-cream; the actual glossy sheen is
# the PAGE_BG_LIGHT gradient below, applied to the page body itself.
OBSIDIAN_LIGHT = "#FFFFFF"       # page background fallback (flat)
OBSIDIAN_2_LIGHT = "#8B6508"     # secondary surface — 70%-darker metallic gold (user request 2026-09-28)
GLASS_BG_LIGHT = "rgba(10, 10, 12, 0.045)"
GLASS_BG_STRONG_LIGHT = "rgba(10, 10, 12, 0.075)"
GLASS_BORDER_LIGHT = "rgba(10, 10, 12, 0.12)"
TEXT_PRIMARY_LIGHT = "#1A1A1D"   # near-black
TEXT_SECONDARY_LIGHT = "#EBDCA6" # light warm gold-cream — muted charcoal was unreadable
                                  # against the darker metallic-gold background (user
                                  # request 2026-09-28); only this line changed.
GRID_LINE_LIGHT = "rgba(10, 10, 12, 0.08)"       # Plotly chart gridlines
ZERO_LINE_LIGHT = "rgba(10, 10, 12, 0.15)"       # Plotly chart zero-line/axis
TRACK_BG_LIGHT = "rgba(10, 10, 12, 0.16)"        # bullet_chart's 0-100% background track

# Defaults — dark, matching the app's original look. ui.py reassigns these
# module-level names at runtime via apply_theme() when the user switches to
# light (see ui.py's `_apply_theme`); every other module keeps importing
# these same plain names (OBSIDIAN, TEXT_PRIMARY, etc.) and gets whichever
# theme is currently active without needing to know theming exists.
# Sidebar's own frosted-glass gradient — kept as a separate pair since it's
# a two-stop gradient, not a flat color, so it can't be derived from
# OBSIDIAN/OBSIDIAN_2 alone.
SIDEBAR_BG_DARK = "linear-gradient(180deg, rgba(21,21,24,0.92), rgba(10,10,12,0.96))"
SIDEBAR_BG_LIGHT = "linear-gradient(180deg, rgba(139,101,8,0.95), rgba(92,66,4,0.97))"  # 70%-darker metallic gold (user request 2026-09-28)

# Full page background — a gradient, not a flat color, so it's kept
# separate from OBSIDIAN (the flat fallback other elements still use).
# Dark: original subtle gold highlights on near-black. Light: a glossy
# gold/yellow-into-white sheen (2026-09-26), deepened to a darker metallic
# yellow per follow-up feedback — two stronger gold radial highlights
# (top-left, top-right) over a warm-white-to-deep-gold diagonal wash,
# echoing the gold pill buttons' own gloss.
PAGE_BG_DARK = (
    "radial-gradient(1100px 620px at 12% -8%, rgba(252,202,4,0.10), transparent 60%),"
    "radial-gradient(900px 500px at 100% 0%, rgba(252,202,4,0.06), transparent 55%),"
    "#0A0A0C"
)
PAGE_BG_LIGHT = (
    # 70%-darker metallic gold (user request 2026-09-28, superseding the
    # earlier lighter gold-into-white version) — same two-highlight
    # structure, just a deeper/more saturated bronze-gold throughout.
    "radial-gradient(1200px 700px at 12% -10%, rgba(139,101,8,0.55), transparent 55%),"
    "radial-gradient(900px 600px at 100% 0%, rgba(92,66,4,0.48), transparent 55%),"
    "linear-gradient(160deg, #B8860B 0%, #8B6508 45%, #5C4204 100%)"
)

OBSIDIAN = OBSIDIAN_DARK
OBSIDIAN_2 = OBSIDIAN_2_DARK
GLASS_BG = GLASS_BG_DARK
GLASS_BG_STRONG = GLASS_BG_STRONG_DARK
GLASS_BORDER = GLASS_BORDER_DARK
TEXT_PRIMARY = TEXT_PRIMARY_DARK
TEXT_SECONDARY = TEXT_SECONDARY_DARK
SIDEBAR_BG = SIDEBAR_BG_DARK
GRID_LINE = GRID_LINE_DARK
ZERO_LINE = ZERO_LINE_DARK
PAGE_BG = PAGE_BG_DARK
TRACK_BG = TRACK_BG_DARK

GLASS_BORDER_GOLD = "rgba(252, 202, 4, 0.35)"   # gold-tinted; unchanged in both themes
TEXT_ON_GOLD = "#1A1400"    # dark text for gold-filled surfaces (contrast) — unchanged in both themes

# Status semantic colors (used for Efficiency bands, Status quadrant, badges)
COLOR_GOOD = "#3DDC84"      # On Track / Efficiency > 50%  (kept distinct from brand gold)
COLOR_WARNING = "#FFC24B"   # Under-scheduled / Efficiency 20-50%
COLOR_CRITICAL = "#FF6B6B"  # Underperforming / Efficiency < 20%
COLOR_NEUTRAL = "#8B8A85"   # No plan data / unknown

STATUS_COLORS = {
    "On Track": COLOR_GOOD,
    "Under-scheduled": COLOR_WARNING,
    "Falling short despite full shifts": COLOR_CRITICAL,
    "Underperforming": COLOR_CRITICAL,
    "No plan data": COLOR_NEUTRAL,
}


def efficiency_color(pct: float) -> str:
    """Section 1 spec: Green >50%, Yellow 20-50%, Red <20%."""
    if pct > 50:
        return COLOR_GOOD
    if pct >= 20:
        return COLOR_WARNING
    return COLOR_CRITICAL


# --------------------------------------------------------------------------
# Changeovers
# --------------------------------------------------------------------------
# Default downtime cost per changeover, in minutes — confirmed by user
# 2026-09-23. Real changeover time varies by machine/product; this is a
# placeholder default until real per-machine numbers are available (same
# "default now, overridable later" pattern as the CFC conversion factors).
CHANGEOVER_MINUTES_DEFAULT = 30


# --------------------------------------------------------------------------
# Logo assets
# --------------------------------------------------------------------------
LOGO_HERO = "assets/logo_hero.png"    # large, hero section
LOGO_ICON = "assets/logo_icon.png"    # square, favicon / small header mark
