import math
import unittest

from vector_takeoff import (
    deduct_openings,
    distance_feet,
    plate_length_feet,
    polyline_length_feet,
    stud_count,
)


class VectorTakeoffTests(unittest.TestCase):
    def test_converts_distance_using_drawing_scale(self):
        self.assertAlmostEqual(distance_feet((0, 0), (3, 4), 12), 5 / 12)

    def test_polyline_sums_segment_lengths(self):
        self.assertAlmostEqual(
            polyline_length_feet([(0, 0), (4, 0), (4, 3)], 12),
            7 / 12,
        )

    def test_stud_count_includes_both_wall_ends(self):
        self.assertEqual(stud_count(10, 16 / 12), 9)

    def test_deducts_openings(self):
        self.assertEqual(deduct_openings(30, [6, 4]), 20)

    def test_rejects_openings_larger_than_wall(self):
        with self.assertRaises(ValueError):
            deduct_openings(10, [6, 5])

    def test_plate_length_uses_plate_count(self):
        self.assertEqual(plate_length_feet(20), 40)
        self.assertEqual(plate_length_feet(20, plate_count=3), 60)

    def test_rejects_invalid_inputs(self):
        for scale in (0, -1, math.inf, math.nan):
            with self.subTest(scale=scale), self.assertRaises(ValueError):
                distance_feet((0, 0), (1, 1), scale)

        with self.assertRaises(ValueError):
            stud_count(-1, 16 / 12)
        with self.assertRaises(ValueError):
            deduct_openings(10, [-1])
        with self.assertRaises(ValueError):
            plate_length_feet(10, plate_count=0)


if __name__ == "__main__":
    unittest.main()
