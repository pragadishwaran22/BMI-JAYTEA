import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import loaders  # noqa: E402
import fulfillment  # noqa: E402
import ui  # noqa: E402
from constants import GOLD, GOLD_DARK, COLOR_GOOD, COLOR_CRITICAL, COLOR_NEUTRAL  # noqa: E402

ui.render_header("Fulfillment Dashboard — Plan vs Produced")

if "weekly_workbook_bytes" not in st.session_state:
    ui.blocked_state("Upload your Week wise Planning report on the Overview page to see this dashboard.")
    st.stop()

raw_bytes = st.session_state["weekly_workbook_bytes"]

# Shown from here until the end of this page's rendering — covers the
# ENTIRE script run, not just the cached fetch, so it's visible for the
# real page-visit/navigation delay (confirmed by user 2026-09-24).
_loader = ui.tea_brewing_loader("Brewing your dashboard…")


@st.cache_data(show_spinner=False)
def _load_weeks(raw_bytes: bytes):
    return loaders.list_report_for_plan_weeks(loaders.make_buffer(raw_bytes))


weeks = _load_weeks(raw_bytes)
if not weeks:
    _loader.empty()
    st.warning("No week blocks found in the 'Report For plan' sheet of this workbook.")
    st.stop()

week_nums_sorted = sorted(weeks.keys(), key=lambda w: int(w))

# Independent week selector for this page (ARCHITECTURE.md)
st.sidebar.header("Filters & Controls")
week_num = st.sidebar.selectbox(
    "Week", week_nums_sorted,
    format_func=lambda w: weeks[w].label,
    index=ui.persisted_index("fulfillment_week", week_nums_sorted), key="fulfillment_week",
)
ui.persist("fulfillment_week", week_num)
wk = weeks[week_num]

if not wk.is_full:
    st.info(
        f"**{wk.label}** is a future/booked-only week — only the Plan is known yet, "
        "there's no Produced data to compare against. Showing the booked totals below; "
        "the KPI row, funnel, and Plan-vs-Produced chart need a completed week."
    )
    rfp = loaders.load_report_for_plan(loaders.make_buffer(raw_bytes), week_num)
    st.metric("Total Booked Week Plan", f"{rfp['Booked Week Plan'].sum():,.0f}")
    st.dataframe(
        rfp[["Item", "Machine Line", "BOM Version", "Booked Week Plan"]]
        .sort_values("Booked Week Plan", ascending=False),
        width="stretch",
    )
    _loader.empty()
    st.stop()

rfp = loaders.load_report_for_plan(loaders.make_buffer(raw_bytes), week_num)

all_lines = sorted(rfp["Machine Line"].unique().tolist())
# Default sourced from the shadow persist key, not the widget's own
# key=session_state — Streamlit clears widget-keyed session_state on
# st.navigation page switches even with an explicit key (confirmed
# 2026-09-23), so that alone can't survive navigating away and back.
# Sanitized against this week's options — different weeks can have
# different Machine Lines, and a stale value outside `options` raises.
_persisted_lines = ui.persisted_default("fulfillment_machine_lines", all_lines)
_default_lines = [l for l in _persisted_lines if l in all_lines]
selected_lines = st.sidebar.multiselect(
    "Machine Line(s)", all_lines, default=_default_lines, key="fulfillment_machine_lines"
)
ui.persist("fulfillment_machine_lines", selected_lines)
scoped = rfp[rfp["Machine Line"].isin(selected_lines)]

# ---------------- KPI row ----------------
st.header("1. Overview")
kpis = fulfillment.compute_fulfillment_kpis(scoped)
ui.kpi_cards({
    "Total Booked Week Plan": f"{kpis['Total Booked Week Plan']:,.0f}",
    "Total Produced": f"{kpis['Total Produced']:,.0f}",
    "Overall Fulfillment %": f"{kpis['Overall Fulfillment %']:.1f}%" if kpis['Overall Fulfillment %'] is not None else "N/A",
})

st.caption(
    "Fulfillment % reflects what was booked under each machine line's label in "
    "Report For plan — not a guaranteed record of which physical machine produced "
    "it (see LOGIC_PLAN.md Step 8/9)."
)

# ---------------- Funnel ----------------
st.header("2. Order Funnel")
funnel_scope_options = ["All lines"] + all_lines
funnel_scope = st.selectbox(
    "Scope", funnel_scope_options,
    index=ui.persisted_index("funnel_scope", funnel_scope_options), key="funnel_scope",
)
ui.persist("funnel_scope", funnel_scope)
funnel_data = fulfillment.compute_funnel(scoped, machine_line=None if funnel_scope == "All lines" else funnel_scope)
ui.plotly_chart(ui.funnel_chart(funnel_data), width="stretch")

# ---------------- Fulfillment by SKU ----------------
st.header("3. Fulfillment by SKU")
st.caption(
    "Booked Week Plan vs Produced summed per item — across EVERY BOM "
    "version and machine line it appears under, regardless of the "
    "sidebar's Machine Line filter — since line-level totals can hide a "
    "single stalled SKU behind others that over-delivered (see the GOLD "
    "BOND / UNIVERSAL TWIN BAG case in LOGIC_PLAN.md Step 8). Scoping this "
    "table by machine line would recreate that exact fragmentation, so it "
    "always reflects the whole week regardless of the line filter above."
)

# Deliberately uses `rfp` (unfiltered), not `scoped` — confirmed 2026-09-22:
# an item like GV ORANGE 24/25 DC ENV TBGS (AR), which only runs on 3
# specific lines, was disappearing from this search entirely whenever the
# sidebar's Machine Line filter didn't happen to include all 3 — a search
# box shouldn't silently depend on an unrelated sidebar control.
sku_ful = fulfillment.compute_sku_fulfillment(rfp)
sku_ful = sku_ful[sku_ful["Booked Week Plan"] > 0].copy()

# Type-ahead drill-down instead of free-text search (confirmed 2026-09-22)
# — st.multiselect filters its option list live as you type, same widget
# already used for Flow Explorer's SKU picker, so typing "GV ORANGE"
# narrows the options to pick from rather than requiring the exact full
# name (and sidesteps the regex-metacharacter search bug entirely, since
# there's no free-text pattern matching involved at all).
sku_options = sku_ful.sort_values("Item")["Item"].tolist()
_persisted_sku = ui.persisted_default("sku_search", [])
_default_sku = [i for i in _persisted_sku if i in sku_options]
search_items = st.multiselect(
    "Search by item — type to filter, pick one or more",
    options=sku_options,
    default=_default_sku,
    key="sku_search",
)
ui.persist("sku_search", search_items)
if search_items:
    sku_ful = sku_ful[sku_ful["Item"].isin(search_items)]

sku_ful = sku_ful.sort_values("Fulfillment %", ascending=True)
st.dataframe(
    sku_ful.style.format({
        "Booked Week Plan": "{:,.0f}", "Produced": "{:,.0f}", "Fulfillment %": "{:.1f}%",
    }),
    width="stretch",
    height=360,
)
sku_csv = sku_ful.to_csv(index=False).encode("utf-8")
st.download_button("Download SKU table as CSV", sku_csv, file_name=f"fulfillment_by_sku_week{week_num}.csv", mime="text/csv", key="sku_csv")


def _sku_label(row) -> str:
    return str(row["Item"])[:40]


# Over-plan explanation: green = the overrun is covered by Last Week Plan
# (uncommitted carryover), red = it exceeds Plan + Last Week Plan and needs
# investigation, grey (default gold-track/no override) = not over plan at
# all. Confirmed by user 2026-09-22.
_OVERPROD_COLOR = {"explained": COLOR_GOOD, "unexplained": COLOR_CRITICAL, "neutral": COLOR_NEUTRAL}


def _bullet_row(r):
    last_week_plan = r.get("Last Week Plan", 0) or 0
    status, note = fulfillment.classify_overproduction(r["Booked Week Plan"], last_week_plan, r["Produced"])
    return {
        "name": _sku_label(r), "capacity": max(r["Booked Week Plan"], r["Produced"]) * 1.05 or 1,
        "production": r["Produced"], "plan": r["Booked Week Plan"],
        "color": _OVERPROD_COLOR[status], "hover_note": note,
    }


ranked_sku = sku_ful[sku_ful["Fulfillment %"].notna()]
top5_sku = ranked_sku.sort_values("Fulfillment %", ascending=False).head(5)
bottom5_sku = ranked_sku.sort_values("Fulfillment %", ascending=True).head(5)

st.caption("Green = over plan but covered by last week's uncommitted carryover. Red = over plan and unexplained.")
col_top_sku, col_bottom_sku = st.columns(2)
with col_top_sku:
    st.subheader("Top 5 SKUs")
    rows = [_bullet_row(r) for _, r in top5_sku.sort_values("Fulfillment %").iterrows()]
    if rows:
        ui.plotly_chart(ui.bullet_chart(rows, show_capacity=False), width="stretch", key="sku_top5")
    else:
        st.info("No SKUs match the current filters.")
with col_bottom_sku:
    st.subheader("Bottom 5 SKUs")
    rows = [_bullet_row(r) for _, r in bottom5_sku.sort_values("Fulfillment %", ascending=False).iterrows()]
    if rows:
        ui.plotly_chart(ui.bullet_chart(rows, show_capacity=False), width="stretch", key="sku_bottom5")
    else:
        st.info("No SKUs match the current filters.")

# ---------------- Plan vs Produced by line ----------------
st.header("4. Plan vs Produced by Machine Line")
st.caption("Hover a bar — green = over plan but covered by last week's uncommitted carryover, red = over plan and unexplained.")
line_ful = fulfillment.compute_line_fulfillment(scoped)
line_ful = line_ful.sort_values("Fulfillment %", ascending=True)

rows = []
for _, r in line_ful.iterrows():
    last_week_plan = r.get("Last Week Plan", 0) or 0
    status, note = fulfillment.classify_overproduction(r["Booked Week Plan"], last_week_plan, r["Produced (Plan)"])
    rows.append({
        # "capacity" here is a chart-scaling helper only (bar's 100%-width
        # reference), NOT real machine capacity — this page never reads
        # MC_MASTER. show_capacity=False keeps that number out of the tooltip.
        "name": r["Machine Line"], "capacity": max(r["Booked Week Plan"], r["Produced (Plan)"]) * 1.05 or 1,
        "production": r["Produced (Plan)"], "plan": r["Booked Week Plan"],
        "color": _OVERPROD_COLOR[status], "hover_note": note,
    })
ui.plotly_chart(ui.bullet_chart(rows, show_capacity=False), width="stretch")

with st.expander("View as table"):
    st.dataframe(
        line_ful.style.format({
            "Booked Week Plan": "{:,.0f}", "Produced (Plan)": "{:,.0f}", "Fulfillment %": "{:.1f}%",
        }),
        width="stretch",
    )

# ---------------- Week-over-week trend ----------------
st.header("5. Week-over-Week Trend")
trend = fulfillment.compute_weekly_trend(loaders.make_buffer(raw_bytes), week_nums_sorted)
trend_actual = trend[trend["Is Full"]]
trend_future = trend[~trend["Is Full"]]

fig = px.bar(
    trend_actual, x="Week", y=["Booked Week Plan", "Produced"], barmode="group",
    color_discrete_sequence=[GOLD_DARK, GOLD],
)
ui.plotly_chart(fig, width="stretch")

if not trend_future.empty:
    st.caption("Future weeks (booked, not yet due — no Produced data to compare):")
    st.dataframe(
        trend_future[["Week", "Booked Week Plan"]].style.format({"Booked Week Plan": "{:,.0f}"}),
        width="stretch",
    )

_loader.empty()
