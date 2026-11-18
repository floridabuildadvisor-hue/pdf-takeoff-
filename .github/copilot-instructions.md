# Copilot instructions

## Project shape

Python command-line tools, flat at the repo root, that read construction plan PDFs and
produce review material for a quantity takeoff. The work is extraction and organisation
only: count and measure what is drawn, and keep every value traceable to its sheet.

- `pdf_intelligence.py` is the plan-set diagnostic CLI. `analyze_pdf` inventories each page
  (size as displayed, rotation, embedded text count, labeled sheet number, dimension-like
  strings as printed, keyword discipline guess with evidence) and builds the JSON report
  (`schema_version` "1.0"). `render_pdf_pages` writes page previews and `build_html_report`
  writes the HTML review page. It does not produce quantities.
- `visual_inspect.py` renders each page to PNG with `pypdfium2` and optionally marks
  OpenCV template-match boxes for a cropped symbol. The boxes are visual-review candidates,
  not counts.
- `vector_takeoff.py` holds standard-library formula helpers: `distance_feet`,
  `polyline_length_feet`, `deduct_openings`, `stud_count` and `plate_length_feet`. Callers
  pass in points, lengths and a verified scale. Nothing here reads a PDF.
- `TAKEOFF_METHOD.md` is the owner's takeoff method: traceable BOQ lines, plan markup,
  visual and written-dimension checks, the sheet index and the verification loop. Follow
  it for any output that reaches the estimator, and change it only at the owner's request.
- `.claude/skills/pdf-drawing-intelligence/SKILL.md` and `docs/pdf-drawing-intelligence.md`
  record what is implemented, what is only planned, the JSON schema and the test gaps.
  The code wins over the docs.
- Tests: `tests/test_pdf_intelligence.py`, `tests/test_vector_takeoff.py` and
  `tests/test_repo_hygiene.py` (requirements, ignore rules, CI workflow).

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
