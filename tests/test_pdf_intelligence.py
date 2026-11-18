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

    def test_decimal_sheet_ids_are_kept_whole_and_as_printed(self):
        self.assertEqual(extract_sheet_number("SHEET A1.01"), "A1.01")
        self.assertEqual(extract_sheet_number("SHEET: S2.1"), "S2.1")
        self.assertEqual(extract_sheet_number("DWG NO. A-201.1"), "A-201.1")
        self.assertEqual(extract_sheet_number("SHEET NUMBER\nS-3."), "S-3")

    def test_words_after_the_sheet_label_are_not_sheet_numbers(self):
        for text in (
            "SHEET NOTES 1",
            "SHEET NOTES:\n1. VERIFY ALL DIMENSIONS",
            "SHEET INDEX",
            "SEE RADON SHEET FOR ADDITIONAL REQUIREMENTS",
            "SHEET FOR 3 BEDROOMS",
        ):
            self.assertIsNone(extract_sheet_number(text), text)

    def test_bare_numbers_are_never_returned_as_sheet_numbers(self):
        for text in (
            "SHEET 1 OF 15",
            "SHEET NO. 5",
            "SHEET NO.5",
            "DWG NO-12",
            "COVER SHEET\n10-17-26",
            "PAGE\n7\n15",
        ):
            self.assertIsNone(extract_sheet_number(text), text)

    def test_extracts_dimension_strings_without_converting_them(self):
        tokens = extract_dimension_tokens('Overall 24\'-6" and opening 36"')
        self.assertIn("24'-6\"", tokens)
        self.assertIn('36"', tokens)

    def test_keeps_unicode_prime_dimensions_whole_and_as_printed(self):
        self.assertEqual(extract_dimension_tokens("12\u2032-0\u2033"), ["12\u2032-0\u2033"])
        self.assertEqual(
            extract_dimension_tokens("WALL 8\u2032-6 1/2\u2033 HIGH, SLAB 4\u2033"),
            ["8\u2032-6 1/2\u2033", "4\u2033"],
        )

    def test_keeps_typographic_quote_dimensions_whole_and_as_printed(self):
        self.assertEqual(extract_dimension_tokens("24\u2019-6\""), ["24\u2019-6\""])
        self.assertEqual(extract_dimension_tokens("10\u2019-0\u201d"), ["10\u2019-0\u201d"])
        self.assertEqual(extract_dimension_tokens("EL. 10.5\u2019"), ["10.5\u2019"])

    def test_keeps_fraction_only_inches_whole(self):
        self.assertEqual(extract_dimension_tokens('3/4" PLYWOOD'), ['3/4"'])
        self.assertEqual(extract_dimension_tokens("12'-6 1/2\""), ["12'-6 1/2\""])

    def test_scale_notes_are_not_returned_as_dimension_tokens(self):
        for note in (
            'SCALE: 1/4" = 1\'-0"',
            '3/16"=1\'-0"',
            '1 1/2" = 1\'-0"',
            '1" = 20\'',
            "1/8\u2033 = 1\u2032-0\u2033",
            "1/4\" = 1\u2019-0\"",
        ):
            self.assertEqual(extract_dimension_tokens(note), [], note)

    def test_dimensions_next_to_a_scale_note_are_kept(self):
        text = 'FLOOR PLAN  SCALE: 1/4" = 1\'-0"\nOVERALL 24\'-6" BY 36"'
        self.assertEqual(extract_dimension_tokens(text), ["24'-6\"", '36"'])


class BareTitleBlockCodeTests(unittest.TestCase):
    def test_lone_code_on_its_own_line_is_the_sheet_number(self):
        for code in ("C-1", "A-1", "A-6", "E-2", "T-6", "A1.01", "S201", "FP-3"):
            text = f"GENERAL NOTES\n{code}\nPROJECT #: DRAWING: DATE:"
            self.assertEqual(extract_sheet_number(text), code, code)

    def test_repeated_occurrences_of_one_code_still_count_as_one(self):
        self.assertEqual(extract_sheet_number("T-1\nTRUSS LAYOUT\nT-1"), "T-1")

    def test_labeled_match_wins_over_a_bare_code(self):
        self.assertEqual(extract_sheet_number("B-1\nFLOOR PLAN\nSHEET NO. A-101"), "A-101")

    def test_code_inside_a_line_of_other_text_is_not_used(self):
        for text in ("R-13 BATT INSULATION", "TYPE W-1 WINDOW", "A-1 FLOOR PLAN  A-2 ELEVATIONS"):
            self.assertIsNone(extract_sheet_number(text), text)

    def test_two_different_bare_codes_are_ambiguous_and_give_none(self):
        self.assertIsNone(extract_sheet_number("B-1\nBEAM SCHEDULE\nT-2"))

    def test_bare_numbers_and_long_codes_are_never_returned(self):
        for text in ("7", "15\nFLOOR PLAN", "2024\n10-17-26", "NER-200", "12'-0\""):
            self.assertIsNone(extract_sheet_number(text), text)


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
                "low_text_content": False,
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
        self.assertFalse(report["pages"][0]["low_text_content"])
        self.assertTrue(report["pages"][1]["low_text_content"])
        self.assertEqual(report["pages"][1]["review_status"], "needs_ocr_or_visual_review")


if __name__ == "__main__":
    unittest.main()
