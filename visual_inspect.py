#!/usr/bin/env python3
"""Render PDF pages and optionally mark template-matching candidates for review.

This is a visual-inspection starter, not an automatic quantity estimator. Review
all marked candidates against the drawing and its legend before using them.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium


def render_pdf(pdf_path: Path, output_dir: Path, dpi: int) -> list[Path]:
    """Render each PDF page to a PNG and return the generated image paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    document = pdfium.PdfDocument(str(pdf_path))
    rendered_paths: list[Path] = []
    try:
        for page_index in range(len(document)):
            page = document[page_index]
            try:
                pil_image = page.render(scale=dpi / 72).to_pil().convert("RGB")
                rgb_image = np.asarray(pil_image)
                bgr_image = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)
                image_path = output_dir / f"page-{page_index + 1:03d}.png"
                if not cv2.imwrite(str(image_path), bgr_image):
                    raise OSError(f"Could not write rendered image: {image_path}")
                rendered_paths.append(image_path)
            finally:
                page.close()
    finally:
        document.close()
    return rendered_paths


def mark_template_matches(
    image_path: Path,
    template_path: Path,
    threshold: float,
    max_matches: int,
) -> int:
    """Draw non-overlapping template matches onto image_path in place."""
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not read rendered page: {image_path}")
    if template is None:
        raise ValueError(f"Could not read template image: {template_path}")

    image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    height, width = template_gray.shape
    image_height, image_width = image_gray.shape
    if height > image_height or width > image_width:
        raise ValueError(
            f"Template ({width}x{height}) is larger than page "
            f"({image_width}x{image_height}); render at a higher DPI or use a smaller template."
        )

    scores = cv2.matchTemplate(image_gray, template_gray, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(scores >= threshold)
    boxes = [[int(x), int(y), width, height] for x, y in zip(xs, ys)]
    confidences = [float(scores[y, x]) for x, y in zip(xs, ys)]

    # Non-maximum suppression keeps one box for clusters of nearby match peaks.
    indices = cv2.dnn.NMSBoxes(boxes, confidences, threshold, 0.3) if boxes else []
    selected = np.asarray(indices).reshape(-1).tolist() if len(indices) else []
    selected = sorted(selected, key=lambda i: confidences[i], reverse=True)[:max_matches]

    for rank, index in enumerate(selected, start=1):
        x, y, box_width, box_height = boxes[index]
        score = confidences[index]
        cv2.rectangle(image, (x, y), (x + box_width, y + box_height), (0, 0, 255), 2)
        cv2.putText(
            image,
            f"candidate {rank}: {score:.2f}",
            (x, max(20, y - 7)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )

    if not cv2.imwrite(str(image_path), image):
        raise OSError(f"Could not write annotated image: {image_path}")
    return len(selected)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="Input blueprint PDF")
    parser.add_argument("--output", type=Path, default=Path("output/rendered"), help="Output directory")
    parser.add_argument("--dpi", type=int, default=200, help="Render resolution (default: 200 DPI)")
    parser.add_argument("--template", type=Path, help="Optional PNG/JPG crop of one symbol to search for")
    parser.add_argument("--threshold", type=float, default=0.82, help="Template match score threshold, 0 to 1")
    parser.add_argument("--max-matches", type=int, default=200, help="Maximum candidates marked per page")
    args = parser.parse_args()
    if args.dpi <= 0:
        parser.error("--dpi must be greater than zero")
    if not 0 <= args.threshold <= 1:
        parser.error("--threshold must be between 0 and 1")
    if args.max_matches < 1:
        parser.error("--max-matches must be at least 1")
    return args


def main() -> None:
    args = parse_args()
    if not args.pdf.is_file():
        raise SystemExit(f"PDF not found: {args.pdf}")
    if args.template is not None and not args.template.is_file():
        raise SystemExit(f"Template image not found: {args.template}")

    pages = render_pdf(args.pdf, args.output, args.dpi)
    for page_path in pages:
        if args.template:
            count = mark_template_matches(page_path, args.template, args.threshold, args.max_matches)
            print(f"{page_path}: rendered; marked {count} candidate(s)")
        else:
            print(f"{page_path}: rendered")
    print("Inspect the PNGs in the output directory; candidate boxes require human verification.")


if __name__ == "__main__":
    main()
