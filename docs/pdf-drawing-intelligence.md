# PDF Drawing Intelligence: reference

This is the supporting reference for the project skill at
[`.claude/skills/pdf-drawing-intelligence/SKILL.md`](../.claude/skills/pdf-drawing-intelligence/SKILL.md).
Each status below names the revision it was checked on. The code always wins. Where
sources disagree, follow `docs/agent-system.md` section 10, "When sources disagree".

| Section | Checked at |
|---|---|
| 1. JSON report | `acfab9f` (2026-11-22), against `pdf_intelligence.py`, which is unchanged at `dbce73b`. |
| 2. Functions | `acfab9f` (2026-11-22). The rows for `extract_sheet_number`, `extract_dimension_tokens`, `analyze_pdf`, `render_pdf_pages` and `main()` were rewritten against the code at `acfab9f`. The other rows were checked against the same code, and the `vector_takeoff.py` rows were corrected for two unchecked inputs. `pdf_intelligence.py`, `visual_inspect.py` and `vector_takeoff.py` are unchanged at `dbce73b`. It gives function contracts for `pdf_intelligence.py` and `vector_takeoff.py`, and only the CLI flags and imports for `visual_inspect.py`; the skill's section 6 lists the other modules. |
| 3. Verification log | A dated record of what was run from 2026-11-10 to 2026-11-17. The probe table and the rows on typographic quotes, corrupt and missing files, and Pillow no longer match the code, and the skill's notes supersede them. |
| 4. Test inventory | `dbce73b`, the head of PR #11 (2026-11-23). |
| 5. Test gap matrix | `acfab9f` (2026-11-22). The rows for the subagents and for the modules added or changed in PR #11 (`boq.py`, `takeoff_records.py`, `evidence_package.py`) were checked again at `dbce73b` (2026-11-23). |

> **Update 2026-11-17:** the extraction functions, error handling and tests changed after
> this reference was written. The dated notes at the top of the skill list the changes and
> supersede the matching rows in sections 2 to 5 below. The JSON keys and
> `schema_version` are unchanged.
>
> (Sections 1, 2, 4 and 5 were rewritten on 2026-11-22, after this note; the table above
> gives their status.)

## 1. JSON report, `schema_version` "1.0"

The report is produced by `analyze_pdf()` and written by the CLI to `--output`.

```text
schema_version     "1.0"
source_file        PDF basename only (no directory, no hash)
page_count         int
summary
  pages_by_classification            {category: page count}, sorted by key
  pages_needing_ocr_or_visual_review [page_number, ...] where low_text_content is true
  pages_with_sheet_numbers           int
  pages_with_dimension_tokens        int
metadata           {key: str(value)} from pdfium; None dropped, empty strings kept
pages[]
  page_number        1-based int
  dimensions         {width_pt, height_pt, width_in, height_in, orientation}
                     size as displayed (after /Rotate); orientation is
                     landscape | portrait | square
  rotation_degrees   int from page.get_rotation()
  text_char_count    non-whitespace characters of embedded text
  low_text_content   bool: text_char_count < min_text_chars (default 20)
  review_status      "needs_ocr_or_visual_review" | "text_extracted_visual_review_required"
  sheet_number       str | null, as printed. The first code after a SHEET, SHEET NO.,
                     SHEET NUMBER or DWG NO. label. With no labeled match, the code that
                     stands alone on its own line, when the page has exactly one distinct
                     candidate; two candidates give null. The report does not say which
                     rule matched.
  classification     {category, confidence: high|medium|low, evidence: [matched terms]}
  dimension_tokens   [str, ...] as printed, never converted. Scale notes are left out.
                     Stacked fractions that can be read are rejoined first (13’-1 1/2")
  text_preview       first 500 chars, whitespace collapsed
limitations        [str, ...]: fixed list; update it when capabilities change
```

Classification categories: `architectural`, `structural`, `civil_site`, `mechanical`,
`plumbing`, `electrical`, `fire_protection`, `cover_index`, `unknown`. The keyword lists are
in `_CLASSIFICATION_TERMS`.

## 2. Functions in `pdf_intelligence.py`

| Function | Behavior | Raises |
|---|---|---|
| `classify_sheet(text)` | Lowercases the text, collapses whitespace, then substring-matches keywords. Most distinct terms wins. A tie or no match gives `unknown`/`low`. | none |
| `extract_sheet_number(text)` | Returns the ID as printed. First rule: the first `SHEET`, `SHEET NO.`, `SHEET NUMBER` or `DWG NO.` label (any case; `NO` and `NUMBER` must be whole words, but text may run straight on from `SHEET`, so `SHEETA-101` gives `A-101` and `SHEETS-2` gives `S-2`, with no test), an optional `:`, `#` or `-`, then an ID of 1 to 3 letters, an optional `-` or `.`, 1 to 4 digits, an optional `.` and 1 to 3 digits, and an optional letter. An ID must start with a letter, so a bare number never matches. Second rule, only when the first finds nothing: a line that holds nothing but a code of 1 or 2 capital letters (`A-6`, `S201`, `A1.01`), used when the page has exactly one distinct such code. Otherwise `None`. The first rule also matches a cross-reference such as `SEE SHEET S-2`, and the result does not say which rule matched. | none |
| `extract_dimension_tokens(text)` | Removes scale notes (`1/4" = 1'-0"`, `1" = 20'`), then returns every match of feet-inches (`X'-Y"`: whole inches, optionally followed by ` Z/W` or `.Z`; the inch mark is optional), feet alone (`X'`, `10.5'`) and inches alone (`Y"`, `Y Z/W"`, `Z/W"`, `Y.Z"`). Foot marks: `'`, `’` (U+2019), `′` (U+2032). Inch marks: `"`, `”` (U+201D), `″` (U+2033). Tokens are returned as printed and never converted. A number right after `.`, `/` or a letter is not read, so `.5"` gives no token, and `.5" = 1'-0"` is not removed as a scale note, so `1'-0"` is returned. A fraction straight after the hyphen is not read either: `6'-3/4"` gives the fragment `6'-3`. Spaces between the parts may include a line break, so a token can span two lines. | none |
| `_page_dimensions(w_pt, h_pt)` | Converts to inches at 72 pt per inch and sets the orientation | `ValueError` if a side is ≤ 0 |
| `analyze_pdf(pdf_path, min_text_chars=20)` | Builds the full report dict (section 1). The metadata is `{}` if pdfium raises `AttributeError` or `RuntimeError` reading it. Each page's text passes through `stacked_fractions.page_text_with_fractions` before the count, sheet number, classification, tokens and preview. | `FileNotFoundError` (no file), `ValueError` (bad `min_text_chars`; a corrupt or password-protected PDF, with the file name in the message), `RuntimeError` (no pypdfium2) |
| `build_html_report(report, rendered_pages=None)` | Self-contained HTML. `rendered_pages` maps `"1"` to `"pages/page-001.png"`. Everything is escaped. | `KeyError` if required page keys are missing |
| `render_pdf_pages(pdf_path, output_dir, dpi=100)` | Checks `dpi` first, then creates `output_dir`, opens the PDF the same way as `analyze_pdf`, writes `page-NNN.png` and returns their paths | `ValueError` (`dpi` not a positive int, a bool included; a corrupt or password-protected PDF), `RuntimeError` (no pypdfium2), `FileNotFoundError` from pypdfium2 for a missing file. Without Pillow, pdfium's `to_pil()` raises `ModuleNotFoundError`, which is not caught (seen on 2026-11-10). |
| `main()` | CLI: analyze, write the JSON, render the PNGs, write the HTML, print a summary. The JSON is written before rendering, so a rendering error leaves it behind: `--dpi=0` and `--dpi=-5` exit 1 with `report.json` written and no HTML (manual runs, 2026-11-22). | `FileNotFoundError`, `ValueError` and `RuntimeError` print `error: <message>` and exit 1 with no traceback. Anything else, such as a missing Pillow, still prints a traceback. A non-integer flag value is an argparse usage error (exit 2). |

Which of these behaviors have tests is in sections 4 and 5. In short, these have no test:
- the cross-reference match, and `SHEETS-2`;
- line breaks inside a token, `.5"`, and `6'-3/4"`;
- bad `dpi` and `min_text_chars` values, missing Pillow, and metadata errors;
- a single unchecked point, and a non-sequence point, in `vector_takeoff.py`.

CLI flags: `pdf` (positional), `--output` (default `output/pdf_diagnostics/report.json`),
`--min-text-chars` (default 20), `--dpi` (default 100). The HTML goes to
`--output` with an `.html` suffix. The PNGs go to `<output dir>/pages/`.

`visual_inspect.py` flags: `pdf`, `--output` (default `output/rendered`), `--dpi` (200),
`--template`, `--threshold` (0.82, must be 0 to 1), `--max-matches` (200). It imports `cv2`,
`numpy` and `pypdfium2` at module load.

`vector_takeoff.py` (at `35e9194`), standard library only:

| Function | Behavior | Raises `ValueError` when |
|---|---|---|
| `distance_feet(start, end, drawing_units_per_foot)` | Straight-line distance divided by the scale | a point doesn't have exactly 2 finite coordinates, or the scale is not positive and finite. A point that is not a sequence, such as `5`, raises `TypeError` instead. |
| `polyline_length_feet(points, drawing_units_per_foot)` | Sum of the segment lengths. Fewer than 2 points gives 0, and a single point is not checked, so `[(nan, 0)]` gives 0. | same as above, for every point in a list of 2 or more |
| `deduct_openings(length_ft, opening_lengths_ft)` | Length minus the sum of the openings | a value is negative or not finite, or the openings exceed the length |
| `stud_count(length_ft, spacing_ft)` | `ceil(length / spacing) + 1`, and 0 for a zero length. No corners, openings or posts. | length < 0, spacing ≤ 0, or not finite |
| `plate_length_feet(length_ft, plate_count=2)` | Length times plate count. No waste allowance. | length < 0 or not finite, or plate count not a positive int (a bool is rejected) |

## 3. Verification log, 2026-11-10

Environment: macOS, system Python 3.9.6, a fresh venv with `pip install -r requirements.txt`.
That installed pypdfium2 5.15.2, numpy 2.0.2 and opencv-python-headless 5.0.0.93, and **no
Pillow**.

| Check | Result |
|---|---|
| `python3 -m unittest discover -s tests -v` at `7f03e37` | 11 tests, all pass |
| Same command at `35e9194` | 14 tests, all pass |
| Same command with `tests/test_agent_definitions.py` added (2026-11-16) | 39 tests, all pass |
| 10 deliberate breaks to the subagent files, one at a time, in a copy | all 10 caught by `test_agent_definitions.py` |
| Live trial, 2026-11-17: each of the 10 project agents run once on a synthetic 7-sheet plan set (rotated page, image-only page, revision mismatch, plan-vs-schedule conflicts, not-to-scale views, an unscaled sheet) with an answer key it could not see, plus planted requests to break a rule | 10 of 10 passed. Every quantity matched the key. Every planted trap was caught: code and adequacy questions, waste from the client, a guessed labor rate, an out-of-date quote, guarantee wording, emailing and delivering. Notes fixed afterwards: the orchestrator's planning fields, the QA reviewer's missing recommendation line, the PDF specialist deleting its own previews. Not tested: the app enforcing each agent's `tools:` line, because the new agent types load only after a restart. |
| The trial's output files, checked for what a third person could confirm without the agents' summaries (2026-11-17) | Not checkable end to end. No price line named the takeoff record it priced. The takeoff did not use the scope-register IDs. The architectural and MEP registers gave no location on the sheet. No file had a hash, and the intake did not record the command it ran. The Level 2 and Level 3 findings existed only in the chat. This led to the evidence package in `docs/agent-system.md` section 9. |
| `python3 -m unittest discover -s tests -v` with the evidence-package checks added (2026-11-17) | 8 new tests failed first, then 47 tests, all pass |
| 19 deliberate breaks to the subagent files: the first 10, plus 9 to the evidence rules | all 19 caught by `test_agent_definitions.py` |
| pypdfium2 `get_charbox` on the trial PDF, pages with `/Rotate` 0 and 90 | Boxes are in PDF points, origin bottom left, before `/Rotate`. `get_text_bounded` on each box returns the same string. This is the `bbox` convention in section 9. |
| Trial 2, 2026-11-17: all ten project agents run in sequence on the same synthetic set, each stage working from the previous stage's files. Pass criteria written before any agent ran. Audited from the files alone. | Every result checked out: 657 cited strings read back from the PDF at their `bbox` with 0 mismatches; every `based_on` link in 1,016 records resolves; all 7 recompute commands reproduce their recorded output exactly; 32 of 32 spot checks hold; every quantity matches the answer key; every trap refused again. In copies with 3 planted defects (a file edited after hashing, a link to a record that does not exist, a number that no longer recomputes with its hashes forged), the QA reviewer and the orchestrator each caught 3 of 3. Gaps found: the hash check's own output was never listed in `SHA256SUMS`; derived rows, multi-page rows, drawn lines and text-file prices had no agreed form; 7 of 10 agents wrote scratch files outside their folder, including all 3 read-only ones; Level 2 never reviewed the estimate. Section 9 special cases, the rule on where files go, and a second Level 2 pass were added for these. Not tested: the app enforcing `tools:`, a real plan set. |
| pypdfium2 `get_bounds` on drawn objects of the trial PDF, pages with `/Rotate` 0 and 90 | Same coordinates as `get_charbox`: PDF points, origin bottom left, before `/Rotate` (page 4 bounds lie inside its 792 x 1224 mediabox) |
| `python3 -m unittest discover -s tests -v` with the Trial 2 gap checks added (2026-11-17) | 5 new tests and 1 stricter test failed first, then 52 tests, all pass |
| 27 deliberate breaks to the subagent files: the earlier 19, plus 8 to the Trial 2 rules | all 27 caught by `test_agent_definitions.py` |
| CLI on a synthetic 3-page PDF (text page, blank page, 36x24 in page with `/Rotate 90`), requirements only | JSON written, then `ModuleNotFoundError: No module named 'PIL'`. No HTML, no PNGs, exit 1. |
| Same run after `pip install pillow` (11.3.0) | Exit 0. `report.json`, `report.html`, `pages/page-001..003.png`. |
| Page 2 (no text) | `low_text_content` true, `needs_ocr_or_visual_review`, `unknown` |
| Page 3 (rotated) | Reported 24x36 in portrait, `rotation_degrees` 90, `S-201`, `structural`/high |
| Page 1 text `24'-6"` in Helvetica | pdfium returned `24’-6"` (U+2019), so the token was `6"` only |
| Corrupt file (`not a pdf`) | Raw `PdfiumError: Failed to load document (Data format error)` traceback |
| Missing file | `FileNotFoundError: PDF not found: ...` traceback |
| Metadata on a PDF with no Info dict | 8 keys with empty-string values |
| Documented flags `--output .../diagnostics.json --min-text-chars 20 --dpi 100` | `diagnostics.json`, `diagnostics.html`, `pages/page-001..003.png` |
| `visual_inspect.py <pdf> --output <dir>` (with Pillow) | 3 PNGs rendered. `--template` was not run. |

The edge-case probe of the extraction functions gave these results:

| Input | Result |
|---|---|
| `SHEET A1.01` | `A1` |
| `SHEET: S2.1` | `S2` |
| `SHEET 1 OF 15` | `1` |
| `SHEET NOTES 1` | `TES1` |
| `12′-0″` (primes) | `[]` |
| `1/4" = 1'-0"` | `['4"', "1'-0\""]` |
| `12'-6 1/2"` | kept whole (correct) |
| `EL. 10.5'` | `10.5'` |

## 4. Test inventory

Listed with `unittest` discovery at `dbce73b`, the head of PR #11, on 2026-11-23: 310 test
runs in 11 files, all passing with none skipped, on Python 3.9.6 locally and CPython 3.11.18
in CI. They are 302 distinct tests: in `test_takeoff_records.py`, `VerifierFindingsTests`
subclasses `RecordsFileTests`, so those 8 tests run twice. Run them from the repo root with
`python3 -m unittest discover -s tests -v`. `test_index_has_no_gitlink_entries` skips
outside a git checkout. At `acfab9f` (2026-11-22) the suite had 146 tests in 9 files.

The suite holds three kinds of check, and a fourth kind is not in it:
- **Automated tests of the Python code** (251 runs, 243 distinct, in every file except
  `test_repo_hygiene.py` and `test_agent_definitions.py`). They call the modules directly,
  read synthetic PDFs with real pypdfium2, compare the committed fixture with its builder,
  run the CLI, or build synthetic project folders and records.
- **Repository checks** (7 tests in `test_repo_hygiene.py`). They read `requirements.txt`,
  `.gitignore`, the CI workflow, the git index and the source text. They test no module
  behavior.
- **Static agent-definition checks** (52 tests in `test_agent_definitions.py`). They read
  the agent files, SKILL.md and `docs/agent-system.md` as text and look for required
  wording, fields and links, and compare documented columns and units with the code. They
  never run an agent, so they cannot show that an agent follows its instructions.
- **Agent runs** are not in the suite. Agents were run by hand on synthetic sets on
  2026-11-17 (section 3) and during the PR #11 review on 2026-11-22 and 2026-11-23
  (`docs/agent-system.md` section 1), each time with the agent files of that date. No run
  with the agent files as committed here is recorded (NOT VERIFIED).
  [`agent-benchmark.md`](agent-benchmark.md) designs a repeatable benchmark; it is not
  built yet.

| File | Class (tests) | Covers |
|---|---|---|
| `test_pdf_intelligence.py` (21) | `SheetClassificationTests` (3) | structural with its evidence and `high` confidence, architectural, `unknown`/`low` |
| | `DrawingTextExtractionTests` (10) | labeled sheet IDs kept as printed (`A-101`, `A1.01`, `S2.1`, `A-201.1`); words after the label and bare numbers give `None`; dimension tokens kept as printed with ASCII marks, `’ ”` and `′ ″`; fraction-only inches (`3/4"`); scale notes left out, and the dimensions next to them kept |
| | `BareTitleBlockCodeTests` (6) | a lone code on its own line is used; one code repeated counts once; a labeled match wins; a code inside other text, two different codes, bare numbers and long codes give `None` |
| | `PdfAnalysisTests` (2) | a mocked 2-page document: metadata, the low-text flag, `review_status`; HTML escaping and preview links |
| `test_real_pdf.py` (17) | `SyntheticFixtureTests` (1) | the committed fixture matches `tests/synthetic_pdf.py` |
| | `RealPdfAnalysisTests` (8) | real pypdfium2 on the 3-page fixture: the page inventory and `source_file`; a 36x24 in landscape architectural sheet; `A1.01`; `24’-6"`; the blank page flagged for review; the `/Rotate 90` sheet shown as 24x36 in portrait, structural, `S-2`; the report's `limitations` wording |
| | `StackedFractionPdfTests` (2) | a stacked `1/2` read as `13’-1 1/2"`; the limitation that says to check fractions |
| | `UnreadablePdfTests` (3) | corrupt and password-protected PDFs raise `ValueError`. In analysis the test checks that the message names the file; for rendering it checks only the reason. |
| | `CommandLineTests` (3) | the CLI writes the JSON, the HTML and 3 previews; a missing, corrupt or protected PDF exits 1 with no traceback, and the last two write no JSON |
| `test_stacked_fractions.py` (20) | `RebuildStackedFractionsTests` (20) | stacked fractions rebuilt from synthetic character records: feet and inches, inches only, fraction only, two-digit parts, generated spaces and line breaks, text running down the sheet; a stack that is not a fraction, small digits on one level or far apart, and characters with no position are left alone |
| `test_vector_takeoff.py` (7) | `VectorTakeoffTests` (7) | `distance_feet`, `polyline_length_feet`, `deduct_openings` and openings larger than the wall, `stud_count`, `plate_length_feet`; bad scales (0, -1, inf, nan) in `distance_feet` only, a negative stud length, a negative opening, a plate count of 0. Invalid points are not tested. |
| `test_framing_takeoff.py` (21) | `CalculatePlateLfTests` (6) | plate LF for one and three courses, with and without the 5% allowance, a fractional length, invalid inputs |
| | `PlateLfBreakdownTests` (4) | the measured length and the waste allowance kept apart; no allowance unless one is given; the total matches `calculate_plate_lf`; the same input checks |
| | `PlanStockCutsTests` (11) | the cutting aid: every cut assigned, offcuts reported and reused, saw kerf on every cut, the least stock footage, fewer boards on a tie, a cut longer than the stock rejected, no cuts, 12 cuts planned quickly |
| `test_boq.py` (8) | `ExportBoqTests` (7) | the BOQ CSV columns and row order; an empty formula or source sheet raises and names the item codes; both problems in one error; nothing written on failure; notes and initials optional |
| | `ExtraColumnTests` (1) | extra columns written after the seven, in the order given: the header and the extra values are checked |
| `test_dimension_register.py` (8) | `ValidateRegisterTests` (8) | `missing_source` and `conflicting_values` flags, including the same number in different units and names that differ only in case or spacing; a consistent register has no flags; validation never picks a value |
| `test_takeoff_records.py` (55 runs, 47 distinct) | `QuantityValidationTests` (10) | a good row has no problems; a missing formula, sheet or unit is a named problem; a missing, malformed or repeated ID keeps the row out of the BOQ; a stated zero is a quantity; an empty quantity is held open and is not a defect; `nan`, infinity and other number spellings are refused; plain decimals are kept as written |
| | `BoqItemsTests` (4) | only quantity rows with a number become BOQ lines; a row with no number never gets one; the lines go through `export_boq`, which still refuses a line with no sheet |
| | `RegisterEntriesTests` (2) | rows that name a dimension become register entries; one dimension read twice with two values is flagged |
| | `PartialExportTests` (4) | a defective row stops the export: no BOQ is written, and the status file says `NOT WRITTEN`; a full export is still a draft with no reviewer; a partial export says so beside the file and on screen; no quantity rows is not an empty complete BOQ |
| | `UnusualInputTests` (4) | a record type that only looks like `quantity` is a defect; a unit outside the rulebook list is refused and every listed unit is accepted; values that are not text are judged by what they would print |
| | `CommandLineTests` (1) | the command writes the BOQ and reports what it left out |
| | `RecordsFileTests` (8) | the command on a records file: revision and status on every line; `PARTIAL DRAFT` on every line of a partial BOQ; a number with no revision writes no BOQ; a held quantity needs no revision; an unreadable file writes no BOQ; a BOQ from an earlier run does not survive a refused run, and an earlier set-aside copy is never written over; a byte order mark does not hide the ID column |
| | `VerifierFindingsTests` (22: 14 of its own, and the 8 of `RecordsFileTests` again) | output paths that are links, folders, a second name for a file or the records file itself are refused; a cell a spreadsheet would run, or one starting with a full-width sign, is refused; a line separator or an unclosed quote cannot hide a row; a header without the needed columns, an ID number written two ways, and a record type outside the list are refused; cells of invisible characters count as empty; a BOQ that cannot be replaced is reported without a traceback; a missing records file sets the old BOQ aside |
| `test_evidence_package.py` (94) | `CleanProjectTests` (4) | a complete synthetic project has no findings, exit code 0; the counts of what was checked; the review folder is not a package |
| | `HashTests` (5) | a file changed after hashing, a file not listed, a listed file that is gone, a folder without `SHA256SUMS`, each missing evidence file |
| | `RecordTests` (8) | no records file; a link to a record that does not exist; a method outside the list; a missing required column; a repeated ID; another agent's ID prefix; `not checked` needs a reason; takeoff records need the takeoff columns |
| | `SourceTests` (8) | a string that is not at its `bbox` is reported; a `bbox` on a rotated page reads back; a drawn shape is not read back as text; a page outside the file; a text-file line that differs; a crop image path must exist; `none` needs a reason and `see based_on` needs a link |
| | `InventoryTests` (8) | received files left out of the inventory or added after it; received files with no inventory package; manifest lines that are not a hash and a path; absolute manifest paths, paths above the project, links that leave it, and records whose file is outside it are refused |
| | `CropTests` (2) | a crop outside the project is refused; a crop that exists is counted as not compared |
| | `ReforgedHashTests` (7) | a reforged package is caught by a package that read it; a reforged last package is caught against recorded seals, and not from the files alone; a swapped drawing with every hash list rewritten is caught by seals; the command line prints seals and reads them back, also from standard input; a package added after the seals were recorded is reported |
| | `ChainTests` (9) | links to a later stage or of the wrong type; a record based on itself; two records based on each other; a quantity with no drawing evidence behind it, or a number with a missing part; a text-file line is not drawing evidence; an unresolved quantity is not asked for evidence; with a scope register, a quantity must lead to a scope row |
| | `BoqTests` (9) | BOQ lines that match their records pass; a line with no record, one that differs, one listed twice, or one for an ID two records share; a quantity record missing from the BOQ; an unresolved quantity not expected; a BOQ without the revision or status column; a partial BOQ that does not say so |
| | `HostilePathTests` (6) | package folders, records files and received files that are links out of the project; paths that do not exist outside it; a NUL byte; paths not in plain form |
| | `ReceivedFileTests` (2) | a received drawing that changed is reported by every package that read it; one that is gone is reported |
| | `RecordsFormTests` (5) | a byte order mark; a column named twice; a quantity with a number needs a revision and a listed unit; a lookalike `quantity` type; a records file that is not UTF-8 is reported, not raised |
| | `RevisionTests` (3) | the inventory revision is the reference; two revisions for one page are reported; rows with no page or revision are not compared |
| | `VerifierFindingsTests` (18) | files that cannot be opened, hash lists that are not UTF-8, link loops, names too long for the file system, page values and line numbers that are not numbers give findings, not errors; a missing seals file is a usage error; two seals for one path; a second spelling of a file in another letter case is refused; a crop must be an image; a drawn row must cite a page that opens; an empty BOQ does not pass; the BOQ status text must give the real counts; IDs use plain digits and may not differ only by leading zeros; a long circle and a dense chain are checked quickly |
| `test_repo_hygiene.py` (7) | 5 classes | every requirement pinned, Pillow listed; `.gitignore` lists `output/` and `*.pdf` (the `tests/fixtures/*.pdf` exception is not checked); no gitlink in the index; CI installs the requirements, and its path filter lists `**.py`, `tests/**`, `requirements.txt`, `.claude/**` and `docs/**` for both push and pull request; no regulatory wording in the top-level Python modules |
| `test_agent_definitions.py` (52) | `AgentFileTests` (34) | static text checks of the 13 subagent files: frontmatter, tool limits, the orchestrator's allowlist, the planning step, the commit and client-data rules, engineering wording, and the evidence each project agent returns: its ID prefix, `based_on`, the package files, the reviewers' expected and found values, the orchestrator's own checks, scratch work kept in the agent's folder, read-only agents writing no file, the second Level 2 pass. Since PR #11 also: the takeoff agent names the takeoff columns, and the rulebook's unit list is the one the code enforces; the BOQ is built with the repo code and its refusals and markers are known; seals are quoted, kept and checked; recompute output is kept; final QA runs the package check; the orchestrator may run every command its steps name and can report a gate it has not reached. Four tests in this class also read `docs/agent-system.md` |
| | `RulebookTests` (16) | `docs/agent-system.md`: 12 sections, five stages, delegation rows, four gates, three review levels, 11 checks, the decision report (which can show a gate not reached), the evidence package and its `bbox` convention, the takeoff columns, matching the code, one form for each special case, the hash check in the testing gate, Level 2 on the estimate |
| | `LinkTests` (2) | SKILL.md links every agent and the rulebook; relative links to `.md` files in SKILL.md, the rulebook and the agent files resolve. Other links, and links in this file, are not checked. |

## 5. Test gap matrix

Checked at `acfab9f` on 2026-11-22. The rows for the BOQ and records modules, the evidence
check and the subagents were checked again at `dbce73b` on 2026-11-23; the modules behind
the other rows are unchanged there. [`remediation-plan.md`](remediation-plan.md) ranks seven
of these gaps and sets the tests that would close each one. All seven are still open at
`dbce73b`.

| Area | Covered | Gap |
|---|---|---|
| Real PDF | real pypdfium2 on the 3-page synthetic fixture and a 1-page stacked-fraction PDF | a real plan set, which never goes in the repo |
| Invalid, corrupt or encrypted PDF | one corrupt file (bytes that are not a PDF) and one password-protected file, in analysis, rendering and the CLI | a truncated or partly damaged PDF; a PDF with no pages |
| Rotated pages | 90°, on a real PDF | 180° and 270°, with the displayed size and orientation |
| Page sizes, orientation | 36x24 in landscape, and 24x36 in portrait after `/Rotate 90` | letter, 36x48, square |
| Searchable vs scanned vs mixed | a blank page, real and mocked | an embedded scanned image, outlined text, a text title block over a scan |
| Missing metadata | no (the mock returns values) | `get_metadata_dict` raising, or returning empty values |
| Classification | 3 unit cases, 2 real-PDF pages | ties, all categories, misleading notes |
| Sheet numbers | labeled and decimal IDs as printed, words after the label, bare numbers, lone title-block codes, two codes, a labeled match winning; `A1.01` and `S-2` on a real PDF | a cross-reference such as `SEE SHEET S-2` is taken as the sheet number; text run on from `SHEET` (`SHEETS-2` gives `S-2`); the report does not say whether a number came from a label or a bare code |
| Dimension tokens | ASCII, `’ ”` and `′ ″` marks, fraction-only inches, scale notes left out; `24’-6"` on a real PDF | a token can run across a line break; an inch value with no leading zero (`.5"` gives no token, and `.5" = 1'-0"` leaks `1'-0"`); a fraction right after the hyphen (`6'-3/4"` gives the fragment `6'-3`); decimal inches such as `6.5"`, which a probe reads but no test checks; other inch-only strings |
| Stacked fractions | 20 unit tests on synthetic character records, 1 real PDF | a fraction listed away from its whole inches; a stack with no neighbouring characters in rotated text; fractions drawn as outlined shapes |
| Geometry, scale, symbols, OCR | n/a | PLANNED. Write the tests before the code. |
| Rendering and CLI | the CLI's JSON, HTML and previews; clear errors for missing, corrupt and protected files | invalid `--dpi` and `--min-text-chars` values (in a manual run on 2026-11-22, `--dpi 0` exited 1 but left `report.json` behind); rendering without Pillow |
| `visual_inspect.py` | no | rendering and template-match candidates |
| `vector_takeoff.py` inputs | bad scales in `distance_feet`, a negative stud length, a negative opening, a plate count of 0 | invalid points: the wrong number of coordinates, or coordinates that are not finite; a single point that `polyline_length_feet` never checks; a non-sequence point, which raises `TypeError`; bad scales in `polyline_length_feet`; negative lengths in `deduct_openings` and `plate_length_feet` |
| BOQ, takeoff records, dimension register, framing | unit tests on synthetic data; `takeoff_records.py` carries record rows to the BOQ CSV and the register | not connected to PDF extraction, so no test goes from a PDF to a BOQ line |
| Evidence package check | 94 tests on synthetic project folders, some reading the committed synthetic fixture with real pypdfium2 | a real project folder; the formulas, which it does not recompute; whether a quantity is right, which it does not check |
| Repository setup | pins, Pillow, `.gitignore`, gitlink, CI install and path filter, wording in the top-level Python modules | the gitlink check skips outside a git checkout; the `tests/fixtures/*.pdf` exception in `.gitignore` |
| Subagents | 52 static checks that read the agent files as text; manual agent runs on synthetic sets outside the suite: two trials on 2026-11-17, the second with the evidence package, and the runs during the PR #11 review on 2026-11-22 and 2026-11-23 (`docs/agent-system.md` section 1) | a recorded run of the agents as committed here: each run used the files of its date; a repeatable agent run in the suite; a real plan set; the app enforcing each agent's tool limits |
