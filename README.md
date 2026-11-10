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

The default waste allowance is 5%. The result is material linear footage, not a purchase/stock-length optimization. This first version does not yet add corner/intersection allowances, laps, splices, opening adjustments, or project-specific framing conditions. Confirm the plate build-up from the applicable plans and specifications before using the result for procurement.

Run the unit tests:

```bash
python -m unittest discover -s tests -v
```
