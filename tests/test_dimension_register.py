"""Dimension register tests. All data is synthetic."""

import unittest

from dimension_register import validate_register


def _entry(name, value, unit, source_sheet):
    return {"name": name, "value": value, "unit": unit, "source_sheet": source_sheet}


class ValidateRegisterTests(unittest.TestCase):
    def test_consistent_register_has_no_flags(self):
        entries = [
            _entry("wall height", 20.2, "FT", "A-3"),
            _entry("wall height", 20.2, "FT", "A-5"),
            _entry("thermal area", 1050, "SF", "A-4"),
        ]
        self.assertEqual(validate_register(entries), [])

    def test_wall_height_printed_with_two_values_is_flagged(self):
        flags = validate_register([
            _entry("wall height", 20.2, "FT", "A-3"),
            _entry("wall height", 18.77, "FT", "A-5"),
        ])
        self.assertEqual(flags, [{
            "issue": "conflicting_values",
            "name": "wall height",
            "occurrences": [
                {"value": 20.2, "unit": "FT", "source_sheet": "A-3"},
                {"value": 18.77, "unit": "FT", "source_sheet": "A-5"},
            ],
        }])

    def test_thermal_area_printed_with_two_values_is_flagged(self):
        flags = validate_register([
            _entry("thermal area", 1050, "SF", "A-4"),
            _entry("thermal area", 1314.5, "SF", "E-1"),
        ])
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0]["issue"], "conflicting_values")
        self.assertEqual([o["value"] for o in flags[0]["occurrences"]], [1050, 1314.5])

    def test_both_conflicts_are_flagged_in_one_register(self):
        flags = validate_register([
            _entry("wall height", 20.2, "FT", "A-3"),
            _entry("thermal area", 1050, "SF", "A-4"),
            _entry("wall height", 18.77, "FT", "A-5"),
            _entry("thermal area", 1314.5, "SF", "E-1"),
            _entry("slab thickness", 4, "IN", "A-3"),
        ])
        self.assertEqual(
            [(flag["issue"], flag["name"]) for flag in flags],
            [("conflicting_values", "wall height"), ("conflicting_values", "thermal area")],
        )

    def test_names_match_regardless_of_case_and_spacing(self):
        flags = validate_register([
            _entry("Wall Height", 20.2, "FT", "A-3"),
            _entry("  wall   height ", 18.77, "FT", "A-5"),
        ])
        self.assertEqual([flag["issue"] for flag in flags], ["conflicting_values"])

    def test_same_number_in_different_units_is_a_conflict(self):
        flags = validate_register([
            _entry("wall height", 20, "FT", "A-3"),
            _entry("wall height", 20, "IN", "A-5"),
        ])
        self.assertEqual([flag["issue"] for flag in flags], ["conflicting_values"])

    def test_missing_source_is_flagged(self):
        entries = [
            _entry("wall height", 20.2, "FT", ""),
            _entry("thermal area", 1050, "SF", None),
            {"name": "slab thickness", "value": 4, "unit": "IN"},
            _entry("roof pitch run", 12, "IN", "A-2"),
        ]
        flags = validate_register(entries)
        self.assertEqual(
            [(flag["issue"], flag["name"]) for flag in flags],
            [
                ("missing_source", "wall height"),
                ("missing_source", "thermal area"),
                ("missing_source", "slab thickness"),
            ],
        )
        self.assertEqual(flags[0]["occurrences"], [{"value": 20.2, "unit": "FT", "source_sheet": ""}])

    def test_validation_never_picks_a_value(self):
        entries = [
            _entry("wall height", 20.2, "FT", "A-3"),
            _entry("wall height", 18.77, "FT", "A-5"),
        ]
        snapshot = [dict(entry) for entry in entries]
        flag = validate_register(entries)[0]
        self.assertEqual(entries, snapshot)
        self.assertNotIn("resolved_value", flag)
        self.assertNotIn("value", flag)


if __name__ == "__main__":
    unittest.main()
