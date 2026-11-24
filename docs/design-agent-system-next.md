# Design: next agent-system changes (review fixes 5 to 9)

Status: PROPOSED. Not implemented. Not part of PR #11. Each section is its own change, with
its own `test:` commit before its `feat:` or `fix:` commit. Nothing here changes a public
signature in `vector_takeoff.py` or `pdf_intelligence.py`, and nothing adds a dependency.

Order: 1, then 2, then 6. Sections 3, 4 and 5 are independent of those and of each other.

## 1. Canonical measurement-record schema

**Problem.** `docs/agent-system.md` section 9 lists thirteen things a measurement record
carries. Only eight have a column name the code reads (`takeoff_records.TAKEOFF_COLUMNS`).
Scale, how the scale was verified, measurement type, deductions, confidence, unit conversion
and trade have no agreed name, so each run invents its own and no script can check them.

**Proposal.** Add these columns to a `QTO-` records file. All are text.

| Column | Values | Required on |
|---|---|---|
| `measurement_type` | `linear`, `area`, `volume`, `count`, `assembly` | `quantity` rows |
| `trade` | free text | `quantity` rows |
| `viewport` | the detail or viewport, such as `2/A-1`; empty for the whole sheet | rows that read a sheet |
| `scale` | as printed, such as `1/4" = 1'-0"`; `written dimension` when nothing is scaled; `unknown` | `input` rows |
| `scale_check` | the ID of the record that verified the scale; empty with `written dimension` | `input` rows whose `scale` is a ratio |
| `conversion` | such as `CF/27 = CY`; `none` | `quantity` and `calc` rows |
| `deducts` | the ID of the row this row is subtracted from; empty otherwise | deduction rows |
| `confidence` | `high`, `medium`, `low` | `quantity` rows |
| `second_count` | the ID of the independent recount | `quantity` rows with `low` |

Rules a script can check:
- `record_type` needs no change. Since PR #11 the list is closed in
  `takeoff_records.RECORD_TYPES`: `input`, `calc`, `deduction`, `scale`, `comparison`,
  `alternative`, `quantity`.
- An `input` row measured by scale (`method` is `vector_geometry`) needs a `scale_check`
  that resolves. `scale` of `unknown` on such a row is a finding. This removes the conflict
  between "stop if the scale is unknown" and "prefer written dimensions": a row read from a
  written dimension says `written dimension` and needs no scale at all.
- A `quantity` row whose `measurement_type` is `area` or `volume` and that has deduction
  rows pointing at it must name them in its formula.
- One row cites one page. A value read on several pages gets one row per page.
- `bbox` on a text row is the bounds of the whole printed string, not of one token.

**Where.** New module `measurement_record.py` with `MEASUREMENT_COLUMNS` and
`measurement_row_problems(row)`. `evidence_package.py` calls it for the takeoff package, the
way it calls `quantity_row_problems` now. Older packages are checked against the columns
they were written with: the checker reads a `schema` line in `commands.txt`
(`schema: 2026-11`), and a package without it gets the current eight columns only.

**Tests.** One per rule, on rows built in memory. One for an older package with no `schema`
line.

**Already settled in the PR #11 review.** The unit list in section 9 is enforced on
`quantity` rows with a number (`takeoff_records.ALLOWED_UNITS`), and those rows need a
`revision`.

**Open for the owner.** Whether `FT` and `IN` are allowed on `input` rows, which the list
does not cover today.

## 2. Full recompute-output capture and diff

**Problem.** Every package has "one command that recomputes every calculated value".
Nothing records what that command printed, so the orchestrator cannot `diff` a second run
against the first, and `evidence_package.py` cannot find a quantity that was changed and
re-hashed.

**Proposal.**
- The recompute command prints one line per calculated row, in ID order:
  `<id>\t<quantity>\t<unit>`. Nothing else goes to stdout.
- The agent saves that output as `recompute_output.txt` in its folder, before
  `SHA256SUMS` (the agents are already told to keep it; the line format is new).
- New module `recompute_check.py`: `recompute_rows(records)` evaluates each `formula` with
  a small evaluator (numbers, `+ - * /`, parentheses, `[ID]` references; no names, no
  calls, no `eval`) and returns `(id, computed, recorded)`. Command line:
  `python3 -B recompute_check.py <records.csv>` prints the same line format and exits 1 on
  any difference above a stated tolerance (half of the last recorded decimal place).
- `evidence_package.py` gains two findings: `recompute_missing` (no `recompute_output.txt`) and
  `recompute_differs` (a line in `recompute_output.txt` does not match the record).
- The orchestrator runs `recompute_check.py` and `diff`s its output against `recompute_output.txt`.
  `diff` and `cd` go on its allowed-command list.

This closes most of the re-forged hash gap: a quantity changed after the fact no longer
equals its formula. It does not close a change to an `input` row's `quantity` that still
disagrees with `as_printed`; that needs the printed-dimension parser (`parse_dimension` in
`pdf_intelligence.py`) applied to `as_printed`, which is a third finding,
`input_differs_from_print`, for rows whose `as_printed` is a single dimension.

**Seals.** Done in the PR #11 review: the check prints `SEAL` lines for received files and
hash lists, reads them back with `--seals`, and section 9 has the procedure. What is left
for this change is the comparison of `recompute_output.txt`, which agents are already told
to keep, with a rerun.

**Tests.** The evaluator on each operator and on a refused expression; a records file
changed after `recompute_output.txt`; a changed input with a matching output file.

## 3. Plan-first specialist workflow

**Problem.** Every specialist is told to "return the planning block before any result".
A subagent returns once, so the plan and the result arrive together and nobody can accept
or correct the plan.

**Proposal.** Two calls, recorded in files.
- Call 1: the brief ends with `MODE: plan`. The agent writes only `PLAN.md` in its folder
  (scope, assumptions, risks, sheets to read, files to write, acceptance criteria) and
  returns it. It measures nothing.
- The orchestrator shows the plans to the owner in one decision report. The owner's answer
  is saved, as typed, in `02_Working/review/plan-acceptance.md`, with the sha256 of each
  accepted `PLAN.md`.
- Call 2: the brief ends with `MODE: execute` and names the accepted plan's sha256. The
  agent checks the hash, works, and lists `PLAN.md` in `SHA256SUMS`.
- `evidence_package.py`: `plan_missing` when a package has no `PLAN.md`, `plan_not_accepted`
  when its hash is not in `plan-acceptance.md`.
- Read-only agents return the plan as text in call 1; the orchestrator saves it in
  `02_Working/review/`.

**Open for the owner.** Whether every plan needs the owner's yes, or only plans that list a risk or
an assumption. The second is faster and is the recommendation.

## 4. Failure and resume protocol

**Problem.** Nothing says what an agent does when a file cannot be read, a command fails or
it runs out of turns, or how the next run tells finished work from half-finished work.

**Proposal.**
- Each package has `STATE.md` with one line: `state: planned | in progress | complete |
  failed`, the time, and on `failed` the command and its output.
- An agent sets `in progress` before its first write and `complete` only after
  `SHA256SUMS` is written and the package check has no finding in its own folder.
- On a failure it stops, writes `failed`, leaves every file as it is, and returns the
  failure. It does not retry with a different method without saying so, and it never fills
  a gap with a value.
- Resume: a package that is not `complete` is not read by a later stage. The orchestrator
  moves it to `02_Working/<agent>/scratch/attempt-<n>/` and starts the agent again. IDs
  from the failed attempt are not reused.
- `evidence_package.py`: `package_not_complete` for a package whose state is not
  `complete`, and `based_on` links into such a package are findings.
- The orchestrator's gate value `fail` gets a reason line naming the package and state.

**Tests.** Each state; a link into a failed package.

## 5. Missing `TAKEOFF_METHOD.md` outputs

`TAKEOFF_METHOD.md` is the owner's document and is not changed. Three things it asks for
have no code today:

| Method section | Missing | Proposal |
|---|---|---|
| 3, clickable markup | Nothing ties a BOQ line to a mark on the plan. | New module `markup_page.py`: from the records, one HTML page per sheet with the page image and one box per record `bbox`, each linking to its BOQ line and showing ID, quantity, formula and sheet. Reads only; writes into the report agent's folder. Uses `pypdfium2` rendering, already a dependency. |
| 6, items per sheet in `drawings.md` | The sheet index has no "items extracted from that sheet" column filled from records. | `takeoff_records.items_by_sheet(records)` and a command that prints the column for `drawings.md`. |
| 1, reviewer initials | `reviewer_initials` is always empty and nothing checks a reviewed BOQ. | Leave empty in every generated file. Add a check that a file named as delivered has initials on every line; the checker never writes them. |

The rotation rule from the owner's takeoff standard applies to the markup page: boxes are
drawn in page coordinates before `/Rotate`, then the page transform is applied once.

## 6. Repeatable drawing-to-takeoff benchmark

**Problem.** `tests/test_agent_definitions.py` reads the agent files. It runs no agent.
Agent behavior on a drawing has only been tried by hand, on one small set.

`docs/agent-benchmark.md` is a separate and fuller benchmark design (designed, not built,
never run). This section is the earlier sketch. The two have to be reconciled before either
is built.

**Proposal.** A benchmark that anyone can rerun and that an auditor scores from files.

- `benchmarks/wall_slab_v1/make_set.py`: builds the synthetic plan set, deterministic,
  marked "SYNTHETIC TEST SET - NOT A PROJECT" on every sheet. The built PDF is not
  committed (`*.pdf` is ignored); a test checks the builder's output hash.
- `benchmarks/wall_slab_v1/request.txt` and `answer_key.md`.
- `benchmarks/README.md`: the run procedure. Agents run in order (inventory, plan review,
  takeoff, report) in a fresh project folder outside the repo, each with the agent file as
  its only instruction. A separate auditor, given only the project folder, the answer key
  and the repo, scores each numbered check `PASS`, `FAIL` or `NOT ATTEMPTED` and writes
  `score.csv`. The auditor never sees an agent's reply.
- `benchmarks/score.py`: reads `score.csv`, prints the result per measure and the total,
  and compares with the last recorded run in `benchmarks/results/<date>.csv`.

The ten measures and what the set plants for each:

| Measure | Planted |
|---|---|
| Sheet identification | A rotated sheet, a page with no text, a revision that differs from the index. |
| Detail identification | Two details marked not to scale, and an enlarged plan on the same sheet. |
| Written dimensions | Dimensions on plan, elevation, detail and schedule. |
| Scale calibration | A second viewport at another scale; a sheet whose printed scale disagrees with its own written dimension; one length with no written dimension. |
| Opening deductions | Doors and windows to deduct, and an interior door that must not be deducted. |
| Assembly interpretation | One wall type with a layer on one face, one with a layer on each face and a different height. |
| Quantity calculations | Ten quantities with exact answers. |
| Unresolved behavior | A thickness printed two ways; a question outside takeoff; an item named as out of scope. |
| BOQ export | Ten lines expected, one held open, status `PARTIAL DRAFT`. |
| Evidence traceability | The package check, the hash check, three chains followed by hand, each recompute command rerun. |

A v1 of this set, request and key was built and run once during the PR #11 review, outside
the repo, on 2026-11-23 from 04:24 to 04:52 UTC: four stages, run as general agents with
the agent files of that time, then a separate auditor who alone had the key. It scored 39
PASS and 6 NOT ATTEMPTED out of 45 checks. The score file, the review report and the agent
files used are not archived in this repo, and the score has not been re-checked
independently. It is one run on one small set: it shows the procedure works, not how
accurate the agents are on real drawings.

**What the benchmark cannot show.** Real plan sets have scans, OCR, hundreds of sheets and
inconsistent drafting. A synthetic set measures whether the rules are followed on clean
input. A claim about accuracy on real work needs a real set with a human-made key, kept
outside this public repo.

**Next sets.** A scanned-page set (image only), a multi-revision set, and a set with a
schedule that disagrees with the plan count.
