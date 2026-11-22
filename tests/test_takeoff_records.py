"""Checks on takeoff_records: takeoff record rows to the BOQ export and the register."""
from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import takeoff_records
from boq import BOQ_COLUMNS, export_boq
from dimension_register import validate_register


def row(record_id, record_type, **fields):
    base = dict.fromkeys(takeoff_records.TAKEOFF_COLUMNS, "")
    base.update(id=record_id, record_type=record_type, sheet="S-3", item="slab on grade")
    base.update(fields)
    return base


RECORDS = [
    row("QTO-001", "input", dimension="slab length", quantity="40", unit="FT",
        formula="40 + 0/12"),
    row("QTO-002", "input", dimension="slab width", quantity="24", unit="FT",
        formula="24 + 0/12"),
    row("QTO-003", "quantity", description="Slab area, net as drawn",
        formula="[QTO-001]*[QTO-002]", quantity="960", unit="SF",
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


if __name__ == "__main__":
    unittest.main()
