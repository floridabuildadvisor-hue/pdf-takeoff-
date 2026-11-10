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


## PDF drawing intelligence (first diagnostic milestone)

Inspect a client plan set before starting a material takeoff:

```bash
python3 -m pip install -r requirements.txt
python3 pdf_intelligence.py path/to/client-plans.pdf
```

The default JSON report is written to `output/pdf_diagnostics/report.json`. Choose another destination or adjust the low-text flag threshold with:

```bash
python3 pdf_intelligence.py path/to/client-plans.pdf \\
  --output output/project-001/diagnostics.json \\
  --min-text-chars 20
```

For each page, the report records PDF page dimensions (points and inches), orientation, rotation, extractable character count, a short text preview, a labeled sheet number when found, dimension-like text tokens, and a keyword-based discipline classification with its matched evidence. Pages with fewer than 20 non-whitespace text characters are flagged for OCR or visual review. The threshold is configurable.

**Interpretation limits:** This milestone extracts text embedded in PDFs. It does not yet perform OCR on scanned sheets, recognize symbols, trace wall or opening geometry, calibrate drawing scale, or calculate takeoff quantities. Dimension strings are preserved as text; they are not converted into measurements or verified against scale. Classification is a keyword heuristic, not an AI-certified sheet identification. Review every page against the original drawing before using the report for estimating.

Run tests with:

```bash
python -m unittest discover -s tests -v
```
