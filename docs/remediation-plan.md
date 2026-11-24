# Remediation plan: seven open technical gaps

Written on 2026-11-22 against `main` at `acfab9f`. The modules it covers are unchanged at
`dbce73b`, the head of PR #11 (checked 2026-11-23). Every gap below is **OPEN**. A gap is
resolved only when its tests are on `main` and the full suite passes. Until then, SKILL.md
section 14 and the gap matrix in [`pdf-drawing-intelligence.md`](pdf-drawing-intelligence.md)
section 5 keep listing it.

- **Where the code changes,** each new test must fail before the change and pass after it.
- **Where the code is already right,** and the gap is only a missing test (most of gap 6),
  the new test passes at once. It must then be shown to fail against a deliberately broken
  copy of the code, so it is known to catch a regression. Record that check in the PR.

**Rules for every fix**
- Write the failing test first and commit it as `test: ...`, then the fix as `fix: ...`.
- Keep the JSON keys stable. A new key or a changed meaning bumps `schema_version`, and
  needs the owner's approval first.
- In the same change, update SKILL.md section 14, docs sections 2, 4 and 5, and the report's
  `limitations` list in `pdf_intelligence.py` when the change affects it.
- Never weaken an existing test. Every acceptance list below also requires the full
  existing suite to pass, whether or not it names the tests.
- Synthetic PDFs only. Build new ones inside the test or with a new function in
  `tests/synthetic_pdf.py`. Never change the committed fixture: `SyntheticFixtureTests`
  compares it byte for byte with its builder.

## Priority order

Wrong values come first, then output that looks complete but is not, then omissions, then
behavior that is probably right but has no test.

| # | Gap | Why this rank |
|---|---|---|
| 1 | `SEE SHEET S-2` read as the sheet number | Puts a wrong sheet number in the report as if it were the title block's. Every record traced to that page inherits it. |
| 2 | A dimension token that runs across a line break | Can join text from two lines into a dimension that is not printed anywhere. |
| 3 | `.5"` with no leading zero, and a fraction right after the hyphen | Some forms are missed (`.5"`), and some return a wrong value: `6'-3/4"` gives `6'-3`, and `.5" = 1'-0"` leaks `1'-0"` as a dimension. |
| 4 | `--dpi 0` leaves `report.json` | A failed run leaves a JSON that looks like a finished one. |
| 5 | Invalid points in `vector_takeoff.py` | The checks exist but have no test, and one case passes silently. |
| 6 | 180° and 270° page rotation | Probably correct today, but no test shows it, and the `bbox` rule in `docs/agent-system.md` section 9 was checked only at 0° and 90°. |
| 7 | `visual_inspect.py` has no tests | An older tool. Its output is review candidates only, never counts. |

## 1. A cross-reference read as the sheet number

- **Status:** OPEN.
- **Module:** `pdf_intelligence.py`, `extract_sheet_number`, `_SHEET_NUMBER_RE`.
- **Now:** the first labeled match anywhere in the text wins. `WALL TYPES, SEE SHEET S-2\nA-6`
  gives `S-2`, and `REFER TO SHEET A-501 FOR DETAILS\nA-2` gives `A-501` (probes on
  2026-11-22). No test covers this.
- **Expected:**
  - A label that follows a cross-reference word on the same line (`SEE`, `REFER TO`,
    `PER`, `ON`) is not a sheet-number match.
  - A labeled match at the start of a line ranks first, then the lone-code rule, then any
    other labeled match.
- **Missing tests:**
  - `WALL TYPES, SEE SHEET S-2\nA-6` gives `A-6`.
  - `REFER TO SHEET A-501 FOR DETAILS\nA-2` gives `A-2`.
  - `SEE SHEET S-2` alone on the page gives `None`.
  - `SEE SHEET S-2\nSHEET NO. A-101` gives `A-101`.
  - A real-PDF test: a synthetic sheet with a cross-reference note and a title-block code.
- **Acceptance:**
  - The tests above pass.
  - All 21 tests in `test_pdf_intelligence.py` and the `A1.01` and `S-2` real-PDF tests
    still pass. One of them, `test_analyzes_pages_and_flags_image_only_page`, already
    covers a mid-line label with no cross-reference word
    (`ARCHITECTURAL FLOOR PLAN SHEET NO. A-101` gives `A-101`).
  - The `limitations` text about sheet numbers is updated.
- **Regression risks:**
  - Real title blocks where text extraction puts the label mid-line after other text.
    Keeping those as the last-resort rule limits this.
  - The word list can miss other phrasings (`AS SHOWN ON`, `SIM. TO`), so keep the
    "check every sheet number against the title block" rule.
- **Separate decision (not in this fix):** a `sheet_number_source` field (`label`,
  `lone_code`) would close the related gap, "the report does not say which rule matched".
  It is a schema change, so it needs the owner's approval and a `schema_version` bump.

## 2. A dimension token that runs across a line break

- **Status:** OPEN.
- **Module:** `pdf_intelligence.py`, `extract_dimension_tokens`, `_DIMENSION_RE` (and
  `_SCALE_NOTE_RE`, which uses the same spacing).
- **Now:** the spaces allowed between the parts of a token (`\s`) include line breaks.
  `24'-\n6"` gives one token, `24'-\n6"`. No test covers this.
- **Expected:**
  - A token never contains `\n` or `\r`.
  - A dimension split by a line break gives no token: neither `24'` nor `6"`, because
    each fragment would look like a real dimension.
  - Tokens on separate lines are unaffected.
- **Missing tests:**
  - `24'-\n6"` gives `[]`.
  - `6\n1/2"` gives no `6 1/2"`.
  - `WALL 24'-6"\nSLAB 4"` gives `["24'-6\"", '4"']`.
  - `24' - 6"` (spaces only) still gives one token.
  - A scale note split across two lines is still left out.
  - A real-PDF test with `24'-` and `6"` drawn as two text objects on the same baseline,
    to record whether pdfium puts a line break between them.
- **Acceptance:**
  - The tests above pass.
  - Every existing token test, all 20 stacked-fraction tests and the real-PDF token tests
    still pass.
  - The `limitations` list says that a dimension broken across lines is not read.
- **Regression risks:**
  - If pdfium inserts a line break inside a dimension that is printed on one line, that
    dimension stops being read. The same-baseline real-PDF test is the check for this.
  - Generated line breaks inside stacked fractions are already dropped by
    `stacked_fractions.py`, and its tests must stay green.

## 3. Inch forms that are missed or misread: `.5"` and `6'-3/4"`

- **Status:** OPEN.
- **Module:** `pdf_intelligence.py`, `_DIMENSION_RE` and `_SCALE_NOTE_RE`.
- **Now** (probes on 2026-11-22; no test covers any of these):
  - The look-behind that stops a token starting inside a number also stops `.5"`, so
    `.5" GAP` gives `[]`. `0.5"` and `6.5"` give tokens.
  - `.5" = 1'-0"` is not removed as a scale note, so it returns `1'-0"`, a scale written
    as a dimension.
  - In feet-inches, the inches must start with a whole number. `6'-3/4"` gives the
    fragment `6'-3`, which looks like a real dimension.
- **Expected:**
  - `.5"` and `.75"` give tokens as printed.
  - `6'-3/4"` gives `6'-3/4"`.
  - `.5" = 1'-0"` is left out as a scale note.
  - A dot right after a letter or digit still starts no token, so `A.5"` gives `[]`, and
    `1.5"` gives `1.5"`, not `.5"`.
- **Missing tests:**
  - `.5" GAP` gives `['.5"']`.
  - `0.5"` and `6.5"` give themselves.
  - `1.5"` gives `['1.5"']`.
  - `A.5"` gives `[]`.
  - `6'-3/4"` gives `["6'-3/4\""]`.
  - `.5" = 1'-0"` as a scale note gives `[]`.
- **Acceptance:** the tests above pass, and every existing token and scale-note test still
  passes.
- **Regression risks:**
  - Text such as `NO.5"` or a grid reference like `A.5` must not become tokens. Keep the
    look-behind for letters and digits before the dot.
  - Allowing a fraction after the hyphen must not swallow a following, separate number.

## 4. An invalid `--dpi` leaves `report.json` behind

- **Status:** OPEN.
- **Module:** `pdf_intelligence.py`, `main()` (and `render_pdf_pages`, which keeps its own
  check for callers that use it as a library).
- **Now:** `main()` writes the JSON before it renders. `--dpi=0` and `--dpi=-5` exit 1 with
  `report.json` written and no HTML (manual runs, 2026-11-22). `--min-text-chars=-1` exits 1
  with nothing written, because analysis fails first. A non-integer value is an argparse
  usage error (exit 2). None of this has a test.
- **Expected:**
  - Invalid `--dpi` and `--min-text-chars` values are rejected before anything is written:
    exit 1, `error: <message>`, no traceback, and no file in the output folder.
  - Other rendering failures keep the documented order (the JSON first; SKILL.md
    section 7). Changing that order is a separate decision.
- **Missing tests:**
  - CLI with `--dpi=0`, `--dpi=-5` and `--min-text-chars=-1`: exit 1, the message on
    stderr, no `Traceback`, and no `report.json`.
  - `render_pdf_pages(..., dpi=0)` and `dpi=True` raise `ValueError`.
  - `analyze_pdf(..., min_text_chars=-1)` and `min_text_chars=True` raise `ValueError`.
- **Acceptance:**
  - The tests above pass.
  - The three existing CLI tests still pass, and the success run still writes the JSON,
    the HTML and 3 previews.
- **Regression risks:**
  - Keep exit code 1. Moving the check into argparse would change it to 2 for scripts that
    check it.
  - Keep the existing error wording, which the tests match.

## 5. Invalid points in `vector_takeoff.py`

- **Status:** OPEN.
- **Module:** `vector_takeoff.py`, `_validated_point`, `distance_feet`,
  `polyline_length_feet`.
- **Now:** the code rejects a point without exactly two coordinates and a coordinate that is
  not finite, but no test covers either. Two cases are worse (probes on 2026-11-22):
  - `polyline_length_feet([(nan, 0)], 12)` returns `0`, because a single point is never
    checked.
  - `distance_feet(5, (1, 1), 12)` raises `TypeError`, not `ValueError`.
- **Expected:**
  - Every point is checked, even when there are fewer than 2.
  - A point that is not a sequence raises `ValueError`.
  - Fewer than 2 valid points still gives `0`, as documented.
- **Missing tests:**
  - `(0,)`, `(1, 2, 3)`, `(nan, 0)`, `(inf, 0)` and `("a", 0)` in `distance_feet`.
  - The same points inside `polyline_length_feet`, including a single-point list.
  - A non-sequence point.
  - Bad scales in `polyline_length_feet`.
  - Negative lengths in `deduct_openings` and `plate_length_feet`.
  - A `bool` plate count.
- **Acceptance:** the tests above pass, and the 7 existing tests still pass.
- **Regression risks:**
  - A caller that relied on `polyline_length_feet` returning `0` for a single bad point
    will now get an error. No caller in this repo does.

## 6. 180° and 270° page rotation

- **Status:** OPEN.
- **Module:** `pdf_intelligence.py`, `analyze_pdf` and `_page_dimensions` (pdfium's
  `get_size` and `get_rotation`), and `stacked_fractions.py`, which reads the baseline
  direction from neighbouring characters.
- **Now:** only `/Rotate 90` is tested. 180° and 270° are NOT VERIFIED. The `bbox`
  convention in `docs/agent-system.md` section 9 (PDF points, origin bottom left, before
  `/Rotate`) was checked at 0° and 90° only.
- **Expected:**
  - At 180° the displayed size and orientation equal the media box.
  - At 270° they are swapped, as at 90°.
  - `rotation_degrees` is 180 or 270.
  - Text, the sheet number and dimension tokens are read as on an unrotated page.
- **Missing tests:**
  - A new builder function (for example `build_rotation_set_pdf()`) with one page at each
    of 0°, 90°, 180° and 270°, read with real pypdfium2. Check `rotation_degrees`, the
    displayed inches, orientation, `sheet_number` and `dimension_tokens`.
  - A stacked fraction on a 180° and a 270° page.
  - A `get_charbox` check at 180° and 270° for the section 9 convention.
- **Acceptance:**
  - The tests above pass, and the committed fixture is unchanged.
  - If pdfium reports something else, the test records the actual behavior, the gap
    becomes a bug with its own fix, and the docs say so.
- **Regression risks:**
  - Changing the committed fixture would break `SyntheticFixtureTests`. Build the new PDF
    in the test instead.

## 7. `visual_inspect.py` has no tests

- **Status:** OPEN.
- **Module:** `visual_inspect.py`: `render_pdf`, `mark_template_matches`, `parse_args`,
  `main`.
- **Now:**
  - No test imports it.
  - It imports `cv2`, `numpy` and `pypdfium2` at module load.
  - A corrupt PDF prints a raw `PdfiumError` traceback (manual run, 2026-11-22), because
    it opens files without `pdf_intelligence._open_document`.
  - Rendering ran once, unmocked, on a synthetic 3-page PDF on 2026-11-10. Template matching
    has no recorded run.
- **Expected:**
  - Rendering writes one PNG per page, about `points / 72 * dpi` pixels on each side.
  - Template matching marks at most `--max-matches` boxes, each labeled "candidate", and
    returns their number.
  - A template larger than the page and an unreadable image raise `ValueError`.
  - A corrupt or password-protected PDF gives a clear error with no traceback.
- **Missing tests:**
  - Render the 3-page fixture at 72 and 144 DPI and check the file names and pixel sizes.
  - A synthetic page with a drawn symbol repeated N times, the template cropped from the
    rendered page: N candidates at the default threshold, and no more than `--max-matches`.
  - A template larger than the page; a missing template file.
  - `parse_args` rejecting `--dpi 0`, `--threshold 1.5` and `--max-matches 0` (exit 2).
  - A corrupt PDF.
- **Acceptance:**
  - The tests above pass in CI with the pinned `opencv-python-headless`.
  - The output wording stays "candidate" and never "count".
- **Regression risks:**
  - Match scores can differ between OpenCV builds, so assert counts on high-contrast
    synthetic shapes, not exact scores.
  - The module-level import means the test file fails to import without OpenCV. CI
    installs it from `requirements.txt`, but a local run without it fails rather than
    skips.

## Suggested PR boundaries

1. **Gaps 1, 2 and 3:** extraction rules in `pdf_intelligence.py`, with their tests, the
   `limitations` list and the docs. They share the regexes, so test them together.
2. **Gap 4:** the CLI check order, with CLI tests.
3. **Gaps 5 and 6:** mostly tests, plus the small `vector_takeoff.py` change.
4. **Gap 7:** `visual_inspect.py` tests, and the error-handling change if the owner wants it.
