"""
Fulfillment Dashboard (Plan vs Produced) — calculation layer.
Implements LOGIC_PLAN.md Step 8 and LOGIC_PLAN_FULFILLMENT.md. No UI code here.
"""
from __future__ import annotations

import pandas as pd

from loaders import list_report_for_plan_weeks, load_report_for_plan


def compute_sku_fulfillment(report_for_plan: pd.DataFrame) -> pd.DataFrame:
    """Item-level Booked Week Plan / Produced / Fulfillment %, summed
    across BOM Version and Machine Line — one row per distinct Item name,
    not per `Report For plan` row (per user request, 2026-09-22: a SKU
    that spans multiple BOM versions should read as one number, not be
    fragmented across rows). Item Name is already merge-corrected by
    loaders.load_report_for_plan() (see LOGIC_PLAN.md's 2026-09-22
    correction — the source sheet uses merged Excel cells for Item, not a
    "blank after first mention" convention); any row still blank here
    genuinely has no name in the source and groups together as "(unnamed
    item)" rather than being dropped.

    Note: no cross-sheet join is performed either way (see LOGIC_PLAN.md
    Step 8) — this only sums rows already present in `report_for_plan`.
    """
    df = report_for_plan.copy()
    blank = df["Item"].isna() | (df["Item"].astype(str).str.strip().isin(["", "nan", "None"]))
    df.loc[blank, "Item"] = "(unnamed item)"

    agg_cols = {"Booked Week Plan": ("Booked Week Plan", "sum"), "Produced": ("Produced", "sum")}
    if "Last Week Plan" in df.columns:
        agg_cols["Last Week Plan"] = ("Last Week Plan", "sum")
    grouped = df.groupby("Item", as_index=False).agg(**agg_cols)
    grouped["Fulfillment %"] = grouped.apply(
        lambda r: (r["Produced"] / r["Booked Week Plan"] * 100) if r["Booked Week Plan"] else None,
        axis=1,
    )
    return grouped


def classify_overproduction(booked_week_plan: float, last_week_plan: float, produced: float) -> tuple[str, str]:
    """For a SKU where Produced > Booked Week Plan, explain whether the
    overrun is accounted for by last week's uncommitted carryover, or is
    unexplained. Confirmed by user 2026-09-22:
      - Produced <= Booked Week Plan               -> "neutral" (not over
                                                        plan at all, nothing
                                                        to flag)
      - Booked Week Plan < Produced
        <= Booked Week Plan + Last Week Plan        -> "explained" (the
                                                        overrun is covered
                                                        by last week's
                                                        uncommitted plan
                                                        carrying over)
      - Produced > Booked Week Plan + Last Week Plan -> "unexplained"
                                                        (exceeds every
                                                        known demand
                                                        figure — needs
                                                        investigation)
    Returns (status, hover_note) — status is one of "neutral", "explained",
    "unexplained"; hover_note is ready-to-use HTML (with a leading <br>)
    for bullet_chart's hover_note field, or "" for neutral.
    """
    if produced <= booked_week_plan:
        return "neutral", ""
    total_known_demand = booked_week_plan + last_week_plan
    if produced <= total_known_demand:
        return (
            "explained",
            f"<br><br><b>Over plan, but explained:</b><br>"
            f"Last Week Plan (uncommitted): {last_week_plan:,.0f}<br>"
            f"Plan + Last Week Plan: {total_known_demand:,.0f} ≥ Produced",
        )
    return (
        "unexplained",
        f"<br><br><b>Over plan — needs investigation:</b><br>"
        f"Produced exceeds Plan + Last Week Plan<br>"
        f"({produced:,.0f} > {total_known_demand:,.0f})",
    )


def sku_machine_line_flows(report_for_plan: pd.DataFrame, items: list[str]) -> pd.DataFrame:
    """Item -> Machine Line flows for Sankey use — EVERY machine line the
    given SKU(s) are assigned to in `Report For plan`, regardless of
    Booked Week Plan or Produced (confirmed by user 2026-09-22: show every
    assigned line, not just the ones with output). Sums both Booked Week
    Plan and Produced across BOM versions within the same (Item, Machine
    Line) pair, so the caller can decide what to display per row:
      - Produced > 0                    -> real production happened
      - Produced == 0, Booked > 0       -> assigned + committed, nothing
                                            made yet (surfaced on hover)
      - Produced == 0, Booked == 0      -> assigned but nothing booked or
                                            made either — a genuine zero,
                                            not a data gap
    `Report For plan` has no individual physical Machine No (that's only
    in `weekly production`), so Machine Line is the finest grouping
    available here — same caveat as everywhere else in this module: a
    line here reflects what was booked/produced under that label, not a
    verified single physical machine (see LOGIC_PLAN.md Step 8/9).
    """
    df = report_for_plan.copy()
    blank = df["Item"].isna() | (df["Item"].astype(str).str.strip().isin(["", "nan", "None"]))
    df.loc[blank, "Item"] = "(unnamed item)"

    scoped = df[df["Item"].isin(items)]
    agg = scoped.groupby(["Item", "Machine Line"], as_index=False)[["Booked Week Plan", "Produced"]].sum()
    return agg.reset_index(drop=True)


def compute_line_fulfillment(report_for_plan: pd.DataFrame) -> pd.DataFrame:
    """Roll SKU-level Booked Week Plan / Produced up to Machine Line grain."""
    agg_cols = {
        "Booked Week Plan": ("Booked Week Plan", "sum"),
        "Produced (Plan)": ("Produced", "sum"),
    }
    if "Last Week Plan" in report_for_plan.columns:
        agg_cols["Last Week Plan"] = ("Last Week Plan", "sum")
    agg = report_for_plan.groupby("Machine Line").agg(**agg_cols).reset_index()
    agg["Fulfillment %"] = agg.apply(
        lambda r: (r["Produced (Plan)"] / r["Booked Week Plan"] * 100) if r["Booked Week Plan"] else None,
        axis=1,
    )
    return agg


def compute_fulfillment_kpis(report_for_plan: pd.DataFrame) -> dict:
    """Plant-wide KPI row for a full (non-future) week."""
    if not report_for_plan.attrs.get("is_full", True):
        raise ValueError("Week has no Produced data (future/PM week) — KPIs are undefined")
    total_booked = report_for_plan["Booked Week Plan"].sum()
    total_produced = report_for_plan["Produced"].sum()
    # Plant-wide sum of "Last week Plan (uncommited Qty)" — same figure
    # classify_overproduction() already uses per-line/per-SKU to explain an
    # over-100% number as covered by last week's uncommitted carryover
    # demand, rolled up here to the whole-week total (confirmed by user
    # 2026-09-25) for the Overview page's Overall Fulfillment % tooltip.
    total_last_week_plan = report_for_plan["Last Week Plan"].sum() if "Last Week Plan" in report_for_plan.columns else 0
    total_with_carryover = total_booked + total_last_week_plan
    return {
        "Total Booked Week Plan": total_booked,
        "Total Produced": total_produced,
        "Overall Fulfillment %": (total_produced / total_booked * 100) if total_booked else None,
        "Total Last Week Plan": total_last_week_plan,
        "Fulfillment % incl. Last Week Plan": (total_produced / total_with_carryover * 100) if total_with_carryover else None,
    }


def compute_day_fulfillment(daily_sku: pd.DataFrame, day_offset: int) -> dict:
    """Plant-wide day-wise KPI, summed across every SKU for one day
    (Monday=offset 0 .. Saturday=offset 5) — from
    capacity.daily_sku_totals()'s 'weekly production'-sourced grain, NOT
    'Report For plan' (confirmed by user 2026-09-28: that sheet has no
    day-level data at all)."""
    day_rows = daily_sku[daily_sku["Day Offset"] == day_offset]
    total_planned = float(day_rows["Planned Qty"].sum())
    total_produced = float(day_rows["Production Qty"].sum())
    return {
        "Day Planned Qty": total_planned,
        "Day Produced Qty": total_produced,
        "Day Fulfillment %": (total_produced / total_planned * 100) if total_planned else None,
    }


def compute_funnel(report_for_plan: pd.DataFrame, machine_line: str | None = None) -> dict:
    """Booked Week Plan -> Commited -> Produced funnel, optionally scoped
    to one machine line."""
    if not report_for_plan.attrs.get("is_full", True):
        raise ValueError("Week has no Commited/Produced data (future/PM week)")
    df = report_for_plan
    if machine_line:
        df = df[df["Machine Line"] == machine_line]
    return {
        "Booked Week Plan": df["Booked Week Plan"].sum(),
        "Commited": df["Commited"].sum(),
        "Produced": df["Produced"].sum(),
    }


def compute_weekly_trend(path, week_nums: list[str]) -> pd.DataFrame:
    """Booked vs Produced totals across multiple weeks. Future (PM) weeks
    come back with Produced = None (not 0) so they're never plotted as a
    missed week — the UI must handle None distinctly from a real zero.
    """
    weeks = list_report_for_plan_weeks(path)
    rows = []
    for wn in week_nums:
        if wn not in weeks:
            continue
        rfp = load_report_for_plan(path, wn)
        is_full = rfp.attrs.get("is_full", True)
        booked = pd.to_numeric(rfp["Booked Week Plan"], errors="coerce").fillna(0).sum()
        produced = pd.to_numeric(rfp["Produced"], errors="coerce").sum() if is_full else None
        rows.append({
            "Week": weeks[wn].label,
            "Week Num": wn,
            "Is Full": is_full,
            "Booked Week Plan": booked,
            "Produced": produced,
        })
    return pd.DataFrame(rows)
