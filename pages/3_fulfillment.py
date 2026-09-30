import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import loaders  # noqa: E402
import capacity  # noqa: E402
import fulfillment  # noqa: E402
import ui  # noqa: E402
from constants import GOLD, GOLD_DARK, COLOR_GOOD, COLOR_CRITICAL, COLOR_NEUTRAL, GLASS_BORDER_GOLD, GOLD_SOFT  # noqa: E402

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

# Week vs Day-wise is an either/or VIEW, not two sections shown together
# — confirmed by user 2026-09-28: seeing both at once was confusing: "i
# should not get both the details(week and daywise) together... either i
# should get week respective data all over the page... or day wise."
view_options = ["Week", "Day wise"]
view_mode = st.sidebar.radio(
    "View", view_options,
    index=ui.persisted_index("fulfillment_view", view_options), key="fulfillment_view",
    horizontal=True,
)
ui.persist("fulfillment_view", view_mode)

week_num = st.sidebar.selectbox(
    "Week", week_nums_sorted,
    format_func=lambda w: weeks[w].label,
    index=ui.persisted_index("fulfillment_week", week_nums_sorted), key="fulfillment_week",
)
ui.persist("fulfillment_week", week_num)
wk = weeks[week_num]

# Day-wise data is sourced from the 'weekly production' sheet, NOT
# 'Report For plan' (which has no day-level data at all, only weekly
# totals — confirmed by user 2026-09-28). Loaded regardless of view_mode
# (cheap/cached) so switching the radio doesn't need a rerun-triggered
# reload.
@st.cache_data(show_spinner=False)
def _load_weekly_production_week(raw_bytes: bytes, week_label: str):
    prod_raw = loaders.load_weekly_production_raw(loaders.make_buffer(raw_bytes))
    date_ranges = loaders.load_week_date_ranges(loaders.make_buffer(raw_bytes))
    prod_weeks = loaders.discover_weeks(prod_raw, date_ranges)
    return prod_raw, prod_weeks.get(week_label)


prod_raw, day_week = _load_weekly_production_week(raw_bytes, f"WEEK NO-{week_num}")
date_options = [day_week.start + timedelta(days=n) for n in range(6)] if day_week and day_week.start else []

selected_date = None
if view_mode == "Day wise":
    if date_options:
        selected_date = st.sidebar.selectbox(
            "Date", date_options,
            format_func=lambda d: f"{d.strftime('%d-%m-%Y')} ({d.strftime('%A')})",
            index=ui.persisted_index("fulfillment_date", date_options), key="fulfillment_date",
        )
        ui.persist("fulfillment_date", selected_date)
    else:
        st.sidebar.info("No day-level data for this week.")

# rfp is loaded regardless of view_mode — needed for the "Machine Line(s)"
# filter's options (shared by both views) even in Day-wise mode, and for
# Week mode's own sections below.
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

# ============================================================
# WEEK VIEW — unchanged from before the Day-wise feature existed
# ============================================================
if view_mode == "Week":
    if not wk.is_full:
        st.info(
            f"**{wk.label}** is a future/booked-only week — only the Plan is known yet, "
            "there's no Produced data to compare against. Showing the booked totals below; "
            "the KPI row, funnel, and Plan-vs-Produced chart need a completed week."
        )
        st.metric("Total Booked Week Plan", f"{rfp['Booked Week Plan'].sum():,.0f}")
        st.dataframe(
            rfp[["Item", "Machine Line", "BOM Version", "Booked Week Plan"]]
            .sort_values("Booked Week Plan", ascending=False),
            width="stretch",
        )
        _loader.empty()
        st.stop()

    # ---------------- KPI row ----------------
    st.header("1. Overview")
    kpis = fulfillment.compute_fulfillment_kpis(scoped)
    ui.kpi_cards(
        {
            "Total Booked Week Plan": f"{kpis['Total Booked Week Plan']:,.0f}",
            "Last Week Uncommitted Plan": f"{kpis['Total Last Week Plan']:,.0f}",
            "Total Produced": f"{kpis['Total Produced']:,.0f}",
            "Overall Fulfillment %": f"{kpis['Fulfillment % incl. Last Week Plan']:.1f}%" if kpis['Fulfillment % incl. Last Week Plan'] is not None else "N/A",
        },
        highlight={"Overall Fulfillment %"},
    )

    st.caption(
        "Fulfillment % reflects what was booked under each machine line's label in "
        "Report For plan — not a guaranteed record of which physical machine produced "
        "it (see LOGIC_PLAN.md Step 8/9). Overall Fulfillment % = Total Produced / "
        "(Total Booked Week Plan + Total Last Week Plan uncommitted) — confirmed by "
        "user 2026-09-29."
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

# ============================================================
# DAY-WISE VIEW — from 'weekly production', not 'Report For plan'
# (confirmed by user 2026-09-28). Sections needing data that has no
# day-level equivalent (Commited for the funnel, Machine Line breakdown)
# are either simplified (Funnel -> 2-stage Planned/Produced, per user's
# explicit choice) or omitted (Plan vs Produced by Machine Line has no
# day-wise counterpart yet).
# ============================================================
else:
    if day_week is None or not date_options:
        st.warning(
            "No matching 'weekly production' data found for this week — "
            "day-wise Plan vs Produced isn't available."
        )
        _loader.empty()
        st.stop()

    daily_sku = capacity.daily_sku_totals(prod_raw, day_week, machine_lines=selected_lines)
    day_offset = (selected_date - day_week.start).days
    day_rows = daily_sku[daily_sku["Day Offset"] == day_offset]

    # ---------------- KPI row ----------------
    col_h, col_badge = st.columns([5, 2])
    with col_h:
        st.header("1. Overview")
    with col_badge:
        st.markdown(
            f'<div style="text-align:right;padding-top:0.7rem;">'
            f'<span class="bi-pill" style="color:{GOLD};border-color:{GLASS_BORDER_GOLD};background:{GOLD_SOFT};'
            f'font-weight:700;text-transform:uppercase;letter-spacing:0.03em;">'
            f'{selected_date.strftime("%d-%m-%Y")} ({selected_date.strftime("%A").upper()})'
            f'</span></div>',
            unsafe_allow_html=True,
        )
    day_kpis = fulfillment.compute_day_fulfillment(daily_sku, day_offset)
    ui.kpi_cards({
        "Day Planned Qty": f"{day_kpis['Day Planned Qty']:,.0f}",
        "Day Produced Qty": f"{day_kpis['Day Produced Qty']:,.0f}",
        "Day Fulfillment %": f"{day_kpis['Day Fulfillment %']:.1f}%" if day_kpis['Day Fulfillment %'] is not None else "N/A",
    })
    st.caption(
        "From the 'weekly production' sheet, Shift A + Shift B combined, grouped by SKU — "
        "'Report For plan' has no day-level data, only weekly totals (see LOGIC_PLAN.md)."
    )

    # ---------------- Order Funnel (2-stage — no 'Commited' at day level) ----------------
    st.header("2. Order Funnel")
    funnel_data = {
        "Planned": float(day_rows["Planned Qty"].sum()),
        "Produced": float(day_rows["Production Qty"].sum()),
    }
    ui.plotly_chart(ui.funnel_chart(funnel_data), width="stretch")

    # ---------------- Fulfillment by SKU (day-wise) ----------------
    st.header("3. Fulfillment by SKU")
    day_sku = day_rows.rename(columns={"Planned Qty": "Planned", "Production Qty": "Produced"}).copy()
    day_sku["Fulfillment %"] = day_sku.apply(
        lambda r: (r["Produced"] / r["Planned"] * 100) if r["Planned"] else None, axis=1
    )
    day_sku = day_sku[day_sku["Planned"] > 0]

    sku_options = day_sku.sort_values("Item")["Item"].tolist()
    _persisted_sku = ui.persisted_default("fulfillment_day_sku_search", [])
    _default_sku = [i for i in _persisted_sku if i in sku_options]
    search_items = st.multiselect(
        "Search by item — type to filter, pick one or more",
        options=sku_options,
        default=_default_sku,
        key="fulfillment_day_sku_search",
    )
    ui.persist("fulfillment_day_sku_search", search_items)
    if search_items:
        day_sku = day_sku[day_sku["Item"].isin(search_items)]

    day_sku = day_sku.sort_values("Fulfillment %", ascending=True)
    st.dataframe(
        day_sku[["Item", "Planned", "Produced", "Fulfillment %"]].style.format({
            "Planned": "{:,.0f}", "Produced": "{:,.0f}", "Fulfillment %": "{:.1f}%",
        }),
        width="stretch",
        height=360,
    )
    day_sku_csv = day_sku.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download day-wise SKU table as CSV", day_sku_csv,
        file_name=f"fulfillment_by_sku_{selected_date.strftime('%Y%m%d')}.csv",
        mime="text/csv", key="day_sku_csv",
    )

    def _day_bullet_row(r):
        return {
            "name": str(r["Item"])[:40], "capacity": max(r["Planned"], r["Produced"]) * 1.05 or 1,
            "production": r["Produced"], "plan": r["Planned"],
        }

    ranked_day_sku = day_sku[day_sku["Fulfillment %"].notna()]
    top5_day_sku = ranked_day_sku.sort_values("Fulfillment %", ascending=False).head(5)
    bottom5_day_sku = ranked_day_sku.sort_values("Fulfillment %", ascending=True).head(5)

    col_top_day, col_bottom_day = st.columns(2)
    with col_top_day:
        st.subheader("Top 5 SKUs")
        rows = [_day_bullet_row(r) for _, r in top5_day_sku.sort_values("Fulfillment %").iterrows()]
        if rows:
            ui.plotly_chart(ui.bullet_chart(rows, show_capacity=False), width="stretch", key="day_sku_top5")
        else:
            st.info("No SKUs match the current filters.")
    with col_bottom_day:
        st.subheader("Bottom 5 SKUs")
        rows = [_day_bullet_row(r) for _, r in bottom5_day_sku.sort_values("Fulfillment %", ascending=False).iterrows()]
        if rows:
            ui.plotly_chart(ui.bullet_chart(rows, show_capacity=False), width="stretch", key="day_sku_bottom5")
        else:
            st.info("No SKUs match the current filters.")

    # ---------------- Day-over-Day trend (replaces Week-over-Week in this view) ----------------
    st.header("4. Day-over-Day Trend")
    trend = daily_sku.groupby("Day Offset")[["Planned Qty", "Production Qty"]].sum().reset_index()
    trend["Date"] = trend["Day Offset"].apply(
        lambda n: (day_week.start + timedelta(days=int(n))).strftime("%d-%m (%a)")
    )
    fig = px.bar(
        trend, x="Date", y=["Planned Qty", "Production Qty"], barmode="group",
        color_discrete_sequence=[GOLD_DARK, GOLD],
    )
    ui.plotly_chart(fig, width="stretch")

_loader.empty()
