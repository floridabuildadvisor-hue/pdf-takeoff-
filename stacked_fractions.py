"""Reassemble stacked fractions that text extraction returns run together.

Plan fonts draw 13'-1 1/2" with the 1 and the 2 of the fraction as smaller
digits above and below the baseline. Plain text extraction returns the digits
in a row, 13'-112", which reads as a different dimension. This module uses each
character's position and size to write the fraction back as 1/2.

A stack is rewritten only when the geometry is clear and the result is a
proper fraction of an inch (halves to sixty-fourths). Anything else is left
exactly as extracted. The result is a reading aid; fractional dimensions still
need to be checked against the drawing.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

_FOOT_MARKS = "'’′"
_INCH_MARKS = '"”″'
_DIMENSION_CHARS = "0123456789-" + _FOOT_MARKS + _INCH_MARKS
_DENOMINATORS = (2, 4, 8, 16, 32, 64)
_SMALL_RATIO = 0.9       # stacked digits are drawn at about 3/4 of the main size
_SAME_SIZE = 0.02


def _center(record: Mapping[str, Any]) -> tuple[float, float]:
    left, bottom, right, top = record["box"]
    return ((left + right) / 2, (bottom + top) / 2)


def _has_geometry(record: Mapping[str, Any]) -> bool:
    return record.get("box") is not None and bool(record.get("size"))


def _extent(record: Mapping[str, Any]) -> float:
    left, bottom, right, top = record["box"]
    return max(right - left, top - bottom)


def _near(first: Mapping[str, Any], second: Mapping[str, Any]) -> bool:
    """True when two characters sit within a few glyph widths of each other."""
    (ax, ay), (bx, by) = _center(first), _center(second)
    return math.hypot(bx - ax, by - ay) <= 3 * max(_extent(first), _extent(second))


def _same_size(first: float, second: float) -> bool:
    return abs(first - second) <= _SAME_SIZE * max(first, second)


def _skip_whitespace(chars: Sequence[Mapping[str, Any]], index: int, step: int) -> int:
    """Move index past whitespace in the given direction (text extraction generates it)."""
    while 0 <= index < len(chars) and chars[index]["char"].isspace():
        index += step
    return index


def _small_digit_run(chars: Sequence[Mapping[str, Any]], start: int) -> tuple[list[int], int]:
    """Find a run of smaller digits starting at start.

    Returns the digit indexes and the index just past the run. Whitespace
    between the digits is allowed, because extraction can put a space or a
    line break between a numerator and its denominator. An empty list means
    there is no such run at start.
    """
    first = chars[start]
    if not first["char"].isdigit() or not _has_geometry(first):
        return [], start
    digits = []
    index = start
    while index < len(chars):
        candidate = _skip_whitespace(chars, index, 1)
        if not (
            candidate < len(chars) and chars[candidate]["char"].isdigit()
            and _has_geometry(chars[candidate]) and _same_size(chars[candidate]["size"], first["size"])
        ):
            break
        digits.append(candidate)
        index = candidate + 1
    end = digits[-1] + 1

    before = _skip_whitespace(chars, start - 1, -1)
    after = _skip_whitespace(chars, end, 1)
    if before >= 0 and _has_geometry(chars[before]) and chars[before]["char"] in _DIMENSION_CHARS:
        reference = chars[before]["size"]
    elif after < len(chars) and _has_geometry(chars[after]) and chars[after]["char"] in _INCH_MARKS:
        reference = chars[after]["size"]
    else:
        return [], start
    if first["size"] < _SMALL_RATIO * reference:
        return digits, end
    return [], start


def _reading_direction(chars: Sequence[Mapping[str, Any]], start: int, end: int) -> tuple[float, float]:
    """Unit vector along the baseline, taken from the main-size characters around the run."""
    last = _skip_whitespace(chars, start - 1, -1)
    first = last + 1
    while (
        first > 0 and _has_geometry(chars[first - 1]) and chars[first - 1]["char"] in _DIMENSION_CHARS
        and (first > last or _near(chars[first - 1], chars[first]))
    ):
        first -= 1
    anchors = [_center(chars[index]) for index in range(first, last + 1)]
    after = _skip_whitespace(chars, end, 1)
    if after < len(chars) and _has_geometry(chars[after]) and chars[after]["char"] in _INCH_MARKS:
        anchors.append(_center(chars[after]))
    if len(anchors) >= 2:
        dx = anchors[-1][0] - anchors[0][0]
        dy = anchors[-1][1] - anchors[0][1]
        length = math.hypot(dx, dy)
        if length > 0:
            return (dx / length, dy / length)
    return (1.0, 0.0)


def _fraction(chars: Sequence[Mapping[str, Any]], digits: list[int], end: int) -> str | None:
    """Return 'N/D' when the digits are a numerator above a denominator, else None."""
    if len(digits) < 2:
        return None
    along = _reading_direction(chars, digits[0], end)
    up = (-along[1], along[0])
    placed = []
    for index in digits:
        cx, cy = _center(chars[index])
        placed.append((cx * up[0] + cy * up[1], cx * along[0] + cy * along[1], chars[index]["char"]))
    placed.sort()

    gaps = [placed[index + 1][0] - placed[index][0] for index in range(len(placed) - 1)]
    split = max(range(len(gaps)), key=gaps.__getitem__)
    glyph = min(
        max(chars[index]["box"][2] - chars[index]["box"][0], chars[index]["box"][3] - chars[index]["box"][1])
        for index in digits
    )
    if gaps[split] < 0.5 * glyph:
        return None  # all on one level: a superscript or a small label, not a stack

    lower, upper = placed[: split + 1], placed[split + 1:]
    # The two groups must share one slot along the baseline, not sit far apart.
    slot_offset = abs(
        sum(item[1] for item in upper) / len(upper) - sum(item[1] for item in lower) / len(lower)
    )
    if slot_offset > len(digits) * glyph:
        return None

    numerator = "".join(char for _, _, char in sorted(upper, key=lambda item: item[1]))
    denominator = "".join(char for _, _, char in sorted(lower, key=lambda item: item[1]))
    if int(denominator) not in _DENOMINATORS or not 0 < int(numerator) < int(denominator):
        return None
    return f"{numerator}/{denominator}"


def rebuild_stacked_fractions(chars: Sequence[Mapping[str, Any]]) -> str:
    """Join character records into text, writing stacked fractions as N/D.

    Each record has ``char``, ``box`` (left, bottom, right, top) and ``size``.
    Records with no box or size pass through unchanged. Whitespace generated
    inside a rebuilt fraction, or between it and its inch mark, is dropped.
    """
    pieces: list[str] = []
    index = 0
    while index < len(chars):
        digits, end = _small_digit_run(chars, index)
        fraction = _fraction(chars, digits, end) if digits else None
        if fraction is None:
            pieces.append(chars[index]["char"])
            index += 1
            continue
        before = _skip_whitespace(chars, index - 1, -1)
        if (
            before >= 0 and chars[before]["char"].isdigit() and _has_geometry(chars[before])
            and _near(chars[before], chars[digits[0]])
        ):
            # Whole inches belong to this fraction: one space, whatever was generated.
            while pieces and pieces[-1].isspace():
                pieces.pop()
            pieces.append(" ")
        pieces.append(fraction)
        after = _skip_whitespace(chars, end, 1)
        index = after if after < len(chars) and chars[after]["char"] in _INCH_MARKS else end
    return "".join(pieces)


def page_text_with_fractions(text_page: Any, text: str) -> str:
    """Return a pdfium text page's text with stacked fractions reassembled.

    ``text`` is the page's plain extracted text. It is returned unchanged when
    the text page gives no per-character data or its character count does not
    line up with the text.
    """
    if not hasattr(text_page, "count_chars") or not hasattr(text_page, "get_charbox"):
        return text
    if not any(char.isdigit() for char in text) or text_page.count_chars() != len(text):
        return text
    try:
        import pypdfium2.raw as pdfium_raw
    except ImportError:
        return text

    records = []
    for index, char in enumerate(text):
        if char in _DIMENSION_CHARS:
            records.append({
                "char": char,
                "box": text_page.get_charbox(index),
                "size": pdfium_raw.FPDFText_GetFontSize(text_page, index),
            })
        else:
            records.append({"char": char, "box": None, "size": None})
    return rebuild_stacked_fractions(records)
