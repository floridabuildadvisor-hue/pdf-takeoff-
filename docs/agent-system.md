# Agent system: roles, stages, gates and review

This is the shared rulebook for the subagents in `.claude/agents/`. Every agent reads it
before it works. The project knowledge is in
[`SKILL.md`](../.claude/skills/pdf-drawing-intelligence/SKILL.md), and the takeoff method is
in [`TAKEOFF_METHOD.md`](../TAKEOFF_METHOD.md).

## 1. What this is

A management layer (`project-orchestrator`) and a set of specialists for takeoff and
estimating work. The orchestrator understands the request, picks the specialists, sequences
them, checks their results against the quality gates, and gives the owner one clear decision
before anything is changed or published.

**Status.** The agents are a way of working. They add no code capability.
- What the code can do is in SKILL.md: the status notes at the top, then section 8. Today it
  inventories PDF pages, keeps dimension strings as printed, rejoins stacked fractions, has
  math and framing helpers, exports a BOQ CSV and flags a dimension register. Reading
  quantities out of a PDF is PLANNED in code.
- So a quantity that an agent reads from a drawing is `native_text`, `ocr_text` or
  `image_interpretation`. It is unverified until the estimator checks it.
- The agent files are checked by `tests/test_agent_definitions.py`. Those tests read the
  files and run no agent.
- On 2026-11-17 each of the ten project agents was run once on a synthetic 7-sheet plan set
  with known answers and planted traps. All ten passed; the results are in
  `docs/pdf-drawing-intelligence.md` section 3. They ran as general agents that read their
  files, so the `tools:` limits were followed by instruction, not enforced by the app.
- The evidence package (section 9) was run in a second trial on 2026-11-17, with all ten
  agents in sequence. Every result could be checked from the files alone, and the QA
  reviewer and the orchestrator each caught 3 of 3 planted defects. The results are in
  `docs/pdf-drawing-intelligence.md` section 3.
- The special cases, the rule on where files go, and the second Level 2 pass were added
  after that trial.
- During the PR #11 review, agents ran again on synthetic sets. They ran as general agents
  reading the versions of their files at that time, not the files as committed here, so
  the `tools:` limits were not enforced by the app:
  - on 2026-11-22, trial stages (intake, plan, structural register, takeoff, Level 2 and
    Level 3) and two live runs, the quantity takeoff agent and the orchestrator;
  - on 2026-11-23, from 04:24 to 04:52 UTC, a four-stage benchmark (inventory, plan review,
    takeoff, BOQ draft). A separate auditor, the only one given the answer key, scored it
    39 PASS and 6 NOT ATTEMPTED out of 45 checks.

  The review report, the score file and the exact agent files used are not archived in this
  repo, and the score has not been re-checked independently. No run with the agent files as
  committed here is recorded: NOT VERIFIED.
- `evidence_package.py` checks a package and `takeoff_records.py` carries takeoff rows to
  the BOQ export (section 9). Both are tested on synthetic files only.
- The agents have not been run on a real plan set: NOT VERIFIED.

**The owner's own takeoff pipeline.** Client projects may run through the owner's private
`takeoff` skill and its pipeline. Where a session has that skill, its step table, state files
and measurement rules win over this file. These agents add roles, gates and review levels on
top of it. They never replace it and never skip its human review step.

## 2. Organization

| Agent | Role | Stage | Writes files? |
|---|---|---|---|
| `project-orchestrator` | Intake, plan, assignments, sequence, dependencies, deadlines, gates, one decision | All | No |
| `pdf-drawing-specialist` | PDF and document specialist: extraction, sheet index, OCR flags, scale and unit detection | 1 | Yes |
| `architectural-plan-reviewer` | Floor plans, elevations, sections, doors, windows, finishes | 2 | Project files only |
| `structural-plan-reviewer` | Foundations, concrete, rebar, steel, framing | 2 | Project files only |
| `mep-civil-reviewer` | Mechanical, electrical, plumbing and civil scope | 2 | Project files only |
| `quantity-takeoff-agent` | Linear, area, volume, count and assembly quantities | 3 | Project files only |
| `cost-estimator` | Material, labor, equipment, subcontractor and pricing | 4 | Project files only |
| `senior-estimator-reviewer` | Independent quantity and cost review (Level 2) | 5 | No |
| `qa-compliance-reviewer` | Completeness, consistency, formulas, traceability (Level 3) | 5 | No |
| `report-proposal-specialist` | BOQ, estimate, exclusions, assumptions and the final PDF | 5 | Project files only |
| `architect-reviewer` | Software architecture of this repo's code | Code changes | No |
| `qa-test-runner` | Tests first, the real suite, actual counts | Code changes | Tests |
| `takeoff-domain-reviewer` | Business boundaries and wording, on code, docs and client text | Both | No |

"Project files" are in the project folder the orchestrator names. That folder is outside this
repo, because the repo is public.

## 3. The five stages

| # | Stage | Who | Done when |
|---|---|---|---|
| 1 | Document intake and project coordination | `project-orchestrator`, `pdf-drawing-specialist` | Files inventoried. Sheet index built. Requested scope recorded as asked. Scale status known per sheet. The owner has accepted the plan. |
| 2 | Construction drawings interpretation | The three plan reviewers | A scope register per discipline: what is drawn, where, and which sheet, detail or schedule governs. Conflicts and gaps are listed. |
| 3 | Quantity takeoff | `quantity-takeoff-agent` | Every item in scope has a measurement record (section 9). Level 1 review is recorded. |
| 4 | Cost estimating | `cost-estimator` | Only if the owner asked for pricing. Every priced line has a source and date, or is marked `PRICE REQUIRED`. |
| 5 | Review, QA and report | `senior-estimator-reviewer`, `qa-compliance-reviewer`, `takeoff-domain-reviewer`, `report-proposal-specialist` | Levels 2 and 3 are done. The package is built as a DRAFT. The owner has one decision to make. |

A stage starts only when the stage before it is done. Stage 4 is skipped when no pricing was
requested. When it runs, Level 2 reviews the estimate too, before final QA (section 7).

A **code change** to this repo follows a shorter path: plan, failing test (`qa-test-runner`),
change, tests again, then `architect-reviewer` and `takeoff-domain-reviewer`.

## 4. Planning block

Every specialist states this before it works, and the orchestrator rejects a plan that
misses a field:

1. **Scope.** What it will do, and what it will not do.
2. **Assumptions.** Each one written down. None silent.
3. **Risks.** What could make the result wrong: an unverified scale, a missing sheet, an
   older revision, a low-text page, a schedule that disagrees with the plan.
4. **Files affected.** The repo files it will change, or the sheets it will read and the
   project files it will write.
5. **Acceptance criteria.** Checks that someone can run or look up. They come from two
   places:
   - **the code as it is today:** read it and run it, and use the status labels;
   - **the project rules:** `TAKEOFF_METHOD.md`, SKILL.md section 2, and the owner's
     measurement rules.

**Licensing boundary.** The owner is an estimator, not an engineer, and Florida engineering
licensing rules apply. Acceptance criteria never include a building-code or engineering
verdict. An item that needs design judgment becomes a question for the client's licensed
professional.

## 5. Delegation: who is needed, what it receives, what it returns

| Specialist | Needed when | Receives | Must return |
|---|---|---|---|
| `pdf-drawing-specialist` | A new or revised plan set arrives. A page will not read. A scale or unit is unclear. Code that reads PDFs changes. | PDF paths, the requested scope, the project folder | File inventory. Sheet index (page, sheet number, title, discipline, revision, size, rotation, text status). Scale per sheet and viewport as printed, with how it was verified, or `unknown`. Units. Pages that need OCR or visual review. What it could not read. |
| `architectural-plan-reviewer` | Scope touches floor plans, elevations, sections, doors, windows or finishes | Sheet index, the architectural sheets, the requested scope | Scope register. Door, window and finish schedule cross-checks. Heights for wall-area checks. Conflicts, gaps, questions, items seen but not in scope. |
| `structural-plan-reviewer` | Scope touches foundations, concrete, rebar, steel or framing | Sheet index, the structural sheets, the requested scope | Scope register by element type. Schedules used. Plan, section and schedule cross-checks. Conflicts, gaps, and questions for the client's licensed professional. |
| `mep-civil-reviewer` | Scope touches mechanical, electrical, plumbing or civil sheets | Sheet index, those sheets, the requested scope | Scope register by system. Equipment and fixture schedule cross-checks. Which drawings are diagrams and not to scale. Conflicts, gaps, questions. |
| `quantity-takeoff-agent` | A scope register exists and the scales it needs are verified | Scope register, sheets, verified scales, measurement rules | Measurement records. Totals by item. The Level 1 result. The low-confidence list and how each was recounted. |
| `cost-estimator` | The owner asked for pricing and supplied or approved the price sources | Reviewed quantities, price sources with dates | Priced lines by material, labor, equipment and subcontractor. Source and date for each. The `PRICE REQUIRED` list. Waste factors on their own lines. |
| `senior-estimator-reviewer` | After Level 1, before final QA | The records and the sheets, not the producer's reasoning | Independent recount of high-risk and sampled items. A variance table. Conflicts and omissions. Per item: agrees, differs or cannot check. |
| `qa-compliance-reviewer` | The whole package is assembled | The package and every record behind it | A result for each item in section 8. Blocking failures and warnings. A recommendation. |
| `report-proposal-specialist` | Final QA has no blocking failure | Reviewed records, assumptions, exclusions, questions | DRAFT BOQ, estimate, assumptions and exclusions, and the final PDF draft. A list of every wording change. |
| `architect-reviewer` | A code change is planned or finished | The plan and the diff | `OK to proceed` or `Changes needed`, with findings |
| `qa-test-runner` | Before and after any code change | The required behavior | The failing test, then the real counts |
| `takeoff-domain-reviewer` | Before any user-facing text is committed or shown to a client | The files or outputs | `Ready for estimator review` or `Changes needed`, with findings |

Every brief names the goal, the scope, the input paths, the return format above, and what
the specialist must not do. Every return also carries its evidence package (section 9). A
return without one is sent back.

## 6. Quality gates

A gate that fails stops the work. The orchestrator reports which gate failed and why.

| Gate | Takeoff or estimate | Code change |
|---|---|---|
| **1. Implementation** | The plan has all five fields and the owner accepted it. Work stays inside its scope. Scale is verified per sheet and viewport before anything is measured. Every quantity has a measurement record. | The plan has all five fields and the owner accepted it. The change is the smallest that works. Modules stay separate. No new dependency without a stated reason. |
| **2. Testing** | The orchestrator checks each evidence package itself: `python3 -B evidence_package.py <project folder>` reports no findings, `shasum -a 256 -c 02_Working/<agent>/SHA256SUMS` prints `OK` for every file, and the recompute command in `commands.txt` gives the recorded numbers. Every formula recomputes to its quantity. Each low-confidence item is recounted by a second, independent path. Totals are checked against written dimensions where they exist. | A failing test came first. The full suite was run and the real counts are reported. No test was deleted, skipped or weakened. |
| **3. Review** | Levels 1, 2 and 3 are done (section 7). Every finding is closed, or listed as open for the owner. | `architect-reviewer` and `takeoff-domain-reviewer` have reported. Every finding is closed, or listed as open for the owner. |
| **4. Release** | The orchestrator gave the decision report (section 11) and the owner said yes in chat. Until then the package stays DRAFT, and nothing is sent, delivered or marked as reviewed. | The owner saw the diff and said yes in chat. Until then there is no commit, push, pull request or merge. |

After the owner approves, the documentation is updated in the same change (section 10).

## 7. Three-level review

1. **Production review (Level 1).** The agent that produced the work checks its own
   measurement records, drawing references, scales, units and classifications, and records
   the result.
2. **Independent technical review (Level 2).** `senior-estimator-reviewer` recounts from the
   sheets before it reads the producer's formula. It checks high-risk quantities, a sample
   of the rest, the calculations, drawing conflicts and omissions. It reviews the
   quantities before pricing. When pricing was requested, Level 2 runs again on the
   estimate after stage 4, before final QA.
3. **Final QA and authorization (Level 3).** `qa-compliance-reviewer` checks the whole
   package against section 8. The orchestrator then gives one decision report. **The owner
   authorizes. No agent does.**

**High-risk items** are always reviewed at Level 2:
- low-confidence items, and items read from a scan, OCR or an image;
- items on a sheet whose scale was not verified;
- items with deductions, and assemblies;
- items measured across more than one sheet;
- the largest quantities and the largest cost lines;
- categories the owner has marked as fragile, such as secondary steel, the building
  envelope and areas.

The sample size for the rest comes from the owner. If none was given, the reviewer states
the size it used and why.

## 8. Reviewer checklist

Each item gets `pass`, `fail` or `not checked`, with the sheet and the evidence.

| # | Check | What to confirm |
|---|---|---|
| 1 | **Drawing scale** | The scale is verified on every sheet and every viewport, against a written dimension. Details marked not to scale are not measured. Markups, custom columns and legends agree with the drawing. |
| 2 | **Sheet reference** | Each item cites the right sheet number and revision. Revisions were compared, by overlay where possible, and the takeoff uses the current set. Changes between revisions are flagged. |
| 3 | **Measurements** | Length, width, area, perimeter and volume are right. 2D linear, area and count takeoffs match the drawing. 3D checks: wall areas use a height read from a section or elevation, never an assumed one. |
| 4 | **Units** | SF, LF, CY, CF, EA, TON and the rest are right for the item and consistent across the package. Every conversion is shown. |
| 5 | **Duplicates** | Nothing is measured twice across sheets, enlarged plans, details or disciplines. |
| 6 | **Missing scope** | No room, element, floor or trade in the requested scope is missing, checked against the sheet index and the scope registers. |
| 7 | **Openings** | Doors, windows and voids are deducted where the method says so, and each deduction is recorded. |
| 8 | **Assemblies** | Each assembly has the composition and material layers shown on the drawings. |
| 9 | **Waste** | A waste factor appears only when the owner supplied or approved it. It is documented with its source and kept separate from the net quantity. |
| 10 | **Pricing** | Every price has a current, applicable source, with its date and unit basis. Nothing is invented. A line without a source is `PRICE REQUIRED`. |
| 11 | **Assumptions** | Unclear or missing information is disclosed as an assumption, an exclusion or a question. |

## 9. Records and evidence

**Measurement record.** Every quantity carries:
- an item reference, a description, and its trade or classification;
- the source file, page, sheet number and revision, and the detail or viewport;
- the scale used and how it was verified;
- the measurement type: linear, area, volume, count or assembly;
- the dimensions as printed, with where each one is on the sheet;
- the formula, which must recompute to the quantity;
- the unit and any unit conversion;
- deductions for openings and voids, each listed;
- the net quantity as drawn;
- the extraction method: `native_text`, `ocr_text`, `vector_geometry`,
  `image_interpretation` or `human_verified`;
- a confidence level (`high`, `medium`, `low`) and the verification status;
- assumptions, and the agent that produced it.

**No source, no number.** A quantity without a traceable source is listed as `NO SOURCE`
(the owner's pipeline writes `SEM FONTE`) and raised as a question. It never gets a value.

**Units.** US customary only: LF, SF, SY, CF, CY, EA, LS, LB, TON, GAL, SQ, BF, MBF. Where
the owner's pipeline lists its allowed units, that list wins. The repo code holds this list
as `takeoff_records.ALLOWED_UNITS` and refuses a `quantity` row with a number and any other
unit, or the same unit written another way (`sf`, `SQFT`). Rows of other types, such as an
`input` in feet, are not held to the list.

**Net first.** Quantities are net, as drawn. A waste factor or a price is a separate,
labeled value with its own source. No correction factor is ever used to make a total close:
a mismatch is reported.

**Evidence package.** A result counts only when someone who never saw the agent's work can
check each number from the files alone. A summary in the return is never the only copy of a
result. Every agent that writes files leaves these in its own folder, `02_Working/<agent>/`,
where `<agent>` is the agent's name, such as `02_Working/quantity-takeoff-agent/`:

| File | What it holds |
|---|---|
| The records: `records.csv`, or `register.csv` for a sheet index or scope register | One row per item, with the fields below. |
| `commands.txt` | Every command run, exactly as typed, with its folder, its exit code and the files it wrote. One of them recomputes every calculated value from the records. |
| `SHA256SUMS` | The sha256 of every file the agent read or wrote, except itself, with paths relative to the project folder. Run in the project folder, `shasum -a 256 -c 02_Working/<agent>/SHA256SUMS` prints `OK` for each file. That output goes in the return, never in a file: a file written after `SHA256SUMS` cannot be listed in it. |
| `CHECK.md` | Three to five spot checks a person can do in a few minutes. Each gives the record ID, where to look, and the value to expect. |

Every record row has:
- `id`: the agent's prefix (table below) and a number, such as `QTO-007`. An ID never
  changes and is never reused.
- `based_on`: the IDs the row comes from. A price line names its takeoff record. A takeoff
  record names its scope-register row. A finding names the record it checks. Only rows that
  come straight from the received files have none.
- `file`, `page`, `sheet` and `revision`: where the value comes from. For a price, that is
  the quote or price sheet.
- `as_printed`: the string exactly as printed, before any conversion.
- `bbox`: where that string is, as `x0,y0,x1,y1` in PDF points. The origin is the bottom
  left of the page before `/Rotate` is applied, which is how pypdfium2 `get_charbox`
  reports text. On a page with no text layer, give the path of a crop image instead. If
  neither exists, write `none` and the reason.
- `method`: the extraction method listed above.
- `status`: `checked against source`, or `not checked: <reason>`.

**Takeoff rows.** A `QTO-` records file also has these columns, because the repo code reads
them:
- `record_type`: one of `input` (a printed value used in a formula), `calc` (a step),
  `deduction`, `scale` (a scale check), `comparison`, `alternative` (a value shown beside
  another and not chosen) and `quantity` (a net quantity that goes to the BOQ). The list is
  closed: the code refuses any other text, so a row cannot be kept out of every check by a
  type that reads like `quantity` and is not. Only `quantity` rows become BOQ lines.
  Packages written before this list was closed (2026-11-23) are legacy: they may use
  `compare` (now `comparison`), `held` (now a `quantity` row with an empty `quantity`) and
  `total` (now `calc`, or `quantity` when it goes to the BOQ). They are kept as they were
  written and are not edited to fit. The check reports those rows as `bad_record_type`, and
  on a legacy package that finding is expected.
- `item` and `description`: what the row measures.
- `dimension`: the name of the dimension or count the row reads, such as `CF-1 width`. Use
  the same name every time the same thing is read from another place, so two different
  values are flagged. Leave it empty on rows that read nothing.
- `formula`, `quantity` and `unit`. A `quantity` row with no agreed number leaves
  `quantity` empty and says why in `status`. It never gets a value.
- `assumptions`.

`python3 -B takeoff_records.py <records.csv> <boq.csv>`, run from the repo root, writes the
`quantity` rows as BOQ lines with `export_boq`. It prints `NOT EXPORTED` for each one with
no number, and `FLAG` for each dimension that `validate_register` flags. The record ID is
the BOQ item code.

A `quantity` row is exported only with a plain number (digits, with an optional decimal
part), a unit from the list above, a formula, a sheet and a `QTO-<number>` ID used once.
`0` is a number. `nan`, `inf`, `1e3`, `1,000`, a sign and words are not. An empty
`quantity` holds the row open. Any other defect prints `REJECTED <id>` and no BOQ is
written: one defective row stops the whole export. So does a `record_type` outside the
list, a cell made only of characters that print nothing, and a formula, sheet, revision or
item that starts with `=`, `+`, `-` or `@`, which a spreadsheet would run. So does a
records file that is not UTF-8, has an unclosed quote, names a column twice, has a row of
the wrong length or lacks a needed column. When no BOQ is written, a `<boq.csv>` from an
earlier run is renamed `<boq.csv>.SUPERSEDED`, or `<boq.csv>.SUPERSEDED.2` and so on when
that name is in use: a copy set aside before is never written over, and the status names
the copy. The command refuses to start (exit code 2)
when the BOQ, status or superseded path is a link or a folder, or is the records file.

Every BOQ line carries two columns after the seven of `TAKEOFF_METHOD.md`:
- `source_revision`: the `revision` of the quantity record. A row with a number and no
  revision, or one made only of characters that print nothing, is defective: the command
  prints `REJECTED <id>: no revision` and writes no BOQ.
- `boq_status`: `DRAFT: all <n> quantity rows, not reviewed`, or
  `PARTIAL DRAFT: <n> of <m> quantity rows, not reviewed`. It is on every line, so a line
  copied out of the file still says it is from a partial draft.

The command also writes `<boq.csv>.STATUS.txt`. Its first word is `DRAFT`, `PARTIAL DRAFT`
or `NOT WRITTEN`. No BOQ from this command is a reviewed one.

**The package check.** `python3 -B evidence_package.py <project folder>`, run from the repo
root, checks every package in `02_Working/`: the hashes, the columns, the IDs, every
`based_on` link, and every `as_printed` string read back at its `bbox`. It only reads. An
agent that writes files runs it before it returns and puts the output in its reply. It does
not recompute formulas and it does not check that a quantity is right.

It also checks, as file integrity:
- every file in `01_Received/` is listed in the `pdf-drawing-specialist` `SHA256SUMS`, so a
  drawing left out, or added after the inventory, is reported;
- every path in a `SHA256SUMS`, a `file` column or a crop `bbox`, and the BOQ file, stays
  inside the project folder, links followed. A path that leaves it is reported and not
  read. A path is written one way only: names joined by `/`, spelled as the folder lists
  them, with no `..`, `.`, backslash or `~`;
- `page` is a page number in plain digits, an ID number is plain digits, and two IDs that
  are the same number written two ways (`QTO-7`, `QTO-007`) are reported;
- a crop image is a PNG or JPEG file, and a `drawn` row cites a page that opens;
- every record's `file` is in its own package's `SHA256SUMS`.

And, as the chain from drawing to BOQ:

| Link | Rule |
|---|---|
| `based_on` leads to a record | Always. |
| No circle of `based_on` links | Always. |
| A record is based on its own stage or an earlier one (`DOC-`, then `ARC-` `STR-` `MEP-`, then `QTO-`, `EST-`, `RPT-`) | Always. |
| A `QTO-` `input` row is not based on a `calc` or `quantity` row | Always. |
| A `quantity` row with a number has a unit, a formula and a sheet | Always. |
| Behind a `quantity` row with a number, some record gives a place on a drawing: `x0,y0,x1,y1` or a crop image | Always. A `line <n>` in a text file does not count. |
| Behind it, some record is a scope-register row | Only when the project has a scope register. |
| A `quantity` row with no number | Not checked for evidence. It is held open. |
| A `quantity` row with a number has a `revision` and a unit from the list | Always. |
| Two records never give different revisions for the same page of the same file. The `pdf-drawing-specialist` rows are the reference | Always, for rows that give a page and a revision. |
| Each line of `02_Working/report-proposal-specialist/boq.csv` has the ID, quantity, unit, formula, sheet and revision of one `quantity` record whose ID no other record uses, and each `quantity` record with a number has a line | Only when that file exists. |
| `boq_status` on every line is the exact text for the real counts: `PARTIAL DRAFT: <n> of <m> quantity rows, not reviewed` while any `quantity` row is held open, and `DRAFT: all <m> quantity rows, not reviewed` otherwise | Only when that file exists. An empty BOQ file is checked too. |

The revision rule compares records with each other. Whether a sheet is the current
revision of the set is still a question for the plan reviewer and the owner.

Linked IDs show that a path exists. They do not show that the right thing was measured.
A crop image is checked for existence only: the output counts each one as not compared.

**What a hash shows, and what it does not.** A hash shows that a file still matches a
recorded digest. It does not show that the file was the right one when the digest was
taken, or that the digest itself was not rewritten. Every file an agent can write is inside
the project, so nothing inside the project can be the last word. The last word is a copy
the agents cannot reach: the owner's.

The check also cannot show that the received files are the whole drawing set. A sheet or a
file that was never sent leaves no trace in a hash. Whether the set is complete is a
question for the sheet index, the plan reviewer and the owner.

**A file with a second name.** A path inside the project does not show that the file is
only in the project. A file can have a second name elsewhere on the same disk (a hard
link), and a change made through that name changes the project's file without touching the
project folder. The check follows no link out of the project, but it does not detect a
second name. It reports the change as `hash_mismatch` or `seal_mismatch` only the next time
it runs, and nothing covers the time between a check and the use of the file. So:
- received files are copied into `01_Received/`, never linked;
- the project is kept on a disk only the owner's own tools write to;
- the check is run with the saved seals immediately before any release.

The BOQ command does refuse to write over a file that has a second name, and it refuses a
BOQ path that is the records file under another spelling.

**Seals.** The check prints `SEAL <sha256>  <path>` for every file in `01_Received/` and for
every package's `SHA256SUMS`. The procedure:

1. **At intake.** `pdf-drawing-specialist` runs the check and quotes the `SEAL` lines in its
   reply. The orchestrator puts them in the `Seals` line of its decision report. The owner
   must compare the received-file seals with the files she sent (`shasum -a 256 <file>` on
   her own copy) and keep the report. This is the only step that ties the project to the
   real drawings, and only the owner can do it. Until it is done, no seal says anything
   about the real drawings.
2. **After each stage.** Every agent that writes files quotes the `SEAL` lines of its last
   run. The orchestrator runs the check itself and reports the full list again.
3. **At the start of the next stage, and before any release.** The owner, or the brief,
   gives the orchestrator the `SEAL` lines of the last decision report. The orchestrator
   runs `python3 -B evidence_package.py <project folder> --seals -` with those lines on
   standard input, which writes no file.
   - `seal_mismatch` on a received file: the drawings changed. Stop.
   - `seal_mismatch` on a package whose stage was not reopened: stop and report it.
   - `seal_missing` for a new package: expected for the stage just run. It gets its seal
     in this report.
   - `seal_conflict`: the lines given have two different seals for one path. Stop, and use
     only the lines of the owner's kept report. The check never picks one for her.
4. **A reopened stage** gets a new seal only in a decision report that says which stage was
   reopened and why.

Seals are not kept in a file in the project as the only copy: an agent could rewrite it.

**Reproducing a calculation.** Each package keeps the script of its recompute command and
that command's full output, as `recompute_output.txt`, both listed in `SHA256SUMS`. With
the received files, the records and that script, anyone can rerun the calculation and
compare. The package check does not yet rerun it or compare the output.

**Special cases.** Each has one form, so a script can check every row:
- **Several pages.** One row cites one page. A value read from several pages gets one row
  per page, plus a row that combines them.
- **A row that only combines or compares other rows,** such as a cross-check, a finding or
  a total: `as_printed` and `bbox` say `see based_on`. Every records file still has every
  column.
- **A drawn line or shape with no text:** `as_printed` is `drawn`, and `bbox` is the
  object's bounds as pypdfium2 `get_bounds` reports them. Those use the same coordinates as
  text.
- **A value from a text file,** such as a quote, a price sheet or an email: `page` is empty,
  `bbox` is `line <n>`, and `as_printed` is the text on that line.

**Where files go.** An agent that writes files writes only in its own folder in
`02_Working/`. Test copies, break tests and other scratch work go in a `scratch/` folder
inside it, and are listed in `SHA256SUMS` like any other file. A read-only agent writes no
file anywhere, not even a temporary one. It runs a script with `python3 -c` or a heredoc
instead of saving it.

| Agent | ID prefix |
|---|---|
| `pdf-drawing-specialist` | `DOC-` |
| `architectural-plan-reviewer` | `ARC-` |
| `structural-plan-reviewer` | `STR-` |
| `mep-civil-reviewer` | `MEP-` |
| `quantity-takeoff-agent` | `QTO-` |
| `cost-estimator` | `EST-` |
| `senior-estimator-reviewer` | `L2-` |
| `qa-compliance-reviewer` | `L3-` |
| `report-proposal-specialist` | `RPT-` |

**Read-only agents** cannot write files. They return the same fields as a table, plus
`expected`, `found`, and the command or formula that shows the difference. The orchestrator
has each of those returns saved, unedited, in `02_Working/review/`.

## 10. Project memory

- **Verify before you rely.** Read the code and run it. The code wins over any document. If
  they disagree, report it as a finding. Other conflicts follow "When sources disagree"
  below.
- **Update the documentation when a change is approved**, in the same change:
  - the SKILL.md status tables and baseline;
  - `docs/pdf-drawing-intelligence.md` and this file;
  - `README.md` and `.github/copilot-instructions.md`;
  - the report's `limitations` list in `pdf_intelligence.py`.

  `TAKEOFF_METHOD.md` is the owner's document. Change it only at the owner's request.
- **On a project,** keep the sheet index (`drawings.md`), the assumptions, exclusions and
  questions log, and the project status current.
- **Read-only agents** list the documentation updates that are needed. The orchestrator
  assigns them to an agent that can write.
- **Never record client names, files or data in this repo.**

### When sources disagree

This is the only full statement of this rule. Other files link here.

**Instructions and policy** (what an agent must do):
1. **Authority.** Each kind of question has one governing source:
   - what the code does: the code and its tests on `main`;
   - the takeoff method: `TAKEOFF_METHOD.md`;
   - agent roles, gates, reviews and evidence: this file;
   - one agent's duties: its agent file, within this file;
   - SKILL.md and `docs/pdf-drawing-intelligence.md` describe the code and never override
     it.
2. **Merged text first.** Within one authority, text merged to `main` outranks text on a
   branch, in an open pull request, in a working tree, or in a design marked PROPOSED. A
   newer draft never overrides older merged text.
3. **Recency,** only between sources of the same authority that are both merged, or both
   not: the more recently checked text wins.
4. **Supersession.** A text replaces another only where it says so, naming what it
   replaces (file, section, date). Nothing is superseded by implication, and a
   supersession reaches no further than its stated scope.
5. **Escalation.** If a conflict still stands, do not choose. Report both sources as a
   finding, with file and line, and ask the owner. Record the owner's decision in the
   decision report (section 11) and in the documentation update.

Two things outrank all of this: the owner's explicit instruction in chat for the current
request, and, on a client project, the owner's `takeoff` skill (section 1).

**Facts that belong to one version** (test counts, test results, review results, release
status):
- Each one names the exact revision it was measured on: a commit SHA, or for uncommitted
  work the sha256 of the patch.
- A fact stays true for its own revision. Historical counts stay valid for their
  revisions.
- When the revision changes, measure again. Never carry an older count forward over a
  newer candidate's result.
- Never decide between two facts by the rules above. Compare their revisions: if they name
  different revisions, both can be true. A fact that names no revision is unverified until
  it is measured again.

## 11. Decision report

The orchestrator ends every request with this, and nothing else is changed or published
until the owner answers:

```text
Decision needed: <one sentence>
Recommendation:  Proceed | Do not proceed | Need your input
Why:             <two to four lines, each naming the record ID, file or command output it rests on>
Gates:           1 Implementation <pass|fail|not started> · 2 Testing <pass|fail|not started> · 3 Review <pass|fail|not started> · 4 Release <waiting for your yes>
Open items:      <list, or none>
Seals:           <every SEAL line from the last package check, or "no project folder">
If you say yes:  <exactly what will be changed, committed, pushed or sent>
```

A gate the work has not reached is `not started`. It is never reported as `pass`.

## 12. Rules that never bend

- **Evidence, not summaries.** A number counts only when it has a record ID and a source the
  owner can open and check (section 9).

- **Estimator, not engineer.** Never write "meets code", "complies", "structurally
  adequate", "safe", "certified" or "engineered". Use "extracted", "measured", "counted",
  "flagged for review" or "as printed on sheet X".
- **Takeoff and estimating only.** No purchasing and no supplier ordering. Supplier stock is
  never optimized as a takeoff requirement. A supplier assumption never replaces a quantity
  from the plans.
- **Never assume a scale**, and never invent a dimension, a quantity, a price or a rate.
- **Scope is only what was requested.** Other things seen are listed as "not in scope" and
  are not quantified.
- **Client data stays out of this repo.**
- **Everything is a DRAFT until the owner records the review.** No agent approves,
  authorizes, delivers, sends or invoices.
- **No commit, push, pull request or merge without the owner's yes in chat.**
