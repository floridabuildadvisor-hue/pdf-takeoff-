# PDF Drawing Intelligence: reference

This is the supporting reference for the project skill at
[`.claude/skills/pdf-drawing-intelligence/SKILL.md`](../.claude/skills/pdf-drawing-intelligence/SKILL.md).
Everything here was checked on 2026-11-10. `pdf_intelligence.py` and `visual_inspect.py`
were checked at `7f03e37`, and they are unchanged at `35e9194`. `vector_takeoff.py` and the
test count were checked at `35e9194`. Re-check them if the code has changed since then.

> **Update 2026-11-17:** the extraction functions, error handling and tests changed after
> this reference was written. The dated notes at the top of the skill list the changes and
> supersede the matching rows in sections 2 to 5 below. The JSON keys and
> `schema_version` are unchanged.

## 1. JSON report, `schema_version` "1.0"

The report is produced by `analyze_pdf()` and written by the CLI to `--output`.

```text
schema_version     "1.0"
source_file        PDF basename only (no directory, no hash)
page_count         int
summary
  pages_by_classification            {category: page count}, sorted by key
  pages_needing_ocr_or_visual_review [page_number, ...] where low_text_content is true
  pages_with_sheet_numbers           int
  pages_with_dimension_tokens        int
metadata           {key: str(value)} from pdfium; None dropped, empty strings kept
pages[]
  page_number        1-based int
  dimensions         {width_pt, height_pt, width_in, height_in, orientation}
                     size as displayed (after /Rotate); orientation is
                     landscape | portrait | square
  rotation_degrees   int from page.get_rotation()
  text_char_count    non-whitespace characters of embedded text
  low_text_content   bool: text_char_count < min_text_chars (default 20)
  review_status      "needs_ocr_or_visual_review" | "text_extracted_visual_review_required"
  sheet_number       str | null (first labeled match only)
  classification     {category, confidence: high|medium|low, evidence: [matched terms]}
  dimension_tokens   [str, ...] exactly as printed
  text_preview       first 500 chars, whitespace collapsed
limitations        [str, ...]: fixed list; update it when capabilities change
```

Classification categories: `architectural`, `structural`, `civil_site`, `mechanical`,
`plumbing`, `electrical`, `fire_protection`, `cover_index`, `unknown`. The keyword lists are
in `_CLASSIFICATION_TERMS`.

## 2. Functions in `pdf_intelligence.py`

| Function | Behavior | Raises |
|---|---|---|
| `classify_sheet(text)` | Lowercases the text, collapses whitespace, then substring-matches keywords. Most distinct terms wins. A tie or no match gives `unknown`/`low`. | none |
| `extract_sheet_number(text)` | First `SHEET` / `SHEET NO.` / `SHEET NUMBER` / `DWG NO.` label, then 0 to 3 letters, an optional `-` or `.`, 1 to 4 digits, and an optional letter. Whitespace is removed and `.` becomes `-`. | none |
| `extract_dimension_tokens(text)` | Regex for `X'-Y"`, `X'-Y Z/W"`, `X'`, `Y"` and `Y Z/W"`. ASCII marks only. | none |
| `_page_dimensions(w_pt, h_pt)` | Converts to inches at 72 pt per inch and sets the orientation | `ValueError` if a side is ≤ 0 |
| `analyze_pdf(pdf_path, min_text_chars=20)` | Builds the full report dict | `FileNotFoundError`, `ValueError` (bad `min_text_chars`), `RuntimeError` (no pypdfium2). A corrupt PDF raises `pypdfium2.PdfiumError` unhandled. |
| `build_html_report(report, rendered_pages=None)` | Self-contained HTML. `rendered_pages` maps `"1"` to `"pages/page-001.png"`. Everything is escaped. | `KeyError` if required page keys are missing |
| `render_pdf_pages(pdf_path, output_dir, dpi=100)` | Writes `page-NNN.png` and returns their paths | `ValueError` (bad dpi), `RuntimeError` (no pypdfium2). Missing Pillow raises `ModuleNotFoundError` unhandled. |
| `main()` | CLI: JSON, then PNGs, then HTML, then a printed summary | propagates all of the above as tracebacks |

CLI flags: `pdf` (positional), `--output` (default `output/pdf_diagnostics/report.json`),
`--min-text-chars` (default 20), `--dpi` (default 100). The HTML goes to
`--output` with an `.html` suffix. The PNGs go to `<output dir>/pages/`.

`visual_inspect.py` flags: `pdf`, `--output` (default `output/rendered`), `--dpi` (200),
`--template`, `--threshold` (0.82, must be 0 to 1), `--max-matches` (200). It imports `cv2`,
`numpy` and `pypdfium2` at module load.

`vector_takeoff.py` (at `35e9194`), standard library only:

| Function | Behavior | Raises `ValueError` when |
|---|---|---|
| `distance_feet(start, end, drawing_units_per_foot)` | Straight-line distance divided by the scale | a point doesn't have exactly 2 finite coordinates, or the scale is not positive and finite |
| `polyline_length_feet(points, drawing_units_per_foot)` | Sum of the segment lengths. Fewer than 2 points gives 0. | same as above |
| `deduct_openings(length_ft, opening_lengths_ft)` | Length minus the sum of the openings | a value is negative or not finite, or the openings exceed the length |
| `stud_count(length_ft, spacing_ft)` | `ceil(length / spacing) + 1`, and 0 for a zero length. No corners, openings or posts. | length < 0, spacing ≤ 0, or not finite |
| `plate_length_feet(length_ft, plate_count=2)` | Length times plate count. No waste allowance. | length < 0 or not finite, or plate count not a positive int (a bool is rejected) |

## 3. Verification log, 2026-11-10

Environment: macOS, system Python 3.9.6, a fresh venv with `pip install -r requirements.txt`.
That installed pypdfium2 5.15.2, numpy 2.0.2 and opencv-python-headless 5.0.0.93, and **no
Pillow**.

| Check | Result |
|---|---|
| `python3 -m unittest discover -s tests -v` at `7f03e37` | 11 tests, all pass |
| Same command at `35e9194` | 14 tests, all pass |
| CLI on a synthetic 3-page PDF (text page, blank page, 36x24 in page with `/Rotate 90`), requirements only | JSON written, then `ModuleNotFoundError: No module named 'PIL'`. No HTML, no PNGs, exit 1. |
| Same run after `pip install pillow` (11.3.0) | Exit 0. `report.json`, `report.html`, `pages/page-001..003.png`. |
| Page 2 (no text) | `low_text_content` true, `needs_ocr_or_visual_review`, `unknown` |
| Page 3 (rotated) | Reported 24x36 in portrait, `rotation_degrees` 90, `S-201`, `structural`/high |
| Page 1 text `24'-6"` in Helvetica | pdfium returned `24’-6"` (U+2019), so the token was `6"` only |
| Corrupt file (`not a pdf`) | Raw `PdfiumError: Failed to load document (Data format error)` traceback |
| Missing file | `FileNotFoundError: PDF not found: ...` traceback |
| Metadata on a PDF with no Info dict | 8 keys with empty-string values |
| Documented flags `--output .../diagnostics.json --min-text-chars 20 --dpi 100` | `diagnostics.json`, `diagnostics.html`, `pages/page-001..003.png` |
| `visual_inspect.py <pdf> --output <dir>` (with Pillow) | 3 PNGs rendered. `--template` was not run. |

The edge-case probe of the extraction functions gave these results:

| Input | Result |
|---|---|
| `SHEET A1.01` | `A1` |
| `SHEET: S2.1` | `S2` |
| `SHEET 1 OF 15` | `1` |
| `SHEET NOTES 1` | `TES1` |
| `12′-0″` (primes) | `[]` |
| `1/4" = 1'-0"` | `['4"', "1'-0\""]` |
| `12'-6 1/2"` | kept whole (correct) |
| `EL. 10.5'` | `10.5'` |

## 4. Test inventory

| File | Test | Covers |
|---|---|---|
| `test_pdf_intelligence.py` | `test_identifies_structural_sheet_from_multiple_signals` | classification, evidence, `high` confidence |
| | `test_unknown_page_is_not_forced_into_a_discipline` | `unknown`/`low` |
| | `test_architectural_sheet_classification` | architectural category |
| | `test_extracts_sheet_number_from_labeled_title_block_text` | `SHEET NO.: A-101` |
| | `test_extracts_dimension_strings_without_converting_them` | `24'-6"`, `36"` kept as printed |
| | `test_html_report_escapes_text_and_links_rendered_pages` | escaping, preview link |
| | `test_analyzes_pages_and_flags_image_only_page` | mocked 2-page doc, metadata, low-text flag, `review_status` |
| `test_vector_takeoff.py` | `test_converts_distance_using_drawing_scale` | `distance_feet` |
| | `test_polyline_sums_segment_lengths` | `polyline_length_feet` |
| | `test_deducts_openings` | `deduct_openings` |
| | `test_rejects_openings_larger_than_wall` | openings larger than the wall |
| | `test_stud_count_includes_both_wall_ends` | `stud_count` |
| | `test_plate_length_uses_plate_count` | `plate_length_feet` |
| | `test_rejects_invalid_inputs` | bad scales (0, -1, inf, nan), a negative stud length, a negative opening, a plate count of 0. Invalid points are no longer tested. |

## 5. Test gap matrix

| Area | Covered | Gap |
|---|---|---|
| Valid real PDF | no (mocked only) | add a small committed fixture PDF (synthetic, no client data) |
| Invalid, corrupt or encrypted PDF | no | expect a clear error, not a raw traceback |
| Multi-page set | 2-page mock | real multi-page fixture |
| Rotated pages | no | 90, 180 and 270 with expected displayed size and orientation |
| Page sizes, orientation | no | letter, 24x36, 36x48, square |
| Searchable vs scanned vs mixed | blank-page mock | image-only page, outlined text, text title block over a scan |
| Missing metadata | no | `get_metadata_dict` raising, or returning empty values |
| Classification | 3 cases | ties, all categories, misleading notes |
| Sheet numbers | 1 case | decimal IDs, unlabeled IDs, `SHEET 1 OF 15`, false positives |
| Dimension tokens | 1 case | Unicode marks, fractions, scale notes, inch-only, stacked fractions |
| Geometry, scale, symbols, OCR | n/a | PLANNED. Write the tests before the code. |
| Rendering and CLI | no | `render_pdf_pages`, the `main()` output files, missing Pillow |
| `visual_inspect.py` | no | rendering and template-match candidates |
