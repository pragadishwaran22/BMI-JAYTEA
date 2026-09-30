import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import loaders  # noqa: E402
import capacity  # noqa: E402
import fulfillment  # noqa: E402
import status as status_mod  # noqa: E402
import ui  # noqa: E402
from constants import efficiency_color, GOLD, GOLD_DARK, CHANGEOVER_MINUTES_DEFAULT  # noqa: E402

MC_MASTER_PATH = Path(__file__).parent.parent / "source data" / "MC MASTER.xlsx"
ITEM_MASTER_PATH = Path(__file__).parent.parent / "source data" / "Item Master.xlsx"
ITEM_MASTER_SUPPLEMENT_PATH = Path(__file__).parent.parent / "source data" / "Item Master Supplement.xlsx"

ui.render_header("Machine Capacity Efficiency")

if "weekly_workbook_bytes" not in st.session_state:
    ui.blocked_state("Upload your Week wise Planning report on the Overview page to see this dashboard.")
    st.stop()

raw_bytes = st.session_state["weekly_workbook_bytes"]
supplement_bytes = st.session_state.get("item_master_supplement_bytes")

# Shown from here until the very last line of this page — covers the
# ENTIRE script run (data load + every table/chart built below), not just
# the cached fetch, so it's visible for the real page-visit/navigation
# delay, not just a near-instant cache hit (confirmed by user 2026-09-24).
_loader = ui.tea_brewing_loader("Brewing your dashboard…")


@st.cache_data(show_spinner=False)
def _load_base(raw_bytes: bytes, supplement_bytes: bytes | None):
    mc_master = loaders.load_mc_master(str(MC_MASTER_PATH))
    item_master = loaders.load_item_master(str(ITEM_MASTER_PATH))
    item_master = loaders.merge_item_master(
        item_master, loaders.load_item_master_supplement(str(ITEM_MASTER_SUPPLEMENT_PATH))
    )
    if supplement_bytes:
        supplement_df = loaders.load_item_master_supplement(loaders.make_buffer(supplement_bytes))
        item_master = loaders.merge_item_master(item_master, supplement_df)
    prod_raw = loaders.load_weekly_production_raw(loaders.make_buffer(raw_bytes))
    date_ranges = loaders.load_week_date_ranges(loaders.make_buffer(raw_bytes))
    weeks = loaders.discover_weeks(prod_raw, date_ranges)
    return mc_master, item_master, prod_raw, weeks


mc_master, item_master, prod_raw, weeks = _load_base(raw_bytes, supplement_bytes)

if not weeks:
    _loader.empty()
    st.warning("No week blocks found in the 'weekly production' sheet of this workbook.")
    st.stop()

week_labels = list(weeks.keys())

# Independent week selector for this page (ARCHITECTURE.md)
st.sidebar.header("Filters & Controls")
week_label = st.sidebar.selectbox(
    "Week", week_labels, index=ui.persisted_index("capacity_week", week_labels), key="capacity_week",
)
ui.persist("capacity_week", week_label)
wk = weeks[week_label]
if wk.start and wk.end:
    st.sidebar.caption(f"{wk.start.strftime('%d-%b-%Y')} to {wk.end.strftime('%d-%b-%Y')} · {len(wk.labeled_days)} labeled days")

line_eff = capacity.compute_line_efficiency(prod_raw, mc_master, wk, item_master)

if line_eff.empty:
    _loader.empty()
    st.warning("No production rows found for this week.")
    st.stop()

# Bring in Fulfillment / Status if this week has a matching Report For plan block
status_df = None
if wk.week_num:
    try:
        rfp = loaders.load_report_for_plan(loaders.make_buffer(raw_bytes), wk.week_num)
        if rfp.attrs.get("is_full", True):
            line_ful = fulfillment.compute_line_fulfillment(rfp)
            status_df = status_mod.compute_status(line_eff, line_ful)
    except ValueError:
        pass

table_source = status_df if status_df is not None else line_eff

all_lines = table_source["Machine Line"].tolist()
# Default sourced from the shadow persist key, not the widget's own
# key=session_state — Streamlit clears widget-keyed session_state on
# st.navigation page switches even with an explicit key (confirmed
# 2026-09-23), so that alone can't survive navigating away and back.
# Sanitized against this week's options — different weeks can have
# different Machine Lines, and a stale value outside `options` raises.
_persisted_lines = ui.persisted_default("capacity_machine_lines", all_lines)
_default_lines = [l for l in _persisted_lines if l in all_lines]
selected_lines = st.sidebar.multiselect(
    "Machine Line(s)", all_lines, default=_default_lines, key="capacity_machine_lines"
)
ui.persist("capacity_machine_lines", selected_lines)

only_with_production = st.sidebar.checkbox(
    "Show only machines with production",
    value=ui.persisted_default("capacity_only_with_production", False),
    key="capacity_only_with_production",
)
ui.persist("capacity_only_with_production", only_with_production)

view = table_source[table_source["Machine Line"].isin(selected_lines)].copy()
if only_with_production:
    view = view[view["Actual Production (Tbgs)"] > 0]

# ---------------- Section 1: Overview ----------------
st.header("1. Machine Line Efficiency Overview")

sort_options = ["Efficiency % (High to Low)", "Production Volume (High to Low)", "Machine Name (A-Z)"]
sort_option = st.radio(
    "Sort by", sort_options,
    index=ui.persisted_index("capacity_sort_option", sort_options),
    horizontal=True, key="capacity_sort_option",
)
ui.persist("capacity_sort_option", sort_option)
if sort_option.startswith("Efficiency"):
    view = view.sort_values("Efficiency %", ascending=False)
elif sort_option.startswith("Production"):
    view = view.sort_values("Actual Production (Tbgs)", ascending=False)
else:
    view = view.sort_values("Machine Line", ascending=True)
view = view.reset_index(drop=True)

display_cols = [
    "Machine Line", "Shifts Worked", "Total Available (Tbgs)",
    "Actual Production (Tbgs)", "Efficiency %", "Wasted Capacity %",
]
if status_df is not None:
    display_cols += ["Fulfillment %", "Status"]
if "Unconverted Qty (CFC)" in view.columns:
    display_cols += ["Unconverted Qty (CFC)"]
if status_df is not None:
    display_cols += ["Produced (Plan)"]

disp = view[display_cols].copy()
disp = disp.rename(columns={
    "Total Available (Tbgs)": "Available Capacity (Tbgs)",
    # Produced straight from Report For plan's own Produced column — already
    # in Tbgs there, no CFC->Tbgs conversion applied (unlike Actual
    # Production (Tbgs), which is converted from weekly production's CFC
    # cells). Kept side by side so the two sources can be cross-checked
    # (confirmed by user 2026-09-23).
    "Produced (Plan)": "Actual Production (No CFC Conversion)",
})

fmt = {
    "Available Capacity (Tbgs)": "{:,.0f}",
    "Actual Production (Tbgs)": "{:,.0f}", "Efficiency %": "{:.2f}%",
    "Wasted Capacity %": "{:.2f}%",
}
if "Actual Production (No CFC Conversion)" in disp.columns:
    fmt["Actual Production (No CFC Conversion)"] = "{:,.0f}"
if "Fulfillment %" in disp.columns:
    fmt["Fulfillment %"] = "{:.1f}%"
if "Unconverted Qty (CFC)" in disp.columns:
    fmt["Unconverted Qty (CFC)"] = "{:,.0f}"

styled = disp.style.map(
    lambda v: f"background-color:{efficiency_color(v)}22;color:{efficiency_color(v)};font-weight:600;",
    subset=["Efficiency %"],
)
if "Unconverted Qty (CFC)" in disp.columns:
    # Actual Production (Tbgs) excludes any row whose item has no known
    # CFC->Tbgs factor (see loaders.load_item_master) — flagged here rather
    # than silently mixing units or guessing a factor (confirmed 2026-09-23).
    styled = styled.map(
        lambda v: "background-color:#ff6b6b22;color:#ff6b6b;font-weight:600;" if v > 0 else "",
        subset=["Unconverted Qty (CFC)"],
    )
styled = styled.format(fmt)
st.dataframe(styled, width="stretch", height=460)

incomplete = view[view.get("Unconverted Qty (CFC)", 0) > 0] if "Unconverted Qty (CFC)" in view.columns else pd.DataFrame()
if not incomplete.empty:
    with st.expander(f"⚠ {len(incomplete)} machine line(s) have items with no CFC → Tbgs conversion factor — Actual Production is understated for these"):
        for _, r in incomplete.iterrows():
            st.markdown(f"**{r['Machine Line']}** — unconverted qty (still in CFC, not counted in Actual Production): {r['Unconverted Qty (CFC)']:,.0f}  \n"
                        f"Items missing a factor: {r['Items Missing Conversion Factor']}")

# Workbook-wide (every week block, not just the one selected above) list of
# items with no CFC->Tbgs factor at all — catches new SKUs before they show
# up as an "Unconverted Qty" flag on some future week. Copy this list back
# to Claude to get a fillable mapping form for just these items
# (2026-09-23 — see the "CFC Conversion Mapping" artifact workflow).
all_unmatched = capacity.find_items_without_cfc_factor(prod_raw, item_master)
if all_unmatched:
    with st.expander(f"📋 {len(all_unmatched)} item(s) in this workbook have no CFC → Tbgs conversion factor at all (any week)"):
        st.caption(
            "Copy this list and send it to Claude to generate a fillable mapping form for just these "
            "items, the same way the first 40 were mapped."
        )
        st.text_area("Unmatched items", value="\n".join(all_unmatched), height=200, key="unmatched_items_textarea")
        st.download_button(
            "Download list as .txt",
            "\n".join(all_unmatched).encode("utf-8"),
            file_name="unmatched_cfc_items.txt",
            mime="text/plain",
        )

csv = disp.to_csv(index=False).encode("utf-8")
st.download_button("Download table as CSV", csv, file_name=f"machine_efficiency_{week_label.replace(' ', '_')}.csv", mime="text/csv")

if view.empty:
    _loader.empty()
    st.info("No machine lines match the current filters.")
    st.stop()

# ---------------- Section 2: Deep Dive ----------------
st.header("2. Machine Line Deep Dive")
dd_options = view["Machine Line"].tolist()
dd_line = st.selectbox(
    "Select a machine line", dd_options,
    index=ui.persisted_index("capacity_dd_line", dd_options), key="capacity_dd_line",
)
ui.persist("capacity_dd_line", dd_line)

row = view[view["Machine Line"] == dd_line].iloc[0]

# Per-machine breakdown, since the line-level Shifts Worked / Capacity/Shift
# shown in Section 1 are SUMS across however many physical machines make up
# this line — not a single machine's rate. Surfaced as hover help here
# rather than relabeling the metric names (2026-09-21).
machine_eff = capacity.compute_machine_efficiency(prod_raw, mc_master, wk, item_master)
machine_rows = machine_eff[machine_eff["Machine Line"] == dd_line].sort_values("Machine No")
unmatched_for_line = [m for (ml, m) in machine_eff.attrs.get("unmatched_machines", []) if ml == dd_line]

if len(machine_rows) > 1:
    lines = [f"Sum across {len(machine_rows)} machines:"]
    for _, m in machine_rows.iterrows():
        star = " *" if m.get("Capacity Inferred") else ""
        lines.append(f"{m['Machine No']}: {m['Capacity/Shift (Tbgs)']:,.0f} × {m['Shifts Worked']:.0f} shifts = {m['Total Available (Tbgs)']:,.0f}{star}")
    if machine_rows["Capacity Inferred"].any():
        lines.append("* capacity inferred from this line's other machines (no MC_MASTER row of its own)")
    if unmatched_for_line:
        lines.append(f"Excluded (line has no matched machines to infer from): {', '.join(unmatched_for_line)}")
    machine_help = "\n\n".join(lines)
else:
    machine_help = None

metric_cols = st.columns(5 if status_df is not None else 4)
metric_cols[0].metric("Shifts Worked", f"{row['Shifts Worked']:,.0f}", help=machine_help)
metric_cols[1].metric("Capacity/Shift", f"{row['Capacity/Shift (Tbgs)']:,.0f}", help=machine_help)
_deep_dive_production = row["Produced (Plan)"] if status_df is not None else row["Actual Production (Tbgs)"]
metric_cols[2].metric("Actual Production", f"{_deep_dive_production:,.0f}")
metric_cols[3].metric("Efficiency", f"{row['Efficiency %']:.2f}%")
if status_df is not None:
    metric_cols[4].markdown(f"**Status**<br>{ui.status_badge(row['Status'])}", unsafe_allow_html=True)

st.subheader("Shifts breakdown")
machine_options = capacity.machine_numbers_for_line(prod_raw, dd_line)
scope_options = ["All machines (combined)"] + machine_options
scope = st.selectbox(
    "Machine",
    scope_options,
    index=ui.persisted_index("capacity_machine_scope", scope_options),
    key="capacity_machine_scope",
    help="Line totals sum every physical machine's shifts and capacity together — pick one machine here to see its own numbers instead.",
)
ui.persist("capacity_machine_scope", scope)
machine_no = None if scope == "All machines (combined)" else scope

breakdown = capacity.daily_breakdown(prod_raw, wk, dd_line, machine_no=machine_no)
if breakdown.empty:
    st.info("No shift-level data for this selection.")
else:
    bd_disp = breakdown.copy()
    bd_disp["Day"] = bd_disp["Day"].astype(str)
    st.dataframe(
        bd_disp.style.format({"Planned Qty": "{:,.0f}", "Production Qty": "{:,.0f}"}),
        width="stretch",
    )

st.subheader("Changeovers")
st.caption(
    "A changeover is a different ITEM running in the same shift slot on the same "
    "physical machine (two rows for the same item under different BOM versions "
    "sharing a slot does NOT count — same product, confirmed by user 2026-09-23), "
    "OR a different item set running in Shift B vs Shift A on the same day, same "
    "machine (confirmed by user 2026-09-29 — checked same-day only, not across a "
    "day boundary). "
    f"Each changeover is estimated at {CHANGEOVER_MINUTES_DEFAULT} min of downtime "
    "(a default placeholder, not yet a real per-machine number)."
)
changeover_slots = capacity.find_changeover_slots(prod_raw, wk, dd_line, machine_no=machine_no)

if changeover_slots.empty:
    st.success("No changeovers in this selection.")
else:
    total_changeovers = int(changeover_slots["Changeovers"].sum())

    # Est. Tbgs lost needs each machine's own Target_Tbgs_Min rate straight
    # from MC_MASTER — not available for machines whose capacity is only
    # inferred from siblings, so those are excluded and flagged rather than
    # guessed at (same "flag, don't guess" rule as the CFC conversion gaps).
    mc_rate = mc_master.set_index(["Machine_Line", "Machine_No"])["Target_Tbgs_Min"]
    per_machine = changeover_slots.groupby("Machine No")["Changeovers"].sum()
    lost_tbgs = 0.0
    machines_without_rate = []
    for mno, cnt in per_machine.items():
        key = (dd_line, mno)
        if key in mc_rate.index:
            rate = mc_rate.loc[key]
            if isinstance(rate, pd.Series):
                rate = rate.iloc[0]
            lost_tbgs += cnt * CHANGEOVER_MINUTES_DEFAULT * float(rate)
        else:
            machines_without_rate.append(mno)

    cc1, cc2 = st.columns(2)
    cc1.metric("Changeovers", f"{total_changeovers:,.0f}")
    cc2.metric(
        "Est. Tbgs Lost", f"{lost_tbgs:,.0f}",
        help=f"{total_changeovers} changeovers x {CHANGEOVER_MINUTES_DEFAULT} min x each machine's Target Tbgs/Min rate",
    )
    if machines_without_rate:
        st.caption(
            f"⚠ Est. Tbgs Lost excludes machine(s) with no MC_MASTER row (capacity inferred, "
            f"no direct rate to use): {', '.join(machines_without_rate)}"
        )

    st.dataframe(
        changeover_slots[["Machine No", "Day", "Shift", "Items", "Changeovers"]],
        width="stretch",
    )

if not breakdown.empty:
    st.subheader("Daily production")
    daily = breakdown.groupby("Day", sort=False)[["Planned Qty", "Production Qty"]].sum().reset_index()
    fig = px.bar(
        daily, x="Day", y=["Planned Qty", "Production Qty"], barmode="group",
        labels={"value": "Tbgs", "variable": "Metric"},
        color_discrete_sequence=[GOLD_DARK, GOLD],
    )
    ui.plotly_chart(ui.style_fig(fig), width="stretch")

# ---------------- Section 3: Performance Comparison ----------------
st.header("3. Performance Comparison")
ranked = view[view["Total Available (Tbgs)"] > 0].sort_values("Efficiency %", ascending=False)
top5 = ranked.head(5)
bottom5 = ranked.tail(5).sort_values("Efficiency %", ascending=True)

# Capacity vs Produced, both in Tbgs — Total Available (Tbgs) is real
# machine capacity from MC_MASTER, Actual Production (Tbgs) is the
# CFC->Tbgs-converted weekly production figure, same unit on both sides.
# No Plan here at all (show_plan=False) — Booked Week Plan is a different
# unit (CFC) and isn't part of this comparison (confirmed by user
# 2026-09-23 — this chart is Capacity vs Production only).
def _perf_row(r):
    return {
        "name": r["Machine Line"], "capacity": r["Total Available (Tbgs)"],
        "production": r["Actual Production (Tbgs)"], "plan": 0,
        "status": r.get("Status") if status_df is not None else None,
    }


col_top, col_bottom = st.columns(2)
with col_top:
    st.subheader("Top 5 Most Efficient")
    rows = [_perf_row(r) for _, r in top5.sort_values("Efficiency %").iterrows()]
    ui.plotly_chart(ui.bullet_chart(rows, show_plan=False), width="stretch", key="mc_perf_top5")

with col_bottom:
    st.subheader("Bottom 5 Least Efficient")
    rows = [_perf_row(r) for _, r in bottom5.sort_values("Efficiency %", ascending=False).iterrows()]
    ui.plotly_chart(ui.bullet_chart(rows, show_plan=False), width="stretch", key="mc_perf_bottom5")

_loader.empty()
