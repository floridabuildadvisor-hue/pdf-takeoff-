"""Checks on evidence_package: the script that checks an agent's evidence package.

Each test builds a small project folder in a temporary directory from the
synthetic plan set. No project or client data.
"""
from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import pypdfium2 as pdfium

import evidence_package
from tests.synthetic_pdf import FIXTURE_PATH

PDF_REL = "01_Received/synthetic_plan_set.pdf"
REQUEST_REL = "01_Received/request.txt"
DOC = "pdf-drawing-specialist"
QTO = "quantity-takeoff-agent"
STR = "structural-plan-reviewer"
RPT = "report-proposal-specialist"
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


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class InventoryTests(ProjectCase):
    """Every received file is in the document inventory, and every path stays inside."""

    def add_line(self, agent: str, digest: str, relative: str) -> None:
        sums = self.project / "02_Working" / agent / "SHA256SUMS"
        sums.write_text(sums.read_text() + f"{digest}  {relative}\n", encoding="utf-8")

    def test_a_received_file_added_after_the_inventory_is_reported(self):
        shutil.copy(FIXTURE_PATH, self.project / "01_Received" / "addendum_1.pdf")
        self.assertEqual(self.findings(), [(DOC, "received_not_inventoried", "")])

    def test_a_received_drawing_left_out_of_the_inventory_is_reported(self):
        sums = self.project / "02_Working" / DOC / "SHA256SUMS"
        kept = [line for line in sums.read_text().splitlines() if PDF_REL not in line]
        sums.write_text("\n".join(kept) + "\n", encoding="utf-8")
        found = self.findings()
        self.assertIn((DOC, "received_not_inventoried", ""), found)
        # DOC-001 cites a file its own package never hashed.
        self.assertIn((DOC, "source_not_hashed", "DOC-001"), found)

    def test_a_project_with_received_files_and_no_inventory_package_is_reported(self):
        shutil.rmtree(self.project / "02_Working" / DOC)
        self.assertIn((DOC, "no_inventory", ""), self.findings())

    def test_a_manifest_path_above_the_project_is_refused_and_not_read(self):
        outside = self.project.parent / f"{self.project.name}-outside.txt"
        outside.write_text("not a project file\n", encoding="utf-8")
        self.addCleanup(outside.unlink)
        self.add_line(QTO, sha(outside), f"../{outside.name}")
        self.assertEqual(self.findings(), [(QTO, "path_outside_project", "")])

    def test_an_absolute_manifest_path_is_refused(self):
        self.add_line(QTO, sha(FIXTURE_PATH), str(FIXTURE_PATH))
        self.assertEqual(self.findings(), [(QTO, "path_outside_project", "")])

    def test_a_link_that_leaves_the_project_is_refused(self):
        link = self.project / "02_Working" / QTO / "plans.pdf"
        os.symlink(FIXTURE_PATH, link)
        self.add_line(QTO, sha(FIXTURE_PATH), f"02_Working/{QTO}/plans.pdf")
        self.assertEqual(self.findings(), [(QTO, "path_outside_project", "")])

    def test_a_record_whose_file_is_outside_the_project_is_refused(self):
        rows = qto_rows()
        rows[0]["file"] = "../../" + PDF_REL
        self.write_package(QTO, "records.csv", rows)
        self.assertIn((QTO, "path_outside_project", "QTO-001"), self.findings())

    def test_a_manifest_line_that_is_not_a_hash_and_a_path_is_reported(self):
        sums = self.project / "02_Working" / QTO / "SHA256SUMS"
        sums.write_text(sums.read_text() + "OK 01_Received/request.txt\n", encoding="utf-8")
        self.assertEqual(self.findings(), [(QTO, "bad_manifest_line", "")])


class CropTests(ProjectCase):
    def with_crop(self, relative: str) -> None:
        rows = doc_rows()
        rows[3].update(as_printed="OVERALL", bbox=relative, method="image_interpretation")
        self.write_package(DOC, "register.csv", rows)

    def test_a_crop_that_exists_is_counted_as_not_compared(self):
        crops = self.project / "02_Working" / DOC / "crops"
        crops.mkdir()
        (crops / "p2.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"not a picture of the sheet")
        self.with_crop(f"02_Working/{DOC}/crops/p2.png")
        result = evidence_package.check_project(self.project)
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["counts"]["crops_not_compared"], 1)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            evidence_package.main([str(self.project)])
        self.assertIn("1 crop image(s) exist but were not compared", output.getvalue())

    def test_a_crop_outside_the_project_is_refused(self):
        self.with_crop("../" + self.project.name + "/" + PDF_REL + "/../../../etc/hosts")
        self.assertEqual(self.findings(), [(DOC, "path_outside_project", "DOC-004")])


class ReforgedHashTests(ProjectCase):
    """A manifest rewritten after a change. Only another copy of the hash can show it."""

    def change_and_reforge(self, agent: str, name: str, old: str, new: str) -> None:
        path = self.project / "02_Working" / agent / name
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8")
        self.write_sums(agent)

    def test_a_reforged_package_is_caught_by_a_package_that_read_it(self):
        register = self.project / "02_Working" / DOC / "register.csv"
        sums = self.project / "02_Working" / QTO / "SHA256SUMS"
        sums.write_text(sums.read_text() + f"{sha(register)}  02_Working/{DOC}/register.csv\n")
        self.assertEqual(self.findings(), [])
        self.change_and_reforge(DOC, "register.csv", "no text and no drawing", "no text")
        self.assertEqual(self.findings(), [(QTO, "hash_mismatch", "")])

    def test_a_reforged_last_package_is_not_caught_from_the_files_alone(self):
        # Stated limit: nothing in the project still holds the earlier hash.
        self.change_and_reforge(QTO, "records.csv", "24.5,LF", "42.5,LF")
        self.assertEqual(self.findings(), [])

    def test_a_reforged_last_package_is_caught_against_recorded_seals(self):
        seals = evidence_package.check_project(self.project)["seals"]
        self.assertEqual(sorted(seals), sorted([PDF_REL, REQUEST_REL,
                                                f"02_Working/{DOC}/SHA256SUMS",
                                                f"02_Working/{QTO}/SHA256SUMS"]))
        self.change_and_reforge(QTO, "records.csv", "24.5,LF", "42.5,LF")
        result = evidence_package.check_project(self.project, seals=seals)
        self.assertEqual([(f["package"], f["check"]) for f in result["findings"]],
                         [(QTO, "seal_mismatch")])

    def test_a_package_added_after_the_seals_were_recorded_is_reported(self):
        seals = evidence_package.check_project(self.project)["seals"]
        del seals[f"02_Working/{QTO}/SHA256SUMS"]
        result = evidence_package.check_project(self.project, seals=seals)
        self.assertEqual([(f["package"], f["check"]) for f in result["findings"]],
                         [(QTO, "seal_missing")])

    def test_a_swapped_drawing_with_every_hash_list_rewritten_is_caught_by_seals(self):
        seals = evidence_package.check_project(self.project)["seals"]
        request = self.project / REQUEST_REL
        request.write_text("Take off the overall wall.\nQuantities only.\nAnd the roof.\n")
        self.write_sums(DOC)
        self.write_sums(QTO)
        self.assertEqual(self.findings(), [])
        result = evidence_package.check_project(self.project, seals=seals)
        self.assertEqual(sorted((f["package"], f["check"]) for f in result["findings"]), [
            ("01_Received", "seal_mismatch"), (DOC, "seal_mismatch"), (QTO, "seal_mismatch")])

    def test_seals_can_be_passed_on_standard_input(self):
        seals = evidence_package.check_project(self.project)["seals"]
        text = "".join(f"SEAL {digest}  {path}\n" for path, digest in seals.items())
        self.change_and_reforge(QTO, "records.csv", "24.5,LF", "42.5,LF")
        with mock.patch("sys.stdin", io.StringIO(text)), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(evidence_package.main([str(self.project), "--seals", "-"]), 1)

    def test_the_command_line_prints_seals_and_reads_them_back(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(evidence_package.main([str(self.project)]), 0)
        seal_lines = [line[len("SEAL "):] for line in output.getvalue().splitlines()
                      if line.startswith("SEAL ")]
        self.assertEqual(len(seal_lines), 4)
        seal_file = self.project.parent / f"{self.project.name}-seals.txt"
        seal_file.write_text("\n".join(seal_lines) + "\n", encoding="utf-8")
        self.addCleanup(seal_file.unlink)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                evidence_package.main([str(self.project), "--seals", str(seal_file)]), 0)
            self.change_and_reforge(QTO, "records.csv", "24.5,LF", "42.5,LF")
            self.assertEqual(
                evidence_package.main([str(self.project), "--seals", str(seal_file)]), 1)


class ChainTests(ProjectCase):
    """Links between records. Connected IDs show a path, not that a quantity is right."""

    def rewrite_qto(self, index, **changes):
        rows = qto_rows()
        rows[index].update(changes)
        self.write_package(QTO, "records.csv", rows)

    def add_scope_package(self):
        row = dict.fromkeys(BASE, "")
        row.update(id="STR-001", based_on="DOC-001", file=PDF_REL, page="1", sheet="A1.01",
                   revision="none printed", as_printed="OVERALL 24'-6\"",
                   bbox=bbox_of(1, "OVERALL", 14), method="native_text", status=CHECKED)
        self.write_package(STR, "register.csv", [row])

    def test_two_records_based_on_each_other_are_reported(self):
        self.rewrite_qto(0, based_on="DOC-001 QTO-002")
        found = self.findings()
        self.assertIn((QTO, "cyclic_based_on", "QTO-001"), found)
        self.assertEqual([f for f in found if f[1] == "cyclic_based_on"],
                         [(QTO, "cyclic_based_on", "QTO-001")])

    def test_a_record_based_on_itself_is_reported(self):
        self.rewrite_qto(1, based_on="QTO-001 QTO-002")
        self.assertEqual(self.findings(), [(QTO, "cyclic_based_on", "QTO-002")])

    def test_a_link_to_a_later_stage_is_the_wrong_type(self):
        rows = doc_rows()
        rows[4]["based_on"] = "DOC-001 QTO-001"
        self.write_package(DOC, "register.csv", rows)
        self.assertEqual(self.findings(), [(DOC, "wrong_link_type", "DOC-005")])

    def test_a_printed_input_based_on_a_calculated_row_is_the_wrong_type(self):
        rows = qto_rows()
        rows.append({**rows[0], "id": "QTO-003", "based_on": "QTO-002"})
        self.write_package(QTO, "records.csv", rows)
        self.assertEqual(self.findings(), [(QTO, "wrong_link_type", "QTO-003")])

    def test_a_quantity_with_no_drawing_evidence_behind_it_is_reported(self):
        # QTO-001 now only points at DOC-004, a row with no place on a sheet.
        self.rewrite_qto(0, based_on="DOC-004", as_printed="see based_on", bbox="see based_on")
        self.assertEqual(self.findings(), [(QTO, "no_drawing_evidence", "QTO-002")])

    def test_a_text_file_line_is_not_drawing_evidence(self):
        self.rewrite_qto(0, based_on="DOC-003", file=REQUEST_REL, page="",
                         as_printed="Quantities only.", bbox="line 2")
        self.assertEqual(self.findings(), [(QTO, "no_drawing_evidence", "QTO-002")])

    def test_an_unresolved_quantity_is_not_asked_for_evidence(self):
        rows = qto_rows()
        rows[0].update(based_on="DOC-004", as_printed="see based_on", bbox="see based_on")
        rows[1].update(quantity="", status="not checked: the plan and the schedule differ")
        self.write_package(QTO, "records.csv", rows)
        self.assertEqual(self.findings(), [])

    def test_with_a_scope_register_a_quantity_must_lead_to_a_scope_row(self):
        self.add_scope_package()
        self.assertEqual(self.findings(), [(QTO, "no_scope_record", "QTO-002")])
        self.rewrite_qto(0, based_on="STR-001")
        self.assertEqual(self.findings(), [])

    def test_a_quantity_row_with_a_number_and_a_missing_part_is_reported(self):
        for change in ({"unit": ""}, {"formula": ""}, {"sheet": ""}, {"quantity": "nan"},
                       {"quantity": "inf"}, {"quantity": "about 24"}):
            with self.subTest(change=change):
                self.rewrite_qto(1, **change)
                self.assertEqual(self.findings(), [(QTO, "incomplete_quantity", "QTO-002")])


class BoqTests(ProjectCase):
    """BOQ lines against the quantity records they must come from."""

    LINE = {"item_code": "QTO-002", "quantity": "24.5", "unit": "LF", "formula": "[QTO-001]",
            "source_sheet": "A1.01", "notes": "overall wall", "reviewer_initials": "",
            "source_revision": "none printed"}
    WHOLE = "DRAFT: all 1 quantity rows, not reviewed"
    PARTIAL = "PARTIAL DRAFT: 1 of 2 quantity rows, not reviewed"

    def write_boq(self, lines, status=WHOLE, drop=()):
        row = dict.fromkeys(BASE, "")
        row.update(id="RPT-001", based_on="QTO-002", as_printed="see based_on",
                   bbox="see based_on", method="native_text", status=CHECKED)
        folder = self.project / "02_Working" / RPT
        folder.mkdir(parents=True, exist_ok=True)
        columns = [c for c in list(self.LINE) + ["boq_status"] if c not in drop]
        with (folder / "boq.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows({"boq_status": status, **line} for line in lines)
        self.write_package(RPT, "records.csv", [row])

    def test_a_boq_whose_lines_match_their_records_has_no_findings(self):
        self.write_boq([self.LINE])
        result = evidence_package.check_project(self.project)
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["counts"]["boq_lines"], 1)

    def test_a_boq_line_with_no_quantity_record_is_reported(self):
        self.write_boq([self.LINE, {**self.LINE, "item_code": "QTO-099"},
                        {**self.LINE, "item_code": "QTO-001"}, {**self.LINE, "item_code": ""}])
        self.assertEqual(self.findings(), [
            (RPT, "boq_no_record", "QTO-099"),
            (RPT, "boq_no_record", "QTO-001"),
            (RPT, "boq_no_record", ""),
        ])

    def test_a_boq_line_that_differs_from_its_record_is_reported(self):
        for change in ({"quantity": "25.5"}, {"unit": "SF"}, {"unit": "lf"},
                       {"source_sheet": "S-2"}, {"formula": "[QTO-001]*1.1"},
                       {"source_revision": "REV 3"}, {"source_revision": ""}):
            with self.subTest(change=change):
                self.write_boq([{**self.LINE, **change}])
                self.assertEqual(self.findings(), [(RPT, "boq_differs", "QTO-002")])

    def test_a_quantity_record_missing_from_the_boq_is_reported(self):
        rows = qto_rows()
        rows.append({**rows[1], "id": "QTO-003"})
        self.write_package(QTO, "records.csv", rows)
        self.write_boq([self.LINE], status="DRAFT: all 2 quantity rows, not reviewed")
        self.assertEqual(self.findings(), [(RPT, "boq_missing_line", "QTO-003")])

    def test_an_unresolved_quantity_is_not_expected_in_the_boq(self):
        rows = qto_rows()
        rows.append({**rows[1], "id": "QTO-003", "quantity": "",
                     "status": "not checked: the plan and the schedule differ"})
        self.write_package(QTO, "records.csv", rows)
        self.write_boq([self.LINE], status=self.PARTIAL)
        self.assertEqual(self.findings(), [])

    def test_a_partial_boq_that_does_not_say_partial_is_reported(self):
        rows = qto_rows()
        rows.append({**rows[1], "id": "QTO-003", "quantity": "",
                     "status": "not checked: the plan and the schedule differ"})
        self.write_package(QTO, "records.csv", rows)
        self.write_boq([self.LINE], status=self.WHOLE)
        self.assertEqual(self.findings(), [(RPT, "boq_status_wrong", "")])

    def test_a_boq_without_the_revision_or_status_column_is_reported(self):
        for column in ("source_revision", "boq_status"):
            with self.subTest(column=column):
                self.write_boq([self.LINE], drop=(column,))
                self.assertEqual(self.findings(), [(RPT, "boq_missing_column", "")])

    def test_a_boq_line_for_an_id_two_records_share_is_not_matched(self):
        rows = qto_rows()
        rows.append({**rows[1]})
        self.write_package(QTO, "records.csv", rows)
        self.write_boq([self.LINE])
        self.assertIn((RPT, "boq_no_record", "QTO-002"), self.findings())

    def test_a_boq_line_listed_twice_is_reported(self):
        self.write_boq([self.LINE, self.LINE])
        self.assertEqual(self.findings(), [(RPT, "boq_no_record", "QTO-002")])


class HostilePathTests(ProjectCase):
    """Paths written to get the checker to read or trust something outside the project."""

    def add_line(self, agent, digest, relative):
        sums = self.project / "02_Working" / agent / "SHA256SUMS"
        sums.write_text(sums.read_text() + f"{digest}  {relative}\n", encoding="utf-8")

    def test_paths_that_are_not_in_plain_form_are_refused(self):
        digest = sha(self.project / REQUEST_REL)
        for relative in (f"02_Working/../{REQUEST_REL}", f"./{REQUEST_REL}",
                         REQUEST_REL.replace("/", "//"), "01_Received\\request.txt",
                         "01_Received/../../../etc/hosts", "~/request.txt",
                         "01_Received/no-such-folder/../request.txt"):
            with self.subTest(path=relative):
                self.write_sums(QTO)
                self.add_line(QTO, digest, relative)
                self.assertEqual(self.findings(), [(QTO, "path_outside_project", "")])

    def test_a_path_with_a_nul_byte_is_refused_without_an_error(self):
        checker = evidence_package._Checker(self.project)
        self.assertIsNone(checker.inside("01_Received/plans\x00.pdf"))

    def test_a_path_that_does_not_exist_outside_the_project_is_refused(self):
        rows = qto_rows()
        rows[0]["file"] = "../no-such-folder/no-such-file.pdf"
        self.write_package(QTO, "records.csv", rows)
        self.assertIn((QTO, "path_outside_project", "QTO-001"), self.findings())

    def test_a_package_folder_that_is_a_link_out_of_the_project_is_not_read(self):
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside)
        real = self.project / "02_Working" / QTO
        shutil.move(str(real), str(outside / QTO))
        os.symlink(outside / QTO, real)
        result = evidence_package.check_project(self.project)
        self.assertIn({"package": QTO, "check": "path_outside_project", "record": "",
                       "detail": f"02_Working/{QTO} is a link out of the project; not read"},
                      result["findings"])
        self.assertEqual(result["counts"]["records"], 5)

    def test_a_records_file_that_is_a_link_out_of_the_project_is_not_read(self):
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside)
        real = self.project / "02_Working" / QTO / "records.csv"
        shutil.move(str(real), str(outside / "records.csv"))
        os.symlink(outside / "records.csv", real)
        result = evidence_package.check_project(self.project)
        self.assertIn((QTO, "path_outside_project"),
                      [(f["package"], f["check"]) for f in result["findings"]])
        self.assertEqual(result["counts"]["records"], 5)

    def test_a_received_file_that_is_a_link_out_of_the_project_is_refused(self):
        os.remove(self.project / PDF_REL)
        os.symlink(FIXTURE_PATH, self.project / PDF_REL)
        found = self.findings()
        self.assertIn((DOC, "path_outside_project", ""), found)
        self.assertIn((QTO, "path_outside_project", "QTO-001"), found)


class ReceivedFileTests(ProjectCase):
    def test_a_received_drawing_that_is_gone_is_reported(self):
        os.remove(self.project / PDF_REL)
        found = self.findings()
        self.assertIn((DOC, "hash_mismatch", ""), found)

    def test_a_received_drawing_that_changed_is_reported_by_every_package_that_read_it(self):
        with (self.project / PDF_REL).open("ab") as handle:
            handle.write(b"\n% changed after the inventory\n")
        found = [f for f in self.findings() if f[1] == "hash_mismatch"]
        self.assertEqual(found, [(DOC, "hash_mismatch", ""), (QTO, "hash_mismatch", "")])


class RecordsFormTests(ProjectCase):
    def raw_rewrite(self, agent, name, change):
        path = self.project / "02_Working" / agent / name
        path.write_bytes(change(path.read_bytes()))
        self.write_sums(agent)

    def test_a_byte_order_mark_does_not_hide_the_records(self):
        self.raw_rewrite(QTO, "records.csv", lambda data: b"\xef\xbb\xbf" + data)
        result = evidence_package.check_project(self.project)
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["counts"]["records"], 7)

    def test_a_records_file_that_is_not_utf8_is_reported_not_raised(self):
        self.raw_rewrite(QTO, "records.csv", lambda data: data + b"QTO-009,\xff\xfe\n")
        self.assertIn((QTO, "unreadable_records", ""), self.findings())

    def test_a_column_named_twice_is_reported(self):
        self.raw_rewrite(QTO, "records.csv", lambda data: data.replace(
            b"assumptions\r\n", b"assumptions,quantity\r\n", 1))
        self.assertIn((QTO, "unreadable_records", ""), self.findings())

    def test_a_record_type_that_only_looks_like_quantity_is_reported(self):
        rows = qto_rows()
        rows[1]["record_type"] = "Quantity"
        self.write_package(QTO, "records.csv", rows)
        self.assertEqual(self.findings(), [(QTO, "bad_record_type", "QTO-002")])

    def test_a_quantity_with_a_number_needs_a_revision_and_a_listed_unit(self):
        for change in ({"revision": ""}, {"unit": "sqft"}):
            with self.subTest(change=change):
                rows = qto_rows()
                rows[1].update(change)
                self.write_package(QTO, "records.csv", rows)
                self.assertEqual(self.findings(), [(QTO, "incomplete_quantity", "QTO-002")])

    def test_a_revision_that_prints_nothing_is_no_revision(self):
        for revision in (" ", "\u200b", "\ufeff\u00a0"):
            with self.subTest(revision=ascii(revision)):
                rows = qto_rows()
                rows[1]["revision"] = revision
                self.write_package(QTO, "records.csv", rows)
                self.assertIn((QTO, "incomplete_quantity", "QTO-002"), self.findings())


class ImportTests(unittest.TestCase):
    def test_the_module_loads_without_pypdfium2_and_says_so_when_a_pdf_is_read(self):
        code = (
            "import sys, tempfile\n"
            "from pathlib import Path\n"
            "sys.modules['pypdfium2'] = None\n"
            "import evidence_package\n"
            "with tempfile.TemporaryDirectory() as folder:\n"
            "    checker = evidence_package._Checker(Path(folder))\n"
            "    print(checker.read_pdf_text('a.pdf', '1', ('0',) * 4))\n")
        done = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True,
                              cwd=Path(__file__).resolve().parent.parent)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(done.stdout.startswith("<could not read a.pdf page 1:"), done.stdout)
        self.assertIn("pypdfium2", done.stdout)


class RevisionTests(ProjectCase):
    def test_two_revisions_recorded_for_one_page_are_reported(self):
        rows = qto_rows()
        rows[0]["revision"] = "REV 3"
        self.write_package(QTO, "records.csv", rows)
        self.assertEqual(self.findings(), [(QTO, "revision_differs", "QTO-001")])

    def test_the_inventory_revision_is_the_reference(self):
        rows = doc_rows()
        rows[0]["revision"] = "REV 2"
        self.write_package(DOC, "register.csv", rows)
        self.assertEqual(self.findings(), [(QTO, "revision_differs", "QTO-001"),
                                           (QTO, "revision_differs", "QTO-002")])

    def test_rows_with_no_page_or_no_revision_are_not_compared(self):
        rows = qto_rows()
        rows[0]["revision"] = ""
        self.write_package(QTO, "records.csv", rows)
        self.assertEqual(self.findings(), [])


class VerifierFindingsTests(ProjectCase):
    """Cases an independent check of this module broke on 2026-11-23."""

    def add_line(self, agent, digest, relative):
        sums = self.project / "02_Working" / agent / "SHA256SUMS"
        sums.write_text(sums.read_text() + f"{digest}  {relative}\n", encoding="utf-8")

    def checks(self):
        return [check for _, check, _ in self.findings()]

    # --- no traceback ----------------------------------------------------

    def test_a_link_loop_is_a_finding_not_an_error(self):
        a, b = (self.project / "01_Received" / name for name in ("loopa", "loopb"))
        os.symlink(b, a)
        os.symlink(a, b)
        self.add_line(QTO, "0" * 64, "01_Received/loopa")
        self.assertIn((QTO, "path_outside_project", ""), self.findings())

    def test_a_name_too_long_for_the_file_system_is_a_finding_not_an_error(self):
        self.add_line(QTO, "0" * 64, "01_Received/" + "x" * 300)
        rows = doc_rows()
        rows[3]["bbox"] = "01_Received/" + "y" * 300
        self.write_package(DOC, "register.csv", rows)
        found = self.findings()
        self.assertIn((QTO, "hash_mismatch", ""), found)
        self.assertIn((DOC, "bad_bbox", "DOC-004"), found)

    def test_a_page_that_is_not_a_page_number_is_a_finding_not_an_error(self):
        for page in ("inf", "-inf", "1e999", "9" * 400, "01", "1.0", "\u0661", "0", "-1"):
            with self.subTest(page=page):
                rows = doc_rows()
                rows[0]["page"] = page
                self.write_package(DOC, "register.csv", rows)
                self.assertIn((DOC, "bad_page", "DOC-001"), self.findings())

    def test_a_hash_list_that_is_not_utf8_is_a_finding_not_an_error(self):
        (self.project / "02_Working" / QTO / "SHA256SUMS").write_bytes(b"\xff\xfe\x00bad")
        self.assertIn((QTO, "bad_manifest_line", ""), self.findings())

    def test_a_file_that_cannot_be_opened_is_a_finding_not_an_error(self):
        target = self.project / REQUEST_REL
        os.chmod(target, 0)
        self.addCleanup(os.chmod, target, 0o600)
        self.assertIn("hash_mismatch", self.checks())

    def test_a_missing_seals_file_is_a_usage_error_not_a_traceback(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(evidence_package.main(
                [str(self.project), "--seals", str(self.project / "no-such-seals.txt")]), 2)

    def test_two_recorded_seals_for_one_path_are_a_finding(self):
        seals = evidence_package.check_project(self.project)["seals"]
        right = [f"SEAL {digest}  {path}" for path, digest in sorted(seals.items())]
        wrong = f"SEAL {'0' * 64}  {PDF_REL}"
        seal_file = self.project.parent / f"{self.project.name}-two-seals.txt"
        self.addCleanup(lambda: seal_file.unlink() if seal_file.exists() else None)
        for name, lines in (("wrong first", [wrong] + right), ("wrong last", right + [wrong])):
            with self.subTest(order=name):
                seal_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = evidence_package.main([str(self.project), "--seals", str(seal_file)])
                self.assertEqual(code, 1)
                self.assertIn("seal_conflict", output.getvalue())
        # The same line twice is not a conflict.
        seal_file.write_text("\n".join(right + right) + "\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                evidence_package.main([str(self.project), "--seals", str(seal_file)]), 0)

    def test_a_text_line_number_too_long_to_be_a_number_is_a_finding(self):
        rows = doc_rows()
        rows[2]["bbox"] = "line " + "9" * 5000
        self.write_package(DOC, "register.csv", rows)
        self.assertIn((DOC, "read_back_mismatch", "DOC-003"), self.findings())

    # --- paths -----------------------------------------------------------

    def test_a_boq_that_is_a_link_out_of_the_project_is_not_read(self):
        outside = self.project.parent / f"{self.project.name}-boq.csv"
        outside.write_text("item_code\nSECRET-ID\n", encoding="utf-8")
        self.addCleanup(outside.unlink)
        folder = self.project / "02_Working" / RPT
        folder.mkdir()
        os.symlink(outside, folder / "boq.csv")
        result = evidence_package.check_project(self.project)
        self.assertNotIn("SECRET-ID", repr(result["findings"]))
        self.assertIn((RPT, "path_outside_project"),
                      [(f["package"], f["check"]) for f in result["findings"]])

    def test_a_second_spelling_of_a_file_in_another_letter_case_is_refused(self):
        self.add_line(QTO, sha(self.project / REQUEST_REL), "01_Received/REQUEST.TXT")
        self.assertEqual(self.findings(), [(QTO, "path_outside_project", "")])

    # --- IDs -------------------------------------------------------------

    def test_ids_use_plain_digits(self):
        rows = qto_rows()
        rows[1]["id"] = "QTO-\u0662"
        self.write_package(QTO, "records.csv", rows)
        self.assertIn((QTO, "bad_id", "QTO-\u0662"), self.findings())

    def test_ids_that_differ_only_by_leading_zeros_are_reported(self):
        rows = doc_rows()
        rows.append({**rows[3], "id": "DOC-04"})
        self.write_package(DOC, "register.csv", rows)
        self.assertEqual(self.findings(), [(DOC, "duplicate_id", "DOC-04")])

    # --- record types and evidence ---------------------------------------

    def test_a_record_type_outside_the_list_is_reported_in_a_takeoff_file(self):
        for text in ("qu\u0430ntity", "quantities", "qty", ""):
            with self.subTest(record_type=text):
                rows = qto_rows()
                rows[1]["record_type"] = text
                self.write_package(QTO, "records.csv", rows)
                self.assertEqual(self.findings(), [(QTO, "bad_record_type", "QTO-002")])

    def test_a_drawn_row_must_cite_a_page_that_opens(self):
        for change in ({"page": "999"}, {"file": REQUEST_REL, "page": "1"}):
            with self.subTest(change=change):
                rows = doc_rows()
                rows[3].update(as_printed="drawn", bbox="0,0,0,0", method="vector_geometry",
                               **change)
                self.write_package(DOC, "register.csv", rows)
                self.assertEqual(self.findings(), [(DOC, "bad_bbox", "DOC-004")])

    def test_a_crop_must_be_an_image_file(self):
        rows = doc_rows()
        rows[3].update(as_printed="OVERALL", bbox=f"02_Working/{DOC}/CHECK.md",
                       method="image_interpretation")
        self.write_package(DOC, "register.csv", rows)
        self.assertEqual(self.findings(), [(DOC, "bad_bbox", "DOC-004")])

    # --- BOQ -------------------------------------------------------------

    def write_boq_text(self, text):
        folder = self.project / "02_Working" / RPT
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "boq.csv").write_text(text, encoding="utf-8")
        row = dict.fromkeys(BASE, "")
        row.update(id="RPT-001", based_on="QTO-002", as_printed="see based_on",
                   bbox="see based_on", method="native_text", status=CHECKED)
        self.write_package(RPT, "records.csv", [row])

    def test_an_empty_boq_does_not_pass(self):
        header = ("item_code,quantity,unit,formula,source_sheet,notes,reviewer_initials,"
                  "source_revision,boq_status\n")
        for text in ("", "\n\n", header):
            with self.subTest(text=text[:10]):
                self.write_boq_text(text)
                self.assertIn((RPT, "boq_missing_line", "QTO-002"), self.findings())

    def test_boq_status_must_be_the_exact_text_with_the_real_counts(self):
        header = ("item_code,quantity,unit,formula,source_sheet,notes,reviewer_initials,"
                  "source_revision,boq_status\n")
        line = 'QTO-002,24.5,LF,[QTO-001],A1.01,overall wall,,none printed,"{}"\n'
        for status in ("DRAFTED AND REVIEWED - FINAL", "DRAFT: all 57 quantity rows, not reviewed",
                       "DRAFT: all 1 quantity rows, not reviewed. COMPLETE"):
            with self.subTest(status=status):
                self.write_boq_text(header + line.format(status))
                self.assertEqual(self.findings(), [(RPT, "boq_status_wrong", "")])
        self.write_boq_text(header + line.format("DRAFT: all 1 quantity rows, not reviewed"))
        self.assertEqual(self.findings(), [])

    # --- speed -----------------------------------------------------------

    def test_a_long_circle_and_a_dense_chain_are_checked_quickly(self):
        import time
        base = doc_rows()[3]
        circle = [{**base, "id": f"DOC-{n}", "based_on": f"DOC-{100 + (n - 99) % 400}"}
                  for n in range(100, 500)]
        dense = [{**base, "id": f"DOC-{n}",
                  "based_on": " ".join(f"DOC-{m}" for m in range(1000, n))}
                 for n in range(1000, 1200)]
        self.write_package(DOC, "register.csv", doc_rows() + circle + dense)
        start = time.monotonic()
        found = self.findings()
        self.assertLess(time.monotonic() - start, 5)
        self.assertEqual([f for f in found if f[1] == "cyclic_based_on"],
                         [(DOC, "cyclic_based_on", "DOC-100")])


if __name__ == "__main__":
    unittest.main()
