"""Stacked-fraction tests on synthetic character records (no PDF needed)."""

import math
import unittest

from stacked_fractions import rebuild_stacked_fractions

MAIN = 12.0
SMALL = 9.0


def _chars(pieces, angle_deg=0.0):
    """Lay out (text, size, raise) pieces left to right along a baseline.

    ``raise`` shifts a piece above (+) or below (-) the baseline, the way a
    plan font draws the numerator and denominator of a stacked fraction.
    """
    angle = math.radians(angle_deg)
    along = (math.cos(angle), math.sin(angle))
    up = (-math.sin(angle), math.cos(angle))
    records = []
    cursor = 0.0
    for text, size, lift in pieces:
        if size is None:
            # Whitespace the extractor generates: no position, no size.
            # ``lift`` is reused as a jump along the baseline to the next piece.
            records.extend({"char": char, "box": None, "size": None} for char in text)
            cursor += lift
            continue
        for char in text:
            width = size * 0.5
            cx = 100 + along[0] * (cursor + width / 2) + up[0] * (lift + size * 0.35)
            cy = 100 + along[1] * (cursor + width / 2) + up[1] * (lift + size * 0.35)
            half = size * 0.3
            records.append({
                "char": char,
                "box": (cx - half, cy - half, cx + half, cy + half),
                "size": size,
            })
            cursor += width
    return records


class RebuildStackedFractionsTests(unittest.TestCase):
    def test_feet_inches_and_stacked_half(self):
        records = _chars([("13'-1", MAIN, 0), ("1", SMALL, 4), ("2", SMALL, -3), ('"', MAIN, 0)])
        self.assertEqual(rebuild_stacked_fractions(records), "13'-1 1/2\"")

    def test_two_digit_inches_and_two_digit_denominator(self):
        records = _chars([("29'-10", MAIN, 0), ("3", SMALL, 4), ("16", SMALL, -3), ('"', MAIN, 0)])
        self.assertEqual(rebuild_stacked_fractions(records), "29'-10 3/16\"")

    def test_two_digit_numerator(self):
        records = _chars([("0'-5", MAIN, 0), ("15", SMALL, 4), ("16", SMALL, -3), ('"', MAIN, 0)])
        self.assertEqual(rebuild_stacked_fractions(records), "0'-5 15/16\"")

    def test_denominator_listed_before_numerator_is_ordered_by_position(self):
        # Rotated text on real sheets can list the lower digit first.
        records = _chars([("36'-5", MAIN, 0), ("8", SMALL, -3), ("3", SMALL, 4), ('"', MAIN, 0)])
        self.assertEqual(rebuild_stacked_fractions(records), "36'-5 3/8\"")

    def test_text_running_down_the_sheet(self):
        for angle in (-69, 90, -90, 180, 45):
            records = _chars(
                [("36'-5", MAIN, 0), ("3", SMALL, 4), ("8", SMALL, -3), ('"', MAIN, 0)],
                angle_deg=angle,
            )
            self.assertEqual(rebuild_stacked_fractions(records), "36'-5 3/8\"", angle)

    def test_inches_only_with_stacked_fraction(self):
        records = _chars([("SLAB 3", MAIN, 0), ("1", SMALL, 4), ("2", SMALL, -3), ('" THICK', MAIN, 0)])
        self.assertEqual(rebuild_stacked_fractions(records), 'SLAB 3 1/2" THICK')

    def test_fraction_with_no_whole_inches(self):
        records = _chars([("10'-", MAIN, 0), ("3", SMALL, 4), ("4", SMALL, -3), ('"', MAIN, 0)])
        self.assertEqual(rebuild_stacked_fractions(records), "10'-3/4\"")

    def test_several_dimensions_in_one_text(self):
        records = _chars([
            ("13'-1", MAIN, 0), ("1", SMALL, 4), ("2", SMALL, -3), ('" ', MAIN, 0),
            ("24'-6", MAIN, 0), ("1", SMALL, 4), ("4", SMALL, -3), ('" ', MAIN, 0),
            ("44'-0\"", MAIN, 0),
        ])
        self.assertEqual(rebuild_stacked_fractions(records), "13'-1 1/2\" 24'-6 1/4\" 44'-0\"")

    def test_plain_text_is_returned_unchanged(self):
        for text in ("44'-0\"", "13'-112\"", "ROOM 112", "2x4 @ 16\" O.C.", ""):
            self.assertEqual(rebuild_stacked_fractions(_chars([(text, MAIN, 0)])), text)

    def test_small_digits_on_one_level_are_not_a_fraction(self):
        # A superscript or a small note number: both digits raised, none lowered.
        records = _chars([("NOTE 5", MAIN, 0), ("12", SMALL, 4), (" SEE PLAN", MAIN, 0)])
        self.assertEqual(rebuild_stacked_fractions(records), "NOTE 512 SEE PLAN")

    def test_a_stack_that_is_not_a_fraction_of_an_inch_is_left_alone(self):
        # 8 over 3 is not a proper fraction; do not invent one.
        records = _chars([("5", MAIN, 0), ("8", SMALL, 4), ("3", SMALL, -3), ('"', MAIN, 0)])
        self.assertEqual(rebuild_stacked_fractions(records), '583"')

    def test_line_break_generated_inside_the_stack_is_dropped(self):
        records = _chars([
            ("7'-11", MAIN, 0), ("3", SMALL, 4), ("\r\n", None, -4.5), ("8", SMALL, -3),
            ("\r\n", None, 0), ('"', MAIN, 0), (" ", None, 0), ("2'-5\"", MAIN, 0),
        ])
        self.assertEqual(rebuild_stacked_fractions(records), "7'-11 3/8\" 2'-5\"")

    def test_space_generated_between_whole_inches_and_the_stack(self):
        for angle in (0, 35):
            records = _chars([
                ("69'-5", MAIN, 0), (" ", None, 0), ("1", SMALL, 4), ("16", SMALL, -3), ('"', MAIN, 0),
            ], angle_deg=angle)
            self.assertEqual(rebuild_stacked_fractions(records), "69'-5 1/16\"", angle)

    def test_stack_on_its_own_with_generated_line_breaks(self):
        records = _chars([
            ("NOTES", MAIN, 0), ("\r\n", None, 0), ("1", SMALL, 4), ("\r\n", None, -4.5),
            ("2", SMALL, -3), ('"', MAIN, 0),
        ])
        self.assertEqual(rebuild_stacked_fractions(records), "NOTES\r\n1/2\"")

    def test_small_digits_far_apart_are_not_joined_across_a_line_break(self):
        records = _chars([
            ("4'-2", MAIN, 0), ("1", SMALL, 4), ("\r\n", None, 300), ("2", SMALL, -3), ('"', MAIN, 0),
        ])
        self.assertEqual(rebuild_stacked_fractions(records), "4'-21\r\n2\"")

    def test_line_break_generated_between_whole_inches_and_the_stack(self):
        for angle in (0, 90):
            records = _chars([
                ("19'-10\"", MAIN, 0), ("\r\n", None, 40), ("3", MAIN, 0), ("\r\n", None, 0),
                ("1", SMALL, 4), ("2", SMALL, -3), ("\r\n", None, 0), ('"', MAIN, 0),
            ], angle_deg=angle)
            self.assertEqual(rebuild_stacked_fractions(records), "19'-10\"\r\n3 1/2\"", angle)

    def test_number_on_the_line_above_is_not_taken_as_the_whole_inches(self):
        # "BEDROOM 3" ends one line; a stacked 1/2" starts the next, far away.
        records = _chars([
            ("BEDROOM 3", MAIN, 0), ("\r\n", None, 300), ("1", SMALL, 4), ("\r\n", None, -4.5),
            ("2", SMALL, -3), ('" GYP', MAIN, 0),
        ])
        self.assertEqual(rebuild_stacked_fractions(records), "BEDROOM 3\r\n1/2\" GYP")

    def test_previous_token_elsewhere_on_the_sheet_does_not_skew_the_baseline(self):
        # Extraction can list the inch mark of a far-away dimension right before this one.
        far_mark = {"char": '"', "box": (700.0, 30.0, 703.0, 33.0), "size": MAIN}
        records = [far_mark] + _chars([
            ("69'-5", MAIN, 0), (" ", None, 0), ("1", SMALL, 4), ("16", SMALL, -3), ('"', MAIN, 0),
        ], angle_deg=62)
        self.assertEqual(rebuild_stacked_fractions(records), "\"69'-5 1/16\"")

    def test_stack_on_its_own_ignores_a_far_away_character_listed_before_it(self):
        # The inch mark of another dimension, far to the right, comes first in the text.
        far_mark = {"char": '"', "box": (817.0, 107.0, 819.0, 110.0), "size": MAIN}
        records = [far_mark] + _chars([
            ("\r\n", None, 0), ("1", SMALL, 4), ("\r\n", None, -4.5), ("2", SMALL, -3),
            ("\r\n", None, 0), ('"', MAIN, 0),
        ])
        self.assertEqual(rebuild_stacked_fractions(records), "\"\r\n1/2\"")

    def test_characters_without_position_data_pass_through(self):
        records = [{"char": char, "box": None, "size": None} for char in "13'-112\""]
        self.assertEqual(rebuild_stacked_fractions(records), "13'-112\"")


if __name__ == "__main__":
    unittest.main()
