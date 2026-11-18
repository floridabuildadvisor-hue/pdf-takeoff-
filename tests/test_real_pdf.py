"""Unmocked tests: real pypdfium2 reading a synthetic, non-project PDF."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pdf_intelligence import analyze_pdf, render_pdf_pages
from tests.synthetic_pdf import (
    FIXTURE_PATH,
    build_password_protected_pdf,
    build_plan_set_pdf,
    build_stacked_fraction_pdf,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class SyntheticFixtureTests(unittest.TestCase):
    def test_committed_fixture_matches_its_builder(self):
        self.assertEqual(FIXTURE_PATH.read_bytes(), build_plan_set_pdf())


class RealPdfAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = analyze_pdf(FIXTURE_PATH)
        cls.pages = cls.report["pages"]

    def test_inventories_every_page(self):
        self.assertEqual(self.report["page_count"], 3)
        self.assertEqual([page["page_number"] for page in self.pages], [1, 2, 3])
        self.assertEqual(self.report["source_file"], "synthetic_plan_set.pdf")

    def test_text_sheet_size_and_classification(self):
        page = self.pages[0]
        self.assertEqual(page["dimensions"]["width_in"], 36.0)
        self.assertEqual(page["dimensions"]["height_in"], 24.0)
        self.assertEqual(page["dimensions"]["orientation"], "landscape")
        self.assertEqual(page["classification"]["category"], "architectural")
        self.assertFalse(page["low_text_content"])

    def test_decimal_sheet_number_is_kept_whole(self):
        self.assertEqual(self.pages[0]["sheet_number"], "A1.01")

    def test_dimension_with_typographic_foot_mark_is_kept_whole(self):
        # pdfium returns the foot mark of this font as U+2019, not ASCII.
        self.assertEqual(self.pages[0]["dimension_tokens"], ["24’-6\""])

    def test_report_limitations_state_how_tokens_and_sheet_numbers_are_read(self):
        limitations = " ".join(self.report["limitations"])
        self.assertIn("Scale notes are left out", limitations)
        self.assertIn("no SHEET or DWG label", limitations)
        self.assertIn("Stacked fractions", limitations)

    def test_report_still_states_what_it_does_not_read_or_check(self):
        limitations = " ".join(self.report["limitations"])
        for subject in ("symbols", "walls", "openings", "geometry", "quantities"):
            self.assertIn(subject, limitations)
        self.assertIn("no opinion on the design", limitations)
        self.assertIn("estimator review", limitations)

    def test_blank_page_is_flagged_for_review(self):
        page = self.pages[1]
        self.assertTrue(page["low_text_content"])
        self.assertEqual(page["review_status"], "needs_ocr_or_visual_review")
        self.assertIsNone(page["sheet_number"])

    def test_rotated_sheet_reports_displayed_size_and_title_block_code(self):
        page = self.pages[2]
        self.assertEqual(page["rotation_degrees"], 90)
        self.assertEqual(page["dimensions"]["width_in"], 24.0)
        self.assertEqual(page["dimensions"]["height_in"], 36.0)
        self.assertEqual(page["dimensions"]["orientation"], "portrait")
        self.assertEqual(page["classification"]["category"], "structural")
        self.assertEqual(page["sheet_number"], "S-2")


class StackedFractionPdfTests(unittest.TestCase):
    def test_stacked_fraction_is_read_as_a_fraction_not_run_together(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf_path = Path(folder) / "stacked.pdf"
            pdf_path.write_bytes(build_stacked_fraction_pdf())
            page = analyze_pdf(pdf_path)["pages"][0]
        self.assertEqual(page["dimension_tokens"], ["13\u2019-1 1/2\"", "44\u2019-0\""])
        self.assertIn("13\u2019-1 1/2\"", page["text_preview"])
        self.assertNotIn("112", page["text_preview"])

    def test_limitations_say_fractions_are_reassembled_and_need_checking(self):
        limitations = " ".join(analyze_pdf(FIXTURE_PATH)["limitations"])
        self.assertIn("Stacked fractions are reassembled from character positions", limitations)
        self.assertIn("check fractional dimensions against the drawing", limitations)


class UnreadablePdfTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.corrupt = self.folder / "corrupt.pdf"
        self.corrupt.write_bytes(b"this is not a PDF file")
        self.protected = self.folder / "protected.pdf"
        self.protected.write_bytes(build_password_protected_pdf())

    def test_corrupt_pdf_raises_a_clear_error(self):
        with self.assertRaisesRegex(ValueError, r"corrupt\.pdf.*not a readable PDF"):
            analyze_pdf(self.corrupt)

    def test_password_protected_pdf_raises_a_clear_error(self):
        with self.assertRaisesRegex(ValueError, r"protected\.pdf.*password"):
            analyze_pdf(self.protected)

    def test_rendering_reports_the_same_clear_errors(self):
        with self.assertRaisesRegex(ValueError, "not a readable PDF"):
            render_pdf_pages(self.corrupt, self.folder / "pages")
        with self.assertRaisesRegex(ValueError, "password"):
            render_pdf_pages(self.protected, self.folder / "pages")


class CommandLineTests(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "pdf_intelligence.py"), *args],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )

    def test_cli_writes_json_html_and_page_previews(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "diagnostics.json"
            result = self._run(str(FIXTURE_PATH), "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["page_count"], 3)
            self.assertTrue(output.with_suffix(".html").is_file())
            previews = sorted(path.name for path in (Path(folder) / "pages").glob("*.png"))
            self.assertEqual(previews, ["page-001.png", "page-002.png", "page-003.png"])


    def test_cli_reports_unreadable_pdfs_without_a_traceback(self):
        with tempfile.TemporaryDirectory() as folder:
            cases = {
                "corrupt.pdf": (b"this is not a PDF file", "not a readable PDF"),
                "protected.pdf": (build_password_protected_pdf(), "password"),
            }
            for name, (data, expected) in cases.items():
                pdf_path = Path(folder) / name
                pdf_path.write_bytes(data)
                output = Path(folder) / name.replace(".pdf", ".json")
                result = self._run(str(pdf_path), "--output", str(output))
                self.assertEqual(result.returncode, 1, name)
                self.assertIn(expected, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(output.exists(), name)

    def test_cli_reports_a_missing_pdf_without_a_traceback(self):
        result = self._run("no-such-file.pdf")
        self.assertEqual(result.returncode, 1)
        self.assertIn("PDF not found", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
