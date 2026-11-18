import math
import time
import unittest

from framing_takeoff import calculate_plate_lf, plan_stock_cuts, plate_lf_breakdown


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


class PlateLfBreakdownTests(unittest.TestCase):
    def test_measured_length_and_waste_allowance_are_reported_separately(self):
        breakdown = plate_lf_breakdown(20, 3, 5)
        self.assertEqual(breakdown["wall_length_ft"], 20)
        self.assertEqual(breakdown["plate_courses"], 3)
        self.assertAlmostEqual(breakdown["measured_lf"], 60)
        self.assertEqual(breakdown["waste_percent"], 5)
        self.assertAlmostEqual(breakdown["waste_allowance_lf"], 3)
        self.assertAlmostEqual(breakdown["total_lf"], 63)
        self.assertEqual(breakdown["formula"], "20 LF x 3 courses = 60 LF measured; + 5% waste allowance = 63 LF")

    def test_total_matches_calculate_plate_lf(self):
        for length, courses, waste in ((20, 3, 5), (12.5, 2, 0), (33.25, 3, 10)):
            self.assertAlmostEqual(
                plate_lf_breakdown(length, courses, waste)["total_lf"],
                calculate_plate_lf(length, courses, waste),
            )

    def test_waste_allowance_is_never_applied_unless_stated(self):
        breakdown = plate_lf_breakdown(20, 3)
        self.assertEqual(breakdown["waste_percent"], 0)
        self.assertAlmostEqual(breakdown["total_lf"], breakdown["measured_lf"])
        self.assertEqual(breakdown["formula"], "20 LF x 3 courses = 60 LF measured; no waste allowance")

    def test_rejects_the_same_invalid_inputs_as_calculate_plate_lf(self):
        for args in ((0, 3, 5), (20, 0, 5), (20, 3, -1), (20, True, 5)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                plate_lf_breakdown(*args)


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

    def test_small_batch_uses_the_least_stock_footage(self):
        # 6 on an 8 and 4 + 3 on an 8 is 16 LF; 6 + 4 on a 10 and 3 on an 8 is 18 LF.
        plan = plan_stock_cuts([6, 4, 3], [8, 10])
        self.assertAlmostEqual(plan["total_stock_lf"], 16)
        self.assertAlmostEqual(plan["offcut_lf"], 3)

    def test_equal_stock_footage_prefers_fewer_boards(self):
        plan = plan_stock_cuts([4, 4], [4, 8])
        self.assertAlmostEqual(plan["total_stock_lf"], 8)
        self.assertEqual(len(plan["boards"]), 1)

    def test_twelve_equal_cuts_are_planned_quickly(self):
        started = time.perf_counter()
        plan = plan_stock_cuts([7.5] * 12, [8, 10, 12, 14, 16])
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 3, "repeated plate lengths are the usual case")
        self.assertAlmostEqual(plan["total_stock_lf"], 96)
        self.assertEqual(len(plan["boards"]), 6)
        self.assertEqual(sum(len(board["cuts_ft"]) for board in plan["boards"]), 12)

    def test_twelve_mixed_cuts_keep_the_least_stock_footage(self):
        cuts = [11.5, 10.25, 9.75, 9, 8.5, 7.25, 6.5, 5.75, 4.5, 3.25, 2.5, 1.75]
        plan = plan_stock_cuts(cuts, [8, 10, 12, 14, 16])
        self.assertAlmostEqual(plan["total_stock_lf"], 82)
        self.assertCountEqual([cut for board in plan["boards"] for cut in board["cuts_ft"]], cuts)

    def test_kerf_is_charged_for_every_cut_including_the_last_on_a_board(self):
        # Two 8 ft pieces do not come out of one 16 ft board once kerf is counted.
        plan = plan_stock_cuts([8, 8], [16], kerf_ft=0.01)
        self.assertEqual(len(plan["boards"]), 2)

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
