import math
import unittest

from framing_takeoff import calculate_plate_lf, plan_stock_cuts


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


class PlanStockCutsTests(unittest.TestCase):
    def test_all_cuts_are_assigned_and_offcuts_are_reported(self):
        plan = plan_stock_cuts([8, 6, 4], [8, 10, 12])
        assigned = [cut for board in plan["boards"] for cut in board["cuts_ft"]]

        self.assertCountEqual(assigned, [8, 6, 4])
        self.assertAlmostEqual(plan["total_cut_lf"], 18)
        self.assertAlmostEqual(plan["total_stock_lf"], 18)
        self.assertAlmostEqual(plan["offcut_lf"], 0)

    def test_reuses_a_board_offcut_for_another_cut(self):
        plan = plan_stock_cuts([6, 4, 3], [8, 10])
        self.assertEqual(len(plan["boards"]), 2)
        self.assertCountEqual(
            [cut for board in plan["boards"] for cut in board["cuts_ft"]],
            [6, 4, 3],
        )

    def test_accounts_for_saw_kerf(self):
        plan = plan_stock_cuts([5, 4], [10], kerf_ft=0.01)
        self.assertEqual(len(plan["boards"]), 1)
        self.assertAlmostEqual(plan["boards"][0]["kerf_total_ft"], 0.02)
        self.assertAlmostEqual(plan["boards"][0]["remaining_ft"], 0.98)

    def test_returns_empty_plan_for_no_cuts(self):
        plan = plan_stock_cuts([], [8, 10])
        self.assertEqual(plan["boards"], [])
        self.assertEqual(plan["total_stock_lf"], 0)

    def test_rejects_cut_longer_than_available_stock(self):
        with self.assertRaises(ValueError):
            plan_stock_cuts([12.1], [8, 10, 12])

    def test_rejects_invalid_lengths_and_kerf(self):
        invalid_cases = [
            ([0], [8], 0),
            ([8], [], 0),
            ([8], [0], 0),
            ([8], [10], -0.01),
            ([8], [10], math.nan),
            ([8], [10], math.inf),
        ]
        for cuts, stocks, kerf in invalid_cases:
            with self.subTest(cuts=cuts, stocks=stocks, kerf=kerf):
                with self.assertRaises(ValueError):
                    plan_stock_cuts(cuts, stocks, kerf_ft=kerf)


if __name__ == "__main__":
    unittest.main()
