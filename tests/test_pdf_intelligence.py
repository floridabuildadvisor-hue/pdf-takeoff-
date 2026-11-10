import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from pdf_intelligence import (
    analyze_pdf,
    build_html_report,
    classify_sheet,
    extract_dimension_tokens,
    extract_sheet_number,
)


class SheetClassificationTests(unittest.TestCase):
    def test_identifies_structural_sheet_from_multiple_signals(self):
        result = classify_sheet("STRUCTURAL FRAMING PLAN\nBEAM AND COLUMN SCHEDULE")
        self.assertEqual(result["category"], "structural")
        self.assertIn("framing plan", result["evidence"])
        self.assertIn("beam", result["evidence"])
        self.assertEqual(result["confidence"], "high")

    def test_unknown_page_is_not_forced_into_a_discipline(self):
        result = classify_sheet("PROJECT INFORMATION")
        self.assertEqual(result["category"], "unknown")
        self.assertEqual(result["confidence"], "low")

    def test_architectural_sheet_classification(self):
        result = classify_sheet("LEVEL 1 FLOOR PLAN AND BUILDING ELEVATIONS")
        self.assertEqual(result["category"], "architectural")


class DrawingTextExtractionTests(unittest.TestCase):
    def test_extracts_sheet_number_from_labeled_title_block_text(self):
        self.assertEqual(extract_sheet_number("PROJECT: HOUSE\nSHEET NO.: A-101"), "A-101")

    def test_extracts_dimension_strings_without_converting_them(self):
        tokens = extract_dimension_tokens('Overall 24\'-6" and opening 36"')
        self.assertIn("24'-6\"", tokens)
        self.assertIn('36"', tokens)


class PdfAnalysisTests(unittest.TestCase):
    def test_html_report_escapes_text_and_links_rendered_pages(self):
        report = {
            "source_file": "<client>.pdf",
            "page_count": 1,
            "summary": {"pages_by_classification": {"architectural": 1}},
            "pages": [{
                "page_number": 1,
                "dimensions": {"width_in": 24, "height_in": 36, "orientation": "portrait"},
                "rotation_degrees": 0,
                "text_char_count": 42,
                "likely_scanned": False,
                "review_status": "text_extracted_visual_review_required",
                "sheet_number": "A-101",
                "classification": {"category": "architectural", "confidence": "high", "evidence": ["floor plan"]},
                "dimension_tokens": ['24\'-0"'],
                "text_preview": "<script>alert(1)</script>",
            }],
            "limitations": [],
        }
        html = build_html_report(report, {"1": "pages/page-001.png"})
        self.assertIn("pages/page-001.png", html)
        self.assertIn("&lt;client&gt;.pdf", html)
        self.assertNotIn("<script>alert(1)</script>", html)

    def test_analyzes_pages_and_flags_image_only_page(self):
        class FakeTextPage:
            def __init__(self, text):
                self.text = text

            def get_text_range(self):
                return self.text

            def close(self):
                pass

        class FakePage:
            def __init__(self, text):
                self.text = text

            def get_size(self):
                return (612.0, 792.0)

            def get_rotation(self):
                return 0

            def get_textpage(self):
                return FakeTextPage(self.text)

            def close(self):
                pass

        class FakeDocument:
            def __init__(self, path):
                self.pages = [
                    FakePage("ARCHITECTURAL FLOOR PLAN SHEET NO. A-101 24'-0\""),
                    FakePage(""),
                ]

            def __len__(self):
                return len(self.pages)

            def __getitem__(self, index):
                return self.pages[index]

            def get_metadata_dict(self):
                return {"Title": "Sample Plan Set"}

            def close(self):
                pass

        fake_pdfium = types.SimpleNamespace(PdfDocument=FakeDocument)
        with tempfile.TemporaryDirectory() as folder:
            pdf_path = Path(folder) / "plans.pdf"
            pdf_path.write_bytes(b"%PDF-fake")
            with patch.dict("sys.modules", {"pypdfium2": fake_pdfium}):
                report = analyze_pdf(pdf_path)

        self.assertEqual(report["page_count"], 2)
        self.assertEqual(report["metadata"]["Title"], "Sample Plan Set")
        self.assertEqual(report["pages"][0]["sheet_number"], "A-101")
        self.assertEqual(report["pages"][0]["classification"]["category"], "architectural")
        self.assertFalse(report["pages"][0]["likely_scanned"])
        self.assertTrue(report["pages"][1]["likely_scanned"])
        self.assertEqual(report["pages"][1]["review_status"], "needs_ocr_or_visual_review")


if __name__ == "__main__":
    unittest.main()
