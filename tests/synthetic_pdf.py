"""Build small synthetic PDFs for tests. No project or client data.

Run ``python3 tests/synthetic_pdf.py`` from the repo root to rewrite
``tests/fixtures/synthetic_plan_set.pdf``. The output is deterministic, and a
test checks that the committed file matches this builder.
"""

from __future__ import annotations

from pathlib import Path

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "synthetic_plan_set.pdf"

# Each page: (width_pt, height_pt, /Rotate, text lines top to bottom).
# Helvetica with the standard encoding draws ASCII ' as a typographic quote,
# which is how many real plan sets come out of text extraction.
_PLAN_SET_PAGES = (
    (2592, 1728, 0, (
        "SYNTHETIC TEST SHEET - NOT A PROJECT DRAWING",
        "ARCHITECTURAL FLOOR PLAN",
        "OVERALL 24'-6\"",
        "SCALE: 1/4\" = 1'-0\"",
        "SHEET NO. A1.01",
    )),
    (2592, 1728, 0, ()),
    (2592, 1728, 90, (
        "SYNTHETIC TEST SHEET - NOT A PROJECT DRAWING",
        "FOUNDATION PLAN AND FOOTING SCHEDULE",
        "SHEET 3 OF 3",
        "S-2",
    )),
)


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _assemble(objects: list[bytes], trailer_extra: bytes = b"") -> bytes:
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref_at = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += (
        b"trailer\n<< /Size %d /Root 1 0 R%s >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objects) + 1, trailer_extra, xref_at)
    )
    return bytes(out)


def _document_objects(pages) -> list[bytes]:
    # 1 catalog, 2 page tree, 3 font, then a page and a content stream per page.
    kids = " ".join(f"{4 + 2 * index} 0 R" for index in range(len(pages)))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for index, (width, height, rotate, lines) in enumerate(pages):
        content_number = 5 + 2 * index
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] "
            f"/Rotate {rotate} /Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {content_number} 0 R >>".encode("ascii")
        )
        stream = "".join(
            f"BT /F1 24 Tf 72 {height - 100 - 60 * row} Td ({_escape(line)}) Tj ET\n"
            for row, line in enumerate(lines)
        ).encode("ascii")
        objects.append(
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream"
        )
    return objects


def build_plan_set_pdf() -> bytes:
    """Three pages: a text sheet, a blank page and a /Rotate 90 sheet."""
    return _assemble(_document_objects(_PLAN_SET_PAGES))


def build_stacked_fraction_pdf() -> bytes:
    """One page with 13'-1 1/2" drawn the way plan fonts stack the fraction."""
    stream = (
        b"BT /F1 24 Tf 72 500 Td (OVERALL 13'-1) Tj ET\n"
        b"BT /F1 18 Tf 244 509 Td (1) Tj ET\n"
        b"BT /F1 18 Tf 244 493 Td (2) Tj ET\n"
        b"BT /F1 24 Tf 256 500 Td (\") Tj ET\n"
        b"BT /F1 24 Tf 72 400 Td (SLAB 44'-0\") Tj ET\n"
    )
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [4 0 R] /Count 1 >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 792 612] "
        b"/Resources << /Font << /F1 3 0 R >> >> /Contents 5 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream",
    ]
    return _assemble(objects)


def build_password_protected_pdf() -> bytes:
    """A PDF whose encryption dictionary cannot be opened without a password."""
    objects = _document_objects(_PLAN_SET_PAGES[:1])
    objects.append(
        b"<< /Filter /Standard /V 1 /R 2 /Length 40 /P -44 "
        b"/O <" + b"11" * 32 + b"> /U <" + b"22" * 32 + b"> >>"
    )
    trailer = b" /Encrypt %d 0 R /ID [<%s> <%s>]" % (
        len(objects), b"ab" * 16, b"ab" * 16,
    )
    return _assemble(objects, trailer)


if __name__ == "__main__":
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_bytes(build_plan_set_pdf())
    print(f"Wrote {FIXTURE_PATH}")
