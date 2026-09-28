"""
Data loading — MC_MASTER (bundled, permanent) and the weekly workbook
(user-uploaded). No calculation logic here, see capacity.py / fulfillment.py.

Multi-read safety (ARCHITECTURE.md): callers should pass either a plain
path (bundled MC_MASTER) or a fresh io.BytesIO built from raw bytes stored
once in st.session_state (uploaded weekly workbook) — see
make_buffer() below. pandas.read_excel accepts both transparently.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

import openpyxl
import pandas as pd

DATE_RANGE_RE = re.compile(r"(\d{2}-\d{2}-\d{4})\s*To\s*(\d{2}-\d{2}-\d{4})", re.IGNORECASE)
WEEK_NUM_RE = re.compile(r"WEEK[-\s]*(?:NO)?[-\s]*(\d+)", re.IGNORECASE)

REQUIRED_SHEETS = ("Report For plan", "weekly production")


def make_buffer(raw_bytes: bytes) -> io.BytesIO:
    """Fresh, independent stream from immutable bytes — safe to call many
    times against the same uploaded workbook without any shared read
    position to manage."""
    return io.BytesIO(raw_bytes)


def validate_weekly_workbook(raw_bytes: bytes) -> list[str]:
    """Returns a list of problems (empty = valid). Checked before accepting
    an uploaded file, per ARCHITECTURE.md."""
    problems = []
    try:
        xl = pd.ExcelFile(make_buffer(raw_bytes))
    except Exception as e:
        return [f"Could not read this file as an Excel workbook: {e}"]
    for sheet in REQUIRED_SHEETS:
        if sheet not in xl.sheet_names:
            problems.append(f"Missing required sheet: '{sheet}'")
    return problems


# --------------------------------------------------------------------------
# MC_MASTER (bundled, permanent — never user-uploaded)
# --------------------------------------------------------------------------

def load_mc_master(path: str) -> pd.DataFrame:
    """Load machine capacity master data.

    Capacity_Per_Shift = Target_Tbgs_Min x Shift_Min, where Shift_Min
    (HR*60 + MIN) is read directly from MC_MASTER's own SHIFT MIN column.

    Reverted 2026-09-23: a 2026-09-22 change treated MIN as per-shift
    downtime to be excluded from capacity (Capacity = Target x HR*60
    only). The user confirmed that interpretation was wrong — undone here,
    back to using the full Shift_Min as-is. See LOGIC_PLAN.md for history.

    Returns columns: Machine_Line, Machine_No, Target_Tbgs_Min, Shift_Min,
    Capacity_Per_Shift. Keyed by (Machine_Line, Machine_No) — Machine_No is
    not guaranteed unique across lines.
    """
    raw = pd.read_excel(path, sheet_name="Sheet1 (2)", header=0)
    raw = raw.iloc[:, :9]
    raw.columns = [
        "Machine_Line", "Machine_No", "Packer", "Operator", "Machine_No2",
        "Target_Tbgs_Min", "HR", "MIN", "Shift_Min",
    ]
    raw = raw.dropna(subset=["Machine_Line", "Machine_No"]).copy()
    raw["Machine_Line"] = raw["Machine_Line"].astype(str).str.strip()
    raw["Machine_No"] = raw["Machine_No"].astype(str).str.strip()
    for c in ["Target_Tbgs_Min", "Shift_Min"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce").fillna(0)
    raw["Capacity_Per_Shift"] = raw["Target_Tbgs_Min"] * raw["Shift_Min"]
    return raw[["Machine_Line", "Machine_No", "Target_Tbgs_Min", "Shift_Min", "Capacity_Per_Shift"]]


def load_item_master(path: str) -> pd.DataFrame:
    """CFC -> Tbgs conversion factors, keyed by Item_Name.

    Confirmed by user 2026-09-23: `weekly production`'s Production Qty
    cells are recorded in CFC (master box) counts, not Tbgs directly.
    Validated by cross-checking against MC_MASTER capacity — treating raw
    cells as CFC and multiplying by TOTAL TBGS PER CFC brings nearly every
    real machine line to a plausible 75-98% efficiency (vs <1% when the
    raw cells are treated as already being Tbgs).

    Item_Name is the join key against Report For plan / weekly
    production's Item column. Of 227 distinct items across the bundled
    workbook's weeks, 187 match Item_Name exactly; the other 40 have no
    conversion factor here (mostly a missing case-pack prefix, e.g. "AL
    FINA CLOVE 25 DC ENV TBGS" vs Item_Master's "AL FINA CLOVE 24/25 DC
    ENV TBGS") and must be flagged as unconvertible by the caller, not
    guessed at or silently dropped.
    """
    raw = pd.read_excel(path, sheet_name="Sheet1", header=0)
    df = raw[["Item_Name", "TOTAL TBGS PER CFC"]].copy()
    df.columns = ["Item_Name", "Tbgs_Per_CFC"]
    df["Item_Name"] = df["Item_Name"].astype(str).str.strip()
    df["Tbgs_Per_CFC"] = pd.to_numeric(df["Tbgs_Per_CFC"], errors="coerce")
    df = df.dropna(subset=["Item_Name", "Tbgs_Per_CFC"])
    df = df.drop_duplicates(subset="Item_Name", keep="first")
    return df


def load_item_master_supplement(source) -> pd.DataFrame:
    """User-filled mapping for items with no factor in the bundled
    Item_Master (see load_item_master's docstring — the 40 unmatched
    items, e.g. missing case-pack prefixes like "AL FINA CLOVE 25 DC ENV
    TBGS"). `source` is a path or a file-like/bytes buffer of the same
    4-column template handed out for filling: Item_Name, No OF CTN PER
    CFC, NO OF TBGS PER CTN, TOTAL TBGS PER CFC.

    TOTAL TBGS PER CFC is used directly when present; if it's blank but
    both CTN and TBGS-per-CTN are filled, it's computed as their product
    (same relationship the bundled Item_Master holds exactly, confirmed
    2026-09-22). Rows with no usable factor either way are dropped, not
    guessed at.

    Accepts either .xlsx or .csv (the template was handed out as both —
    2026-09-23, some users couldn't get a working download of the .xlsx).
    Format is detected by trying Excel first, falling back to CSV, rather
    than trusting a filename — `source` is often a plain BytesIO by the
    time it reaches here (re-read from session_state bytes), which has no
    filename to sniff.
    """
    try:
        if hasattr(source, "seek"):
            source.seek(0)
        raw = pd.read_excel(source, sheet_name="Sheet1", header=0)
    except Exception:
        if hasattr(source, "seek"):
            source.seek(0)
        raw = pd.read_csv(source)
    df = raw[["Item_Name", "No OF CTN PER CFC", "NO OF TBGS PER CTN", "TOTAL TBGS PER CFC"]].copy()
    df["Item_Name"] = df["Item_Name"].astype(str).str.strip()
    for c in ["No OF CTN PER CFC", "NO OF TBGS PER CTN", "TOTAL TBGS PER CFC"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    computed = df["No OF CTN PER CFC"] * df["NO OF TBGS PER CTN"]
    df["Tbgs_Per_CFC"] = df["TOTAL TBGS PER CFC"].fillna(computed)

    df = df.dropna(subset=["Item_Name", "Tbgs_Per_CFC"])
    df = df[df["Item_Name"] != ""]
    df = df.drop_duplicates(subset="Item_Name", keep="last")
    return df[["Item_Name", "Tbgs_Per_CFC"]]


def merge_item_master(base: pd.DataFrame, supplement: pd.DataFrame | None) -> pd.DataFrame:
    """Overlay a user-filled supplement onto the bundled Item_Master —
    supplement rows win on a shared Item_Name (lets a manual correction
    override the bundled sheet), everything else from `base` is kept."""
    if supplement is None or supplement.empty:
        return base
    combined = pd.concat([base, supplement], ignore_index=True)
    return combined.drop_duplicates(subset="Item_Name", keep="last")


# --------------------------------------------------------------------------
# Workbook filename date (the "as of" date for run-rate style calculations)
# --------------------------------------------------------------------------

def parse_workbook_filename_date(filename: str) -> date | None:
    """The workbook's file name carries the date it was pulled/prepared,
    e.g. 'Week wise Planning report MDK CBE 22-09-2026 (1).xlsx' -> 22-09-2026.
    That date — not the day someone happens to open the dashboard, and not
    the live upload timestamp — is what "today" means for any date-relative
    calculation (e.g. the Weekly Run Rate divisor), confirmed by user
    2026-09-24. Returns None if no DD-MM-YYYY pattern is found, so the
    caller can fall back to another source.
    """
    match = re.search(r"(\d{2})-(\d{2})-(\d{4})", filename)
    if not match:
        return None
    day, month, year = match.groups()
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Week date ranges (from "Report For plan" header)
# --------------------------------------------------------------------------

def load_week_date_ranges(path) -> dict[str, tuple[date, date]]:
    """The 'weekly production' sheet only labels weeks as 'WEEK NO-38'; the
    actual calendar date range lives in the 'Report For plan' sheet's header
    row, e.g. 'PROD WEEK-38(14-09-2026 To 19-09-2026)'.
    Returns {"38": (start, end), ...} keyed by week number string.
    """
    header = pd.read_excel(path, sheet_name="Report For plan", header=None, nrows=1)
    ranges: dict[str, tuple[date, date]] = {}
    for val in header.iloc[0]:
        text = str(val)
        wnum = WEEK_NUM_RE.search(text)
        drange = DATE_RANGE_RE.search(text)
        if wnum and drange:
            start = pd.to_datetime(drange.group(1), format="%d-%m-%Y").date()
            end = pd.to_datetime(drange.group(2), format="%d-%m-%Y").date()
            ranges[wnum.group(1)] = (start, end)
    return ranges


# --------------------------------------------------------------------------
# Weekly production sheet
# --------------------------------------------------------------------------

@dataclass
class WeekInfo:
    label: str
    week_num: str | None
    start: date | None
    end: date | None
    labeled_days: list[str] = field(default_factory=list)   # weekday names within the labeled date range (reference only)
    prod_cols: list[int] = field(default_factory=list)       # ALL Production Qty column idx for this week block
    plan_cols: list[int] = field(default_factory=list)       # ALL Planned Qty column idx for this week block
    col_day_shift: dict = field(default_factory=dict)        # col_idx -> (day, shift)


def load_weekly_production_raw(path) -> pd.DataFrame:
    """`weekly production`'s Item column has the same merged-cell pattern
    as `Report For plan` (128 merges, confirmed via openpyxl) — forward-
    filled here so per-machine product breakdowns (e.g. the Sankey) show
    real item names instead of blanks on every row but a merge's anchor.
    """
    raw = pd.read_excel(path, sheet_name="weekly production", header=None)
    raw[0] = forward_fill_merged_column(path, "weekly production", raw[0], col_letter="A")
    return raw


def discover_weeks(raw: pd.DataFrame, date_ranges: dict[str, tuple[date, date]] | None = None) -> dict[str, WeekInfo]:
    """Scan the header rows and build a WeekInfo per week block found.

    Per LOGIC_PLAN.md Step 2: ALL day/shift columns in a week's block are
    used (including any day outside the labeled date range, e.g. a
    template 'Sunday' column) — nothing is excluded on the basis of date
    range. `labeled_days` is kept only as reference info for the UI.
    """
    date_ranges = date_ranges or {}
    week_row = raw.iloc[0].ffill()
    day_row = raw.iloc[1].ffill()
    shift_row = raw.iloc[2].ffill()
    metric_row = raw.iloc[3]

    weeks: dict[str, WeekInfo] = {}
    for c in range(4, raw.shape[1]):
        label = str(week_row[c]).strip()
        if not label or label.lower() == "nan" or not label.upper().startswith("WEEK NO"):
            continue
        metric = metric_row[c]
        if metric not in ("Planned Qty", "Production Qty"):
            continue

        if label not in weeks:
            wnum_m = WEEK_NUM_RE.search(label)
            wnum = wnum_m.group(1) if wnum_m else None
            start = end = None
            labeled_days: list[str] = []
            if wnum and wnum in date_ranges:
                start, end = date_ranges[wnum]
                d = start
                while d <= end:
                    labeled_days.append(d.strftime("%A"))
                    d += timedelta(days=1)
            weeks[label] = WeekInfo(label=label, week_num=wnum, start=start, end=end, labeled_days=labeled_days)

        wk = weeks[label]
        day = day_row[c]
        shift = shift_row[c]
        wk.col_day_shift[c] = (day, shift)
        if metric == "Planned Qty":
            wk.plan_cols.append(c)
        else:
            wk.prod_cols.append(c)

    return weeks


def forward_fill_merged_column(path, sheet_name: str, series: pd.Series, col_letter: str) -> pd.Series:
    """Restore values lost to merged Excel cells.

    Found 2026-09-22: `Report For plan`'s Item column uses merged cells to
    group multiple BOM-version rows under one SKU name (51 merge ranges in
    that column alone, confirmed via openpyxl — e.g. A93:A100 anchored at
    "CHAYA 12/100 DC ENV TBGS"). Both pandas and a naive openpyxl read only
    return the anchor (top-left) cell's value; every other row in the merge
    reads back as None/NaN — not because the source data is actually
    missing a name, but because reading tools don't forward-fill merges by
    default. This was initially misdiagnosed as "the sheet's own
    convention of blanking repeated names" — it isn't; it's merged-cell
    metadata that has to be read separately from cell values.

    `series` must be a 0-indexed pandas Series read via
    `pd.read_excel(..., header=None)` from `col_letter` of `sheet_name`,
    so `series.index[i]` corresponds to worksheet row `i + 1`.
    `weekly production` has the same pattern in its own Item column (128
    merges) — not fixed here since Item Name isn't read by any calculation
    in capacity.py today, but worth revisiting if that changes.
    """
    if hasattr(path, "seek"):
        path.seek(0)
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[sheet_name]
    out = series.copy()
    for rng in ws.merged_cells.ranges:
        if rng.min_col != rng.max_col or openpyxl.utils.get_column_letter(rng.min_col) != col_letter:
            continue
        anchor_value = ws.cell(row=rng.min_row, column=rng.min_col).value
        for row in range(rng.min_row, rng.max_row + 1):
            idx = row - 1
            if idx in out.index:
                out.loc[idx] = anchor_value
    return out


def load_data_rows(raw: pd.DataFrame) -> pd.DataFrame:
    """weekly production sheet, header rows stripped, columns normalized."""
    data = raw.iloc[4:].reset_index(drop=True)
    data.columns = range(data.shape[1])
    MLINE, MNO = 2, 3
    data[MLINE] = data[MLINE].astype(str).str.strip()
    data[MNO] = data[MNO].astype(str).str.strip()
    return data


# --------------------------------------------------------------------------
# Report For plan
# --------------------------------------------------------------------------

REPORT_FOR_PLAN_WEEK_COLS = {
    # offset within each week's 10-column block, 0-indexed from the block's
    # first data column (see header rows: Last week Plan, Booked Week Plan,
    # Booked in Day Plan, Carry Forwarded, Commited, Produced, Pending Day
    # Plan, Pending Commit, Pending Production, Excess Production)
    "Last Week Plan": 0,
    "Booked Week Plan": 1,
    "Booked in Day Plan": 2,
    "Carry Forwarded": 3,
    "Commited": 4,
    "Produced": 5,
    "Pending Day Plan": 6,
    "Pending Commit": 7,
    "Pending Production": 8,
    "Excess Production": 9,
}


@dataclass
class ReportForPlanWeek:
    week_num: str
    label: str
    col_start: int
    is_full: bool   # True = full 10-column block (Week 38/39 style);
                     # False = "PM WEEK" future week, Booked Week Plan only


def list_report_for_plan_weeks(path) -> dict[str, ReportForPlanWeek]:
    """Scan the header row and classify every week block found: a full
    10-column block (actual weeks, e.g. 'PROD WEEK-38') vs a single
    'Booked Week Plan' column only (future/PM weeks, e.g. 'PM WEEK-40')."""
    raw = pd.read_excel(path, sheet_name="Report For plan", header=None, nrows=2)
    header0, header1 = raw.iloc[0], raw.iloc[1]

    weeks: dict[str, ReportForPlanWeek] = {}
    for c in range(3, raw.shape[1]):
        text = str(header0[c])
        m = WEEK_NUM_RE.search(text)
        if not m or not DATE_RANGE_RE.search(text):
            continue
        wnum = m.group(1)
        is_full = str(header1[c]) == "Last week Plan (uncommited Qty)"
        weeks[wnum] = ReportForPlanWeek(week_num=wnum, label=text, col_start=c, is_full=is_full)
    return weeks


def load_report_for_plan(path, week_num: str) -> pd.DataFrame:
    """SKU-level Planned vs Produced for one week, read directly from
    `Report For plan`. Per LOGIC_PLAN Step 8, this sheet is self-contained
    for this purpose — no join to `weekly production` is performed.

    `week_num` is the week number string, e.g. "38". For a "future" (PM)
    week that only has Booked Week Plan (no Produced/Commited/etc. — see
    LOGIC_PLAN_FULFILLMENT.md), all other columns come back as NaN, not 0,
    so a future week is never mistaken for "produced nothing yet."
    """
    weeks = list_report_for_plan_weeks(path)
    if week_num not in weeks:
        raise ValueError(f"Week {week_num} not found in Report For plan header")
    wk = weeks[week_num]

    raw = pd.read_excel(path, sheet_name="Report For plan", header=None)
    raw[0] = forward_fill_merged_column(path, "Report For plan", raw[0], col_letter="A")
    data = raw.iloc[2:].reset_index(drop=True)
    out = pd.DataFrame({
        "Item": data[0],
        "Machine Line": data[1].astype(str).str.strip(),
        "BOM Version": data[2],
    })

    if wk.is_full:
        for label, offset in REPORT_FOR_PLAN_WEEK_COLS.items():
            out[label] = pd.to_numeric(data[wk.col_start + offset], errors="coerce").fillna(0)
    else:
        out["Booked Week Plan"] = pd.to_numeric(data[wk.col_start], errors="coerce").fillna(0)
        for label in REPORT_FOR_PLAN_WEEK_COLS:
            if label != "Booked Week Plan":
                out[label] = pd.NA

    out = out[out["Machine Line"].notna() & ~out["Machine Line"].isin(["", "nan", "None"])].reset_index(drop=True)
    out.attrs["is_full"] = wk.is_full
    return out
