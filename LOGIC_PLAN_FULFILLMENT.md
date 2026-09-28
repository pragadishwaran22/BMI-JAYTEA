# Fulfillment Dashboard (Plan vs Produced) — Logic Plan

Confirmed 2026-09-21. Second component, separate from Machine Capacity
Efficiency (see `LOGIC_PLAN.md`). No UI/app code until this is signed off.

## Source
`Report For plan` sheet only — self-contained per the Step 8 finding in
`LOGIC_PLAN.md`. No join to `weekly production`.

Grain: one row per (Item, Machine Line, BOM Version) per week.

**Caveat inherited from LOGIC_PLAN.md Step 8/9:** `Report For plan`'s
Machine Line is a planning label, not a guaranteed physical-machine record
(see the GOLD BOND finding). Any "by machine line" view in this dashboard
carries that same caveat — it reflects what was booked under that label,
not necessarily what that specific machine produced.

## Weeks available
- **Week 38, Week 39** — real data, `Produced` is meaningful.
- **Week 40–44** — booked-plan-only (PM weeks). Only `Booked Week Plan`
  exists; no Produced/Commited/etc. columns. Must be handled as a distinct
  case in the UI ("planned, not yet due"), never plotted as 0% fulfillment.

## Columns confirmed usable
```
Booked Week Plan     — total committed order qty for the week
Booked in Day Plan   — portion scheduled into day/shift slots
Carry Forwarded      — backlog carried in from prior week (populated for
                        Week 38; found entirely zero for Week 39 in this
                        snapshot — unconfirmed whether that's real or an
                        unpopulated-column artifact; flag, don't assume)
Commited             — portion committed to produce
Produced             — actual output
```

## Columns confirmed UNUSABLE (2026-09-21)
```
Pending Day Plan     — 0 on all 298 rows, both Week 38 and Week 39
Pending Commit       — 0 on all 298 rows, both weeks
Pending Production   — 0 on all 298 rows, both weeks
Excess Production    — 0 on all 298 rows, both weeks
```
These are unpopulated placeholders in this data snapshot, not real signal.
Do not read them as "zero backlog" — they simply were never filled in.
**Deferred:** whether/how to derive Pending/Excess ourselves
(`max(Booked − Produced, 0)` / `max(Produced − Booked, 0)`) is parked until
the backlog table is designed — not needed for the sections below.

## Metrics (line/SKU grain, rolls up cleanly by summing)
```
Fulfillment %  = Produced / Booked Week Plan × 100      (Step 8, LOGIC_PLAN.md)
```
No new metric needed beyond what Step 8/9 already defined — this dashboard
is a dedicated visual surface for that existing number, not a new formula.

## Sections (backlog table deferred — not in this pass)

### 1. KPI row (confirmed scope: all lines, aggregated, for the selected week)
```
Total Booked Week Plan   = Σ Booked Week Plan   over all rows
Total Produced            = Σ Produced           over all rows
Overall Fulfillment %     = Total Produced / Total Booked Week Plan × 100
```

### 2. Funnel: Booked Week Plan → Commited → Produced
Same scope as the KPI row by default (all lines); drills down to one
machine line or one SKU as a secondary interaction. Shows where volume
drops off between booking, commitment, and actual output.

### 3. Plan vs Produced by machine line
Horizontal bar, two bars per line (Booked Week Plan, Produced), sorted by
Fulfillment % ascending (worst gap first). Same hover-tooltip pattern as
the Component 1 bullet chart.

### 4. Week-over-week trend
Week 38 vs Week 39 only (the two weeks with real Produced data). Weeks
40-44 shown as a separate "booked, not yet due" indicator — never plotted
against Produced=0, which would misrepresent a future week as a missed one.

## Open items
- Backlog table — deferred, not designed yet.

## Resolved, 2026-09-21
- Week 39's all-zero Carry Forwarded (and, confirmed now, all-zero
  Produced too — `compute_fulfillment_kpis`/`compute_weekly_trend` show
  Total Produced = 0 for the whole week) is **not** an unpopulated-column
  artifact. Today's date is 2026-09-21 and Week 39 runs 21–26 Sep — the
  week has the full 10-column structure (`is_full = True`) but simply
  hasn't happened yet. Distinct from the Pending/Excess columns, which are
  unpopulated even in Week 38, a week that's fully in the past.
- `list_report_for_plan_weeks()` / `load_report_for_plan()` now correctly
  distinguish full weeks (38, 39 — 10-column block) from future PM weeks
  (40-44 — Booked Week Plan only); future weeks return `Produced = NaN`,
  never a fabricated 0, and `compute_fulfillment_kpis` / `compute_funnel`
  raise explicitly if called on one. Validated: Week 40-44 all report
  `is_full = False`, Week 38/39 report `True`.
