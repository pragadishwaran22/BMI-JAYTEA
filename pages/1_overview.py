import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import loaders  # noqa: E402
import capacity  # noqa: E402
import fulfillment  # noqa: E402
import status as status_mod  # noqa: E402
import ui  # noqa: E402
from constants import TEXT_ON_GOLD, COLOR_GOOD, COLOR_CRITICAL, COLOR_NEUTRAL  # noqa: E402

MC_MASTER_PATH = Path(__file__).parent.parent / "source data" / "MC MASTER.xlsx"
ITEM_MASTER_PATH = Path(__file__).parent.parent / "source data" / "Item Master.xlsx"
ITEM_MASTER_SUPPLEMENT_PATH = Path(__file__).parent.parent / "source data" / "Item Master Supplement.xlsx"

ui.render_hero()

# --------------------------------------------------------------------------
# Upload — tucked into a compact popover so it doesn't compete with the
# dashboard content below for space (redesigned 2026-09-23). The upload
# logic itself (validate, save to session_state, rerun) is unchanged from
# before; only its container changed from a big inline block to a popover.
# --------------------------------------------------------------------------
has_workbook = "weekly_workbook_bytes" in st.session_state

status_col, upload_col = st.columns([5, 1])
with status_col:
    if has_workbook:
        st.caption(f"✅ Workbook loaded: **{st.session_state['weekly_workbook_name']}**")
    else:
        st.caption("⬆️ No workbook loaded yet — open **Workbook** to upload one.")
with upload_col:
    # Popover has no "close" API in Streamlit 1.64 — it deliberately stays
    # open across a rerun triggered by a widget inside it (so the user can
    # see confirmation), which is exactly what the user didn't want here
    # (confirmed 2026-09-24): it should collapse right after a successful
    # upload and only reopen on the next explicit click. Forced by giving
    # the popover a versioned key that's bumped right before the rerun —
    # Streamlit treats that as a brand-new widget instance and mounts it
    # in its default (closed) state.
    popover_version = st.session_state.get("workbook_popover_version", 0)
    with st.popover("📤 Workbook", use_container_width=True, key=f"workbook_popover_{popover_version}"):
        uploaded = st.file_uploader(
            "Upload the Week wise Planning report workbook (.xlsx)",
            type=["xlsx"],
            help="MC_MASTER (machine capacity specs) is bundled with the app and does not need to be uploaded.",
            key="weekly_workbook_uploader",
        )
        if uploaded is not None:
            raw_bytes = uploaded.getvalue()
            problems = loaders.validate_weekly_workbook(raw_bytes)
            if problems:
                st.error("This file doesn't look like a valid Week wise Planning report:\n\n" + "\n".join(f"- {p}" for p in problems))
            elif st.session_state.get("weekly_workbook_name") != uploaded.name or st.session_state.get("weekly_workbook_bytes") != raw_bytes:
                st.session_state["weekly_workbook_bytes"] = raw_bytes
                st.session_state["weekly_workbook_name"] = uploaded.name
                # "as of" date for this workbook — corrected by user
                # 2026-09-24: this must come from the DATE IN THE WORKBOOK'S
                # OWN FILE NAME (e.g. "...CBE 22-09-2026 (1).xlsx" -> 22-09-2026),
                # not the day/moment it happened to be uploaded. Falls back
                # to the upload day only if the file name has no date in it.
                filename_date = loaders.parse_workbook_filename_date(uploaded.name)
                st.session_state["weekly_workbook_uploaded_at"] = filename_date or date.today()
                st.session_state["workbook_popover_version"] = popover_version + 1
                st.rerun()
        if has_workbook:
            st.caption(f"Currently loaded: **{st.session_state['weekly_workbook_name']}**")

st.write("")

if not has_workbook:
    ui.blocked_state("Upload a workbook above to unlock the dashboard below.")
    st.stop()

raw_bytes = st.session_state["weekly_workbook_bytes"]
supplement_bytes = st.session_state.get("item_master_supplement_bytes")
# Falls back to today only for a workbook that was already in session_state
# from before this "date from filename" feature existed.
uploaded_at = st.session_state.get("weekly_workbook_uploaded_at", date.today())

# Shown from here until the very last line of this page — covers the
# ENTIRE script run (data load + every gauge/chart built below), not just
# the cached fetch. Confirmed by user 2026-09-24: on a cache hit the fetch
# itself is near-instant, but building ~25 Plotly gauges/charts and
# sending them to the browser is real, uncached work on every single page
# visit/navigation/refresh — that's the delay that was invisible before.
_loader = ui.tea_brewing_loader("Brewing your dashboard…")


@st.cache_data(show_spinner=False)
def _load_dashboard(raw_bytes: bytes, supplement_bytes: bytes | None, uploaded_at: date):
    mc_master = loaders.load_mc_master(str(MC_MASTER_PATH))
    item_master = loaders.load_item_master(str(ITEM_MASTER_PATH))
    item_master = loaders.merge_item_master(
        item_master, loaders.load_item_master_supplement(str(ITEM_MASTER_SUPPLEMENT_PATH))
    )
    if supplement_bytes:
        supplement_df = loaders.load_item_master_supplement(loaders.make_buffer(supplement_bytes))
        item_master = loaders.merge_item_master(item_master, supplement_df)

    weeks_full = loaders.list_report_for_plan_weeks(loaders.make_buffer(raw_bytes))
    full_weeks = sorted((w for w in weeks_full.values() if w.is_full), key=lambda w: int(w.week_num))
    if not full_weeks:
        return None

    prod_raw = loaders.load_weekly_production_raw(loaders.make_buffer(raw_bytes))
    date_ranges = loaders.load_week_date_ranges(loaders.make_buffer(raw_bytes))
    wk_infos = loaders.discover_weeks(prod_raw, date_ranges)

    # Prefer the latest week that has ACTUALLY FULLY ELAPSED on the
    # calendar (end date in the past) AND has real Produced data — not
    # just the latest with the full 10-column structure and a nonzero sum.
    # Bug caught 2026-09-24: a week whose date range STRADDLES today (the
    # current, still-in-progress week) can already show a nonzero Produced
    # sum from the days worked so far, which passed the old ">0" check —
    # but dividing that PARTIAL week's production by a fixed 6 days
    # silently understated the true daily run rate (e.g. WEEK NO-39,
    # 21-09 to 26-09, picked on 24-09 with only ~2 days of real data).
    # Falls back to the latest full week (even if 0 or still in progress)
    # only if nothing has genuinely elapsed yet. This uses the LIVE
    # wall-clock date, not the workbook's file-name date — corrected by
    # user 2026-09-24 (scope: "Run Rate only"): the file-name date is only
    # meaningful as the Run Rate divisor's anchor. Using it here too breaks
    # this picker whenever the file name predates its own weeks' end dates
    # (e.g. a file named "...18-09-2026" that already contains a completed
    # WEEK NO-38 ending 19-09-2026) — "which week is the latest complete
    # one" is a viewing-time question, not a workbook-authored one.
    today = date.today()
    latest = None
    for w in reversed(full_weeks):
        wk_candidate = wk_infos.get(f"WEEK NO-{w.week_num}")
        if wk_candidate is None or wk_candidate.end is None or wk_candidate.end >= today:
            continue
        candidate_rfp = loaders.load_report_for_plan(loaders.make_buffer(raw_bytes), w.week_num)
        if candidate_rfp["Produced"].sum() > 0:
            latest = w
            break

    # Bug caught 2026-09-24: when NO week has both calendar-elapsed AND
    # real production (e.g. the highest-numbered "full" week is a future
    # week that's structurally complete but genuinely empty — zero
    # Produced — while an earlier, still-in-progress week already has
    # real data), the old code fell straight back to `full_weeks[-1]`
    # (the highest week NUMBER), which picked that empty future week and
    # showed a misleading 0.0% Fulfillment instead of the real, if
    # in-progress, data one week back. Second pass: prefer the highest
    # week with ANY real Produced data, even if not yet calendar-complete,
    # over an empty "full" week. Only truly empty workbooks fall through
    # to full_weeks[-1] at the very end.
    if latest is None:
        for w in reversed(full_weeks):
            candidate_rfp = loaders.load_report_for_plan(loaders.make_buffer(raw_bytes), w.week_num)
            if candidate_rfp["Produced"].sum() > 0:
                latest = w
                break

    if latest is None:
        latest = full_weeks[-1]

    wk_label = f"WEEK NO-{latest.week_num}"
    if wk_label not in wk_infos:
        return None
    wk_info = wk_infos[wk_label]

    line_eff = capacity.compute_line_efficiency(prod_raw, mc_master, wk_info, item_master)

    rfp = loaders.load_report_for_plan(loaders.make_buffer(raw_bytes), latest.week_num)
    line_ful = fulfillment.compute_line_fulfillment(rfp)
    status_df = status_mod.compute_status(line_eff, line_ful)
    fulfillment_kpis = fulfillment.compute_fulfillment_kpis(rfp)

    # --- Top/Bottom SKUs by Fulfillment % — replaces the old machine-line
    # "Performance Comparison" widget (confirmed by user 2026-09-24): same
    # ranked-bullet-chart pattern already used on the Fulfillment page's
    # "Fulfillment by SKU" section, just surfaced here as a landing-page
    # summary of the 5 best- and worst-fulfilled SKUs for the latest week.
    sku_ful = fulfillment.compute_sku_fulfillment(rfp)
    sku_ful = sku_ful[sku_ful["Booked Week Plan"] > 0]
    ranked_sku = sku_ful[sku_ful["Fulfillment %"].notna()]
    top5_sku = ranked_sku.sort_values("Fulfillment %", ascending=False).head(5)
    bottom5_sku = ranked_sku.sort_values("Fulfillment %", ascending=True).head(5)

    # --- Weekly Run Rate: a LIVE daily-pace number, not a fixed weekly
    # snapshot (confirmed by user 2026-09-24). Unlike `latest` above (the
    # latest FULLY completed week, used for gauges/Fulfillment %/Status),
    # Run Rate tracks the numerically latest week with ANY real
    # production — including one still in progress — and divides by how
    # many calendar days of that week have actually elapsed
    # ((today - week start) + 1, clamped to [1, 6]) instead of always 6.
    # A week already fully finished naturally clamps to 6, same as
    # before; a week still in progress (e.g. WEEK NO-39, start 21-09,
    # viewed on 22-09) gets the correct smaller divisor (2, not 6) instead
    # of understating the true daily rate. Anchored to the date PARSED
    # FROM THE WORKBOOK'S FILE NAME (`uploaded_at` /
    # `loaders.parse_workbook_filename_date`), not the live wall-clock date
    # — corrected by user 2026-09-24: the same workbook file must always
    # produce the same Run Rate, based on the date the file itself carries.
    # Scoped to Run Rate only (confirmed by user) — the "latest completed
    # week" picker above deliberately keeps using the live `today` instead.
    run_rate_as_of = uploaded_at

    def _run_rate_divisor(wk_start) -> int:
        if wk_start is None:
            return 6
        return min(max((run_rate_as_of - wk_start).days + 1, 1), 6)

    all_week_nums = sorted(int(k.replace("WEEK NO-", "")) for k in wk_infos)
    run_rate = 0.0
    run_rate_week_num = None
    for wn in reversed(all_week_nums):
        wk_rr = wk_infos[f"WEEK NO-{wn}"]
        rr_line_eff = line_eff if str(wn) == latest.week_num else \
            capacity.compute_line_efficiency(prod_raw, mc_master, wk_rr, item_master)
        rr_total = float(rr_line_eff["Actual Production (Tbgs)"].sum())
        if rr_total > 0:
            run_rate = rr_total / _run_rate_divisor(wk_rr.start)
            run_rate_week_num = wn
            break

    # Week-over-week trend vs the week right before whichever week Run
    # Rate is anchored to — that earlier week is always fully elapsed by
    # construction, so its own divisor naturally comes out to 6.
    prev_run_rate = None
    if run_rate_week_num is not None:
        prev_label = f"WEEK NO-{run_rate_week_num - 1}"
        if prev_label in wk_infos:
            wk_prev = wk_infos[prev_label]
            prev_line_eff = capacity.compute_line_efficiency(prod_raw, mc_master, wk_prev, item_master)
            prev_total = float(prev_line_eff["Actual Production (Tbgs)"].sum())
            if prev_total > 0:
                prev_run_rate = prev_total / _run_rate_divisor(wk_prev.start)

    return {
        "week_num": latest.week_num,
        "week_label": latest.label,
        "line_eff": line_eff,
        "status_df": status_df,
        "fulfillment_kpis": fulfillment_kpis,
        "top5_sku": top5_sku,
        "bottom5_sku": bottom5_sku,
        "run_rate": run_rate,
        "prev_run_rate": prev_run_rate,
    }


result = _load_dashboard(raw_bytes, supplement_bytes, uploaded_at)

if result is None:
    _loader.empty()
    st.warning("Could not find a completed week with data in this workbook.")
    st.stop()

line_eff = result["line_eff"]
status_df = result["status_df"]
st.caption(f"Based on the latest completed week: {result['week_label']}")

# --------------------------------------------------------------------------
# KPI row — Weekly Run Rate (new) + Fulfillment Overview
# --------------------------------------------------------------------------
kpi_col1, kpi_col2 = st.columns([1, 1])

with kpi_col1:
    run_rate = result["run_rate"]
    prev_run_rate = result["prev_run_rate"]
    with ui.gold_pill_container("run_rate"):
        ui.metric_label("Weekly Run Rate (Tbgs/day)", dark=True)
        ui.plotly_chart(
            ui.run_rate_card(run_rate, prev_run_rate, TEXT_ON_GOLD),
            width="stretch",
        )

with kpi_col2:
    kpis = result["fulfillment_kpis"]
    with ui.gold_pill_container("fulfillment_ratio"):
        ui.metric_label("Overall Fulfillment %", dark=True)
        ui.plotly_chart(
            ui.ratio_card(
                kpis["Overall Fulfillment %"], kpis["Total Produced"], kpis["Total Booked Week Plan"],
                text_color=TEXT_ON_GOLD,
                last_week_plan=kpis.get("Total Last Week Plan"),
                pct_incl_last_week=kpis.get("Fulfillment % incl. Last Week Plan"),
            ),
            width="stretch",
        )

st.write("")

# --------------------------------------------------------------------------
# Machine Line Efficiency — small-multiple gauges
# --------------------------------------------------------------------------
st.subheader("Machine Line Efficiency")
# Sourced from status_df (line_eff merged with line_ful — see status_mod.compute_status)
# rather than line_eff alone, so each gauge's tooltip can also show that
# line's Fulfillment % without a second lookup/merge (confirmed by user 2026-09-24).
gauge_lines = status_df[status_df["Total Available (Tbgs)"] > 0]
GAUGES_PER_ROW = 5
gauge_rows = [gauge_lines.iloc[i:i + GAUGES_PER_ROW] for i in range(0, len(gauge_lines), GAUGES_PER_ROW)]
for chunk in gauge_rows:
    cols = st.columns(GAUGES_PER_ROW)
    for col, (_, r) in zip(cols, chunk.iterrows()):
        with col:
            st.markdown(
                ui.teacup_gauge_html(
                    r["Machine Line"], r["Efficiency %"],
                    produced=r["Actual Production (Tbgs)"], available=r["Total Available (Tbgs)"],
                    machines=r["Machines"], shifts_worked=r["Shifts Worked"],
                    fulfillment_pct=r.get("Fulfillment %"),
                ),
                unsafe_allow_html=True,
            )

st.write("")

# --------------------------------------------------------------------------
# Top / Bottom SKUs by Fulfillment % — replaces the old machine-line
# "Performance Comparison" widget (confirmed by user 2026-09-24). Same
# ranked-bullet-chart + over-production coloring already used on the
# Fulfillment page's "Fulfillment by SKU" section (Booked Week Plan vs
# Produced), just surfaced here for the latest week's 5 best/worst SKUs.
# --------------------------------------------------------------------------
st.subheader("Top / Bottom SKUs by Fulfillment %")
top5_sku = result["top5_sku"]
bottom5_sku = result["bottom5_sku"]

_SKU_OVERPROD_COLOR = {"explained": COLOR_GOOD, "unexplained": COLOR_CRITICAL, "neutral": COLOR_NEUTRAL}


def _sku_row(r):
    last_week_plan = r.get("Last Week Plan", 0) or 0
    status, note = fulfillment.classify_overproduction(r["Booked Week Plan"], last_week_plan, r["Produced"])
    return {
        "name": str(r["Item"])[:40], "capacity": max(r["Booked Week Plan"], r["Produced"]) * 1.05 or 1,
        "production": r["Produced"], "plan": r["Booked Week Plan"],
        "color": _SKU_OVERPROD_COLOR[status], "hover_note": note,
    }


st.caption("Green = over plan but covered by last week's uncommitted carryover. Red = over plan and unexplained.")

sku_col1, sku_col2 = st.columns(2)
with sku_col1:
    st.markdown("**Top 5 SKUs**")
    rows = [_sku_row(r) for _, r in top5_sku.sort_values("Fulfillment %").iterrows()]
    if rows:
        ui.plotly_chart(ui.bullet_chart(rows, show_capacity=False), width="stretch", key="overview_sku_top5")
    else:
        st.info("No SKUs to show for this week.")

with sku_col2:
    st.markdown("**Bottom 5 SKUs**")
    rows = [_sku_row(r) for _, r in bottom5_sku.sort_values("Fulfillment %", ascending=False).iterrows()]
    if rows:
        ui.plotly_chart(ui.bullet_chart(rows, show_capacity=False), width="stretch", key="overview_sku_bottom5")
    else:
        st.info("No SKUs to show for this week.")

_loader.empty()
