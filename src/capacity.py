"""
Machine Capacity Efficiency — calculation layer.
Implements LOGIC_PLAN.md Steps 1-7. No UI code here.
"""
from __future__ import annotations

import pandas as pd

from loaders import WeekInfo, load_data_rows


def _line_mode_capacity(mc_master: pd.DataFrame, line: str) -> float | None:
    """Most common Capacity_Per_Shift among a line's own matched machines
    in MC_MASTER — used to infer capacity for a sibling machine of the
    same line that has no MC_MASTER row of its own. None if the line has
    no matched machines at all (nothing to infer from)."""
    caps = mc_master.loc[mc_master["Machine_Line"] == line, "Capacity_Per_Shift"]
    if caps.empty:
        return None
    return float(caps.mode().iloc[0])


def compute_machine_efficiency(
    raw: pd.DataFrame, mc_master: pd.DataFrame, week: WeekInfo, item_master: pd.DataFrame,
) -> pd.DataFrame:
    """Per-machine (Machine Line, Machine No) efficiency table — the base
    grain everything else rolls up from. Implements LOGIC_PLAN.md Steps 1-5.

    Machines with no MC_MASTER row of their own (e.g. CT-11 under
    CONSTANTA TAG (D); 27/28 under CONSTANTA ENV H) get their capacity
    INFERRED from the most common Capacity/Shift among their own line's
    matched machines, per user decision 2026-09-22 — sibling machines on
    the same line are normally identical specs, confirmed for CONSTANTA
    TAG (D) (all 6 matched machines = 61,200) and, where they disagree
    (CONSTANTA ENV H: 62,500 x7 vs 65,250 x2), the mode (62,500) is used.
    Only truly excluded (and flagged) if the line has ZERO matched
    machines in MC_MASTER to infer from at all.

    Actual Production is converted CFC -> Tbgs per row via `item_master`
    (see loaders.load_item_master) — confirmed 2026-09-23 that
    `weekly production`'s Production Qty cells are CFC counts, not Tbgs.
    Rows whose Item has no conversion factor are excluded from Actual
    Production and reported separately as "Unconverted Qty (CFC)" /
    "Items Missing Conversion Factor" rather than guessed at.
    """
    data = load_data_rows(raw)
    ITEM, MLINE, MNO = 0, 2, 3
    prod_cols = week.prod_cols

    mc_keyed = mc_master.set_index(["Machine_Line", "Machine_No"])
    cfc_factor = item_master.set_index("Item_Name")["Tbgs_Per_CFC"]

    rows = []
    unmatched: list[tuple[str, str]] = []
    inferred: list[tuple[str, str]] = []
    for (line, mno), grp in data.groupby([MLINE, MNO]):
        if line in ("", "nan", "None") or mno in ("", "nan", "None"):
            continue

        vals = grp[prod_cols].apply(pd.to_numeric, errors="coerce").fillna(0) if prod_cols else pd.DataFrame(index=grp.index)
        # A shift is "worked" once per (day, shift) slot, regardless of how
        # many item rows have production in it. Multiple items in the same
        # slot is a changeover mid-shift (confirmed by user 2026-09-23,
        # MD20 HS example: Tuesday Shift A ran GV PASSION FRUIT then VEDAKA
        # GREEN TEA back-to-back), not two separate shifts. A week has at
        # most len(prod_cols) shifts total, so summing per-column first and
        # counting nonzero columns caps this correctly.
        shifts_worked = int((vals.sum(axis=0) > 0).sum()) if prod_cols else 0

        # Each row's weekly total is a CFC count for that (Item, Machine No)
        # pair — converted to Tbgs via that item's own factor before summing.
        row_cfc_total = vals.sum(axis=1) if prod_cols else pd.Series(dtype=float)
        items = grp[ITEM].astype(str).str.strip()
        factor = items.map(cfc_factor)
        has_factor = factor.notna()
        production = float((row_cfc_total[has_factor] * factor[has_factor]).sum())
        unconverted_qty = float(row_cfc_total[~has_factor].sum())
        missing_items = sorted(items[~has_factor & (row_cfc_total > 0)].unique().tolist())

        is_inferred = False
        if (line, mno) in mc_keyed.index:
            cap_row = mc_keyed.loc[(line, mno)]
            if isinstance(cap_row, pd.DataFrame):  # duplicate MC_MASTER rows for same key
                capacity_per_shift = float(cap_row["Capacity_Per_Shift"].iloc[0])
            else:
                capacity_per_shift = float(cap_row["Capacity_Per_Shift"])
        else:
            inferred_cap = _line_mode_capacity(mc_master, line)
            if inferred_cap is None:
                unmatched.append((line, mno))
                continue
            capacity_per_shift = inferred_cap
            is_inferred = True
            inferred.append((line, mno))

        total_available = capacity_per_shift * shifts_worked

        rows.append({
            "Machine Line": line,
            "Machine No": mno,
            "Capacity/Shift (Tbgs)": capacity_per_shift,
            "Shifts Worked": shifts_worked,
            "Total Available (Tbgs)": total_available,
            "Actual Production (Tbgs)": production,
            "Unconverted Qty (CFC)": unconverted_qty,
            "Items Missing Conversion Factor": ", ".join(missing_items),
            "Capacity Inferred": is_inferred,
        })

    df = pd.DataFrame(rows)
    df.attrs["unmatched_machines"] = unmatched
    df.attrs["inferred_machines"] = inferred
    return df


def compute_line_efficiency(
    raw: pd.DataFrame, mc_master: pd.DataFrame, week: WeekInfo, item_master: pd.DataFrame,
) -> pd.DataFrame:
    """Roll the per-machine table up to Machine Line grain — LOGIC_PLAN.md Step 6-7."""
    machine_df = compute_machine_efficiency(raw, mc_master, week, item_master)
    unmatched = machine_df.attrs.get("unmatched_machines", [])
    inferred = machine_df.attrs.get("inferred_machines", [])

    unmatched_by_line: dict[str, list[str]] = {}
    for line, mno in unmatched:
        unmatched_by_line.setdefault(line, []).append(mno)

    inferred_by_line: dict[str, list[str]] = {}
    for line, mno in inferred:
        inferred_by_line.setdefault(line, []).append(mno)

    if machine_df.empty:
        return pd.DataFrame()

    agg = machine_df.groupby("Machine Line").agg(
        Machines=("Machine No", "nunique"),
        **{
            "Shifts Worked": ("Shifts Worked", "sum"),
            "Capacity/Shift (Tbgs)": ("Capacity/Shift (Tbgs)", "sum"),
            "Total Available (Tbgs)": ("Total Available (Tbgs)", "sum"),
            "Actual Production (Tbgs)": ("Actual Production (Tbgs)", "sum"),
            "Unconverted Qty (CFC)": ("Unconverted Qty (CFC)", "sum"),
        },
    ).reset_index()

    # Union of item names (across this line's machines) with no CFC->Tbgs
    # conversion factor, for the "flag, don't guess" UI treatment.
    missing_items_by_line: dict[str, list[str]] = {}
    for line, items_str in zip(machine_df["Machine Line"], machine_df["Items Missing Conversion Factor"]):
        if not items_str:
            continue
        bucket = missing_items_by_line.setdefault(line, [])
        for it in items_str.split(", "):
            if it not in bucket:
                bucket.append(it)
    agg["Items Missing Conversion Factor"] = agg["Machine Line"].map(
        lambda l: ", ".join(sorted(missing_items_by_line.get(l, [])))
    )

    agg["Efficiency %"] = agg.apply(
        lambda r: (r["Actual Production (Tbgs)"] / r["Total Available (Tbgs)"] * 100) if r["Total Available (Tbgs)"] else 0.0,
        axis=1,
    )
    agg["Wasted Capacity (Tbgs)"] = agg["Total Available (Tbgs)"] - agg["Actual Production (Tbgs)"]
    agg["Wasted Capacity %"] = agg.apply(
        lambda r: (r["Wasted Capacity (Tbgs)"] / r["Total Available (Tbgs)"] * 100) if r["Total Available (Tbgs)"] else 0.0,
        axis=1,
    )
    agg["Unmatched Machines"] = agg["Machine Line"].map(
        lambda l: ", ".join(unmatched_by_line.get(l, []))
    )
    agg["Inferred Capacity Machines"] = agg["Machine Line"].map(
        lambda l: ", ".join(inferred_by_line.get(l, []))
    )

    agg = agg.sort_values("Efficiency %", ascending=False).reset_index(drop=True)
    return agg


def machine_product_breakdown(raw: pd.DataFrame, week: WeekInfo, machine_line: str) -> pd.DataFrame:
    """Machine No x Item production totals for one machine line/week — what
    each physical machine actually produced, and how much of each item.
    Item Name comes pre-merge-corrected from loaders.load_weekly_production_raw
    (see its docstring — the sheet uses merged Excel cells for Item, same
    as Report For plan). Rows with zero total production are dropped.
    """
    data = load_data_rows(raw)
    ITEM, MLINE, MNO = 0, 2, 3
    grp = data[data[MLINE] == machine_line]
    if grp.empty:
        return pd.DataFrame(columns=["Machine No", "Item", "Production Qty"])

    prod_cols = week.prod_cols
    out = grp[[MNO, ITEM]].copy()
    out.columns = ["Machine No", "Item"]
    out["Item"] = out["Item"].fillna("(unnamed item)").astype(str).replace({"nan": "(unnamed item)", "": "(unnamed item)"})
    out["Production Qty"] = (
        grp[prod_cols].apply(pd.to_numeric, errors="coerce").sum(axis=1).values if prod_cols else 0.0
    )

    agg = out.groupby(["Machine No", "Item"], as_index=False)["Production Qty"].sum()
    agg = agg[agg["Production Qty"] > 0].sort_values("Production Qty", ascending=False).reset_index(drop=True)
    return agg


def machine_numbers_for_line(raw: pd.DataFrame, machine_line: str) -> list[str]:
    """Every Machine No that appears under this line in weekly production,
    in the order first seen — for populating a per-machine drill-down
    selector. Includes machines with no MC_MASTER capacity match (they
    still have real production rows), unlike compute_machine_efficiency
    which excludes those from the capacity/efficiency numbers."""
    data = load_data_rows(raw)
    MLINE, MNO = 2, 3
    grp = data[data[MLINE] == machine_line]
    seen = []
    for m in grp[MNO]:
        if m not in ("", "nan", "None") and m not in seen:
            seen.append(m)
    return seen


def daily_breakdown(raw: pd.DataFrame, week: WeekInfo, machine_line: str, machine_no: str | None = None) -> pd.DataFrame:
    """Day x Shift Planned/Production breakdown for one machine line in a
    week. By default combines all machines on that line; pass `machine_no`
    to drill into one physical machine only (per-machine breakdown, since
    the line-level numbers are themselves a sum across machines that can
    each have very different shift counts — see LOGIC_PLAN.md's note on
    Capacity/Shift and Shifts Worked being display sums, not per-machine
    rates). Includes every column in the week's block (see LOGIC_PLAN.md
    Step 2 — nothing excluded by date range).
    """
    data = load_data_rows(raw)
    MLINE, MNO = 2, 3
    grp = data[data[MLINE] == machine_line]
    if machine_no is not None:
        grp = grp[grp[MNO] == machine_no]

    seen: dict[tuple, dict] = {}
    ordered_keys: list[tuple] = []
    for c in sorted(week.col_day_shift):
        day, shift = week.col_day_shift[c]
        key = (day, shift)
        if key not in seen:
            seen[key] = {"Day": day, "Shift": shift, "Planned Qty": 0.0, "Production Qty": 0.0}
            ordered_keys.append(key)
        metric = "Planned Qty" if c in week.plan_cols else "Production Qty"
        val = pd.to_numeric(grp[c], errors="coerce").fillna(0).sum() if not grp.empty else 0.0
        seen[key][metric] += val

    return pd.DataFrame([seen[k] for k in ordered_keys])


def daily_sku_totals(raw: pd.DataFrame, week: WeekInfo, machine_lines: list[str] | None = None) -> pd.DataFrame:
    """Day-wise (Monday=offset 0 .. Saturday=offset 5) Planned vs
    Production totals from the 'weekly production' sheet, summed across
    ALL machines and BOTH shifts, grouped by Item (SKU).

    `machine_lines` (optional) scopes the totals to only those Machine
    Line values (column 2) — lets the Fulfillment page's existing
    "Machine Line(s)" sidebar filter apply to day-wise data too, the
    same way it already scopes Report For plan's week-level data. `None`
    (default) keeps all machines/lines, matching the original behavior.

    Confirmed by user 2026-09-28: day-wise fulfillment must come from
    THIS sheet — 'Report For plan' has no day-level data at all, only
    weekly totals — combines Shift A + Shift B into one number per day,
    and is grouped by SKU rather than broken down by machine.

    Day-offset assignment: the week's day-columns are walked in
    ASCENDING COLUMN-INDEX order, and the first 6 DISTINCT day-labels
    encountered are assigned offsets 0 (Monday) through 5 (Saturday) —
    per the user's confirmed rule that a week always starts Monday and
    ends Saturday (e.g. a week starting 21-09-2026 means its 3rd day,
    the 23rd, is Wednesday: `week.start + timedelta(days=2)`). This
    assigns offsets by COLUMN ORDER, not by string-matching "Monday" in
    the sheet's own label text — the 7th distinct label (the sheet's
    template "Sunday" column, per LOGIC_PLAN.md Step 2) is excluded
    entirely, since real weeks are 6 days (matching the Weekly Run
    Rate's existing [1, 6]-day divisor clamp on the Overview page).

    Units stay raw CFC — the same scale this sheet's own Planned
    Qty/Production Qty already use, and the same scale 'Report For
    plan's Booked Week Plan/Produced already use elsewhere on the
    Fulfillment page — no Tbgs conversion here, so day-wise and
    week-wise numbers on the same page stay on one consistent scale.
    """
    data = load_data_rows(raw)
    ITEM, MLINE = 0, 2
    if machine_lines is not None:
        data = data[data[MLINE].isin(machine_lines)]

    day_offsets: dict[str, int] = {}
    for c in sorted(week.col_day_shift):
        day, _shift = week.col_day_shift[c]
        if day not in day_offsets and len(day_offsets) < 6:
            day_offsets[day] = len(day_offsets)

    records = []
    for c in sorted(week.col_day_shift):
        day, _shift = week.col_day_shift[c]
        offset = day_offsets.get(day)
        if offset is None:
            continue  # 7th/template "Sunday" column — excluded
        metric = "Planned Qty" if c in week.plan_cols else "Production Qty"
        vals = pd.to_numeric(data[c], errors="coerce").fillna(0)
        by_item = vals.groupby(data[ITEM]).sum()
        for item, val in by_item.items():
            if item in ("", "nan", "None"):
                continue
            records.append({"Day Offset": offset, "Item": item, "Metric": metric, "Value": val})

    if not records:
        return pd.DataFrame(columns=["Day Offset", "Item", "Planned Qty", "Production Qty"])

    long_df = pd.DataFrame(records)
    pivoted = long_df.pivot_table(
        index=["Day Offset", "Item"], columns="Metric", values="Value", aggfunc="sum", fill_value=0
    ).reset_index()
    for col in ("Planned Qty", "Production Qty"):
        if col not in pivoted.columns:
            pivoted[col] = 0.0
    return pivoted[["Day Offset", "Item", "Planned Qty", "Production Qty"]]


def find_changeover_slots(raw: pd.DataFrame, week: WeekInfo, machine_line: str, machine_no: str | None = None) -> pd.DataFrame:
    """Changeovers on a physical machine, from two sources (confirmed by
    user 2026-09-29):

    1. Intra-shift: more than one distinct ITEM ran in the same shift
       slot. Confirmed by user 2026-09-23: changeovers are keyed on Item
       changing, not BOM Version — two rows for the SAME Item under
       different BOM versions sharing a slot is NOT a changeover (it's
       the same physical product), so items are summed across BOM
       versions per slot before counting distinct ones.
    2. Inter-shift (Shift A -> Shift B, same day only — not across a day
       boundary such as Saturday -> the next Monday): the items running
       in Shift B differ from the items running in Shift A on the same
       machine. This is counted IN ADDITION to any intra-shift
       changeover already counted within Shift A or Shift B
       individually — e.g. Shift A = {X}, Shift B = {X, Y} contributes
       one intra-shift changeover (for Shift B's own X/Y overlap) plus
       one more for the A->B transition, since Shift B's item set as a
       whole differs from Shift A's. A transition is only counted when
       BOTH shifts have at least one item running — a shift with zero
       production isn't a changeover away from or into.

    Computed per physical Machine No even when `machine_no` is None (all
    machines on the line) — two different machines both running in
    "Tuesday Shift A" is not a changeover on either one, only multiple
    items sharing a slot ON THE SAME MACHINE is, and the A->B check is
    likewise per machine.

    Returns one row per changeover: Machine No, Day, Shift, Items, Item
    Count, Changeovers. Intra-shift rows list the distinct item names
    sharing that slot (comma-joined) with Changeovers = Item Count - 1.
    Inter-shift rows use Shift = "Shift A -> Shift B", Items formatted as
    "<Shift A items> -> <Shift B items>", Item Count = size of the union
    of both shifts' items, and Changeovers = 1. The sheet carries no
    within-shift timestamp, so intra-shift slots are reported as "items
    involved", not an ordered sequence.
    """
    data = load_data_rows(raw)
    ITEM, MLINE, MNO = 0, 2, 3
    grp = data[data[MLINE] == machine_line]
    if machine_no is not None:
        grp = grp[grp[MNO] == machine_no]
    cols = ["Machine No", "Day", "Shift", "Items", "Item Count", "Changeovers"]
    if grp.empty:
        return pd.DataFrame(columns=cols)

    prod_cols = week.prod_cols
    rows = []
    for mno, mgrp in grp.groupby(MNO):
        vals = mgrp[prod_cols].apply(pd.to_numeric, errors="coerce").fillna(0) if prod_cols else pd.DataFrame(index=mgrp.index)
        items = mgrp[ITEM].astype(str).str.strip()

        day_shift_items: dict[tuple[str, str], list[str]] = {}
        for c in sorted(prod_cols):
            if c not in week.col_day_shift:
                continue
            day, shift = week.col_day_shift[c]
            nonzero_items = items[vals[c] > 0]
            distinct_items = sorted(set(nonzero_items) - {"", "nan", "None"})
            day_shift_items[(day, shift)] = distinct_items
            if len(distinct_items) > 1:
                rows.append({
                    "Machine No": mno, "Day": day, "Shift": shift,
                    "Items": ", ".join(distinct_items),
                    "Item Count": len(distinct_items),
                    "Changeovers": len(distinct_items) - 1,
                })

        days = sorted({d for d, _ in day_shift_items})
        for day in days:
            a_items = day_shift_items.get((day, "Shift A"), [])
            b_items = day_shift_items.get((day, "Shift B"), [])
            if a_items and b_items and set(a_items) != set(b_items):
                rows.append({
                    "Machine No": mno, "Day": day, "Shift": "Shift A -> Shift B",
                    "Items": f"{', '.join(a_items)} -> {', '.join(b_items)}",
                    "Item Count": len(set(a_items) | set(b_items)),
                    "Changeovers": 1,
                })
    return pd.DataFrame(rows, columns=cols)


def convert_booked_plan_to_tbgs(
    report_for_plan: pd.DataFrame, item_master: pd.DataFrame, include_last_week: bool = False,
) -> tuple[float, list[str]]:
    """Convert Report For plan's Booked Week Plan (Item-level, CFC scale)
    to Tbgs via item_master's per-item Tbgs_Per_CFC factor — the same
    conversion compute_machine_efficiency() already applies to weekly
    production's Production Qty. Needed so a "Required Run Rate" (Booked
    Week Plan / remaining days) is directly comparable to the Tbgs/day
    Weekly Run Rate it's shown next to (confirmed by user 2026-09-29).

    `include_last_week=True` adds "Last Week Plan" (uncommitted carryover)
    into the per-row total before conversion, giving the "Targeted Tbgs"
    figure — Booked Week Plan + Last Week Uncommitted Plan, both CFC->Tbgs
    converted (confirmed by user 2026-09-29) — the same combined demand
    figure fulfillment.compute_fulfillment_kpis() already sums in CFC
    scale as "Fulfillment % incl. Last Week Plan"'s denominator.

    Items with no factor are excluded from the total and returned
    separately (flag, don't guess — same rule as
    compute_machine_efficiency's "Items Missing Conversion Factor").
    Returns (total_tbgs, missing_items).
    """
    df = report_for_plan.copy()
    blank = df["Item"].isna() | (df["Item"].astype(str).str.strip().isin(["", "nan", "None"]))
    df.loc[blank, "Item"] = "(unnamed item)"

    cfc_factor = item_master.set_index("Item_Name")["Tbgs_Per_CFC"]
    items = df["Item"].astype(str).str.strip()
    factor = items.map(cfc_factor)
    has_factor = factor.notna()
    booked = pd.to_numeric(df["Booked Week Plan"], errors="coerce").fillna(0)
    if include_last_week and "Last Week Plan" in df.columns:
        booked = booked + pd.to_numeric(df["Last Week Plan"], errors="coerce").fillna(0)

    total_tbgs = float((booked[has_factor] * factor[has_factor]).sum())
    missing_items = sorted(items[~has_factor & (booked > 0)].unique().tolist())
    return total_tbgs, missing_items


def find_items_without_cfc_factor(raw: pd.DataFrame, item_master: pd.DataFrame) -> list[str]:
    """Every distinct Item name in the whole `weekly production` sheet
    (every week block in this workbook, not just the currently selected
    one) that has no CFC->Tbgs factor in `item_master` — the same check
    compute_machine_efficiency does per row, surfaced workbook-wide so new
    SKUs can be caught and mapped before they ever show up as an
    "Unconverted Qty" flag on a specific week (2026-09-23).
    """
    data = load_data_rows(raw)
    ITEM = 0
    items = data[ITEM].astype(str).str.strip()
    items = items[~items.isin(["", "nan", "None"])].unique()
    known = set(item_master["Item_Name"])
    return sorted(i for i in items if i not in known)
