import math
import unittest

from framing_takeoff import calculate_plate_lf


class CalculatePlateLfTests(unittest.TestCase):
    def test_three_courses_with_five_percent_waste(self):
        # 20 ft wall x 3 plate courses = 60 LF; 5% waste = 63 LF.
        self.assertAlmostEqual(calculate_plate_lf(20, 3, 5), 63)

    def test_one_course_without_waste(self):
        self.assertAlmostEqual(calculate_plate_lf(20, 1, 0), 20)

    def test_fractional_wall_length(self):
        self.assertAlmostEqual(calculate_plate_lf(12.5, 3, 5), 39.375)

    def test_rejects_non_positive_or_non_finite_wall_length(self):
        for length in (0, -1, math.inf, -math.inf, math.nan):
            with self.subTest(length=length), self.assertRaises(ValueError):
                calculate_plate_lf(length, 3, 5)

    def test_rejects_invalid_plate_course_count(self):
        for courses in (0, -1, 1.5, True, "3"):
            with self.subTest(courses=courses), self.assertRaises(ValueError):
                calculate_plate_lf(20, courses, 5)

    def test_rejects_invalid_waste_percentage(self):
        for waste in (-0.1, 100.1, math.inf, math.nan):
            with self.subTest(waste=waste), self.assertRaises(ValueError):
                calculate_plate_lf(20, 3, waste)


if __name__ == "__main__":
    unittest.main()
