# Copilot instructions

## Project shape

Python command-line tools, flat at the repo root, that read construction plan PDFs and
produce review material for a quantity takeoff. The work is extraction and organisation
only: count and measure what is drawn, and keep every value traceable to its sheet.

- `pdf_intelligence.py` is the plan-set diagnostic CLI. `analyze_pdf` inventories each page
  (size as displayed, rotation, embedded text count, sheet number from a label or a lone
  title-block code, dimension-like strings as printed, keyword discipline guess with
  evidence) and builds the JSON report
  (`schema_version` "1.0"). `render_pdf_pages` writes page previews and `build_html_report`
  writes the HTML review page. It does not produce quantities.
- `stacked_fractions.py` reassembles stacked fractions from character positions, so text
  that extraction returns as `13'-112"` is read as `13'-1 1/2"`. `analyze_pdf` runs every
  page through it. It rewrites only clear stacks that form a proper fraction of an inch
  and leaves everything else exactly as extracted.
- `visual_inspect.py` renders each page to PNG with `pypdfium2` and optionally marks
  OpenCV template-match boxes for a cropped symbol. The boxes are visual-review candidates,
  not counts.
- `vector_takeoff.py` holds standard-library formula helpers: `distance_feet`,
  `polyline_length_feet`, `deduct_openings`, `stud_count` and `plate_length_feet`. Callers
  pass in points, lengths and a verified scale. Nothing here reads a PDF.
- `framing_takeoff.py` holds wall-plate formulas and a cutting aid, standard library only.
  `plate_lf_breakdown` returns the measured length, the waste allowance and the total as
  separate values (no allowance unless one is given). `calculate_plate_lf` returns only
  the total and defaults to 5%. `plan_stock_cuts` packs caller-supplied cuts into
  caller-supplied stock lengths; it is a cutting aid, not a takeoff quantity or an order.
- `boq.py` exports BOQ lines to CSV with `export_boq(items, path)`. Columns: `item_code`,
  `quantity`, `unit`, `formula`, `source_sheet`, `notes`, `reviewer_initials`. A line with
  an empty formula or source sheet stops the export with a `ValueError` naming the codes.
- `dimension_register.py` checks a list of dimensions read from the plans with
  `validate_register(entries)`. It flags entries with no source sheet and names printed
  with different values. It only flags; it never chooses a value.
- `TAKEOFF_METHOD.md` is the owner's takeoff method: traceable BOQ lines, plan markup,
  visual and written-dimension checks, the sheet index and the verification loop. Follow
  it for any output that reaches the estimator, and change it only at the owner's request.
- `.claude/skills/pdf-drawing-intelligence/SKILL.md` and `docs/pdf-drawing-intelligence.md`
  record what is implemented, what is only planned, the JSON schema and the test gaps.
  The code wins over the docs.
- Tests: `tests/test_pdf_intelligence.py`, `tests/test_vector_takeoff.py`, `tests/test_boq.py`,
  `tests/test_framing_takeoff.py`,
  `tests/test_stacked_fractions.py`,
  `tests/test_dimension_register.py`,
  `tests/test_repo_hygiene.py` (requirements, ignore rules, CI workflow) and
  `tests/test_real_pdf.py`, which reads the synthetic fixture
  `tests/fixtures/synthetic_plan_set.pdf` with real pypdfium2. Rebuild the fixture with
  `python3 tests/synthetic_pdf.py`.

## Commands

Install the dependencies (pinned, including Pillow for page rendering):

```bash
python3 -m pip install -r requirements.txt
```

Run the full test suite (also run by `.github/workflows/validate.yml` on Python 3.11):

```bash
python3 -m unittest discover -s tests -v
```

Run one test:

```bash
python3 -m unittest tests.test_vector_takeoff.VectorTakeoffTests.test_converts_distance_using_drawing_scale -v
```

Run the CLIs:

```bash
python3 pdf_intelligence.py path/to/plans.pdf
python3 visual_inspect.py path/to/plans.pdf --template path/to/symbol-crop.png
```

There is no build or lint command.

## Rules

- Use estimator language only: "extracted", "measured", "flagged for review", "as printed
  on sheet X". Never "meets code", "certified", "approved", "engineered" or
  "structural/mechanical audit".
- This repository is public. Never commit client PDFs, names, addresses or generated
  reports. `output/` and `*.pdf` are git-ignored. Fixtures are synthetic or plain strings.
- Write the failing test first and commit it as `test:` before the `feat:` or `fix:`
  commit. Never delete, skip or weaken a test.
- Never invent a missing dimension or scale. Use `None` or `unknown` and flag it.

## Code-specific conventions

- `pdf_intelligence.py` imports `pypdfium2` lazily inside its functions so the module
  imports with the standard library only and tests can substitute it through
  `sys.modules`. Keep that pattern.
- Keep parsing, extraction, classification, diagnostics and presentation as separate
  functions. Put new capabilities in new modules.
- Preserve existing JSON keys. Bump `schema_version` on any schema change and update the
  report's `limitations` list when capabilities change.
- Dimension strings are kept exactly as printed and never converted or scaled.
- Every page needs visual review; there is no accepted status.
- Escape every PDF-derived string in the HTML report.
- Keep the formula helpers free of third-party dependencies and keep validating inputs
  (finite two-coordinate points, positive finite scale, non-negative lengths).
- In `visual_inspect.py`, keep argument validation in `parse_args` and execution behind
  `main`. Close PDF pages and documents even when rendering fails.
- Template matching runs on grayscale images, uses non-maximum suppression and caps the
  boxes with `--max-matches`. Do not describe the threshold or the candidate count as a
  verified quantity.
- Keep `from __future__ import annotations`; local Python is 3.9.
