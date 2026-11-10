import math


def _finite_number(value: float, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    return number


def calculate_plate_lf(
    wall_length_ft: float,
    plate_courses: int,
    waste_percent: float = 5,
) -> float:
    """Return total linear feet of wall plate, including the waste allowance.

    This is a baseline material-length calculation:
    wall length x number of plate courses x (1 + waste percentage / 100).

    It does not optimize stock lengths or account for corners, laps, splices,
    intersections, openings, or project-specific framing details.
    """
    length = _finite_number(wall_length_ft, "wall_length_ft")
    if length <= 0:
        raise ValueError("wall_length_ft must be greater than zero")

    if isinstance(plate_courses, bool) or not isinstance(plate_courses, int):
        raise ValueError("plate_courses must be a positive integer")
    if plate_courses <= 0:
        raise ValueError("plate_courses must be a positive integer")

    waste = _finite_number(waste_percent, "waste_percent")
    if not 0 <= waste <= 100:
        raise ValueError("waste_percent must be between 0 and 100")

    return length * plate_courses * (1 + waste / 100)
