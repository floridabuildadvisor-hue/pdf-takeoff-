"""Checks on evidence_package: the script that checks an agent's evidence package.

Each test builds a small project folder in a temporary directory from the
synthetic plan set. No project or client data.
"""
from __future__ import annotations

import csv
import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

import pypdfium2 as pdfium

import evidence_package
from tests.synthetic_pdf import FIXTURE_PATH

PDF_REL = "01_Received/synthetic_plan_set.pdf"
REQUEST_REL = "01_Received/request.txt"
DOC = "pdf-drawing-specialist"
QTO = "quantity-takeoff-agent"
BASE = ("id", "based_on", "file", "page", "sheet", "revision", "as_printed", "bbox",
        "method", "status")
TAKEOFF = ("record_type", "item", "description", "dimension", "formula", "quantity",
           "unit", "assumptions")
CHECKED = "checked against source"


def bbox_of(page_number: int, first_word: str, length: int) -> str:
    """Bounds of `length` characters starting at `first_word`, as x0,y0,x1,y1."""
    document = pdfium.PdfDocument(str(FIXTURE_PATH))
    textpage = document[page_number - 1].get_textpage()
    start, _ = textpage.search(first_word).get_next()
    boxes = [textpage.get_charbox(index) for index in range(start, start + length)]
    return ",".join(f"{value:.2f}" for value in (
        min(box[0] for box in boxes), min(box[1] for box in boxes),
        max(box[2] for box in boxes), max(box[3] for box in boxes),
    ))


def doc_rows() -> list[dict]:
    row = dict.fromkeys(BASE, "")
    row.update(file=PDF_REL, revision="none printed", method="native_text", status=CHECKED)
    return [
        {**row, "id": "DOC-001", "page": "1", "sheet": "A1.01",
         "as_printed": "OVERALL 24'-6\"", "bbox": bbox_of(1, "OVERALL", 14)},
        {**row, "id": "DOC-002", "page": "3", "sheet": "S-2",
         "as_printed": "S-2", "bbox": bbox_of(3, "S-2", 3)},
        {**row, "id": "DOC-003", "file": REQUEST_REL, "as_printed": "Quantities only.",
         "bbox": "line 2"},
        {**row, "id": "DOC-004", "page": "2", "as_printed": "none",
         "bbox": "none: page 2 has no text and no drawing"},
        {**row, "id": "DOC-005", "based_on": "DOC-001 DOC-002",
         "as_printed": "see based_on", "bbox": "see based_on"},
    ]


def qto_rows() -> list[dict]:
    row = dict.fromkeys(BASE + TAKEOFF, "")
    row.update(file=PDF_REL, page="1", sheet="A1.01", revision="none printed",
               method="native_text", status=CHECKED, item="overall wall")
    return [
        {**row, "id": "QTO-001", "based_on": "DOC-001", "record_type": "input",
         "as_printed": "OVERALL 24'-6\"", "bbox": bbox_of(1, "OVERALL", 14),
         "dimension": "overall length", "formula": "24 + 6/12", "quantity": "24.5",
         "unit": "LF"},
        {**row, "id": "QTO-002", "based_on": "QTO-001", "record_type": "quantity",
         "as_printed": "see based_on", "bbox": "see based_on",
         "formula": "[QTO-001]", "quantity": "24.5", "unit": "LF"},
    ]


class ProjectCase(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.project)
        received = self.project / "01_Received"
        received.mkdir()
        shutil.copy(FIXTURE_PATH, self.project / PDF_REL)
        (self.project / REQUEST_REL).write_text(
            "Take off the overall wall.\nQuantities only.\n", encoding="utf-8")
        self.write_package(DOC, "register.csv", doc_rows())
        self.write_package(QTO, "records.csv", qto_rows())

    def write_package(self, agent: str, records_name: str, rows: list[dict]) -> None:
        folder = self.project / "02_Working" / agent
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / records_name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        (folder / "commands.txt").write_text("none run\n", encoding="utf-8")
        (folder / "CHECK.md").write_text("# Spot checks\n", encoding="utf-8")
        self.write_sums(agent)

    def write_sums(self, agent: str) -> None:
        folder = self.project / "02_Working" / agent
        listed = [self.project / PDF_REL, self.project / REQUEST_REL]
        listed += sorted(p for p in folder.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
        lines = [
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  "
            f"{path.relative_to(self.project).as_posix()}"
            for path in listed
        ]
        (folder / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def findings(self) -> list[tuple[str, str, str]]:
        result = evidence_package.check_project(self.project)
        return [(f["package"], f["check"], f["record"]) for f in result["findings"]]


class CleanProjectTests(ProjectCase):
    def test_a_complete_project_has_no_findings(self):
        result = evidence_package.check_project(self.project)
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["packages"], [DOC, QTO])

    def test_it_counts_what_it_checked(self):
        counts = evidence_package.check_project(self.project)["counts"]
        self.assertEqual(counts["records"], 7)
        self.assertEqual(counts["hashed_files"], 10)
        # DOC-001, DOC-002 and QTO-001 from the PDF, DOC-003 from the text file.
        self.assertEqual(counts["read_back"], 4)
        self.assertEqual(counts["links"], 4)

    def test_the_review_folder_is_not_a_package(self):
        review = self.project / "02_Working" / "review"
        review.mkdir()
        (review / "level-2.md").write_text("returned table\n", encoding="utf-8")
        self.assertEqual(self.findings(), [])

    def test_the_command_line_exit_code_is_zero_when_clean(self):
        self.assertEqual(evidence_package.main([str(self.project)]), 0)


class HashTests(ProjectCase):
    def test_a_file_changed_after_hashing_is_reported(self):
        records = self.project / "02_Working" / QTO / "records.csv"
        records.write_text(records.read_text().replace("24.5,LF", "25.5,LF", 1))
        self.assertIn((QTO, "hash_mismatch", ""), self.findings())
        self.assertEqual(evidence_package.main([str(self.project)]), 1)

    def test_a_listed_file_that_is_gone_is_reported(self):
        (self.project / REQUEST_REL).unlink()
        checks = [check for _, check, _ in self.findings()]
        self.assertIn("hash_mismatch", checks)

    def test_a_file_in_the_folder_that_is_not_listed_is_reported(self):
        scratch = self.project / "02_Working" / DOC / "scratch"
        scratch.mkdir()
        (scratch / "notes.txt").write_text("late file\n", encoding="utf-8")
        self.assertEqual(self.findings(), [(DOC, "unlisted_file", "")])

    def test_each_missing_evidence_file_is_reported(self):
        for name in ("commands.txt", "CHECK.md"):
            (self.project / "02_Working" / DOC / name).unlink()
        self.write_sums(DOC)
        self.assertEqual(self.findings(), [(DOC, "missing_file", "")] * 2)

    def test_a_folder_without_sha256sums_is_reported(self):
        (self.project / "02_Working" / DOC / "SHA256SUMS").unlink()
        self.assertIn((DOC, "missing_file", ""), self.findings())


class RecordTests(ProjectCase):
    def rewrite(self, agent, records_name, rows):
        self.write_package(agent, records_name, rows)

    def test_a_missing_required_column_is_reported(self):
        rows = [{k: v for k, v in row.items() if k != "revision"} for row in doc_rows()]
        self.rewrite(DOC, "register.csv", rows)
        self.assertEqual(self.findings(), [(DOC, "missing_column", "")])

    def test_takeoff_records_need_the_takeoff_columns(self):
        rows = [{k: v for k, v in row.items() if k != "dimension"} for row in qto_rows()]
        self.rewrite(QTO, "records.csv", rows)
        self.assertEqual(self.findings(), [(QTO, "missing_column", "")])

    def test_a_folder_with_no_records_file_is_reported(self):
        (self.project / "02_Working" / DOC / "register.csv").unlink()
        self.write_sums(DOC)
        self.assertIn((DOC, "no_records", ""), self.findings())

    def test_an_id_with_another_agents_prefix_is_reported(self):
        rows = qto_rows()
        rows[1]["id"] = "STR-002"
        self.rewrite(QTO, "records.csv", rows)
        self.assertEqual(self.findings(), [(QTO, "bad_id", "STR-002")])

    def test_a_repeated_id_is_reported(self):
        rows = doc_rows()
        rows[1]["id"] = "DOC-001"
        self.rewrite(DOC, "register.csv", rows)
        self.assertIn((DOC, "duplicate_id", "DOC-001"), self.findings())

    def test_a_link_to_a_record_that_does_not_exist_is_reported(self):
        rows = qto_rows()
        rows[0]["based_on"] = "DOC-001 STR-099"
        self.rewrite(QTO, "records.csv", rows)
        self.assertEqual(self.findings(), [(QTO, "unresolved_based_on", "QTO-001")])

    def test_a_method_outside_the_list_is_reported(self):
        rows = doc_rows()
        rows[0]["method"] = "guess"
        self.rewrite(DOC, "register.csv", rows)
        self.assertEqual(self.findings(), [(DOC, "bad_method", "DOC-001")])

    def test_not_checked_needs_a_reason(self):
        rows = doc_rows()
        rows[0]["status"] = "not checked"
        rows[1]["status"] = "not checked: the sheet is rotated"
        self.rewrite(DOC, "register.csv", rows)
        self.assertEqual(self.findings(), [(DOC, "bad_status", "DOC-001")])


class SourceTests(ProjectCase):
    def rewrite_doc(self, index, **changes):
        rows = doc_rows()
        rows[index].update(changes)
        self.write_package(DOC, "register.csv", rows)

    def test_a_string_that_is_not_at_its_bbox_is_reported(self):
        self.rewrite_doc(0, as_printed="OVERALL 26'-6\"")
        self.assertEqual(self.findings(), [(DOC, "read_back_mismatch", "DOC-001")])

    def test_a_bbox_on_a_rotated_page_reads_back(self):
        # DOC-002 is on the /Rotate 90 page; moving its box must fail.
        self.rewrite_doc(1, bbox="10.00,10.00,40.00,20.00")
        self.assertEqual(self.findings(), [(DOC, "read_back_mismatch", "DOC-002")])

    def test_a_text_file_line_that_differs_is_reported(self):
        self.rewrite_doc(2, bbox="line 1")
        self.assertEqual(self.findings(), [(DOC, "read_back_mismatch", "DOC-003")])

    def test_none_needs_a_reason(self):
        self.rewrite_doc(3, bbox="none")
        self.assertEqual(self.findings(), [(DOC, "bad_bbox", "DOC-004")])

    def test_see_based_on_needs_a_link(self):
        self.rewrite_doc(4, based_on="")
        self.assertEqual(self.findings(), [(DOC, "bad_bbox", "DOC-005")])

    def test_a_crop_image_path_must_exist(self):
        self.rewrite_doc(3, bbox="02_Working/pdf-drawing-specialist/crops/p2.png")
        self.assertEqual(self.findings(), [(DOC, "bad_bbox", "DOC-004")])

    def test_a_drawn_shape_is_not_read_back_as_text(self):
        self.rewrite_doc(3, as_printed="drawn", bbox="100.00,100.00,200.00,200.00",
                         method="vector_geometry")
        self.assertEqual(self.findings(), [])

    def test_a_page_outside_the_file_is_reported(self):
        self.rewrite_doc(0, page="9")
        self.assertEqual(self.findings(), [(DOC, "read_back_mismatch", "DOC-001")])


if __name__ == "__main__":
    unittest.main()
