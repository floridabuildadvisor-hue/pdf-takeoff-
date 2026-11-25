---
name: pdf-drawing-intelligence
description: >-
  Use when working in the pdf-takeoff- repository on anything that reads client
  construction PDFs or computes quantities: pdf_intelligence.py, vector_takeoff.py
  framing helpers, TAKEOFF_METHOD.md, the output/pdf_diagnostics reports,
  sheet classification, sheet numbers, dimension strings, low-text or scanned
  pages, OCR, page rendering, geometry, scale, symbols, or takeoff quantities.
  Also use before planning, changing, reviewing, or testing code in this repo.
---

# PDF Drawing Intelligence (pdf-takeoff-)

Project knowledge for the "PDF Drawing Intelligence" milestone. Read this file before any
work in this repo, then go to section 18.

**Verified baseline:** `main` at `35e9194`, checked 2026-11-10 against the code and the test
run. `pdf_intelligence.py` and `visual_inspect.py` have not changed since `7f03e37` (the merge
of PR #2), so the real-PDF runs done on that commit still apply. If `git log -1 origin/main`
shows a newer commit, re-check every status below against the code before relying on it.

**Changes since that baseline (2026-11-17, repo rescue).** These supersede the matching
lines in sections 5, 8, 11, 12, 13, 14, 16 and 17 below, which still describe `35e9194`
(section 14 was rewritten on 2026-11-22; see the note below):

- `requirements.txt` now lists Pillow and pins all four packages. No separate
  `pip install pillow` is needed.
- `.gitignore` excludes `output/` and `*.pdf`.
- The stray `pdf-takeoff-` gitlink is removed.
- CI installs `requirements.txt` and runs on changes to any `*.py`, `tests/**`,
  `requirements.txt`, `.claude/**` and `docs/**`.
- `tests/test_repo_hygiene.py` adds 6 tests (20 in total) that guard the items above.
- `README.md` documents CLI usage again, `.github/copilot-instructions.md` covers all three
  modules and `TAKEOFF_METHOD.md`, and a root `CLAUDE.md` points here.

**Extraction fidelity changes (2026-11-17).** These supersede the matching lines in
sections 8, 9, 11, 14 and 17 below and the probe table in the docs file (section 14 was
rewritten on 2026-11-22; see the note below):

- Dimension tokens accept ASCII marks, typographic quotes (U+2019, U+201D) and primes
  (U+2032, U+2033), and keep fraction-only inches whole (`3/4"`). Tokens are still returned
  as printed.
- Scale notes (`1/4" = 1'-0"`, `1" = 20'`) are left out of dimension tokens. They are not
  read or applied as a scale.
- Sheet numbers are returned as printed (`A1.01`, `S2.1`; dots are no longer rewritten to
  hyphens). The label must be a whole word and the ID must start with a letter, so
  `SHEET NOTES 1`, `SHEET 1 OF 15` and other bare numbers give `None`.
- With no label, a code alone on its own line (`C-1`, `A-6`, `T-3`) is used when the page
  has exactly one distinct candidate. Two different candidates give `None`.
- Corrupt and password-protected PDFs raise `ValueError` naming the file. The CLI prints
  `error: ...` and exits 1 with no traceback.
- `tests/fixtures/synthetic_plan_set.pdf` (built by `tests/synthetic_pdf.py`, no project
  data) is read by real pypdfium2 in `tests/test_real_pdf.py`, including a CLI run that
  writes the JSON, HTML and page previews. 48 tests in total.
- Still open: stacked fractions run together in extracted text (`13'-1 1/2"` can read
  `13'-112"`), a token can span a line break, a cross-reference such as `SEE SHEET S-2`
  counts as a labeled match, and the report does not say whether a sheet number came from
  a label or from a bare code.

**Proof-chain modules (2026-11-17).** Two new standard-library modules, both IMPLEMENTED
and tested with synthetic data, neither connected to PDF extraction yet:

- `boq.py`: `export_boq(items, path)` writes a CSV with `item_code`, `quantity`, `unit`,
  `formula`, `source_sheet`, `notes` and `reviewer_initials`. It raises `ValueError` naming
  the item codes whose formula or source sheet is empty, and writes nothing in that case.
  It does not check that a quantity is right.
- `dimension_register.py`: `validate_register(entries)` returns review flags:
  `missing_source`, and `conflicting_values` when the same name carries different values
  or units. It never picks a value; the estimator resolves each flag against the drawings.
- 63 tests in total.

**Evidence modules (2026-11-22).** Two more modules, both IMPLEMENTED and tested with
synthetic files only. Neither has been run on a real plan set:

- `evidence_package.py`: `check_project(project_dir)` and the command
  `python3 -B evidence_package.py <project folder>` check the agents' evidence packages
  (`docs/agent-system.md` section 9): the sha256 of each listed file, the record columns,
  the IDs, every `based_on` link, and each printed string read back at its `bbox`. It only
  reads. It does not recompute formulas or check that a quantity is right.
  Since the PR #11 review it also checks that every file in `01_Received/` is in the
  `pdf-drawing-specialist` `SHA256SUMS`, that no listed or cited path leaves the project,
  that `based_on` links do not run in a circle or point to a later stage, that every
  quantity with a number leads back to a place on a drawing, and that each line of
  `02_Working/report-proposal-specialist/boq.csv` matches a quantity record. A crop image
  is checked for existence only. Paths must be plain project-relative paths, and two
  revisions recorded for one page are reported. A package whose files and `SHA256SUMS` were
  both rewritten, or a swapped received file, is found only with `--seals <file>` or
  `--seals -`, against `SEAL` lines the owner kept from an earlier decision report.
- `takeoff_records.py`: `boq_items_from_records(records)` and
  `register_entries_from_records(records)` carry takeoff rows to `export_boq` and
  `validate_register`. A quantity row with no number is returned as not exported. The
  command is `python3 -B takeoff_records.py <records.csv> <boq.csv>`.
  `quantity_row_problems(row)` names what stops a row: a quantity that is not a plain
  number (`nan`, `inf`, `1e3` and `1,000` are refused), a unit outside `ALLOWED_UNITS`, no
  formula, no sheet, or an ID that is not `QTO-<number>`. The command writes no BOQ while
  one such row exists, renames an earlier BOQ to `<boq.csv>.SUPERSEDED`, and always writes
  `<boq.csv>.STATUS.txt`, which starts `DRAFT`, `PARTIAL DRAFT` or `NOT WRITTEN`. Every BOQ
  line has `source_revision` and `boq_status`. `boq.export_boq` takes an optional
  `extra_columns`.
- 310 tests in total at `dbce73b` (2026-11-23).

**Framing module merged (2026-11-17).** PR #1 is merged, so `framing_takeoff.py` is on
`main`. This supersedes the PR #1 paragraph in section 16.

- `plate_lf_breakdown` keeps the measured length and the waste allowance apart and adds no
  allowance unless one is given. `calculate_plate_lf` still defaults to 5%; prefer the
  breakdown for anything that reaches a BOQ line.
- `plan_stock_cuts` is a cutting aid on caller-supplied stock lengths. It is not a takeoff
  quantity and not an order; the measured quantity is `total_cut_lf`. Purchasing stays out
  of scope (section 2).
- `vector_takeoff.plate_length_feet` and `framing_takeoff.calculate_plate_lf` overlap: the
  first allows a zero length and has no allowance; the second rejects zero and can add one.

**Stacked fractions (2026-11-17).** New module `stacked_fractions.py`, IMPLEMENTED and
tested with synthetic character records and a synthetic PDF read by real pypdfium2. This
supersedes the "still open" stacked-fraction line above.

- Plan fonts draw `13'-1 1/2"` with the fraction digits smaller, one above and one below
  the baseline. Plain extraction returns `13'-112"`. `page_text_with_fractions` reads each
  character's box (`get_charbox`) and font size (`FPDFText_GetFontSize`) and writes the
  stack back as `1/2`. `analyze_pdf` calls it for every page.
- The baseline direction comes from the characters next to the stack, so rotated and
  diagonal dimension text is read the same way.
- A stack is rewritten only for a proper fraction with a denominator from 2 to 64. Anything
  else stays exactly as extracted.
- Spaces and line breaks that extraction generates inside the stack are dropped.
- Still open: when extraction lists a fraction away from its whole inches (interleaved with
  another dimension), the two are not rejoined; a stack with no neighbouring characters in
  rotated text is left as extracted; fractions drawn as outlined vector shapes are not text
  at all. Fractional dimensions still need checking against the drawing.

**Sections 6 and 14 rewritten (2026-11-22).** Both were rewritten against `acfab9f`, then
checked again at `dbce73b`, the head of PR #11, on 2026-11-23. Section 6 now lists nine
modules. Where they and the notes disagree, follow `docs/agent-system.md` section 10, "When
sources disagree". A test count belongs to the revision it names. Sections 5, 7, 8, 9, 10,
11, 12, 13, 16 and 17 still contain older statements. On 2026-11-24 the pypdfium2 import
and Copilot items in sections 6, 10 and 14 were checked again at `18ea305`, after PR #13.

**Status labels** (based only on code that was read and run):

| Label | Meaning |
|---|---|
| IMPLEMENTED | In code on `main` and exercised by a unit test or a real-PDF run |
| PARTIALLY IMPLEMENTED | Some of the capability exists. The missing part is named. |
| NOT VERIFIED | In code, but no test or run has exercised it |
| PLANNED | Not in code. Do not assume it exists. |
| OUT OF SCOPE | Not part of this product. Don't build it without the owner's explicit request. |

Supporting reference: [docs/pdf-drawing-intelligence.md](../../../docs/pdf-drawing-intelligence.md)
covers the JSON schema, the function list, the verification log, the test inventory and the
test gap matrix.

## 1. Project overview

The repo is a set of Python command-line tools that read construction plan PDFs and produce
review material for a takeoff estimator. The current milestone is a **diagnostic layer**. It
inventories each page of a plan set: size, rotation, embedded text, sheet number,
dimension-like strings, and a likely discipline. It then flags pages that need OCR or visual
review, and writes JSON and HTML reports with page previews. It does **not** measure
quantities from the PDF yet.

The repo is public on GitHub: `floridabuildadvisor-hue/pdf-takeoff-`. Don't commit client
PDFs, client names, or generated reports.

## 2. Business context

- The owner is an independent construction takeoff estimator (StructConsultPro). Clients send
  plan sets, usually as PDFs.
- The platform reads and interprets the set to support accurate quantity takeoffs. The
  estimator reviews and verifies the results, then prepares the client deliverables (outside
  this repo).
- The owner is an **estimator, not an engineer**. Florida engineering licensing rules apply.
  Code, reports and docs must never use engineering or compliance-verdict language: no
  "meets code", "structurally adequate", "certified", "approved" or "engineered". Use
  "extracted", "measured", "flagged for review" or "as printed on sheet X".
- A takeoff is a **measured inventory with traceability**. It is not a design opinion.
- **The takeoff method lives in [`TAKEOFF_METHOD.md`](../../../TAKEOFF_METHOD.md)** at the
  repo root. It covers the auditable BOQ line format, clickable plan markup, visual
  verification rules, written-dimension checks, the `drawings.md` sheet index, the
  verification loop and verified examples. Follow it for any output that reaches the
  estimator. It is the owner's document, so change it only at the owner's request.

**Business boundaries (non-negotiable):**
- Takeoff and estimating services only. No purchasing and no supplier ordering.
- Supplier inventory or stock optimization is not a takeoff requirement.
- Never silently substitute supplier assumptions for quantities documented in the plans.
- Every value keeps traceability to the original drawing, and a human can still verify it.
- Priorities, in order: accuracy, transparency, traceability, professional estimating workflow.

## 3. Product objectives

1. Inventory every page of a client plan set and say what each page probably is, with evidence.
2. Never present missing, uncertain or machine-read data as confirmed fact.
3. Grow toward traceable quantity extraction (geometry, dimensions, scale, symbols). Each
   item keeps its source file, page, sheet, extraction method and verification status.
4. Support the estimator's review. The tools must not replace it.

## 4. User workflow

1. The client sends a PDF plan set.
2. The estimator runs `python3 pdf_intelligence.py <set>.pdf` (see section 13).
3. The estimator opens `report.html`. It shows each page preview beside its extracted sheet
   number, discipline guess with evidence, size, rotation, text count and dimension-like
   strings.
4. Pages flagged `needs_ocr_or_visual_review` get OCR or a manual read. Every other page is
   still `text_extracted_visual_review_required`, so no page is auto-accepted.
5. The estimator uses the report as an index and triage for the manual takeoff.
   Quantities are not produced yet (PLANNED).
6. The estimator verifies the results and prepares client deliverables outside this repo.

## 5. Existing architecture

The repo is a flat layout at the root: no package, no `pyproject.toml`, no `setup.py`.

```
pdf_intelligence.py        # milestone CLI: analyze -> JSON -> render PNGs -> HTML
visual_inspect.py          # older starter: render PNGs + OpenCV template-match candidates
vector_takeoff.py          # scale + framing math helpers (no PDF reading)
TAKEOFF_METHOD.md          # the owner's takeoff method (see section 2)
README.md                  # short overview + planned workflow; no CLI usage any more
tests/test_pdf_intelligence.py   # 7 tests (pypdfium2 mocked)
tests/test_vector_takeoff.py     # 7 tests
tests/test_agent_definitions.py  # 52 checks on the subagent files (no agent is run)
.github/workflows/validate.yml   # unittest on Python 3.11, path-filtered
.github/copilot-instructions.md  # instructions for GitHub Copilot
requirements.txt           # numpy, opencv-python-headless, pypdfium2 (unpinned)
pdf-takeoff-               # stray gitlink to another repo, empty on checkout (see section 14)
```

The PDF engine is **pypdfium2**. `pdf_intelligence.py` imports it lazily inside its functions,
so the module imports with the standard library only and tests can mock it via
`sys.modules`. Keep that pattern.

## 6. Modules

Checked against the code and tests at `dbce73b`, the head of PR #11, on 2026-11-23. Of
the seven modules checked at `acfab9f` on 2026-11-22, only `boq.py` changed since.

| Module | Purpose | Status |
|---|---|---|
| `pdf_intelligence.py` | Page inventory, text extraction, sheet numbers, dimension tokens, classification, JSON/HTML reports, page previews | IMPLEMENTED: 21 unit tests (one mocks pypdfium2) and 17 in `test_real_pdf.py`: 16 read synthetic PDFs with real pypdfium2 or run the CLI, and 1 checks that the committed fixture matches its builder. Limits in section 14. |
| `stacked_fractions.py` | `page_text_with_fractions(text_page, text)`, called by `analyze_pdf` for every page, and `rebuild_stacked_fractions(chars)`. Rewrites a stacked `1` over `2` as `1/2` from character boxes and font sizes. Returns the text unchanged when pdfium gives no per-character data. | IMPLEMENTED: 20 tests on synthetic character records, and 1 test that reads a synthetic PDF with real pypdfium2. Three open cases in section 14. |
| `visual_inspect.py` | Renders pages to `output/rendered/` (200 DPI default). Optionally marks template-match **candidates** from a cropped symbol image. Imports `cv2`, `numpy` and `pypdfium2` at module load. | Rendering ran unmocked on a synthetic 3-page PDF on 2026-11-10, and has no test. Template matching NOT VERIFIED. In the CI path filter (`**.py`), but no test imports it. |
| `vector_takeoff.py` | `distance_feet` and `polyline_length_feet` (drawing units divided by a supplied scale), `deduct_openings`, `stud_count` (regular spacing plus both wall ends; no corners, openings or built-up posts), `plate_length_feet` (length times plate count, no waste allowance). Inputs are validated, except that `polyline_length_feet` never checks a single point and a point that is not a sequence raises `TypeError` (section 14). | IMPLEMENTED: 7 tests. Invalid points and some input checks have no test (section 14). Not connected to PDF extraction: callers pass in points, lengths and the scale. |
| `framing_takeoff.py` | `calculate_plate_lf(wall_length_ft, plate_courses, waste_percent=5)`, `plate_lf_breakdown(wall_length_ft, plate_courses, waste_percent=0)`, which keeps the measured length and any allowance apart, and `plan_stock_cuts(cut_lengths_ft, stock_lengths_ft, kerf_ft=0)`, a cutting aid on caller-supplied stock lengths. | IMPLEMENTED: 21 tests on synthetic inputs. Not connected to PDF extraction. `plan_stock_cuts` is not a takeoff quantity or an order. |
| `boq.py` | `export_boq(items, path, extra_columns=())` writes the BOQ CSV in the `TAKEOFF_METHOD.md` line format, with any `extra_columns` after the seven. Raises `ValueError` naming the items with an empty formula or source sheet, and then writes nothing. It does not check that a quantity is right. | IMPLEMENTED: 8 tests on synthetic items. Not connected to PDF extraction. |
| `dimension_register.py` | `validate_register(entries)` returns `missing_source` and `conflicting_values` flags. It never picks a value. | IMPLEMENTED: 8 tests on synthetic entries. Not connected to PDF extraction. |
| `takeoff_records.py` | `read_records(path)`, `quantity_row_problems(row)`, `boq_items_from_records(records)`, `rejected_quantity_rows(records)` and `register_entries_from_records(records)`, and the command `python3 -B takeoff_records.py <records.csv> <boq.csv>`. Carries `QTO-` record rows to `export_boq` and `validate_register`. A quantity row with no number is held open and never given one; a defective row, or a number with no revision, stops the export. Writes `<boq.csv>.STATUS.txt`. When it writes no BOQ, it sets a BOQ from an earlier run aside as `.SUPERSEDED`, `.SUPERSEDED.2` and so on, never over an earlier copy. Measures and rounds nothing. | IMPLEMENTED: 55 test runs on synthetic records, 47 of them distinct: `VerifierFindingsTests` inherits the 8 tests of `RecordsFileTests`, so those run twice. Not connected to PDF extraction. |
| `evidence_package.py` | `check_project(project_dir, seals=None)` and the command `python3 -B evidence_package.py <project folder> [--seals <file>]`. Checks the agents' evidence packages (`docs/agent-system.md` section 9): the sha256 of each listed file, the document inventory, record columns and IDs, `based_on` links, each printed string read back at its `bbox`, and BOQ lines against quantity records. Prints `SEAL` lines and checks them again with `--seals`. Only reads. It does not recompute formulas or check that a quantity is right. At `dbce73b` it imported `pypdfium2` at module load; since PR #13 (`18ea305`) it imports it only when it reads a PDF. | IMPLEMENTED: 94 tests at `dbce73b` (96 at `18ea305`) on synthetic project folders, some reading the committed synthetic fixture with real pypdfium2. Not run on a real plan set. |

Function contracts for `pdf_intelligence.py` and `vector_takeoff.py` are in the docs file,
section 2, which gives only the CLI flags and imports of `visual_inspect.py`. For
`visual_inspect.py`'s functions and the other modules, the contracts are in their
docstrings and in the dated
notes at the top of this file. Inside `pdf_intelligence.py`, the concerns are
already separate functions: parsing (`analyze_pdf`), extraction (`extract_sheet_number`,
`extract_dimension_tokens`), classification (`classify_sheet`), diagnostics (the report dict)
and presentation (`build_html_report`, `render_pdf_pages`).

**Name collision:** a different `vector_takeoff.py` exists in a separate project (see section
10). It is not this file.

## 7. PDF processing pipeline (`pdf_intelligence.py main()`)

1. Parse the CLI args: `pdf`, `--output`, `--min-text-chars`, `--dpi`.
2. `analyze_pdf()`:
   - Open the PDF with pdfium and read the metadata dict (`{}` on error).
   - For each page, read the size (as displayed, after `/Rotate`), the rotation, and the
     embedded text via `get_text_range()`.
   - Count non-whitespace chars and set `low_text_content = count < min_text_chars`.
   - Extract the sheet number, classify the page, extract dimension tokens, and keep a
     500-char preview.
3. Build the summary and the fixed `limitations` list. Set `schema_version` `"1.0"`.
4. **Write the JSON first** (default `output/pdf_diagnostics/report.json`).
5. `render_pdf_pages()` re-opens the PDF and writes `<json dir>/pages/page-NNN.png`
   (100 DPI). This step needs Pillow.
6. `build_html_report()` writes the HTML next to the JSON with an `.html` suffix. All
   PDF-derived text is HTML-escaped.
7. Print the summary and a reminder to review the source drawings.

If step 5 fails, the JSON exists but the HTML and PNGs do not.

## 8. Current capabilities (`pdf_intelligence.py`, unchanged from 7f03e37 to 35e9194)

| Capability | Status | Notes |
|---|---|---|
| Every page enumerated, 1-based `page_number` | IMPLEMENTED | Real 3-page run + mocked test |
| Page size in pt and inches, orientation | IMPLEMENTED | Reported **as displayed**: a 36x24 in sheet with `/Rotate 90` reports 24x36 portrait |
| Rotation (`rotation_degrees`) | IMPLEMENTED | 90 verified on a real PDF. 180 and 270 NOT VERIFIED. |
| Document metadata | IMPLEMENTED | Empty-string values are kept. Only `None` is dropped. |
| Embedded (native) text extraction | IMPLEMENTED | Raw text only. No positions, no bounding boxes, no fonts. |
| Titles, notes, general labels as fields | PARTIALLY IMPLEMENTED | Only inside `text_preview` (first 500 chars, whitespace collapsed). Not separated. |
| Sheet number | PARTIALLY IMPLEMENTED | Only after a `SHEET` / `SHEET NO.` / `SHEET NUMBER` / `DWG NO.` label, first match. Decimal IDs truncate (see section 14). |
| Dimension-like strings, kept as printed | PARTIALLY IMPLEMENTED | ASCII `'` and `"` only. Never converted or scaled. Typographic quotes break tokens (see section 14). |
| Low-text page flag (possible scan) | IMPLEMENTED | `< 20` non-whitespace chars by default (`--min-text-chars`). The flag is named `low_text_content` on purpose, because a low-text page is not necessarily a scan (commit `43cbefe`). |
| Scanned/image page detection | PARTIALLY IMPLEMENTED | Only the low-text heuristic. No check for image objects, and no split between scans, outlined vector text and blank pages. |
| Discipline classification with evidence | IMPLEMENTED | Keyword lists for 8 categories plus `unknown`. Confidence counts matched terms (`high` ≥2, `medium` 1). It is **not a probability**. Ties and no-match give `unknown`/`low`. |
| Per-page `review_status` | IMPLEMENTED | `needs_ocr_or_visual_review` or `text_extracted_visual_review_required`. Every page needs review. |
| JSON report (`schema_version` 1.0) with summary and `limitations` | IMPLEMENTED | Schema in the docs file |
| HTML visual report with page previews | IMPLEMENTED | Text escaped (tested). Works only if Pillow is installed. |
| Page PNG rendering | IMPLEMENTED | Needs Pillow, which `requirements.txt` does not install |
| Source traceability | PARTIALLY IMPLEMENTED | `source_file` is the basename only. Page-level `page_number` exists. No file hash, no per-item method, location or verification status. |
| Error handling | PARTIALLY IMPLEMENTED | Clear errors for a missing file, a bad `min_text_chars`/`dpi`, and missing pypdfium2. A corrupt PDF gives a raw `PdfiumError` traceback. Missing Pillow gives a raw `ModuleNotFoundError`. |
| Encrypted PDFs, very large sets, mixed native+scan pages on real client sets | NOT VERIFIED | |
| Template-match symbol candidates (`visual_inspect.py`) | NOT VERIFIED | Candidates for review only, never counts |

## 9. Planned capabilities (none exist in code yet)

All items below are **PLANNED**. Check the code before assuming any of them exists.

- **Geometry:** reading lines, polylines, closed shapes, boundaries, rooms, walls, openings,
  regions, and the spatial relationships between them out of the PDF. (The math helpers in
  `vector_takeoff.py` exist; extracting the geometry they need does not.)
- **Dimensions and scale:** linear, overall, partial and elevation dimensions, and dimension
  strings, keeping units and references. Scale comes from the sheet or detail and is
  confirmed against drawn lengths. **Never silently assume a scale.** If the scale is
  unknown, report it as unknown.
- **Symbols and annotations:** section, detail and elevation markers, callouts, legends.
- **Per-item traceability:** each extracted item keeps its source PDF, page, sheet number,
  extraction method, confidence or verification status, and a visual reference (bounding box
  or crop).
- **OCR workflow:** a provenance value on every item, from this set: `native_text`,
  `ocr_text`, `vector_geometry`, `image_interpretation`, `human_verified`. OCR output is never
  presented as a verified measurement. An OCR failure is reported, never treated as "no
  information".
- **Structured titles, notes and labels**, and a sheet-number pattern for decimal IDs such as
  `A1.01`.
- **Robustness:** a clean CLI error for corrupt or encrypted PDFs, Pillow in requirements,
  pinned dependency versions.

## 10. Technical decisions

**Decisions recorded in the code and commits:**
- Classification is conservative. Ties give `unknown` and nothing is forced into a
  discipline. The matched terms are kept as `evidence`.
- Dimension strings are kept exactly as printed and never converted (the
  `extract_dimension_tokens` docstring and its test).
- The low-text flag doesn't claim the page is a scan (`43cbefe refine: label low-text pages
  without assuming scan origin`).
- Every page needs visual review. There is no "accepted" status.
- The report embeds a `limitations` list. Update it whenever capabilities change.
- `pdf_intelligence.py` imports pypdfium2 lazily, so its unit tests need no PDF library.
  Since `18ea305`, `evidence_package.py` also imports it only when it reads a PDF.
  `visual_inspect.py` imports it at module load, the one exception. The
  standard-library unittest needs no extra dependencies.
- The HTML report is self-contained, links relative `pages/page-NNN.png` files, and escapes
  every PDF-derived string (`ed924f8` and `49c4591` made it tolerate partial summaries).
- The `vector_takeoff.py` helpers refuse to run without an explicit, valid scale or length,
  and their docstrings name what they leave out (for example, `stud_count` ignores corners,
  openings and built-up posts). Keep stating those gaps.

**Lessons from related prior work. These are NOT implemented in this repo.** They come from a
real 15-sheet residential permit-set takeoff done with PyMuPDF in the separate
`structconsultpro-dashboard` project (`reports/tools/vector_takeoff.py`,
`reports/tools/schedule_checks.py`). Read that code for reference. Don't copy it here unless
the owner asks.
- Architect-exported PDFs often have no CAD layers (OCGs). Wall linework there was found by
  pen weight (1.44 pt and 1.68 pt strokes).
- Architectural fonts draw stacked fractions as separate spans (`6'-9`, a raised `1`, a
  lowered `2`), which must be reassembled.
- Some schedules are outlined vector text and cannot be extracted as text.
- Scale was derived as 1/4" = 1'-0" (18 pt per ft) and confirmed by dimension strings that
  matched drawn lengths.
- Vertical text and inches-only strings need their own handling.
- This repo uses **pypdfium2**, not PyMuPDF. Adding PyMuPDF would be a new dependency
  (license: AGPL or commercial). The owner must approve it first.

## 11. Testing requirements

- **Framework:** standard-library `unittest`. There is no pytest and no test config file. Tests
  live in `tests/` and import modules from the repo root.
- **Command (from the repo root):** `python3 -m unittest discover -s tests -v`
- **Baseline:** 14 code tests pass at `35e9194`. That is 7 in `test_pdf_intelligence.py` and 7 in
  `test_vector_takeoff.py`, run on Python 3.9.6 locally on 2026-11-10. CI runs Python 3.11.
- **Subagent checks:** `test_agent_definitions.py` adds 52 tests. The full suite runs 310
  at `dbce73b` (2026-11-23). `docs/pdf-drawing-intelligence.md` section 4 has the count by
  file.
  They read the files in `.claude/agents/` and `docs/agent-system.md`. They do not run any
  agent, so agent behavior on a plan set is still NOT VERIFIED.
- **Coverage today:** classification (3 tests), sheet number (1), dimension tokens (1), HTML
  escaping and preview links (1), and `analyze_pdf` with a mocked 2-page document (1), plus
  the `vector_takeoff.py` helpers (7).
- **Verified examples:** `TAKEOFF_METHOD.md` section 9 asks for sample drawings with
  known-good answers. None are in the repo yet. The repo is public, so use synthetic plans
  or plans cleared for sharing, and label them as non-project data.
- **Main gaps:** no real PDF fixture, no test for rendering or the CLI, no rotated-page, corrupt
  or encrypted PDF test, and no `visual_inspect.py` tests. The full matrix is in the docs file.
- **Future tests must cover:** valid and invalid PDFs, multi-page sets, rotated pages (90, 180,
  270), page sizes, searchable vs scanned vs mixed pages, missing metadata, classification,
  geometry, dimensions, OCR failures, diagnostics output, and error paths.
- Use TDD: write a failing test, commit it as `test: ...`, then implement as `feat:` / `fix:`.
- **Never delete, skip or weaken a test to make a build pass.**

## 12. Installation

Use a virtual environment. On this Mac, `python` is not on PATH, so use `python3`.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install pillow
```

The `pillow` line is required. Without it the CLI writes the JSON report, then crashes before
the HTML and the page previews. `requirements.txt` is unpinned. The verified versions were
pypdfium2 5.15.2, numpy 2.0.2, opencv-python-headless 5.0.0.93 and Pillow 11.3.0.

## 13. Execution

```bash
python3 pdf_intelligence.py path/to/client-plans.pdf
python3 pdf_intelligence.py path/to/client-plans.pdf --output output/project-001/diagnostics.json --min-text-chars 20 --dpi 100
```

Outputs, all relative to the JSON path:
- the JSON report (default `output/pdf_diagnostics/report.json`);
- the HTML report at the same path with an `.html` suffix;
- page previews at `<json dir>/pages/page-001.png` and onward.

Paths are relative to the current directory. `.gitignore` does not exclude `output/`, so
never `git add` generated reports. The README stopped documenting CLI usage in `f19622f`, so
the commands in this section are the reference.

Other tools:

```bash
python3 visual_inspect.py plans.pdf
python3 visual_inspect.py plans.pdf --template crop.png --threshold 0.82
```

## 14. Known limitations (checked at `acfab9f`, 2026-11-22, and at `dbce73b`, 2026-11-23)

The pypdfium2 import and Copilot items were checked again at `18ea305` on 2026-11-24.

Each item says whether a test covers the behavior. "No test" means it was seen in the code or
a manual run only.

**Extraction**
- **Sheet numbers:** a cross-reference such as `SEE SHEET S-2` or `REFER TO SHEET A-501`
  counts as a labeled match and becomes the sheet number (no test). The report does not say
  whether a number came from a label or from a lone code. A lone code needs a 1- or 2-letter
  prefix, so `NER-200` gives `None` (tested), and it must be in capital letters (no test).
  Text that runs straight on from `SHEET` is read as a label, so `SHEETS-2` gives `S-2`
  (no test). Check every sheet number against the title block.
- **Dimension tokens:** a token can run across a line break, because the spaces between its
  parts may include one (no test). `.5"` gives no token, and `.5" = 1'-0"` is not removed
  as a scale note, so `1'-0"` is returned (no test). A fraction right after the hyphen is
  not read: `6'-3/4"` gives the fragment `6'-3` (no test). Decimal inches such as
  `6.5"` and mixed inches such as `1 1/2"` came out whole in a probe but have no test.
  Treat every token as unverified until it is checked against the drawing.
- **Stacked fractions** are left as extracted when the fraction is listed away from its
  whole inches, when a stack in rotated text has no neighbouring characters, and when the
  fraction is drawn as outlined shapes (no tests for these three cases).
- **Scale notes** are left out of the tokens (tested), but they are not read or applied as a
  scale. No scale is ever detected.
- **Classification** is plain substring keyword matching. "FLOOR PLAN WITH BEAM" ties, so it
  is `unknown`. "beam" or "column" in a general note can tip a sheet. The confidence is a
  count, not a probability. Ties and `medium` confidence have no test.
- **Low-text heuristic:** a vector-only sheet with outlined text, a blank page and a scan all
  look the same. A page with a text title block over a scanned drawing is *not* flagged.
  Only a blank page is tested.
- **Rotation:** 90° is tested on a real PDF. 180° and 270° are NOT VERIFIED.
- **Metadata:** if pdfium raises reading it, the report shows `{}` with no flag (no test).
- There is no OCR, no geometry, no scale, no symbols, no quantities, and no per-item location
  (all PLANNED, sections 4 and 9).

**Errors and the CLI**
- Corrupt and password-protected PDFs give a clear `ValueError` and a CLI exit of 1
  (tested with one file of each). A truncated file and a PDF with no pages have no test.
- The CLI writes the JSON before it renders, so `--dpi=0` or `--dpi=-5` exits 1 and leaves
  `report.json` with no HTML (manual runs, 2026-11-22; no test).
- Without Pillow, rendering raises `ModuleNotFoundError` with a traceback. Pillow is now in
  `requirements.txt`, so this happens only when the install was skipped (no test).
- The PDF is opened twice (once to analyze, once to render).

**Other modules**
- `vector_takeoff.py`: invalid points, bad scales in `polyline_length_feet`, and negative
  lengths in `deduct_openings` and `plate_length_feet` are rejected by the code but have no
  test. Two inputs are not rejected: `polyline_length_feet` returns 0 for a single point
  without checking it, so `[(nan, 0)]` gives 0, and a point that is not a sequence raises
  `TypeError`, not `ValueError` (no tests).
- `visual_inspect.py` has no tests, and template matching is NOT VERIFIED.
- `framing_takeoff.calculate_plate_lf` defaults to a 5% allowance. Use
  `plate_lf_breakdown` for anything that reaches a BOQ line. It overlaps
  `vector_takeoff.plate_length_feet`, which allows a zero length and has no allowance.
- `boq.py`, `dimension_register.py`, `framing_takeoff.py`, `takeoff_records.py` and
  `vector_takeoff.py` are not connected to PDF extraction. No test goes from a PDF to a BOQ
  line.
- `evidence_package.py` and `takeoff_records.py` are tested on synthetic project folders
  and records only.
- In `test_takeoff_records.py`, `VerifierFindingsTests` subclasses `RecordsFileTests`, so
  8 tests run twice: 310 test runs at `dbce73b` are 302 distinct tests.

**Repository and CI**
- CI runs the whole suite, including the real-pypdfium2 tests, but only on synthetic PDFs.
  No real plan set is ever tested, and none may be committed.
- CI runs on changes to any `*.py`, `tests/**`, `requirements.txt`, `.claude/**`, `docs/**`
  and the workflow file. Changes to `README.md`, `TAKEOFF_METHOD.md`, `CLAUDE.md`,
  `.gitignore` or `.github/copilot-instructions.md` alone do not trigger it.
- `.gitignore` ignores `output/` and every `*.pdf` except `tests/fixtures/*.pdf`. A report
  written anywhere else in the repo, such as `report.json` at the root, is not ignored.
- The subagent checks in `test_agent_definitions.py` read the agent files as text. Agents
  ran on synthetic sets on 2026-11-17, 2026-11-22 and 2026-11-23 (`docs/agent-system.md`
  section 1), but no run with the agent files as committed here is recorded (NOT
  VERIFIED).

**Resolved since 2026-11-10** (kept so older references still make sense): Pillow is in
`requirements.txt` and every package is pinned; typographic quotes and primes are read; scale
notes are left out; decimal sheet IDs are kept whole and `SHEET NOTES 1` gives `None`; corrupt
PDFs give a clear error; the stray `pdf-takeoff-` gitlink is removed; real-PDF tests run in
CI; `.github/copilot-instructions.md` covers the nine modules on `main` at `18ea305`;
`evidence_package.py` imports `pypdfium2` only when it reads a PDF (PR #13), and
`architect-reviewer.md` names `visual_inspect.py` as the one exception to that rule.

## 15. Development conventions

- Inspect the code before changing it. Make surgical changes, don't rewrite needlessly, and
  preserve working behavior and existing JSON keys. Bump `schema_version` on any schema
  change, and keep it backward compatible where practical.
- Keep the modules separate: parsing, extraction, classification, diagnostics and
  presentation. Put new capabilities (geometry, OCR, symbols) in **new modules** rather than
  growing `pdf_intelligence.py`. Add each new module to the CI path filter.
- Use structured outputs (dicts/JSON with snake_case keys). Every extracted item keeps its
  source references.
- Never invent missing dimensions, scales or drawing info. Use `None` or `unknown` and flag
  it. State uncertainty explicitly in the output, not just in the docs.
- Raise clear, useful errors (`ValueError`, `FileNotFoundError`, `RuntimeError` with an
  install hint). Do not swallow failures.
- Avoid unnecessary dependencies. Any new one needs a reason and goes in `requirements.txt`.
- Keep `from __future__ import annotations`. The code uses `str | None` hints and local Python
  is 3.9.
- Escape every PDF-derived string in the HTML.
- Use estimator language only (section 2).
- Document decisions in commit messages and in this skill. Verify before calling anything
  complete.

## 16. Git / PR workflow

- **Never commit, push, open a PR or merge without the owner's explicit yes in chat.** Show
  the diff first. Never merge PRs yourself.
- Branch names follow `feature/<topic>` and `docs/<topic>`. Branch off up-to-date
  `origin/main`.
- Commit prefixes as used in history: `test:`, `feat:`, `fix:`, `docs:`, `ci:`, `refine:`.
  The TDD order is visible in history: a `test:` commit comes before its `feat:` commit.
- PR #2 (`feature/pdf-drawing-intelligence`, 12 commits) was **merged** on 2026-11-10 as
  `7f03e37`. Keep that history and branch.
- Three commits then went straight to `main` without a PR: `f19622f` (TAKEOFF_METHOD.md and
  the README rewrite), `0534008` (framing helpers and tests) and `35e9194` (Copilot
  instructions and the stray gitlink).
- PR #1 (`feature/wall-plate-takeoff`: `framing_takeoff.py`, wall-plate LF with a 5% default
  waste allowance, and a stock-length cutting planner) is **open, not merged**. That code is
  not on `main`. `main` now has its own `plate_length_feet` with no waste allowance, so
  compare the two before merging anything. PR #1's cutting planner optimizes against
  supplier stock lengths, which touches the "no supplier stock optimization" boundary.
  Whether it merges is the owner's call.
- Never overwrite uncommitted work. Never stash, reset or force-push without explicit
  approval.
- Changes the CI path filter skips need a manual test run, and the PR must report it.

## 17. Roadmap (suggested order; all PLANNED)

1. Robustness: add Pillow to requirements, a clean error for corrupt PDFs, and a real-PDF test
   fixture. Make `output/` git-ignored, which needs the owner's OK.
   Start the verified-example set from `TAKEOFF_METHOD.md` section 9.
2. Fix the extraction fidelity issues in section 14: Unicode feet and inch marks, decimal
   sheet IDs, filtering scale notes. Each fix starts with a failing test.
3. Per-item provenance model: source, page, sheet, method, location, confidence and
   verification status.
4. Text with positions (bounding boxes) and structured titles, notes and labels.
5. Vector geometry extraction, then scale detection with explicit confirmation, then measured
   dimensions.
6. Symbols, markers and legends.
7. OCR workflow with provenance separation.

## 18. Instructions for future sessions

Before any feature, fix or review:

1. Read this SKILL.md and `TAKEOFF_METHOD.md`, plus the docs file if you touch the schema
   or tests.
2. Inspect the repo: `git status`, branch, `git log --oneline -15 origin/main`, open PRs.
3. Review the relevant code and tests. Don't trust this file over the code.
4. Find related decisions in commit messages, PR bodies and section 10.
5. Understand the milestone: what is IMPLEMENTED and what is only PLANNED.
6. Identify regression risks to the JSON schema, the HTML report and the CLI flags.
7. Write a short plan with a verifiable check for each step.
8. Implement incrementally, in small commits.
9. Add or update tests first (TDD), and never delete tests.
10. Run `python3 -m unittest discover -s tests -v` and report the actual count.
11. Update docs: README, this skill's status tables, `.github/copilot-instructions.md`, and
    the report's `limitations` list.
12. Report the changed files, test results and remaining limitations.

**Rules for every session:**
- Don't ask the owner to repeat anything documented here. Verify facts with tools before
  asking.
- Don't assume a PLANNED feature exists.
- If a change falls outside the request or outside section 2's boundaries, say so and explain
  why before making it.

**Project subagents** live in `.claude/agents/`. The rulebook they all follow is
[`docs/agent-system.md`](../../../docs/agent-system.md): the five stages, the planning block,
who gets delegated what, the quality gates, the three review levels and the reviewer
checklist.

**Start every request with [`project-orchestrator`](../../agents/project-orchestrator.md).**
It understands the request, picks the specialists, sequences them, checks their results
against the gates, and gives the owner one decision before anything is changed or published.

| Subagent | Role | Writes files? |
|---|---|---|
| [`project-orchestrator`](../../agents/project-orchestrator.md) | Intake, plan, assignments, dependencies, deadlines, gates, one decision | No |
| [`pdf-drawing-specialist`](../../agents/pdf-drawing-specialist.md) | PDF extraction, sheet index, OCR flags, scale and unit detection | Yes |
| [`architectural-plan-reviewer`](../../agents/architectural-plan-reviewer.md) | Floor plans, elevations, sections, doors, windows, finishes | Project files only |
| [`structural-plan-reviewer`](../../agents/structural-plan-reviewer.md) | Foundations, concrete, rebar, steel, framing | Project files only |
| [`mep-civil-reviewer`](../../agents/mep-civil-reviewer.md) | Mechanical, electrical, plumbing and civil scope | Project files only |
| [`quantity-takeoff-agent`](../../agents/quantity-takeoff-agent.md) | Linear, area, volume, count and assembly quantities | Project files only |
| [`cost-estimator`](../../agents/cost-estimator.md) | Material, labor, equipment, subcontractor and pricing | Project files only |
| [`senior-estimator-reviewer`](../../agents/senior-estimator-reviewer.md) | Independent quantity and cost review (Level 2) | No |
| [`qa-compliance-reviewer`](../../agents/qa-compliance-reviewer.md) | Completeness, consistency, formulas, traceability (Level 3) | No |
| [`report-proposal-specialist`](../../agents/report-proposal-specialist.md) | BOQ, estimate, exclusions, assumptions and the final PDF | Project files only |
| [`architect-reviewer`](../../agents/architect-reviewer.md) | Software architecture: system design, data flow, API and CLI contracts, performance | No |
| [`qa-test-runner`](../../agents/qa-test-runner.md) | Failing test first, the real suite, the actual counts | Tests |
| [`takeoff-domain-reviewer`](../../agents/takeoff-domain-reviewer.md) | Business boundaries and estimator wording | No |

Status: the subagents are a way of working. They add no code capability. Each project agent
passed two trials on a synthetic plan set (2026-11-17), with the agent files of that date.
Agents ran again on synthetic sets during the PR #11 review (2026-11-22 and 2026-11-23;
`docs/agent-system.md` section 1). None has been run on a real plan set (NOT VERIFIED). A
quantity an agent reads from a drawing is unverified until the estimator checks it.

Every project agent must leave an evidence package (`docs/agent-system.md` section 9): one
row per item with its own ID, the IDs it is based on, the string as printed and where it is
on the sheet, the commands it ran, and a `SHA256SUMS` file that `shasum -a 256 -c` can
check. A second trial on the same synthetic set (2026-11-17) ran all ten agents with these
rules. Every result could be checked from the files alone, and the QA reviewer and the
orchestrator each caught 3 of 3 planted defects. The special cases, the rule on where
files go and the second Level 2 pass came out of that trial. Agents ran again during the
PR #11 review (`docs/agent-system.md` section 1), but no run with the agent files as
committed here is recorded (NOT VERIFIED).

No subagent commits, pushes, opens PRs, sends, delivers or authorizes. The owner does.
