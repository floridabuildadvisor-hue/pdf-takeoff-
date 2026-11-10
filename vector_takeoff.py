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


def distance_feet(start: Point, end: Point, drawing_units_per_foot: float) -> float:
    """Convert a vector distance to feet using the verified drawing scale."""
    scale = float(drawing_units_per_foot)
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("drawing_units_per_foot must be a positive finite number")

    x1, y1 = _validated_point(start, "start")
    x2, y2 = _validated_point(end, "end")
    return math.hypot(x2 - x1, y2 - y1) / scale
