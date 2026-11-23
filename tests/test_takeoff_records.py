"""Checks on takeoff_records: takeoff record rows to the BOQ export and the register."""
from __future__ import annotations

import contextlib
import csv
import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import takeoff_records
from boq import BOQ_COLUMNS, export_boq
from dimension_register import validate_register


def row(record_id, record_type, **fields):
    base = dict.fromkeys(takeoff_records.TAKEOFF_COLUMNS, "")
    base.update(id=record_id, record_type=record_type, sheet="S-3", revision="",
                item="slab on grade")
    base.update(fields)
    return base


RECORDS = [
    row("QTO-001", "input", dimension="slab length", quantity="40", unit="FT",
        formula="40 + 0/12"),
    row("QTO-002", "input", dimension="slab width", quantity="24", unit="FT",
        formula="24 + 0/12"),
    row("QTO-003", "quantity", description="Slab area, net as drawn",
        formula="[QTO-001]*[QTO-002]", quantity="960", unit="SF", revision="REV 2",
        assumptions="No opening is drawn."),
    row("QTO-004", "calc", formula="[QTO-003]*4/12", quantity="320", unit="CF"),
    row("QTO-005", "quantity", description="F-1 count", item="pad footing F-1",
        sheet="S-1", formula="none", quantity="", unit="EA",
        assumptions="Plan shows 4 and the schedule shows 5."),
]


class BoqItemsTests(unittest.TestCase):
    def test_only_quantity_rows_with_a_number_become_boq_lines(self):
        items, not_exported = takeoff_records.boq_items_from_records(RECORDS)
        self.assertEqual(items, [{
            "item_code": "QTO-003",
            "quantity": "960",
            "unit": "SF",
            "formula": "[QTO-001]*[QTO-002]",
            "source_sheet": "S-3",
            "notes": "slab on grade: Slab area, net as drawn; No opening is drawn.",
            "reviewer_initials": "",
        }])
        self.assertEqual([r["id"] for r in not_exported], ["QTO-005"])

    def test_a_quantity_row_without_a_number_never_gets_one(self):
        for text in ("", "HELD", "about 5"):
            with self.subTest(quantity=text):
                held = [row("QTO-009", "quantity", quantity=text, formula="none")]
                items, not_exported = takeoff_records.boq_items_from_records(held)
                self.assertEqual(items, [])
                self.assertEqual(len(not_exported), 1)

    def test_the_lines_go_through_export_boq(self):
        items, _ = takeoff_records.boq_items_from_records(RECORDS)
        with tempfile.TemporaryDirectory() as folder:
            path = export_boq(items, Path(folder) / "boq.csv")
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.reader(handle))
        self.assertEqual(tuple(rows[0]), BOQ_COLUMNS)
        self.assertEqual(rows[1][:3], ["QTO-003", "960", "SF"])

    def test_a_line_with_no_sheet_is_still_refused_by_export_boq(self):
        records = [row("QTO-003", "quantity", sheet="", quantity="960", unit="SF",
                       formula="[QTO-001]*[QTO-002]")]
        items, _ = takeoff_records.boq_items_from_records(records)
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "QTO-003"):
                export_boq(items, Path(folder) / "boq.csv")


class RegisterEntriesTests(unittest.TestCase):
    def test_rows_that_name_a_dimension_become_register_entries(self):
        entries = takeoff_records.register_entries_from_records(RECORDS)
        self.assertEqual(entries, [
            {"name": "slab length", "value": "40", "unit": "FT", "source_sheet": "S-3"},
            {"name": "slab width", "value": "24", "unit": "FT", "source_sheet": "S-3"},
        ])
        self.assertEqual(validate_register(entries), [])

    def test_the_same_dimension_read_twice_with_two_values_is_flagged(self):
        records = [
            row("QTO-010", "calc", dimension="F-1 count", quantity="4", unit="EA", sheet="S-1"),
            row("QTO-011", "calc", dimension="F-1 count", quantity="5", unit="EA", sheet="S-2"),
        ]
        flags = validate_register(takeoff_records.register_entries_from_records(records))
        self.assertEqual([flag["issue"] for flag in flags], ["conflicting_values"])
        self.assertEqual(
            [o["source_sheet"] for o in flags[0]["occurrences"]], ["S-1", "S-2"])


class CommandLineTests(unittest.TestCase):
    def test_it_writes_the_boq_and_reports_what_it_left_out(self):
        with tempfile.TemporaryDirectory() as folder:
            records_path = Path(folder) / "records.csv"
            with records_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(RECORDS[0]))
                writer.writeheader()
                writer.writerows(RECORDS)
            boq_path = Path(folder) / "out" / "boq.csv"
            code = takeoff_records.main([str(records_path), str(boq_path)])
            with boq_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.reader(handle))
        # One quantity has no number, so the result is not clean.
        self.assertEqual(code, 1)
        self.assertEqual([r[0] for r in rows], ["item_code", "QTO-003"])


def good(record_id="QTO-003", **fields):
    base = dict(sheet="S-3", quantity="960", unit="SF", formula="[QTO-001]*[QTO-002]")
    base.update(fields)
    return row(record_id, "quantity", **base)


class QuantityValidationTests(unittest.TestCase):
    """A quantity row becomes a BOQ line only when every part of it is usable."""

    def exported(self, records):
        items, not_exported = takeoff_records.boq_items_from_records(records)
        return [i["item_code"] for i in items], [r["id"] for r in not_exported]

    def test_a_good_row_has_no_problems(self):
        self.assertEqual(takeoff_records.quantity_row_problems(good()), [])
        self.assertEqual(self.exported([good()]), (["QTO-003"], []))

    def test_nan_and_infinity_are_not_numbers(self):
        for text in ("nan", "NaN", "inf", "+inf", "-inf", "Infinity", "-Infinity"):
            with self.subTest(quantity=text):
                self.assertEqual(self.exported([good(quantity=text)]), ([], ["QTO-003"]))
                self.assertTrue(takeoff_records.quantity_row_problems(good(quantity=text)))

    def test_other_number_spellings_are_refused(self):
        for text in ("1e3", "1_000", "1,000", "0x10", "12 SF", "+5", "-5", "5.", "1/2",
                     "\u0665", "5 5"):
            with self.subTest(quantity=text):
                self.assertEqual(self.exported([good(quantity=text)]), ([], ["QTO-003"]))

    def test_plain_decimals_are_accepted_as_written(self):
        for text in ("960", "11.85", "0.5", ".5", "007"):
            with self.subTest(quantity=text):
                items, _ = takeoff_records.boq_items_from_records([good(quantity=text)])
                self.assertEqual([i["quantity"] for i in items], [text])

    def test_a_stated_zero_is_a_quantity(self):
        for text in ("0", "0.0"):
            with self.subTest(quantity=text):
                self.assertEqual(self.exported([good(quantity=text)]), (["QTO-003"], []))

    def test_a_row_with_no_unit_is_refused(self):
        for text in ("", "   "):
            with self.subTest(unit=text):
                self.assertEqual(self.exported([good(unit=text)]), ([], ["QTO-003"]))
                self.assertIn("no unit", takeoff_records.quantity_row_problems(good(unit=text)))

    def test_a_missing_or_malformed_id_is_refused(self):
        for text in ("", "QTO-", "QTO-1a", "STR-003", "qto-003", "QTO 003", "QTO-003 "):
            with self.subTest(id=text):
                record = good()
                record["id"] = text
                items, not_exported = takeoff_records.boq_items_from_records([record])
                self.assertEqual(items, [])
                self.assertEqual(len(not_exported), 1)

    def test_a_repeated_id_is_refused_every_time_it_appears(self):
        records = [good(), good(quantity="961")]
        self.assertEqual(self.exported(records), ([], ["QTO-003", "QTO-003"]))

    def test_a_missing_formula_or_sheet_is_a_named_problem(self):
        self.assertEqual(takeoff_records.quantity_row_problems(good(formula=" ")), ["no formula"])
        self.assertEqual(takeoff_records.quantity_row_problems(good(sheet="")),
                         ["no source sheet"])

    def test_an_unresolved_quantity_stays_empty_and_is_not_a_defect(self):
        held = row("QTO-005", "quantity", quantity="", unit="EA", formula="none")
        self.assertEqual(takeoff_records.quantity_row_problems(held), [])
        items, not_exported = takeoff_records.boq_items_from_records([held])
        self.assertEqual(items, [])
        self.assertEqual(not_exported[0]["quantity"], "")


class PartialExportTests(unittest.TestCase):
    def run_cli(self, records):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder)
        records_path = folder / "records.csv"
        with records_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
        boq_path = folder / "boq.csv"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = takeoff_records.main([str(records_path), str(boq_path)])
        status_path = folder / "boq.csv.STATUS.txt"
        status = status_path.read_text(encoding="utf-8") if status_path.is_file() else None
        return code, boq_path, status, output.getvalue()

    def test_a_partial_export_says_so_beside_the_file_and_on_screen(self):
        code, boq_path, status, output = self.run_cli(RECORDS)
        self.assertEqual(code, 1)
        self.assertTrue(boq_path.is_file())
        self.assertTrue(status.startswith("PARTIAL DRAFT"))
        self.assertIn("QTO-005", status)
        self.assertIn("1 of 2", status)
        self.assertTrue(output.startswith("PARTIAL DRAFT"))

    def test_a_full_export_is_still_a_draft_with_no_reviewer(self):
        code, boq_path, status, output = self.run_cli(
            [dict(record, revision="REV 2") for record in RECORDS[:4]])
        self.assertEqual(code, 0)
        self.assertTrue(status.startswith("DRAFT"))
        self.assertNotIn("PARTIAL", status)
        self.assertIn("not reviewed", status)
        with boq_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([r["reviewer_initials"] for r in rows], [""])

    def test_a_defective_row_stops_the_export_and_nothing_is_written(self):
        for change in ({"quantity": "nan"}, {"unit": ""}, {"formula": ""}, {"sheet": ""},
                       {"quantity": "about 5"}):
            with self.subTest(change=change):
                code, boq_path, status, output = self.run_cli(RECORDS[:4] + [good("QTO-006", **change)])
                self.assertEqual(code, 1)
                self.assertFalse(boq_path.exists())
                self.assertTrue(status.startswith("NOT WRITTEN"))
                self.assertIn("REJECTED QTO-006", output)

    def test_no_quantity_rows_is_not_an_empty_complete_boq(self):
        code, boq_path, status, output = self.run_cli(RECORDS[:2])
        self.assertEqual(code, 1)
        self.assertFalse(boq_path.exists())
        self.assertTrue(status.startswith("NOT WRITTEN"))


class UnusualInputTests(unittest.TestCase):
    """Rows that try to get past the checks by their type, spelling or encoding."""

    def test_values_that_are_not_text_are_judged_by_what_they_would_print(self):
        for value, exported in ((float("nan"), False), (float("inf"), False), (True, False),
                                (1e20, False), (b"5", False), (["5"], False), (None, False),
                                (5, True), (12.5, True)):
            with self.subTest(quantity=value):
                items, _ = takeoff_records.boq_items_from_records([good(quantity=value)])
                self.assertEqual(bool(items), exported)

    def test_a_record_type_that_only_looks_like_quantity_is_a_defect(self):
        for text in ("Quantity", "QUANTITY", "quantity\u200b", "quantit\u0443", "quantity."):
            with self.subTest(record_type=text):
                record = good()
                record["record_type"] = text
                items, not_exported = takeoff_records.boq_items_from_records([record])
                self.assertEqual(items, [])
                if text != "quantit\u0443":
                    self.assertEqual(len(not_exported), 1)
                    self.assertEqual(len(takeoff_records.rejected_quantity_rows([record])), 1)

    def test_a_unit_outside_the_rulebook_list_is_refused(self):
        for text in ("sf", "SQFT", "M2", "FT", "S F", "SF.", "EACH"):
            with self.subTest(unit=text):
                items, not_exported = takeoff_records.boq_items_from_records([good(unit=text)])
                self.assertEqual((items, len(not_exported)), ([], 1))
                self.assertIn("is not one of", takeoff_records.quantity_row_problems(
                    good(unit=text))[0])

    def test_every_rulebook_unit_is_accepted(self):
        self.assertEqual(takeoff_records.ALLOWED_UNITS, (
            "LF", "SF", "SY", "CF", "CY", "EA", "LS", "LB", "TON", "GAL", "SQ", "BF", "MBF"))
        for unit in takeoff_records.ALLOWED_UNITS:
            self.assertEqual(takeoff_records.quantity_row_problems(good(unit=unit)), [])


class RecordsFileTests(unittest.TestCase):
    HEADER = "id,record_type,item,sheet,revision,quantity,unit,formula\n"
    ROW = "QTO-001,quantity,slab,S-3,REV 2,960,SF,40*24\n"

    def run_cli(self, data: bytes, earlier_boq: str | None = None):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder)
        (folder / "records.csv").write_bytes(data)
        boq_path = folder / "boq.csv"
        if earlier_boq is not None:
            boq_path.write_text(earlier_boq, encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = takeoff_records.main([str(folder / "records.csv"), str(boq_path)])
        return code, folder, output.getvalue()

    def test_a_plain_file_is_exported_with_revision_and_status_on_every_line(self):
        code, folder, output = self.run_cli((self.HEADER + self.ROW).encode())
        self.assertEqual(code, 0)
        with (folder / "boq.csv").open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows[0]["source_revision"], "REV 2")
        self.assertTrue(rows[0]["boq_status"].startswith("DRAFT"))
        self.assertIn("not reviewed", rows[0]["boq_status"])

    def test_every_line_of_a_partial_boq_says_partial_draft(self):
        held = "QTO-002,quantity,slab,S-3,REV 2,,CY,none\n"
        code, folder, output = self.run_cli((self.HEADER + self.ROW + held).encode())
        self.assertEqual(code, 1)
        with (folder / "boq.csv").open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([r["boq_status"][:22] for r in rows], ["PARTIAL DRAFT: 1 of 2 "])

    def test_a_number_with_no_revision_writes_no_boq(self):
        for revision in ("", " ", "\u200b", "\ufeff\u00a0"):
            with self.subTest(revision=ascii(revision)):
                row = f"QTO-001,quantity,slab,S-3,{revision},960,SF,40*24\n"
                code, folder, output = self.run_cli((self.HEADER + self.ROW.replace("001", "002")
                                                     + row).encode(), earlier_boq="old\n")
                self.assertEqual(code, 1)
                self.assertTrue(output.startswith("NOT WRITTEN"), output)
                self.assertIn("REJECTED QTO-001: no revision", output)
                self.assertFalse((folder / "boq.csv").exists())
                self.assertEqual((folder / "boq.csv.SUPERSEDED").read_text(), "old\n")

    def test_a_held_quantity_needs_no_revision(self):
        held = "QTO-002,quantity,wall,A-1,,,SF,none\n"
        code, folder, output = self.run_cli((self.HEADER + self.ROW + held).encode())
        self.assertEqual(code, 1)
        self.assertTrue(output.startswith("PARTIAL DRAFT"), output)
        with (folder / "boq.csv").open(newline="", encoding="utf-8") as handle:
            self.assertEqual([r["source_revision"] for r in csv.DictReader(handle)], ["REV 2"])

    def test_an_earlier_superseded_copy_is_never_written_over(self):
        bad = (self.HEADER + self.ROW.replace("960", "nan")).encode()
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder)
        (folder / "records.csv").write_bytes(bad)
        (folder / "boq.csv.SUPERSEDED.3").mkdir()
        kept = {}
        for text, name in (("first\n", "boq.csv.SUPERSEDED"), ("second\n", "boq.csv.SUPERSEDED.2"),
                           ("third\n", "boq.csv.SUPERSEDED.4")):
            (folder / "boq.csv").write_text(text, encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(takeoff_records.main([str(folder / "records.csv"),
                                                       str(folder / "boq.csv")]), 1)
            kept[name] = text
            self.assertFalse((folder / "boq.csv").exists())
            self.assertIn(f"renamed {name}.", output.getvalue())
            self.assertIn(f"renamed {name}.", (folder / "boq.csv.STATUS.txt").read_text())
            for kept_name, kept_text in kept.items():
                self.assertEqual((folder / kept_name).read_text(), kept_text)
        self.assertTrue((folder / "boq.csv.SUPERSEDED.3").is_dir())

    def test_a_byte_order_mark_does_not_hide_the_id_column(self):
        code, folder, output = self.run_cli(b"\xef\xbb\xbf" + (self.HEADER + self.ROW).encode())
        self.assertEqual(code, 0)

    def test_files_that_cannot_be_read_as_records_write_no_boq(self):
        cases = {
            "not utf-8": (self.HEADER + self.ROW).encode() + b"QTO-002,quantity,\xff\xfe\n",
            "a column named twice": (self.HEADER.replace("formula", "formula,quantity")
                                     + self.ROW.replace("40*24", "40*24,nan")).encode(),
            "a row longer than the header": (self.HEADER + self.ROW.replace("40*24", "40*24,7")
                                             ).encode(),
            "a row shorter than the header": (self.HEADER + "QTO-001,quantity,slab\n").encode(),
            "a NUL byte": (self.HEADER + self.ROW).encode().replace(b"slab", b"sl\x00ab"),
        }
        for name, data in cases.items():
            with self.subTest(case=name):
                code, folder, output = self.run_cli(data)
                self.assertEqual(code, 1)
                self.assertFalse((folder / "boq.csv").exists())
                self.assertTrue(output.startswith("NOT WRITTEN"))

    def test_a_boq_from_an_earlier_run_does_not_survive_a_refused_run(self):
        bad = self.ROW.replace("960", "nan")
        code, folder, output = self.run_cli((self.HEADER + bad).encode(),
                                            earlier_boq="item_code\nQTO-001\n")
        self.assertEqual(code, 1)
        self.assertFalse((folder / "boq.csv").exists())
        self.assertEqual((folder / "boq.csv.SUPERSEDED").read_text(), "item_code\nQTO-001\n")
        self.assertIn("boq.csv.SUPERSEDED", (folder / "boq.csv.STATUS.txt").read_text())


class VerifierFindingsTests(RecordsFileTests):
    """Cases an independent check of this module broke on 2026-11-23."""

    def not_written(self, data, earlier_boq=None):
        code, folder, output = self.run_cli(data, earlier_boq)
        self.assertEqual(code, 1)
        self.assertFalse((folder / "boq.csv").exists())
        self.assertTrue(output.startswith("NOT WRITTEN"), output)
        return folder, output

    def test_a_line_separator_inside_a_cell_does_not_make_a_hidden_row(self):
        for separator in ("\u2028", "\u2029", "\x85", "\x0b", "\x0c", "\x1c"):
            with self.subTest(separator=repr(separator)):
                row = self.ROW.replace("slab", "slab" + separator + "QTO-009,quantity,x,S-3,REV 2,999,LF,1")
                code, folder, output = self.run_cli((self.HEADER + row).encode())
                boq = folder / "boq.csv"
                if boq.exists():
                    with boq.open(newline="", encoding="utf-8") as handle:
                        codes = [r["item_code"] for r in csv.DictReader(handle)]
                    self.assertEqual(codes, ["QTO-001"])

    def test_an_unclosed_quote_that_swallows_a_row_is_refused(self):
        data = self.HEADER + self.ROW.replace("40*24", '"40*24') + self.ROW.replace("001", "002")
        self.not_written(data.encode())

    def test_only_the_listed_record_types_are_allowed(self):
        for text in ("qu\u0430ntity", "quant\u0131ty", "quantities", "quantity row", "qty", ""):
            with self.subTest(record_type=text):
                bad = self.ROW.replace("QTO-001,quantity", f"QTO-002,{text}").replace("960", "nan")
                folder, output = self.not_written((self.HEADER + self.ROW + bad).encode())
                self.assertIn("REJECTED QTO-002", output)
        self.assertEqual(takeoff_records.RECORD_TYPES, (
            "input", "calc", "deduction", "scale", "comparison", "alternative", "quantity"))

    def test_cells_of_invisible_characters_count_as_empty(self):
        for column, value in (("40*24", "\u200b"), ("S-3", "\u200b\u00a0"), ("SF", "\ufeff")):
            with self.subTest(replaced=column):
                self.not_written((self.HEADER + self.ROW.replace(column, value)).encode())

    def test_a_cell_a_spreadsheet_would_run_is_refused(self):
        for value in ("=1+1", "+cmd", "-2+3", "@SUM(1)", '"=HYPERLINK(""http://x"",""S-3"")"'):
            for column in ("40*24", "S-3", "slab"):
                with self.subTest(value=value, replaced=column):
                    self.not_written((self.HEADER + self.ROW.replace(column, value)).encode())

    def test_a_header_without_the_needed_columns_is_refused(self):
        for old, new in (("quantity,", "Quantity,"), (",unit", ", unit"), ("id,", "ID,")):
            with self.subTest(header=new):
                self.not_written((self.HEADER.replace(old, new, 1) + self.ROW).encode())

    def test_a_records_file_that_is_missing_sets_the_old_boq_aside(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder)
        (folder / "boq.csv").write_text("old\n", encoding="utf-8")
        (folder / "boq.csv.STATUS.txt").write_text("DRAFT. old status\n", encoding="utf-8")
        for records in (folder / "missing.csv", folder):
            with self.subTest(records=records.name), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(takeoff_records.main([str(records), str(folder / "boq.csv")]), 1)
        self.assertFalse((folder / "boq.csv").exists())
        self.assertTrue((folder / "boq.csv.STATUS.txt").read_text().startswith("NOT WRITTEN"))

    def test_paths_that_would_overwrite_the_records_are_refused(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder)
        text = self.HEADER + self.ROW
        for records_name, boq_name in (("r.csv", "r.csv"), ("b.csv.STATUS.txt", "b.csv"),
                                       ("b.csv.SUPERSEDED", "b.csv")):
            with self.subTest(records=records_name, boq=boq_name):
                (folder / records_name).write_text(text, encoding="utf-8")
                with contextlib.redirect_stdout(io.StringIO()):
                    code = takeoff_records.main([str(folder / records_name),
                                                 str(folder / boq_name)])
                self.assertEqual(code, 2)
                self.assertEqual((folder / records_name).read_text(encoding="utf-8"), text)

    def test_output_paths_that_are_links_or_folders_are_refused(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder)
        (folder / "r.csv").write_text(self.HEADER + self.ROW, encoding="utf-8")
        (folder / "victim.txt").write_text("keep\n", encoding="utf-8")
        os.symlink(folder / "victim.txt", folder / "a.csv.STATUS.txt")
        os.symlink(folder / "victim.txt", folder / "b.csv")
        (folder / "c.csv.SUPERSEDED").mkdir()
        (folder / "d.csv").mkdir()
        for boq_name in ("a.csv", "b.csv", "c.csv", "d.csv"):
            with self.subTest(boq=boq_name), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    takeoff_records.main([str(folder / "r.csv"), str(folder / boq_name)]), 2)
        self.assertEqual((folder / "victim.txt").read_text(), "keep\n")

    def test_a_boq_path_that_is_the_records_file_under_another_name_is_refused(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder)
        text = self.HEADER + self.ROW
        (folder / "r.csv").write_text(text, encoding="utf-8")
        os.link(folder / "r.csv", folder / "linked.csv")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                takeoff_records.main([str(folder / "r.csv"), str(folder / "linked.csv")]), 2)
        self.assertEqual((folder / "r.csv").read_text(encoding="utf-8"), text)
        # Another case, or the other Unicode spelling of an accented name, is the
        # same file on some disks and a new file on others.
        (folder / "caf\u00e9.csv").write_text(text, encoding="utf-8")
        for records_name, boq_name in (("r.csv", "R.CSV"), ("caf\u00e9.csv", "cafe\u0301.csv")):
            with self.subTest(boq=boq_name):
                same_file = (folder / boq_name).exists()
                with contextlib.redirect_stdout(io.StringIO()):
                    code = takeoff_records.main([str(folder / records_name),
                                                 str(folder / boq_name)])
                self.assertEqual((folder / records_name).read_text(encoding="utf-8"), text)
                if same_file:
                    self.assertEqual(code, 2)

    def test_an_output_file_that_has_a_second_name_is_refused(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder)
        (folder / "r.csv").write_text(self.HEADER + self.ROW, encoding="utf-8")
        (folder / "victim.txt").write_text("keep\n", encoding="utf-8")
        os.link(folder / "victim.txt", folder / "a.csv")
        os.link(folder / "victim.txt", folder / "b.csv.STATUS.txt")
        for boq_name in ("a.csv", "b.csv"):
            with self.subTest(boq=boq_name), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    takeoff_records.main([str(folder / "r.csv"), str(folder / boq_name)]), 2)
        self.assertEqual((folder / "victim.txt").read_text(), "keep\n")

    def test_ids_with_the_same_number_written_two_ways_write_no_boq(self):
        second = self.ROW.replace("QTO-001", "QTO-1").replace("slab", "wall")
        _, output = self.not_written((self.HEADER + self.ROW + second).encode())
        self.assertIn("REJECTED QTO-001", output)
        self.assertIn("REJECTED QTO-1", output)
        records = [good("QTO-3"), good("QTO-003"), good("QTO-4")]
        items, not_exported = takeoff_records.boq_items_from_records(records)
        self.assertEqual([item["item_code"] for item in items], ["QTO-4"])
        self.assertEqual([r["id"] for r in not_exported], ["QTO-3", "QTO-003"])

    def test_a_full_width_sign_at_the_start_of_a_cell_is_refused(self):
        for value in ("\uff1d1+1", "\uff0bcmd", "\uff0d2+3", "\uff20SUM(1)"):
            for column in ("40*24", "S-3", "slab", "REV 2"):
                with self.subTest(value=value, replaced=column):
                    self.not_written((self.HEADER + self.ROW.replace(column, value)).encode())

    def test_a_boq_that_cannot_be_replaced_is_reported_without_a_traceback(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: (os.chmod(folder, 0o700), shutil.rmtree(folder)))
        (folder / "r.csv").write_text(self.HEADER + self.ROW, encoding="utf-8")
        os.chmod(folder, 0o500)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(takeoff_records.main([str(folder / "r.csv"),
                                                   str(folder / "boq.csv")]), 1)
        self.assertIn("NOT WRITTEN", output.getvalue())


if __name__ == "__main__":
    unittest.main()
