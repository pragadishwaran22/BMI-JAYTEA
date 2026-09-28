# Machine Capacity Efficiency — Logic Plan (v2)

Confirmed 2026-09-19. This document is the source of truth for the calculation
layer. No UI/app code should be written until this is signed off.

## Source files
- `source data/MC MASTER.xlsx` → sheet `Sheet1 (2)` — machine capacity specs
  (Machine Line, Machine No, Target Tbgs/Min, Hours, Minutes, Shift_Min)
- `source data/Week wise Planning report MDK CBE 18-09-2026.xlsx`
  - sheet `Report For plan` — used only to read each week's real calendar
    date range from its header row (e.g. `PROD WEEK-38(14-09-2026 To
    19-09-2026)`); the `weekly production` sheet's own week label
    ("WEEK NO-38") carries no dates.
  - sheet `weekly production` — daily shift-by-shift Planned Qty / Production
    Qty, one row per (Item, BOM Version, Machine Line, Machine No).

## Grain: everything is computed per physical machine first, then rolled up

### Step 1 — Capacity/Shift (per Machine No)
```
Capacity_Per_Shift  = Target_Tbgs_Min × Shift_Min      (Shift_Min from MC_MASTER)
```
`Shift_Min` (= HR×60 + MIN, as read directly from MC_MASTER's own SHIFT MIN
column) is used as-is.

**Reverted 2026-09-23 (user):** a 2026-09-22 change treated MC_MASTER's
`MIN` column as per-shift downtime to be excluded from capacity (Capacity =
Target × HR×60 only, dropping the `MIN` minutes). The user has since
confirmed that interpretation was wrong. Undone — back to the original
formula above, using the full `Shift_Min` with no downtime deduction.

Matched by the pair **(Machine Line, Machine No)**, since Machine No is not
guaranteed unique across lines.

**If a Machine No appears in `weekly production` but has no matching row in
MC_MASTER:** its capacity is inferred from the mode of its own line's other
matched machines' Capacity/Shift (confirmed by the user 2026-09-22 — sibling
machines on a line are normally identical specs), and it's included in that
line's Capacity/Shift and Shifts Worked, flagged in the UI as inferred. Only
excluded entirely (and flagged as such) if the line has zero matched
machines in MC_MASTER to infer from at all.

### Step 2 — Valid week window
For the selected week, take its date range from `Report For plan`. The
`weekly production` sheet's day columns run Monday→Sunday as a fixed
template regardless of how many calendar days the week actually spans.

**Sunday (or any day outside the labeled range) is still included** if it has
non-zero data — real production isn't discarded just because it falls outside
the officially labeled window. (Confirmed: include, don't exclude.)

So in practice: use **all day/shift columns present in that week's block**
(currently always Monday–Sunday × Shift A/B = 14 slots), not just the ones
inside the labeled date range.

### Step 3 — Shifts Worked (per Machine No)
```
Shifts_Worked(machine) = COUNT of distinct (day, shift) slots for that
                          machine where SUM of Production Qty across all
                          its rows in that slot > 0
```
**Corrected 2026-09-23 (user):** this is a deduplicated day+shift count, NOT
a raw cell count. If two different SKU/BOM rows on the same machine both
show output in "Tuesday Shift A," that's one shift with a mid-shift
changeover (item swap), not two separate shifts — confirmed with MD20 HS
Week 38: machine 36 and machine 34 each had a slot with two item rows
producing (a changeover), and the correct line-level total is 4 shifts
worked, not the 6 the old cell-count formula gave.

A week has at most `len(prod_cols)` shifts total per machine (14 for a
Mon–Sun x 2-shift week), so this can never overcount past the number of
actual shift slots — unlike the old formula.

**Superseded:** an earlier version of this doc claimed VARIETIES PACK /
C250-06 / Week 38 = 13 shifts worked as a "confirmed against manual count"
example. That number was itself produced by the buggy cell-count formula
being corrected here — under the corrected dedup logic it is 8, not 13. The
original manual count that produced "13" was not deduplicating changeovers
either, so it agreed with the bug rather than catching it.

### Step 4 — Actual Production (per Machine No)
```
Actual_Production(machine) = SUM over its rows of:
    (row's weekly Production Qty total, in CFC) x Tbgs_Per_CFC(Item)
```
**Corrected 2026-09-23 (user):** `weekly production`'s Production Qty cells
are recorded in **CFC** (master box) counts, not Tbgs directly — a CFC is a
master box containing several cartons, each carton containing several
Tbgs (`source data/Item Master.xlsx`, columns `No OF CTN PER CFC` x
`NO OF TBGS PER CTN` = `TOTAL TBGS PER CFC`). Confirmed by cross-checking
against MC_MASTER capacity: treating raw cells as already-Tbgs put nearly
every machine line under 1% efficiency; converting via each item's own
`TOTAL TBGS PER CFC` factor brings nearly every real line to a plausible
75-98% efficiency instead (e.g. CONSTANTA ENV: 0.32% -> 97.95%,
UNIVERSAL TWIN BAG: ~0.1% -> 93.5%).

Join key is `Item_Name` (loaders.load_item_master) against the row's Item.
227 distinct items appear across the bundled workbook's weeks; 187 match
Item_Master exactly. The other 40 have no factor (mostly a missing
case-pack prefix, e.g. planning's "AL FINA CLOVE 25 DC ENV TBGS" vs
Item_Master's "AL FINA CLOVE 24/25 DC ENV TBGS") — their CFC quantity is
excluded from Actual Production and surfaced separately as "Unconverted
Qty (CFC)" / "Items Missing Conversion Factor", flagged in the UI rather
than guessed at. A manual CSV mapping for these 40 is planned as a
follow-up (not yet wired in).

Scope: this conversion is applied only inside `capacity.py`'s Machine
Line Efficiency calculations (Steps 1-7) — `fulfillment.py`'s Booked Week
Plan / Produced numbers and `daily_breakdown()`'s raw day-by-day
Production Qty are untouched for now, per explicit user scoping
(2026-09-23) to "only in machine line efficiency overview table."

Excluded entirely for machines with no MC_MASTER capacity match (Step 1).

### Step 5 — Total Available (per Machine No)
```
Total_Available(machine) = Capacity_Per_Shift(machine) × Shifts_Worked(machine)
```

### Step 6 — Roll up to Machine Line
```
Shifts Worked (line)      = Σ Shifts_Worked(machine)        over its machines
Capacity/Shift (line)     = Σ Capacity_Per_Shift(machine)    over its machines
                             (displayed as a reference figure; not itself
                             used in the efficiency formula — see below)
Total Available (line)    = Σ Total_Available(machine)       over its machines
Actual Production (line)  = Σ Actual_Production(machine)     over its machines
```

### Step 7 — Efficiency & Waste
```
Efficiency %      = Actual Production / Total Available × 100
Wasted Capacity   = Total Available − Actual Production
Wasted Capacity % = Wasted Capacity / Total Available × 100
```
**No clipping.** If a machine over-produces relative to its worked-shift
capacity, Wasted Capacity goes negative and Efficiency % can exceed 100% —
shown as-is, not flagged or floored. (Confirmed.)

## Worked example (validation target)
VARIETIES PACK, Week 38, machine C250-06 only:
- Capacity/Shift = 250 × 480 = 120,000
- Shifts Worked = 13
- Total Available = 1,560,000
- Actual Production = 151,881
- **Efficiency = 9.74%**
- Wasted Capacity = 1,408,119 (90.26%)

## Open items not yet exercised by this example (flag if they come up)
- A machine line where "Capacity/Shift (line)" (Step 6 sum) is shown in the
  UI table — since Total Available is already computed machine-by-machine,
  this sum is a *display convenience*, not part of the math. Worth
  double-checking it doesn't mislead when machines in a line have very
  different capacities.
- Rounding/display precision for Shifts Worked when aggregated across many
  machines (e.g. CONSTANTA ENV H has 11 machine numbers).

## Step 8 — Planned vs Produced (SKU level, separate from Efficiency)

This is **not** part of the Efficiency % calculation (Steps 1-7 are
unaffected). It's a separate view answering "did we make what we committed
to make," at the SKU (Item + BOM Version + Machine Line) grain.

There are two different "planned" figures in the source data — confirmed
2026-09-19 using SUPER VALUE GOLD TEA 12/80 TAGLESS TBGS as the test case:

| Source sheet | Column | Meaning | SUPER VALUE example |
|---|---|---|---|
| `Report For plan` | **Booked Week Plan** | total committed order qty for the week | **1,071** |
| `Report For plan` | Booked in Day Plan | portion of the above actually scheduled into day/shift slots | 527 |
| `weekly production` | Planned Qty (summed) | same as "Booked in Day Plan" — cross-checks exactly | 527 |
| both sheets | Produced | actual output | 626 (cross-checks exactly) |

**Confirmed: use Booked Week Plan (from `Report For plan`) as "Planned" for
this view**, not the day-scheduled figure. Rationale: 527 vs 626 makes
SUPER VALUE look like 105% over-delivery, but it actually only fulfilled
58.5% of what was really booked for the week (1,071) — the unscheduled
backlog (544 units) would otherwise disappear from the picture entirely.

```
Planned (SKU, week)  = Booked Week Plan          (from `Report For plan`, per row)
Produced (SKU, week) = SUM of Production Qty      (from `weekly production`, matched
                                                    by Item Name + Machine Line + BOM
                                                    Version — or cross-checked directly
                                                    against `Report For plan`'s own
                                                    "Produced" column, which matches)
Fulfillment %         = Produced / Planned × 100
```

Matching rows between the two sheets: `Report For plan` is one row per
(M4 Name/Item, Machine Line, BOM Version) — same grain as summing
`weekly production` rows by (Item Name, Machine Line, BOM Version). Where
`Report For plan`'s own "Produced" column already gives this sum directly,
prefer it over re-deriving from `weekly production` (fewer places to
introduce a mismatch).

**Correction, 2026-09-21 — the two sheets do NOT always reconcile, and this
is not just a data-quality edge case:** GOLD BOND 12/100 DC ENV TBGS WITH
SHOPPING BAG genuinely runs on **more than one machine line** (confirmed by
the user, who has floor knowledge this document doesn't). For this SKU,
week 38:

| Source | Machine Line (as labeled) | Produced |
|---|---|---|
| `weekly production` | C250 AF (machine C250-04) | 53 |
| `Report For plan` | CONSTANTA ENV BT | 317 |

`weekly production` has no CONSTANTA ENV BT row for this item at all, so the
317 isn't explained by summing what `weekly production` recorded anywhere
for this SKU. Conclusion: **`Report For plan`'s "Machine Line" column is a
single planning/default label per SKU row — it is not a reliable record of
which physical machine(s) actually produced it.** `weekly production` is the
authoritative source for actual per-shift, per-machine attribution (Steps
1-7 are unaffected by this, since they never read `Report For plan`'s
Machine Line column at all).

Earlier reconciliation checks (SUPER VALUE GOLD TEA: 626 both places;
VARIETIES PACK line total: 151,881 both places) still hold as stated — but
they are per-SKU confirmations, not a general guarantee. Treat any
`Report For plan` vs `weekly production` mismatch as expected/possible, not
automatically an error to chase down.

## Step 9 — Status: reconciling Efficiency % with Fulfillment %

Confirmed 2026-09-19. These are two independent metrics answering different
questions, and neither alone is trustworthy:

- **Efficiency %** (Steps 1-7) — how much of the machine's *actual worked
  shift time* got used. Can be near-zero even when the line delivered
  everything that was ordered, if the plan itself was small that week (see
  UNIVERSAL TWIN BAG: 0.097% efficiency, but see below).
- **Fulfillment %** = `Produced / Booked Week Plan × 100` (line-level, summed
  from `Report For plan` — same source as Step 8, no join to
  `weekly production` needed) — how much of the *committed order* got made.
  Can be 100%+ even when the machine barely ran, or well under 100% even
  when the machine ran flat-out every shift it worked.

**Thresholds (confirmed):**
```
Fulfillment PASS  = Fulfillment % >= 100%
Efficiency  PASS  = Efficiency %  > 50%          (reuses the existing
                                                   Green color band, not a
                                                   separate number)
```

**Status quadrant (per machine line, per week):**
```
Efficiency PASS  AND Fulfillment PASS  -> "On Track"
Efficiency FAIL  AND Fulfillment PASS  -> "Under-scheduled"     (not a floor
                                           problem — not enough was booked
                                           that week; low efficiency is
                                           explained, not a red flag)
Efficiency PASS  AND Fulfillment FAIL  -> "Falling short despite full shifts"
                                           (real floor problem — worked hard,
                                           still missed the plan)
Efficiency FAIL  AND Fulfillment FAIL  -> "Underperforming"     (real floor
                                           problem — under-utilized AND
                                           under-delivered)
```

The point: Efficiency % should never be read alone as a performance verdict.
Status is the verdict; Efficiency % and Fulfillment % are its two inputs,
shown side by side so the reason for a low Efficiency % is never hidden.

**Important caveat, 2026-09-21:** because `Report For plan`'s Machine Line
is a planning label rather than a guaranteed physical assignment (see the
GOLD BOND correction under Step 8), **Fulfillment % per line should be read
as "did the SKUs booked under this line's label get made" — not "did this
specific machine line make what it was asked to make."** When a SKU
legitimately runs across multiple physical lines, its Produced total in
`Report For plan` may reflect output that didn't happen on the line the row
names. Status inherits this same caveat: a line's Status is only as
trustworthy as `Report For plan`'s labeling for the SKUs booked to it.
Efficiency % does not carry this caveat — it is built entirely from
`weekly production`'s own per-machine rows and is unaffected.

**Resolved:** do NOT cross-match rows between `Report For plan` and
`weekly production` by (Item Name, BOM, Machine Line). Confirmed with a real
example (VARIETIES PACK, BOM V8.0) that apparently-blank item names don't
line up 1:1 between the two sheets — e.g. two different blank-named
`Report For plan` rows share the same (Machine Line, BOM), while
`weekly production` has only one blank-named row there. Row-level 1:1
matching by name is unreliable across sheets regardless of the correction
below, since each sheet's own row/merge structure is independent.

**Correction, 2026-09-22 — root cause of the "blank" item names.** Originally
described (wrongly) as "the sheet's own convention of blanking a name after
its first appearance." The real cause, confirmed via openpyxl: `Report For
plan`'s Item column uses **merged Excel cells** — 51 merge ranges in that
column alone, e.g. `A93:A100` anchored at "CHAYA 12/100 DC ENV TBGS" and
merged across 8 rows. A plain read (pandas or a naive openpyxl value read)
only returns the anchor cell's value; every other row in the merge comes
back as None/NaN — not because the name is actually missing, but because
merge *metadata* has to be read separately from cell *values*, and neither
pandas nor a bare openpyxl read does that automatically. `weekly production`
has the same pattern in its own Item column (128 merges) — not fixed there
since no calculation in `capacity.py` reads Item Name today, but worth
revisiting if that changes.

**Fixed:** `loaders.load_report_for_plan()` now calls
`loaders.forward_fill_merged_column()` on the Item column before slicing
into rows, restoring the shared name onto every row each merge spans. The
"do NOT cross-match" conclusion above is unaffected by this fix — it was
never really about blank names in the first place, it's about the two
sheets' row/batch structures being independent of each other.

Instead: build this view **entirely from `Report For plan`**, using its own
Booked Week Plan and Produced columns side by side, per row as given. Do
not join to `weekly production` for this view. Confirmed the two sheets'
Produced totals reconcile exactly (SUPER VALUE GOLD TEA: 626 both places;
VARIETIES PACK line total: 151,881 both places), so `Report For plan` alone
is a reliable, self-contained source for Planned vs Produced.
