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
sheet number when one is found (after a SHEET or DWG label, or a lone title-block code such
as `A-3`), dimension-like strings exactly as printed, and a keyword-based discipline guess
with the matched terms. Pages with fewer than
`--min-text-chars` characters are flagged for OCR or visual review.

**Limits:** only text embedded in the PDF is read. There is no OCR, no symbol recognition,
no geometry, no scale calibration and no quantities. Dimension strings are not converted or
checked against scale, and the discipline guess is a keyword heuristic. Review every page
against the original drawing before using the report.

A damaged or password-protected PDF stops with a one-line `error:` message and exit code 1.

### Page rendering and symbol candidates (`visual_inspect.py`)

```bash
python3 visual_inspect.py path/to/plans.pdf
python3 visual_inspect.py path/to/plans.pdf --template path/to/symbol-crop.png --threshold 0.82
```

Template matching is sensitive to symbol scale, rotation, line weight, and scan quality. It is only a starting point for consistent drawings. Inspect every result and the plan legend; adjust the threshold to reduce missed or false matches. Avoid using the candidate count as a final quantity without human verification.

## Framing takeoff: wall plates

The first framing formula calculates baseline wall-plate linear footage:

```python
from framing_takeoff import calculate_plate_lf

total_lf = calculate_plate_lf(
    wall_length_ft=20,
    plate_courses=3,
    waste_percent=5,
)
print(total_lf)  # 63.0 LF
```

Formula: `wall length × plate courses × (1 + waste_percent / 100)`.

The default waste allowance is 5%. This is a baseline linear-footage estimate only. It does not derive the plate build-up or wall segments from drawings. Plate assemblies must be defined separately: bottom plates stop at openings, and single/double top plates must be counted according to the applicable wall assembly. Account for corners, intersections, laps, splices, and project-specific details before procurement. Do not use a generic linear-footage multiplier as a substitute for that assembly takeoff.

### Stock-length cutting plan

When the actual cut pieces and supplier stock lengths are known, use the cutting-plan helper:

```python
from framing_takeoff import plan_stock_cuts

plan = plan_stock_cuts(
    cut_lengths_ft=[6, 4, 3],
    stock_lengths_ft=[8, 10, 12, 16],
    kerf_ft=0.01,
)
for board in plan["boards"]:
    print(board)
print("Stock LF:", plan["total_stock_lf"])
print("Offcut LF:", plan["offcut_lf"])
```

This uses a best-fit-decreasing heuristic: longer cuts are assigned first, then placed into the existing board that leaves the least offcut. Remaining offcuts can be reused by later cuts in the same input batch. It is a practical heuristic, not a guarantee of the globally cheapest or smallest purchase.

The stock-length planner requires explicit cut lengths and available stock lengths; it does not assume a supplier's inventory. Kerf is configurable. It does not add another 5% reserve because the cutting plan already accounts for cut waste and offcuts; avoid double-counting the 5% allowance from the baseline LF estimator. Keep different plate assemblies or project scopes in separate batches when offcut reuse between them is not permitted.

**Important:** the planner only optimizes a list of cuts supplied to it. It does not read drawings or determine bottom/top plate lengths, opening interruptions, corners, intersections, bearing conditions, or fire-wall assembly requirements. Those must be resolved from the plans/specifications and project RFIs before generating purchase quantities.

Run the unit tests:

```bash
python -m unittest discover -s tests -v
```
