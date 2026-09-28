"""
Status quadrant — reconciles Efficiency % (Component 1) with Fulfillment %
(Component 2). Implements LOGIC_PLAN.md Step 9. Depends on both components,
so it lives on its own rather than inside capacity.py or fulfillment.py.
"""
from __future__ import annotations

import pandas as pd

EFFICIENCY_PASS_THRESHOLD = 50.0    # reuses the Green color band (Efficiency % > 50)
FULFILLMENT_PASS_THRESHOLD = 100.0  # Produced >= 100% of Booked Week Plan

ON_TRACK = "On Track"
UNDER_SCHEDULED = "Under-scheduled"
FALLING_SHORT = "Falling short despite full shifts"
UNDERPERFORMING = "Underperforming"
NO_PLAN_DATA = "No plan data"


def compute_status(line_efficiency: pd.DataFrame, line_fulfillment: pd.DataFrame) -> pd.DataFrame:
    """Merge Efficiency % (capacity utilization) with Fulfillment %
    (plan delivery) into one Status quadrant per LOGIC_PLAN Step 9.
    """
    merged = line_efficiency.merge(line_fulfillment, on="Machine Line", how="left")

    def status(row):
        eff_pass = row["Efficiency %"] > EFFICIENCY_PASS_THRESHOLD
        ful = row["Fulfillment %"]
        if pd.isna(ful):
            return NO_PLAN_DATA
        ful_pass = ful >= FULFILLMENT_PASS_THRESHOLD
        if eff_pass and ful_pass:
            return ON_TRACK
        if not eff_pass and ful_pass:
            return UNDER_SCHEDULED
        if eff_pass and not ful_pass:
            return FALLING_SHORT
        return UNDERPERFORMING

    merged["Status"] = merged.apply(status, axis=1)
    return merged
