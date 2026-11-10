import math
import unittest

from vector_takeoff import distance_feet


class DistanceFeetTests(unittest.TestCase):
    def test_converts_distance_using_drawing_scale(self):
        self.assertAlmostEqual(distance_feet((0, 0), (3, 4), 12), 5 / 12)

    def test_horizontal_and_vertical_segments(self):
        self.assertEqual(distance_feet((2, 1), (8, 1), 2), 3)
        self.assertEqual(distance_feet((2, 1), (2, 5), 2), 2)

    def test_rejects_invalid_scale(self):
        for scale in (0, -1, math.inf, math.nan):
            with self.subTest(scale=scale), self.assertRaises(ValueError):
                distance_feet((0, 0), (1, 1), scale)

    def test_rejects_invalid_points(self):
        for point in ((0,), (0, 1, 2), (0, math.nan), (0, math.inf)):
            with self.subTest(point=point), self.assertRaises(ValueError):
                distance_feet(point, (1, 1), 1)


if __name__ == "__main__":
    unittest.main()
