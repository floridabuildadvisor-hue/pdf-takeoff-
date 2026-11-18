import math
from collections.abc import Sequence

Point = Sequence[float]


def _validated_point(point: Point, name: str) -> tuple[float, float]:
    if len(point) != 2:
        raise ValueError(f"{name} must contain exactly two coordinates")
    x, y = float(point[0]), float(point[1])
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError(f"{name} coordinates must be finite numbers")
    return x, y


def _validated_scale(drawing_units_per_foot: float) -> float:
    scale = float(drawing_units_per_foot)
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("drawing_units_per_foot must be a positive finite number")
    return scale


def distance_feet(start: Point, end: Point, drawing_units_per_foot: float) -> float:
    """Convert a vector distance to feet using the verified drawing scale."""
    scale = _validated_scale(drawing_units_per_foot)
    x1, y1 = _validated_point(start, "start")
    x2, y2 = _validated_point(end, "end")
    return math.hypot(x2 - x1, y2 - y1) / scale


def polyline_length_feet(points: Sequence[Point], drawing_units_per_foot: float) -> float:
    """Sum the connected polyline's segment lengths in feet."""
    scale = _validated_scale(drawing_units_per_foot)
    return sum(
        distance_feet(start, end, scale)
        for start, end in zip(points, points[1:])
    )


def stud_count(length_ft: float, spacing_ft: float) -> int:
    """Estimate studs at regular spacing, including both wall ends.

    This does not account for corners, openings, built-up posts, or project-specific
    framing details. Verify those separately against the drawings and project rules.
    """
    length = float(length_ft)
    spacing = float(spacing_ft)
    if not math.isfinite(length) or length < 0:
        raise ValueError("length_ft must be a finite non-negative number")
    if not math.isfinite(spacing) or spacing <= 0:
        raise ValueError("spacing_ft must be a positive finite number")
    if length == 0:
        return 0
    return math.ceil(length / spacing) + 1


def deduct_openings(length_ft: float, opening_lengths_ft: Sequence[float]) -> float:
    """Subtract opening widths; reject openings whose total exceeds wall length."""
    length = float(length_ft)
    if not math.isfinite(length) or length < 0:
        raise ValueError("length_ft must be a finite non-negative number")

    opening_lengths = [float(opening) for opening in opening_lengths_ft]
    if any(not math.isfinite(opening) or opening < 0 for opening in opening_lengths):
        raise ValueError("opening lengths must be finite non-negative numbers")

    net_length = length - sum(opening_lengths)
    if net_length < 0:
        raise ValueError("opening lengths cannot exceed the wall length")
    return net_length


def plate_length_feet(length_ft: float, plate_count: int = 2) -> float:
    """Calculate total plate length for a wall and specified plate count."""
    length = float(length_ft)
    if not math.isfinite(length) or length < 0:
        raise ValueError("length_ft must be a finite non-negative number")
    if isinstance(plate_count, bool) or not isinstance(plate_count, int) or plate_count < 1:
        raise ValueError("plate_count must be a positive integer")
    return length * plate_count
