#!/usr/bin/env python3
"""Inspect construction PDF pages and create a traceable diagnostic report.

This module extracts PDF text and page metadata. It does not perform OCR,
interpret engineering intent, or certify dimensions and quantities.
"""

from __future__ import annotations

import argparse
import json
import re
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
    args = parser.parse_args()

    report = analyze_pdf(args.pdf, min_text_chars=args.min_text_chars)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Analyzed {report['page_count']} page(s) from {args.pdf}")
    print(f"Pages by classification: {report['summary']['pages_by_classification']}")
    print(f"Pages flagged for OCR/visual review: {report['summary']['pages_needing_ocr_or_visual_review']}")
    print(f"Diagnostic report: {args.output}")
    print("Review the source drawings before relying on extracted text or classifications.")


if __name__ == "__main__":
    main()
