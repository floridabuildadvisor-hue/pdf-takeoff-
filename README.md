# pdf-takeoff-

A lightweight PDF takeoff starter for validating dimensions, marking plan items, and documenting quantities in an auditable workflow.

## Core method

See [TAKEOFF_METHOD.md](TAKEOFF_METHOD.md) for the current takeoff process, QA checks, and standards for keeping measurements auditable and repeatable.

## Install

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The commands below use `python3`; inside the virtual environment use `.venv/bin/python`.

## CLI usage

### Plan-set diagnostics (`pdf_intelligence.py`)

Inventory every page of a plan set before starting a takeoff:

```bash
python3 pdf_intelligence.py path/to/plans.pdf
python3 pdf_intelligence.py path/to/plans.pdf \
  --output output/project-001/diagnostics.json --min-text-chars 20 --dpi 100
```

Outputs, all relative to the JSON path (default `output/pdf_diagnostics/report.json`):

- the JSON report;
- an HTML review page at the same path with an `.html` suffix;
- page previews under `pages/page-001.png` and onward.

For each page the report records the size as displayed, rotation, extracted text count, a
labeled sheet number when one is found, dimension-like strings exactly as printed, and a
keyword-based discipline guess with the matched terms. Pages with fewer than
`--min-text-chars` characters are flagged for OCR or visual review.

**Limits:** only text embedded in the PDF is read. There is no OCR, no symbol recognition,
no geometry, no scale calibration and no quantities. Dimension strings are not converted or
checked against scale, and the discipline guess is a keyword heuristic. Review every page
against the original drawing before using the report.

### Page rendering and symbol candidates (`visual_inspect.py`)

```bash
python3 visual_inspect.py path/to/plans.pdf
python3 visual_inspect.py path/to/plans.pdf --template path/to/symbol-crop.png --threshold 0.82
```

Pages are rendered to `output/rendered/` (200 DPI by default; change with `--dpi` and
`--output`). With `--template`, likely matches of the cropped symbol are boxed in red with
a score. Template matching is sensitive to symbol scale, rotation, line weight and scan
quality. The boxes are candidates for visual review, never a count.

### Formula helpers (`vector_takeoff.py`)

`vector_takeoff.py` has no CLI. It holds tested length and framing helpers that take
points, lengths and a verified scale from the caller.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Client files

`output/` and `*.pdf` are git-ignored. Client plans, client names, addresses and generated
reports stay local and are never committed to this public repository.

## Planned workflow

- Render PDF sheets to images for visual review
- Identify relevant symbols and dimensions
- Mark counts and measurements directly on the drawing
- Store each quantity with its formula and source sheet
- Export a BOQ in Excel or CSV for review
- Verify totals against written dimensions and plan notes
