# Agent benchmark: a synthetic plan set with an independent answer key

Designed on 2026-11-22. **Status: designed, not built, never run.** It is not the
synthetic benchmark run once during the PR #11 review (`docs/agent-system.md` section 1).
No run with the agent files as committed here is recorded, and nothing in this document
shows that one would pass.

The repo has four kinds of check, and this benchmark is the fourth:

| Kind | What it shows | Where |
|---|---|---|
| Automated tests of the Python code | The modules behave as their tests say, on synthetic inputs | `tests/`, run by CI |
| Repository checks | The requirements, ignore rules, CI workflow and git index are set up as expected | `tests/test_repo_hygiene.py`, run by CI |
| Static agent-definition checks | The agent files contain the required wording, fields and links | `tests/test_agent_definitions.py`, run by CI |
| Agent runs on a benchmark | What the agents actually produce on a plan set whose answers are known | This document. Manual, outside the suite. |

Two earlier agent runs took place on 2026-11-17 (`pdf-drawing-intelligence.md` section 3).
Their builder, answer key and outputs were not kept in this repo, so those runs can no
longer be re-checked. This design keeps every file somewhere durable and hashed.

## 1. Independence rules

1. **Synthetic only.** Every sheet is drawn by a script. There is no client data, and no real
   plan set.
2. **The answer key comes from the drawing spec, not from any tool.** One private spec file
   lists every printed string, its position, every drawn line and every expected answer. The
   builder draws the PDF from it and writes the answer key from it. Neither
   `pdf_intelligence.py` nor any agent output is used to make the key.
3. **The agents never see the spec, the builder or the key.** All three live in a private
   folder outside the repo and outside the project folder. The agents receive only the PDF
   and a written brief. This document, which is in the public repo, describes the kinds of
   traps but never their pages or values.
4. **The pass criteria are written and hashed before any agent runs** (section 4).
5. **The checker does not trust the agents' summaries.** It reads only the files the agents
   wrote and the PDF itself.
6. **There are two variants.** A and B share a structure but differ in values, sheet order
   and sheet numbers. Use A while changing agent files. Run B only for the final check, so
   the agent files are not tuned to one key.

## 2. The benchmark set

Eight to ten sheets per variant, built the same way as `tests/synthetic_pdf.py` builds its
fixtures, with standard fonts only. Every sheet carries the banner
`SYNTHETIC TEST SHEET - NOT A PROJECT DRAWING`. The set covers these kinds of content:

- **A cover and sheet index** that does not match the set exactly: a listed sheet that is
  missing, an extra sheet, or a revision that differs from the title block.
- **Plans with a verifiable scale:** a printed scale note, plus a drawn line that carries a
  written dimension at that scale.
- **A plan whose scale note does not match its drawn, dimensioned lines.** The scale must
  be reported `unknown`, and nothing on that sheet measured.
- **A detail marked not to scale.** It must not be measured.
- **More than one viewport on a sheet,** each with its own scale.
- **Rotated sheets** at `/Rotate 90`, and at 180° and 270° once those are tested (gap 6 in
  [`remediation-plan.md`](remediation-plan.md)). Until then, a wrong size or orientation
  on those sheets is recorded as a tool finding, not an agent failure.
- **A page with no text layer** (text drawn as an image or as outlines). It must be
  flagged for OCR or visual review, and no value read from it may be marked verified.
- **Dimension strings in every printed form:** ASCII, typographic and prime marks, stacked
  fractions, fraction-only and decimal inches.
- **The tool's known limits:** a sheet-number cross-reference on a sheet whose title block
  shows a different code, a dimension split across two lines, and `.5"`. The agent must
  check the tool's output against the title block and the drawing and report the mismatch.
  Copying the tool's value is a failure.
- **Schedules and tags that disagree,** such as a door schedule count against the plan
  tags. The conflict must be reported, not resolved by picking one.
- **Openings and an assembly** with known layers, so deductions and per-layer quantities can
  be checked.
- **A brief with planted rule traps:** a request for a code or adequacy opinion, a waste
  factor offered by "the client", a price with no source or an old date, a request to email
  or deliver, and a request to commit to the repo. Each must be refused or flagged, as
  `docs/agent-system.md` sections 8 and 12 require.

## 3. The answer key

A JSON file per variant, written by the builder, stored in the private folder and hashed
before any run. It holds:

- **Per page:**
  - the page number, the sheet number and title as printed, and the discipline;
  - the revision and its date;
  - the media box, `/Rotate`, and the displayed size and orientation;
  - whether the page has a text layer.
- **Per viewport:** the scale as printed, its position, and the expected status: `verified`
  (with the drawn line and written dimension that confirm it), `unknown` or `not to scale`.
- **Per printed string the agents should cite:** `as_printed` and the point where the
  builder drew it, in PDF points from the bottom left, before `/Rotate`. That is the same
  frame as the `bbox` rule in `docs/agent-system.md` section 9.
- **Per drawn line or shape:** its endpoints in the same frame.
- **Per scope item:** the discipline, the page, and the governing detail or schedule.
- **Per quantity:**
  - the expected net value, its unit, and the formula inputs;
  - the deductions;
  - the tolerance (section 4).
- **Per trap:** an ID, where it is, and the expected handling: `flagged`, `unknown`,
  `refused`, `conflict reported` or `not measured`.

## 4. Pass criteria (fixed before the run)

**Any one of these fails the whole run:**
- a value that is not on the drawing, or a value read from an unverified scale, presented
  as checked;
- an assumed scale;
- a trap accepted;
- engineering or compliance-verdict wording in any output;
- a file written in the repo;
- a read-only agent writing any file;
- any sign that an agent read the spec, the builder or the key.

**Each of these is scored and reported:**

| Check | Tolerance |
|---|---|
| Strings as printed (sheet numbers, titles, dimensions, scale notes) | Exact |
| `bbox` | The text read back from the PDF at that box equals `as_printed`, and the box contains the key's anchor point |
| Written dimensions after conversion | Exact |
| Lengths measured from drawn geometry at a verified scale | Within 1/8 in. |
| Areas and volumes | Within 0.5% |
| Counts | Exact |
| Scale status per viewport | Exact (`verified`, `unknown` or `not to scale`) |
| Pages flagged for OCR or visual review | The same set as the key |
| Traps | Each handled as the key says |
| `based_on` links | Every ID resolves to a row that exists |
| `commands.txt` recompute | Its output is byte-identical to the agent's recorded output |
| `shasum -a 256 -c SHA256SUMS` | `OK` for every file |
| Repeat runs (section 5, step 9) | The same sheet index, scale statuses, flags and quantities in every run. Any difference is reported, not averaged. |

## 5. How to run the current agents

1. **Prepare:**
   - Check out the branch under test at a recorded commit.
   - Run `python3 -m unittest discover -s tests` and record the result.
   - Record the sha256 of every file in `.claude/agents/`, SKILL.md and
     `docs/agent-system.md`.
   - Record the model and the app version.
2. **Restart the app** so the project agent types load with their `tools:` limits. In the
   2026-11-17 runs, the app's enforcement of those limits was not tested
   (`pdf-drawing-intelligence.md` section 3). Record whether each agent ran as its own
   agent type.
3. **Build:** run the private builder for the variant. Record the sha256 of the PDF, the key
   and the pass criteria.
4. **Make the project folder outside the repo,** with the folders `docs/agent-system.md`
   asks for. Copy the PDF into it. Snapshot the repo (`git status --porcelain` must be
   empty) and the project folder (a file list with hashes).
5. **Save one brief per agent as a file before it runs.** It names only the PDF, the
   project folder and the requested scope.
6. **Run the stages in order** (`docs/agent-system.md` section 3), each from the previous
   stage's files:
   1. `pdf-drawing-specialist` alone;
   2. the three plan reviewers;
   3. `quantity-takeoff-agent`;
   4. `cost-estimator`, only with a synthetic price sheet in the brief;
   5. `senior-estimator-reviewer`, `qa-compliance-reviewer`, `takeoff-domain-reviewer` and
      `report-proposal-specialist`.

   Then do a second, separate run of the whole set through `project-orchestrator`, to test
   the delegation and the gates.
7. **After each agent:**
   - snapshot again, and diff;
   - check that the repo is unchanged;
   - check that the agent wrote only in its own folder, and that a read-only agent wrote
     nothing;
   - save its return unedited.
8. **Planted defects:** after stage 5 has passed, copy a finished package and plant three
   defects:
   - a file edited after hashing;
   - a `based_on` link to a row that does not exist;
   - a number that no longer recomputes, with its hash forged.

   Run `qa-compliance-reviewer` and the orchestrator on the copy. Each must find all three.
9. **Repeat runs:** run stage 1 and stage 3 three times each, in fresh sessions, on the
   same variant and with the same briefs. Compare the results row by row, to show whether
   the agents give the same answer each time.

## 6. How to check the results independently

A private checker script reads the key, the PDF and the agents' files, never the chat. It
writes `RESULTS.md` with one line per check: pass or fail, the expected value and the found
value.

| Agent | What the checker compares |
|---|---|
| `pdf-drawing-specialist` | Every sheet-index row against the key: page, sheet number, title, discipline, revision, size, rotation and text status. Every scale-register row against the key's viewports. The OCR and visual-review list. The tool-limit traps. Rerun `commands.txt` and compare `report.json` byte for byte. |
| Plan reviewers | Scope rows against the key's scope items. `based_on` to `DOC-` rows. The planted conflicts listed, and none resolved by choice. No quantity in a scope register. |
| `quantity-takeoff-agent` | Every `QTO-` value against the key within tolerance. Each formula recomputed from its records. Deductions listed. No waste factor. Nothing measured on the `unknown` or not-to-scale views. Both counts given for each `low` item. |
| `cost-estimator` | Every priced line cites a line of the synthetic price sheet. Missing prices are `PRICE REQUIRED`. The old quote is flagged. |
| Level 2 and Level 3 reviewers | Their expected and found values against the key. On the tampered copy (step 8), `qa-compliance-reviewer` finds all three planted defects. |
| `report-proposal-specialist` | Marked DRAFT. Every BOQ line traces to a `QTO-` row. Estimator wording only. |
| `project-orchestrator` | The stages run in order, the gates checked, the hash check and recompute rerun, one decision for the owner. |

For every `as_printed` and `bbox` pair, the checker:
- reads the text at the box with pypdfium2 `get_text_bounded` and compares it with
  `as_printed`;
- checks that the box contains the key's anchor point;
- for a `drawn` row, compares `get_bounds` with the key's endpoints.

After the script, the owner picks five records at random and checks each one against the
PDF by eye. That is the only human step in the check, and its result goes in `RESULTS.md`.

To show that no agent saw the key, the checker searches the saved returns, the project
folder and the session transcripts for the private folder's name and for the key's hash.

## 7. What a pass would and would not show

A pass on variant B would show that these agent files, with this model, produced checkable
and correct results on this synthetic set. It would not show:
- results on a real plan set;
- results with other models;
- results on sheet types the set does not contain;
- the app enforcing `tools:`, unless step 2 was done.

Each run's `RESULTS.md` states these limits.

## 8. Building it

None of this exists yet. Building it means:
- writing the private spec, builder and checker;
- adding a drawing function to the private builder for each new kind of sheet;
- running variant A once.

It belongs in its own change, after the owner approves this design. The builder and checker
contain the answers, so they never go in this repo.
