# Copilot instructions

## Project shape

This repository is a small Python starter with two separate pieces:

- `visual_inspect.py` is the user-facing CLI. It renders each PDF page to PNG with `pypdfium2`, converts the rendered image for OpenCV, and optionally searches for a cropped symbol template. Template-match boxes are visual-review candidates, not verified takeoff quantities.
- `vector_takeoff.py` contains a standalone geometry helper. `distance_feet` computes the Euclidean distance between two drawing-space points and divides by a verified drawing-units-per-foot scale. Its tests are in `tests/test_vector_takeoff.py`.

The README documents CLI usage and cautions that template matching is sensitive to drawing conditions. Keep that human-verification limitation clear anywhere candidate matches or counts are presented.

## Commands

Install the CLI dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Run the full test suite (also used by `.github/workflows/validate.yml`):

```bash
python -m unittest discover -s tests -v
```

Run one test:

```bash
python -m unittest tests.test_vector_takeoff.DistanceFeetTests.test_converts_distance_using_drawing_scale -v
```

There is no configured build or lint command. The GitHub Actions validation currently runs the unit tests on Python 3.11.

## Code-specific conventions

- Keep the formula helper independent from PDF/image-processing code; it has no third-party dependencies and validates finite two-coordinate points and a positive finite scale.
- Keep CLI argument validation in `parse_args` and execution behind `main`, so the module remains importable without running the command.
- Treat PDF pages and documents as resources that must be closed, including when rendering fails.
- Template matching runs on grayscale images, uses non-maximum suppression to reduce clustered peaks, and caps returned annotations with `--max-matches`. Preserve these as review aids; do not describe the threshold or candidate count as proof of a correct quantity.
