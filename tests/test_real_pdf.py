"""Unmocked tests: real pypdfium2 reading a synthetic, non-project PDF."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pdf_intelligence import analyze_pdf
from tests.synthetic_pdf import FIXTURE_PATH, build_plan_set_pdf

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


if __name__ == "__main__":
    unittest.main()
