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


def _same_size(first: float, second: float) -> bool:
    return abs(first - second) <= _SAME_SIZE * max(first, second)


def _small_digit_run(chars: Sequence[Mapping[str, Any]], start: int) -> int:
    """Return the end index of a run of smaller digits starting at start, or start."""
    first = chars[start]
    if not first["char"].isdigit() or not _has_geometry(first):
        return start
    end = start
    while (
        end < len(chars) and chars[end]["char"].isdigit() and _has_geometry(chars[end])
        and _same_size(chars[end]["size"], first["size"])
    ):
        end += 1

    before = chars[start - 1] if start > 0 else None
    after = chars[end] if end < len(chars) else None
    if before is not None and _has_geometry(before) and before["char"] in _DIMENSION_CHARS:
        reference = before["size"]
    elif after is not None and _has_geometry(after) and after["char"] in _INCH_MARKS:
        reference = after["size"]
    else:
        return start
    return end if first["size"] < _SMALL_RATIO * reference else start


def _reading_direction(chars: Sequence[Mapping[str, Any]], start: int, end: int) -> tuple[float, float]:
    """Unit vector along the baseline, taken from the main-size characters around the run."""
    first = start
    while first > 0 and _has_geometry(chars[first - 1]) and chars[first - 1]["char"] in _DIMENSION_CHARS:
        first -= 1
    anchors = [_center(chars[index]) for index in range(first, start)]
    if end < len(chars) and _has_geometry(chars[end]):
        anchors.append(_center(chars[end]))
    if len(anchors) >= 2:
        dx = anchors[-1][0] - anchors[0][0]
        dy = anchors[-1][1] - anchors[0][1]
        length = math.hypot(dx, dy)
        if length > 0:
            return (dx / length, dy / length)
    return (1.0, 0.0)


def _fraction(chars: Sequence[Mapping[str, Any]], start: int, end: int) -> str | None:
    """Return 'N/D' when the run is a numerator above a denominator, else None."""
    if end - start < 2:
        return None
    along = _reading_direction(chars, start, end)
    up = (-along[1], along[0])
    placed = []
    for index in range(start, end):
        cx, cy = _center(chars[index])
        placed.append((cx * up[0] + cy * up[1], cx * along[0] + cy * along[1], chars[index]["char"]))
    placed.sort()

    gaps = [placed[index + 1][0] - placed[index][0] for index in range(len(placed) - 1)]
    split = max(range(len(gaps)), key=gaps.__getitem__)
    glyph = min(
        max(chars[index]["box"][2] - chars[index]["box"][0], chars[index]["box"][3] - chars[index]["box"][1])
        for index in range(start, end)
    )
    if gaps[split] < 0.5 * glyph:
        return None  # all on one level: a superscript or a small label, not a stack

    lower, upper = placed[: split + 1], placed[split + 1:]
    numerator = "".join(char for _, _, char in sorted(upper, key=lambda item: item[1]))
    denominator = "".join(char for _, _, char in sorted(lower, key=lambda item: item[1]))
    if int(denominator) not in _DENOMINATORS or not 0 < int(numerator) < int(denominator):
        return None
    return f"{numerator}/{denominator}"


def rebuild_stacked_fractions(chars: Sequence[Mapping[str, Any]]) -> str:
    """Join character records into text, writing stacked fractions as N/D.

    Each record has ``char``, ``box`` (left, bottom, right, top) and ``size``.
    Records with no box or size pass through unchanged.
    """
    pieces: list[str] = []
    index = 0
    while index < len(chars):
        end = _small_digit_run(chars, index)
        fraction = _fraction(chars, index, end) if end > index else None
        if fraction is None:
            pieces.append(chars[index]["char"])
            index += 1
            continue
        after_digit = bool(pieces) and pieces[-1][-1:].isdigit()
        pieces.append((" " if after_digit else "") + fraction)
        index = end
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
