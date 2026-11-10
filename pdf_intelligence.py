#!/usr/bin/env python3
"""Inspect construction PDF pages and create a traceable diagnostic report.

This module extracts PDF text and page metadata. It does not perform OCR,
interpret engineering intent, or certify dimensions and quantities.
"""

from __future__ import annotations

import argparse
import json
import re
from html import escape
from collections import Counter
from pathlib import Path
from typing import Any


_CLASSIFICATION_TERMS = {
    "architectural": (
        "architectural", "floor plan", "reflected ceiling", "building elevation",
        "wall section", "door schedule", "window schedule",
    ),
    "structural": (
        "structural", "foundation plan", "framing plan", "beam", "column",
        "shear wall", "footing schedule", "truss",
    ),
    "civil_site": (
        "site plan", "grading plan", "utility plan", "erosion", "boundary",
        "stormwater", "civil",
    ),
    "mechanical": (
        "mechanical", "hvac", "duct", "air handling", "mechanical schedule",
    ),
    "plumbing": (
        "plumbing", "sanitary", "domestic water", "plumbing riser",
    ),
    "electrical": (
        "electrical", "lighting plan", "power plan", "panel schedule", "one-line",
    ),
    "fire_protection": (
        "fire protection", "sprinkler", "fire alarm",
    ),
    "cover_index": (
        "cover sheet", "sheet index", "drawing index", "general notes",
        "code analysis",
    ),
}

_SHEET_NUMBER_RE = re.compile(
    r"(?:SHEET(?:\s*(?:NO\.?|NUMBER))?|DWG\.?\s*NO\.?)"
    r"\s*[:#-]?\s*([A-Z]{0,3}\s*[-.]?\s*\d{1,4}[A-Z]?)",
    re.IGNORECASE,
)

_DIMENSION_RE = re.compile(
    r"(?<![\w.])(?:"
    r"\d+(?:\.\d+)?\s*'\s*-\s*\d+(?:\s+\d+/\d+|\.\d+)?\s*\"?"
    r"|\d+(?:\.\d+)?\s*'"
    r"|\d+(?:\s+\d+/\d+|\.\d+)?\s*\""
    r")"
)


def classify_sheet(text: str) -> dict[str, Any]:
    """Return a conservative keyword classification with its evidence.

    Confidence describes the number of distinct matched terms, not a
    calibrated probability. Ambiguous ties are left as unknown.
    """
    normalized = " ".join(text.lower().split())
    scores: dict[str, list[str]] = {}
    for category, terms in _CLASSIFICATION_TERMS.items():
        matches = [term for term in terms if term in normalized]
        if matches:
            scores[category] = matches

    if not scores:
        return {"category": "unknown", "confidence": "low", "evidence": []}

    ranked = sorted(scores.items(), key=lambda item: (-len(item[1]), item[0]))
    top_score = len(ranked[0][1])
    tied = [item for item in ranked if len(item[1]) == top_score]
    if len(tied) > 1:
        return {
            "category": "unknown",
            "confidence": "low",
            "evidence": sorted({term for _, terms in tied for term in terms}),
        }

    category, evidence = ranked[0]
    confidence = "high" if len(evidence) >= 2 else "medium"
    return {"category": category, "confidence": confidence, "evidence": evidence}


def extract_sheet_number(text: str) -> str | None:
    """Extract a sheet identifier only when it follows a recognized label."""
    match = _SHEET_NUMBER_RE.search(text)
    if not match:
        return None
    return re.sub(r"\s+", "", match.group(1)).replace(".", "-")


def extract_dimension_tokens(text: str) -> list[str]:
    """Return dimension-like text exactly as printed; do not convert units."""
    return [match.group(0).strip() for match in _DIMENSION_RE.finditer(text)]


def _page_dimensions(width_pt: float, height_pt: float) -> dict[str, Any]:
    width_in = width_pt / 72
    height_in = height_pt / 72
    if width_pt <= 0 or height_pt <= 0:
        raise ValueError("PDF page dimensions must be positive")
    return {
        "width_pt": round(width_pt, 3),
        "height_pt": round(height_pt, 3),
        "width_in": round(width_in, 3),
        "height_in": round(height_in, 3),
        "orientation": "landscape" if width_pt > height_pt else (
            "portrait" if height_pt > width_pt else "square"
        ),
    }


def analyze_pdf(pdf_path: str | Path, min_text_chars: int = 20) -> dict[str, Any]:
    """Analyze each page's extractable text and physical page dimensions."""
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {path}")
    if isinstance(min_text_chars, bool) or not isinstance(min_text_chars, int) or min_text_chars < 0:
        raise ValueError("min_text_chars must be a non-negative integer")

    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise RuntimeError(
            "PDF analysis requires pypdfium2. Install dependencies with "
            "'python -m pip install -r requirements.txt'."
        ) from exc

    document = pdfium.PdfDocument(str(path))
    pages: list[dict[str, Any]] = []
    try:
        try:
            metadata = document.get_metadata_dict() or {}
        except (AttributeError, RuntimeError):
            metadata = {}

        for page_index in range(len(document)):
            page = document[page_index]
            text_page = None
            try:
                width_pt, height_pt = page.get_size()
                rotation = page.get_rotation() if hasattr(page, "get_rotation") else 0
                text_page = page.get_textpage()
                extracted_text = text_page.get_text_range() or ""
                char_count = len(re.sub(r"\s+", "", extracted_text))
                likely_scanned = char_count < min_text_chars
                pages.append({
                    "page_number": page_index + 1,
                    "dimensions": _page_dimensions(float(width_pt), float(height_pt)),
                    "rotation_degrees": int(rotation),
                    "text_char_count": char_count,
                    "likely_scanned": likely_scanned,
                    "review_status": (
                        "needs_ocr_or_visual_review" if likely_scanned
                        else "text_extracted_visual_review_required"
                    ),
                    "sheet_number": extract_sheet_number(extracted_text),
                    "classification": classify_sheet(extracted_text),
                    "dimension_tokens": extract_dimension_tokens(extracted_text),
                    "text_preview": " ".join(extracted_text.split())[:500],
                })
            finally:
                if text_page is not None and hasattr(text_page, "close"):
                    text_page.close()
                if hasattr(page, "close"):
                    page.close()
    finally:
        document.close()

    categories = Counter(page["classification"]["category"] for page in pages)
    scanned_pages = [page["page_number"] for page in pages if page["likely_scanned"]]
    return {
        "schema_version": "1.0",
        "source_file": path.name,
        "page_count": len(pages),
        "summary": {
            "pages_by_classification": dict(sorted(categories.items())),
            "pages_needing_ocr_or_visual_review": scanned_pages,
            "pages_with_sheet_numbers": sum(page["sheet_number"] is not None for page in pages),
            "pages_with_dimension_tokens": sum(bool(page["dimension_tokens"]) for page in pages),
        },
        "metadata": {str(key): str(value) for key, value in metadata.items() if value is not None},
        "pages": pages,
        "limitations": [
            "Text extraction only reads text embedded in the PDF; image-only text requires OCR.",
            "Sheet classification is keyword-based and must be checked against the drawing.",
            "Dimension tokens are returned as printed strings and are not interpreted or scale-verified.",
            "No symbols, walls, openings, geometry, quantities, or code compliance are verified by this report.",
            "Every page remains subject to estimator review before takeoff use.",
        ],
    }



def build_html_report(
    report: dict[str, Any],
    rendered_pages: dict[str, str] | None = None,
) -> str:
    """Build a self-contained visual review page with links to rendered sheets."""
    rendered_pages = rendered_pages or {}
    summary = report["summary"]
    category_rows = "".join(
        f"<li><strong>{escape(category.replace('_', ' ').title())}</strong>: {count}</li>"
        for category, count in summary["pages_by_classification"].items()
    )
    cards = []
    for page in report["pages"]:
        number = page["page_number"]
        image_path = rendered_pages.get(str(number))
        image_html = (
            f'<a href="{escape(image_path, quote=True)}"><img src="{escape(image_path, quote=True)}" '
            f'alt="Rendered PDF page {number}"></a>'
            if image_path else '<div class="no-image">Page image not rendered</div>'
        )
        classification = page["classification"]
        dimensions = page["dimensions"]
        status = "Needs OCR / visual review" if page["likely_scanned"] else "Text extracted — verify visually"
        tokens = ", ".join(page["dimension_tokens"]) or "No dimension-like text tokens found"
        preview = page["text_preview"] or "No embedded text extracted"
        sheet = page["sheet_number"] or "Sheet number not identified"
        cards.append(
            f'<article class="page-card"><div class="page-image">{image_html}</div>'
            f'<div class="page-info"><h2>Page {number} · {escape(sheet)}</h2>'
            f'<p><strong>Classification:</strong> {escape(classification["category"].replace("_", " ").title())} '
            f'({escape(classification["confidence"])} confidence)</p>'
            f'<p><strong>Evidence:</strong> {escape(", ".join(classification["evidence"]) or "None")}</p>'
            f'<p><strong>Page size:</strong> {dimensions["width_in"]} × {dimensions["height_in"]} in '
            f'({escape(dimensions["orientation"])}) · rotation {page["rotation_degrees"]}°</p>'
            f'<p><strong>Extracted text:</strong> {page["text_char_count"]} characters · '
            f'{escape(status)}</p><p><strong>Dimension-like strings:</strong> {escape(tokens)}</p>'
            f'<details><summary>Text preview</summary><pre>{escape(preview)}</pre></details>'
            f'</div></article>'
        )
    limitations = "".join(f"<li>{escape(item)}</li>" for item in report["limitations"])
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>PDF drawing diagnostics — {escape(report["source_file"])}</title>
<style>
:root {{ color-scheme: light; font-family: Inter, Arial, sans-serif; color: #18212f; background: #f3f5f7; }}
body {{ margin: 0; padding: 28px; }} main {{ max-width: 1440px; margin: auto; }}
header, .summary, .page-card, .limits {{ background: white; border: 1px solid #dce2e8; border-radius: 12px; }}
header {{ padding: 24px; }} h1 {{ margin: 0 0 8px; font-size: 26px; }} .muted {{ color: #657181; }}
.summary {{ margin: 18px 0; padding: 20px; display: flex; gap: 36px; flex-wrap: wrap; }}
.summary ul, .limits ul {{ margin: 8px 0 0; padding-left: 20px; }}
.page-card {{ display: grid; grid-template-columns: minmax(260px, 42%) 1fr; gap: 22px; padding: 18px; margin: 14px 0; }}
.page-image {{ background: #e8edf2; border-radius: 8px; padding: 8px; text-align: center; }}
.page-image img {{ display: block; max-width: 100%; max-height: 680px; width: auto; height: auto; margin: auto; }}
.no-image {{ padding: 80px 10px; color: #657181; }} .page-info h2 {{ margin-top: 0; font-size: 19px; }}
.page-info p {{ line-height: 1.45; }} pre {{ white-space: pre-wrap; overflow-wrap: anywhere; background: #f6f8fa; padding: 12px; border-radius: 6px; }}
.limits {{ padding: 18px; margin-top: 20px; }} @media (max-width: 760px) {{ body {{ padding: 12px; }} .page-card {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body><main>
<header><h1>PDF Drawing Diagnostics</h1><div class="muted">{escape(report["source_file"])} · {report["page_count"]} page(s)</div>
<p>This is a preliminary extraction report. Verify every sheet against the original PDF before takeoff.</p></header>
<section class="summary"><div><strong>Pages by likely discipline</strong><ul>{category_rows}</ul></div>
<div><strong>Pages flagged for OCR / visual review</strong><p>{escape(str(summary["pages_needing_ocr_or_visual_review"]) if summary["pages_needing_ocr_or_visual_review"] else "None")}</p></div>
<div><strong>Text recognition indicators</strong><p>Sheet numbers found: {summary.get("pages_with_sheet_numbers", 0)}<br>Pages with dimension-like strings: {summary.get("pages_with_dimension_tokens", 0)}</p></div></section>
<section aria-label="Page-by-page review">{"".join(cards)}</section>
<section class="limits"><strong>Important limitations</strong><ul>{limitations}</ul></section>
</main></body></html>"""


def render_pdf_pages(
    pdf_path: str | Path,
    output_dir: str | Path,
    dpi: int = 100,
) -> list[Path]:
    """Render all pages to PNG thumbnails for the HTML diagnostic report."""
    if isinstance(dpi, bool) or not isinstance(dpi, int) or dpi <= 0:
        raise ValueError("dpi must be a positive integer")
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise RuntimeError(
            "PDF rendering requires pypdfium2. Install dependencies with "
            "'python -m pip install -r requirements.txt'."
        ) from exc

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    document = pdfium.PdfDocument(str(pdf_path))
    rendered: list[Path] = []
    try:
        for page_index in range(len(document)):
            page = document[page_index]
            try:
                image = page.render(scale=dpi / 72).to_pil().convert("RGB")
                image_path = destination / f"page-{page_index + 1:03d}.png"
                image.save(image_path, format="PNG")
                rendered.append(image_path)
            finally:
                if hasattr(page, "close"):
                    page.close()
    finally:
        document.close()
    return rendered


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="Client construction plan PDF")
    parser.add_argument(
        "--output", type=Path, default=Path("output/pdf_diagnostics/report.json"),
        help="JSON diagnostic report path",
    )
    parser.add_argument(
        "--min-text-chars", type=int, default=20,
        help="Pages with fewer non-whitespace extracted characters are flagged for OCR/review",
    )
    parser.add_argument(
        "--dpi", type=int, default=100,
        help="Resolution for page previews in the HTML report (default: 100 DPI)",
    )
    args = parser.parse_args()

    report = analyze_pdf(args.pdf, min_text_chars=args.min_text_chars)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    rendered = render_pdf_pages(args.pdf, args.output.parent / "pages", dpi=args.dpi)
    rendered_map = {str(index + 1): f"pages/{path.name}" for index, path in enumerate(rendered)}
    html_path = args.output.with_suffix(".html")
    html_path.write_text(build_html_report(report, rendered_map), encoding="utf-8")

    print(f"Analyzed {report['page_count']} page(s) from {args.pdf}")
    print(f"Pages by classification: {report['summary']['pages_by_classification']}")
    print(f"Pages flagged for OCR/visual review: {report['summary']['pages_needing_ocr_or_visual_review']}")
    print(f"JSON report: {args.output}")
    print(f"Visual HTML report: {html_path}")
    print("Review the source drawings before relying on extracted text or classifications.")


if __name__ == "__main__":
    main()
