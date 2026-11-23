"""BOQ export tests. All data is synthetic."""

import csv
import tempfile
import unittest
from pathlib import Path

from boq import BOQ_COLUMNS, export_boq


def _item(**overrides):
    item = {
        "item_code": "W-01",
        "quantity": 128.4,
        "unit": "LF",
        "formula": "sum of wall segment lengths, door opening deducted",
        "source_sheet": "A-102",
        "notes": "door opening deducted per detail D-4",
        "reviewer_initials": "VV",
    }
    item.update(overrides)
    return item


class ExportBoqTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "nested" / "boq.csv"

    def _rows(self):
        with self.path.open(newline="", encoding="utf-8") as handle:
            return list(csv.reader(handle))

    def test_columns_are_the_auditable_boq_line_format(self):
        self.assertEqual(
            BOQ_COLUMNS,
            ("item_code", "quantity", "unit", "formula", "source_sheet", "notes", "reviewer_initials"),
        )

    def test_writes_header_and_one_row_per_item_in_order(self):
        items = [_item(), _item(item_code="S-02", quantity=42, unit="SF", source_sheet="A1.01")]
        result = export_boq(items, self.path)
        rows = self._rows()
        self.assertEqual(result, self.path)
        self.assertEqual(rows[0], list(BOQ_COLUMNS))
        self.assertEqual(rows[1], [
            "W-01", "128.4", "LF", "sum of wall segment lengths, door opening deducted",
            "A-102", "door opening deducted per detail D-4", "VV",
        ])
        self.assertEqual(rows[2][:3], ["S-02", "42", "SF"])
        self.assertEqual(len(rows), 3)

    def test_notes_and_reviewer_initials_may_be_left_out(self):
        item = _item()
        del item["notes"], item["reviewer_initials"]
        export_boq([item], self.path)
        self.assertEqual(self._rows()[1][5:], ["", ""])

    def test_empty_formula_raises_and_names_the_item_codes(self):
        items = [_item(), _item(item_code="S-02", formula=""), _item(item_code="C-03", formula="   ")]
        with self.assertRaisesRegex(ValueError, r"formula.*S-02.*C-03") as caught:
            export_boq(items, self.path)
        self.assertNotIn("W-01", str(caught.exception))

    def test_empty_or_missing_source_sheet_raises_and_names_the_item_codes(self):
        missing = _item(item_code="S-02")
        del missing["source_sheet"]
        items = [_item(), missing, _item(item_code="C-03", source_sheet=None)]
        with self.assertRaisesRegex(ValueError, r"source_sheet.*S-02.*C-03"):
            export_boq(items, self.path)

    def test_both_problems_are_reported_in_one_error(self):
        items = [_item(item_code="S-02", formula=""), _item(item_code="C-03", source_sheet="")]
        with self.assertRaises(ValueError) as caught:
            export_boq(items, self.path)
        message = str(caught.exception)
        self.assertRegex(message, r"formula.*S-02")
        self.assertRegex(message, r"source_sheet.*C-03")

    def test_nothing_is_written_when_validation_fails(self):
        with self.assertRaises(ValueError):
            export_boq([_item(formula="")], self.path)
        self.assertFalse(self.path.exists())


class ExtraColumnTests(unittest.TestCase):
    def test_extra_columns_follow_the_seven_and_change_nothing_else(self):
        with tempfile.TemporaryDirectory() as folder:
            path = export_boq([_item(source_revision="REV 2")], Path(folder) / "boq.csv",
                              extra_columns=("source_revision", "boq_status"))
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.reader(handle))
        self.assertEqual(rows[0], list(BOQ_COLUMNS) + ["source_revision", "boq_status"])
        self.assertEqual(rows[1][-2:], ["REV 2", ""])


if __name__ == "__main__":
    unittest.main()
