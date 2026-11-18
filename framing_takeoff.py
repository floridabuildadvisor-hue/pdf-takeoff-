from __future__ import annotations

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


def _positive_lengths(values, name: str) -> list[float]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be a non-empty sequence of positive lengths")
    try:
        lengths = [_finite_number(value, name) for value in values]
    except TypeError as exc:
        raise ValueError(f"{name} must be a non-empty sequence of positive lengths") from exc
    if not lengths or any(length <= 0 for length in lengths):
        raise ValueError(f"{name} must contain only positive lengths")
    return lengths


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


def plate_lf_breakdown(
    wall_length_ft: float,
    plate_courses: int,
    waste_percent: float = 0,
) -> dict:
    """Return wall-plate linear feet with the waste allowance kept separate.

    ``measured_lf`` is wall length x plate courses, the quantity that traces to
    the drawing. ``waste_allowance_lf`` is an allowance chosen by the estimator,
    not something measured, and is zero unless a percentage is given. The
    ``formula`` string is ready for a BOQ line. The same limits as
    calculate_plate_lf apply.
    """
    total = calculate_plate_lf(wall_length_ft, plate_courses, waste_percent)
    measured = calculate_plate_lf(wall_length_ft, plate_courses, 0)
    waste_text = f"+ {waste_percent:g}% waste allowance = {total:g} LF" if waste_percent else "no waste allowance"
    return {
        "wall_length_ft": wall_length_ft,
        "plate_courses": plate_courses,
        "measured_lf": measured,
        "waste_percent": waste_percent,
        "waste_allowance_lf": total - measured,
        "total_lf": total,
        "formula": f"{wall_length_ft:g} LF x {plate_courses} courses = {measured:g} LF measured; {waste_text}",
    }


_EPSILON = 1e-9
_EXACT_SEARCH_MAX_CUTS = 12


def _new_board(stock_length: float) -> dict:
    return {
        "stock_length_ft": stock_length,
        "cuts_ft": [],
        "kerf_total_ft": 0.0,
        "remaining_ft": stock_length,
    }


def _place_cut(board: dict, cut: float, kerf: float) -> None:
    board["cuts_ft"].append(cut)
    board["kerf_total_ft"] += kerf
    board["remaining_ft"] -= cut + kerf
    if abs(board["remaining_ft"]) < _EPSILON:
        board["remaining_ft"] = 0.0


def _copy_boards(boards: list[dict]) -> list[dict]:
    return [{**board, "cuts_ft": list(board["cuts_ft"])} for board in boards]


def _best_fit_decreasing(ordered_cuts: list[float], stocks: list[float], kerf: float) -> list[dict]:
    """Put each cut in the open board that leaves the least offcut, else open the shortest board that fits."""
    boards: list[dict] = []
    for cut in ordered_cuts:
        required = cut + kerf
        fitting = [
            (board["remaining_ft"] - required, index)
            for index, board in enumerate(boards)
            if board["remaining_ft"] + _EPSILON >= required
        ]
        if fitting:
            board = boards[min(fitting)[1]]
        else:
            board = _new_board(min(length for length in stocks if length + _EPSILON >= required))
            boards.append(board)
        _place_cut(board, cut, kerf)
    return boards


def _least_stock_search(ordered_cuts: list[float], stocks: list[float], kerf: float) -> list[dict]:
    """Branch-and-bound for the least stock footage, then the fewest boards."""
    best_boards = _best_fit_decreasing(ordered_cuts, stocks, kerf)
    best_score = (sum(board["stock_length_ft"] for board in best_boards), len(best_boards))

    # still_required[i] is the length, with kerf, of the cuts from index i onward.
    still_required = [0.0]
    for cut in reversed(ordered_cuts):
        still_required.append(still_required[-1] + cut + kerf)
    still_required.reverse()

    smallest_required = ordered_cuts[-1] + kerf if ordered_cuts else 0.0

    def search(index: int, boards: list[dict], stock_lf: float, first_board: int) -> None:
        nonlocal best_boards, best_score
        if index == len(ordered_cuts):
            score = (stock_lf, len(boards))
            if score[0] < best_score[0] - _EPSILON or (
                score[0] <= best_score[0] + _EPSILON and score[1] < best_score[1]
            ):
                best_score = score
                best_boards = _copy_boards(boards)
            return

        # No branch below here can use less stock than this, or fewer boards than it has now.
        # Space too short for even the smallest cut left cannot be used again.
        open_space = sum(
            board["remaining_ft"] for board in boards
            if board["remaining_ft"] + _EPSILON >= smallest_required
        )
        overflow = max(0.0, still_required[index] - open_space)
        least_stock = stock_lf + overflow
        least_boards = len(boards) + math.ceil(overflow / stocks[-1] - _EPSILON)
        if least_stock > best_score[0] + _EPSILON:
            return
        if least_stock >= best_score[0] - _EPSILON and least_boards >= best_score[1]:
            return

        cut = ordered_cuts[index]
        required = cut + kerf
        # A cut equal to the one before it never goes on an earlier board than
        # that one did; swapping two equal cuts gives the same plan.
        if index == 0 or cut != ordered_cuts[index - 1]:
            first_board = 0

        seen_remaining = set()
        for board_index in range(first_board, len(boards)):
            board = boards[board_index]
            remaining_key = round(board["remaining_ft"], 8)
            if remaining_key in seen_remaining or board["remaining_ft"] + _EPSILON < required:
                continue
            seen_remaining.add(remaining_key)
            next_boards = _copy_boards(boards)
            _place_cut(next_boards[board_index], cut, kerf)
            search(index + 1, next_boards, stock_lf, board_index)

        for stock_length in stocks:
            if stock_length + _EPSILON < required:
                continue
            board = _new_board(stock_length)
            _place_cut(board, cut, kerf)
            search(index + 1, boards + [board], stock_lf + stock_length, len(boards))

    search(0, [], 0.0, 0)
    return best_boards


def plan_stock_cuts(
    cut_lengths_ft: list[float],
    stock_lengths_ft: list[float],
    kerf_ft: float = 0,
) -> dict:
    """Assign cuts to stock boards, minimizing stock footage for small batches.

    Up to 12 cuts are packed with branch-and-bound search, minimizing total
    stock footage and then board count. Larger batches use a best-fit-decreasing
    heuristic to keep runtime predictable. Offcuts are reusable within this
    one input batch. This function does not infer wall assemblies or add a
    percentage waste reserve; supply actual cuts and supplier stock lengths.

    Kerf is charged once for every cut, including the last cut on a board, so
    two 8 ft pieces do not fit one 16 ft board when kerf_ft is above zero.

    The result is a cutting aid for the estimator to review. The measured
    takeoff quantity is total_cut_lf; total_stock_lf depends on the stock
    lengths the caller supplied and is not a quantity taken from the drawings.
    """
    cuts = _positive_lengths(cut_lengths_ft, "cut_lengths_ft") if cut_lengths_ft else []
    stocks = sorted(set(_positive_lengths(stock_lengths_ft, "stock_lengths_ft")))
    kerf = _finite_number(kerf_ft, "kerf_ft")
    if kerf < 0:
        raise ValueError("kerf_ft must be zero or greater")

    if cuts and max(cuts) + kerf > max(stocks) + _EPSILON:
        raise ValueError("a required cut plus kerf exceeds the longest available stock length")

    ordered_cuts = sorted(cuts, reverse=True)
    if len(ordered_cuts) <= _EXACT_SEARCH_MAX_CUTS:
        boards = _least_stock_search(ordered_cuts, stocks, kerf)
        method = "branch-and-bound (up to 12 cuts)"
    else:
        boards = _best_fit_decreasing(ordered_cuts, stocks, kerf)
        method = "best-fit-decreasing heuristic"

    return {
        "method": method,
        "boards": boards,
        "total_cut_lf": sum(cuts),
        "total_stock_lf": sum(board["stock_length_ft"] for board in boards),
        "total_kerf_lf": sum(board["kerf_total_ft"] for board in boards),
        "offcut_lf": sum(board["remaining_ft"] for board in boards),
    }
