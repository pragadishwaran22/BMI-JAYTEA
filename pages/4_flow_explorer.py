import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import loaders  # noqa: E402
import capacity  # noqa: E402
import fulfillment  # noqa: E402
import ui  # noqa: E402

ui.render_header("Flow Explorer — Production Flow")

if "weekly_workbook_bytes" not in st.session_state:
    ui.blocked_state("Upload your Week wise Planning report on the Overview page to see this dashboard.")
    st.stop()

raw_bytes = st.session_state["weekly_workbook_bytes"]

# Shown from here until the end of this page's rendering — covers the
# ENTIRE script run (both sections' data loads + Sankey diagrams), not
# just a cached fetch, so it's visible for the real page-visit/navigation
# delay (confirmed by user 2026-09-24).
_loader = ui.tea_brewing_loader("Brewing your dashboard…")

st.caption(
    "Both views below answer the same question — what flowed through what, and how much — "
    "at two different grains and from two different sheets. They're never cross-joined "
    "(see LOGIC_PLAN.md Step 8): the physical-machine view only exists where `weekly "
    "production` tracks it; the SKU view is `Report For plan`'s own machine-line labels."
)

# --------------------------------------------------------------------------
# A. Machine → Product (physical machine, from weekly production)
# --------------------------------------------------------------------------
st.header("Production Flow — Machine → Product")
st.caption("Which physical machine on a line produced which item, and how much. Source: `weekly production`.")
st.info("Note: an SKU with zero production this week will not appear in the graph.")


@st.cache_data(show_spinner=False)
def _load_weekly(raw_bytes: bytes):
    prod_raw = loaders.load_weekly_production_raw(loaders.make_buffer(raw_bytes))
    date_ranges = loaders.load_week_date_ranges(loaders.make_buffer(raw_bytes))
    weeks = loaders.discover_weeks(prod_raw, date_ranges)
    return prod_raw, weeks


prod_raw, weeks = _load_weekly(raw_bytes)

if not weeks:
    st.warning("No week blocks found in the 'weekly production' sheet of this workbook.")
else:
    week_labels = list(weeks.keys())
    col_a, col_b = st.columns(2)
    with col_a:
        week_label = st.selectbox(
            "Week", week_labels,
            index=ui.persisted_index("flow_machine_week", week_labels), key="flow_machine_week",
        )
        ui.persist("flow_machine_week", week_label)
    wk = weeks[week_label]

    data = loaders.load_data_rows(prod_raw)
    lines = sorted(set(data[2].unique()) - {"", "nan", "None"})
    with col_b:
        machine_line = st.selectbox(
            "Machine line", lines,
            index=ui.persisted_index("flow_machine_line", lines), key="flow_machine_line",
        )
        ui.persist("flow_machine_line", machine_line)

    product_flow = capacity.machine_product_breakdown(prod_raw, wk, machine_line)
    if product_flow.empty:
        st.info("No production to show for this machine line.")
    else:
        ui.plotly_chart(
            ui.sankey_chart(product_flow, source_col="Machine No", target_col="Item", value_col="Production Qty"),
            width="stretch",
            key="flow_machine_sankey",
        )

st.divider()

# --------------------------------------------------------------------------
# B. SKU → Machine Line (from Report For plan)
# --------------------------------------------------------------------------
st.header("Production Flow — SKU → Machine Line")
st.caption(
    "Pick one or more SKUs to see how much of each was produced under each "
    "machine line's label. Source: `Report For plan` — no individual physical "
    "machine number (that's only in `weekly production`, used in the view above), "
    "so Machine Line is the finest grouping available here."
)


@st.cache_data(show_spinner=False)
def _load_rfp_weeks(raw_bytes: bytes):
    return loaders.list_report_for_plan_weeks(loaders.make_buffer(raw_bytes))


rfp_weeks = _load_rfp_weeks(raw_bytes)
full_weeks = {wn: w for wn, w in rfp_weeks.items() if w.is_full}

if not full_weeks:
    st.warning("No completed weeks (with Produced data) found in 'Report For plan'.")
else:
    flow_sku_week_options = sorted(full_weeks.keys(), key=int)
    week_num = st.selectbox(
        "Week", flow_sku_week_options,
        format_func=lambda w: full_weeks[w].label,
        index=ui.persisted_index("flow_sku_week", flow_sku_week_options), key="flow_sku_week",
    )
    ui.persist("flow_sku_week", week_num)
    rfp = loaders.load_report_for_plan(loaders.make_buffer(raw_bytes), week_num)
    sku_ful = fulfillment.compute_sku_fulfillment(rfp)
    sku_ful = sku_ful[sku_ful["Booked Week Plan"] > 0]

    all_items = sku_ful.sort_values("Produced", ascending=False)["Item"].tolist()
    _persisted_items = ui.persisted_default("flow_sku_items", all_items[:3])
    _default_items = [i for i in _persisted_items if i in all_items]
    selected_items = st.multiselect("Choose SKU(s)", all_items, default=_default_items, key="flow_sku_items")
    ui.persist("flow_sku_items", selected_items)

    if not selected_items:
        st.info("Select at least one SKU to see its production flow.")
    else:
        flow_df = fulfillment.sku_machine_line_flows(rfp, selected_items)
        if flow_df.empty:
            st.info("No machine line is assigned to the selected SKU(s) this week.")
        else:
            st.caption(
                "Every machine line assigned to the selected SKU(s) is shown — gold "
                "links are real production, amber links are booked but not yet "
                "produced (hover for the booked amount), gray links have neither."
            )
            ui.plotly_chart(
                ui.sku_machine_sankey(flow_df),
                width="stretch",
                key="flow_sku_sankey",
            )

_loader.empty()
