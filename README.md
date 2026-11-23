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

Stacked fractions are reassembled from character positions: a dimension drawn as 13'-1 with
a small 1 over a small 2 is reported as `13'-1 1/2"`, not `13'-112"`. Only clear stacks that
form a proper fraction of an inch are rewritten. Check fractional dimensions against the
drawing.

A damaged or password-protected PDF stops with a one-line `error:` message and exit code 1.

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
points, lengths and a verified scale from the caller. `plate_length_feet` there is the
plain product of wall length and plate count, with no allowance.

### Wall plates (`framing_takeoff.py`)

```python
from framing_takeoff import plate_lf_breakdown

line = plate_lf_breakdown(wall_length_ft=20, plate_courses=3, waste_percent=5)
print(line["measured_lf"])         # 60.0  (traces to the drawing)
print(line["waste_allowance_lf"])  # 3.0   (the estimator's allowance, not measured)
print(line["total_lf"])            # 63.0
print(line["formula"])             # 20 LF x 3 courses = 60 LF measured; + 5% waste allowance = 63 LF
```

`plate_lf_breakdown` adds no allowance unless a percentage is given, and keeps the measured
length and the allowance as separate values so a BOQ line can show both.
`calculate_plate_lf(wall_length_ft, plate_courses, waste_percent=5)` returns only the total
and applies 5% when no percentage is passed.

Both are baseline linear-footage formulas: wall length × plate courses. They do not read
the plate build-up or the wall segments from the drawings. Bottom plates stop at openings,
and single or double top plates are counted per wall assembly as drawn. Corners,
intersections, laps and splices are not included. Take those from the plans before the
quantity is released.

### Stock-length cutting aid (`framing_takeoff.py`)

```python
from framing_takeoff import plan_stock_cuts

plan = plan_stock_cuts(
    cut_lengths_ft=[6, 4, 3],
    stock_lengths_ft=[8, 10, 12, 16],
    kerf_ft=0.01,
)
for board in plan["boards"]:
    print(board)
print("Cut LF:", plan["total_cut_lf"])
print("Stock LF:", plan["total_stock_lf"])
print("Offcut LF:", plan["offcut_lf"])
```

The caller supplies the cut pieces and the stock lengths to consider; nothing is assumed
about what any yard carries. Up to 12 cuts are packed by an exact search for the least
stock footage, then the fewest boards. Larger batches use a best-fit-decreasing heuristic,
which is practical but not guaranteed to be the least. `plan["method"]` says which one ran.

- Kerf is charged once for every cut, including the last cut on a board, so two 8 ft pieces
  do not come out of one 16 ft board when `kerf_ft` is above zero.
- No percentage allowance is added. Do not also apply a waste percentage to the same pieces.
- Offcuts are reused only within one call. Keep assemblies or scopes in separate calls when
  offcuts should not cross between them.

**This is a cutting aid, not a takeoff quantity and not an order.** The measured quantity is
`total_cut_lf`. `total_stock_lf` depends on the stock lengths passed in. The helper does not
read drawings or work out plate lengths, opening interruptions, corners or intersections;
those come from the plans. Purchasing and supplier selection are outside this repository.

### BOQ export and dimension register (`boq.py`, `dimension_register.py`)

Neither has a CLI. `boq.export_boq(items, path)` writes BOQ lines to CSV and refuses any
line with an empty formula or source sheet, naming the item codes.
`dimension_register.validate_register(entries)` flags dimensions with no source sheet and
names that appear with different values, for the estimator to resolve against the drawings.
Neither module checks that a quantity is right.

### Evidence check and takeoff records (`evidence_package.py`, `takeoff_records.py`)

```bash
python3 -B evidence_package.py path/to/project_folder
python3 -B takeoff_records.py path/to/records.csv path/to/boq.csv
```

The first checks the evidence packages in a project's `02_Working` folder, as described in
[docs/agent-system.md](docs/agent-system.md) section 9: file hashes, record columns, IDs,
links between records, and each printed string read back from its place on the sheet. It
only reads, and its exit code is 1 when it has a finding. The second writes the takeoff
`quantity` rows as BOQ lines and prints the rows it left out and the dimensions flagged for
review. Neither recomputes a formula or checks that a quantity is right; every line still
needs the estimator's review. Both are tested on synthetic files only.

The check also reports a received file that the document inventory does not list, a path
that leaves the project, links between records that run in a circle or point to a later
stage, two revisions recorded for one page, a quantity with no place on a drawing behind
it, and a BOQ line that does not match its quantity record. Paths must be plain
project-relative paths; links out of the project are not followed. A crop image is checked
for existence only.

It prints one `SEAL` line for each received file and each package's hash list. A hash shows
that a file matches a recorded digest, not that the digest can be relied on, so the owner
keeps the `SEAL` lines and they are passed back with `--seals <file>` or `--seals -`.
[docs/agent-system.md](docs/agent-system.md) section 9 has the procedure.

The BOQ command writes no file while one quantity row is defective (for example `nan`, a
unit outside the rulebook list, no formula or no sheet), and renames a BOQ left by an
earlier run to `<boq.csv>.SUPERSEDED`. Every line it writes carries `source_revision` and
a `boq_status` that starts `DRAFT` or `PARTIAL DRAFT`. It also writes
`<boq.csv>.STATUS.txt`. A BOQ it writes is never a reviewed one.

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
