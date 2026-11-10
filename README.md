# PDF Takeoff Starter

Starter repository for extracting information from construction PDFs.

## Render and visually inspect PDF pages

The OpenCV visual-inspection starter renders every page of a blueprint PDF to PNG. You can optionally provide a cropped symbol image (for example, an outlet symbol from the plan legend) to mark likely template matches with red boxes and scores. These candidates are for visual review, not a verified takeoff.

Install the dependencies in the Codespace terminal:

```bash
python3 -m pip install -r requirements.txt
```

Render all pages:

```bash
python3 visual_inspect.py path/to/blueprint.pdf
```

Images are saved under `output/rendered/` by default. Change the render resolution or output folder with `--dpi` and `--output`.

Search for a symbol using a tightly cropped PNG/JPG template taken from the same drawing or a similar drawing:

```bash
python3 visual_inspect.py path/to/blueprint.pdf \
  --template path/to/outlet-crop.png \
  --threshold 0.82
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
