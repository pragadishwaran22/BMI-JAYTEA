# App Architecture

Confirmed 2026-09-21. Governs how the Streamlit app is structured once
building starts — logic layers (LOGIC_PLAN.md, LOGIC_PLAN_FULFILLMENT.md)
are unaffected by this, this is UI/UX + code organization only.

## Structure
```
app.py                      # entry point, page navigation only
pages/
  1_overview.py              # landing page — hybrid: nav cards + proactive insights
  2_machine_capacity.py       # Component 1 (Machine Capacity Efficiency)
  3_fulfillment.py            # Component 2 (Fulfillment Dashboard)
  4_...                        # future components slot in here
src/
  loaders.py                  # Excel reading, shared across all components (cached once)
  capacity.py                  # Component 1 calc logic (current data_processing.py)
  fulfillment.py                # Component 2 calc logic
  status.py                     # shared Status/threshold logic (used by both)
  ui.py                          # reusable UI: KPI cards, status badges, bullet-chart
                                   builder, color scales — built once, reused everywhere
  constants.py                   # thresholds, color palette, status labels
LOGIC_PLAN.md / LOGIC_PLAN_FULFILLMENT.md   # stay as source of truth for the math
```

## Confirmed decisions

**Landing page (Overview): hybrid.**
- Nav cards linking to each component (Machine Capacity, Fulfillment, future
  ones as they're added).
- PLUS proactive insights pulled automatically from both components' logic
  — e.g. worst Status lines (Underperforming / Falling short), biggest
  Fulfillment gaps — so the user sees what needs attention before picking
  a page. This is the one place that reads across both `capacity.py` and
  `fulfillment.py` / `status.py`; the component pages themselves stay
  independent of each other.

**Week selector: independent per page, not shared via session_state.**
Each component remembers its own week selection separately. Rationale
(user's call): supports comparing different weeks across components side
by side, rather than forcing one week context across the whole app.

## Confirmed decisions — data input (2026-09-21)

**MC_MASTER is permanent, bundled with the app.** Always loaded from
`source data/MC MASTER.xlsx` in the repo. Never user-uploadable — it
changes far less often than the weekly workbook and isn't the thing that
needs to rotate week to week.

**The weekly workbook ("Week wise Planning report...") is user-uploaded,
not bundled.** Uploaded once via `st.file_uploader` **on the Overview page
only** — not repeated per component page. The uploaded file is stored in
`st.session_state` so Machine Capacity and Fulfillment pages both read the
same uploaded workbook without asking the user to upload it again.

- All existing loader functions (`load_weekly_production_raw`,
  `load_week_date_ranges`, `load_report_for_plan`, etc.) already take a
  `path` argument to `pd.read_excel`, which accepts a file-like object
  (Streamlit's `UploadedFile`) exactly like a path string — no signature
  changes needed, just pass the right object through instead of a
  hardcoded path.
- **Multi-read safety (confirmed 2026-09-21):** on upload, store the raw
  bytes once — `uploaded_file.getvalue()` — in `st.session_state`, not the
  `UploadedFile` object itself. Every loader call constructs its own fresh
  `io.BytesIO(raw_bytes)` from those immutable bytes. This avoids any
  shared read-position/seek state across the many separate reads
  `compute_weekly_trend` (and other multi-call code) makes against the
  same workbook — each read gets a clean stream, no seek(0) calls
  scattered through loader functions, no risk of one read leaving the
  buffer positioned wrong for the next.
- On upload: validate the workbook has both required sheets
  (`Report For plan`, `weekly production`) before accepting it — if either
  is missing, reject with a clear error naming what's missing, don't let a
  wrong file silently produce an empty/broken dashboard.

**Component pages (Machine Capacity, Fulfillment) show a clear blocked
state before any workbook is uploaded** — a message like "Upload your
Week wise Planning report on the Overview page to see this dashboard,"
not sample data and not an empty/broken chart. No charts or tables render
until a valid workbook exists in session_state.

## Why this shape
- `src/ui.py` as a shared component library is the main UI/UX lever — the
  bullet chart, status badges, and color-coding get built once and reused
  identically across pages, so the app feels like one product instead of
  stitched-together reports.
- Calc logic split per component (`capacity.py`, `fulfillment.py`) but
  sharing `status.py`, since Status already spans both (Efficiency from
  Capacity, Fulfillment from the other component) — that logic belongs to
  neither page alone.
- New components (future features) slot in as a new `pages/N_*.py` +
  `src/*.py` pair without touching existing ones.
