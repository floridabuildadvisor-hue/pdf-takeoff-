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
    """
    cuts = _positive_lengths(cut_lengths_ft, "cut_lengths_ft") if cut_lengths_ft else []
    stocks = sorted(set(_positive_lengths(stock_lengths_ft, "stock_lengths_ft")))
    kerf = _finite_number(kerf_ft, "kerf_ft")
    if kerf < 0:
        raise ValueError("kerf_ft must be zero or greater")

    if cuts and max(cuts) + kerf > max(stocks) + 1e-9:
        raise ValueError("a required cut plus kerf exceeds the longest available stock length")

    ordered_cuts = sorted(cuts, reverse=True)
    boards = []

    if len(ordered_cuts) <= 12:
        best_score = None
        best_boards = None

        def search(index, current_boards, current_stock_lf):
            nonlocal best_score, best_boards
            if best_score is not None and current_stock_lf > best_score[0] + 1e-9:
                return
            if index == len(ordered_cuts):
                score = (current_stock_lf, len(current_boards))
                if best_score is None or score < best_score:
                    best_score = score
                    best_boards = [
                        {
                            "stock_length_ft": board["stock_length_ft"],
                            "cuts_ft": list(board["cuts_ft"]),
                            "kerf_total_ft": board["kerf_total_ft"],
                            "remaining_ft": board["remaining_ft"],
                        }
                        for board in current_boards
                    ]
                return

            cut = ordered_cuts[index]
            required = cut + kerf
            seen_remaining = set()
            for board_index, board in enumerate(current_boards):
                remaining_key = round(board["remaining_ft"], 8)
                if remaining_key in seen_remaining:
                    continue
                seen_remaining.add(remaining_key)
                if board["remaining_ft"] + 1e-9 < required:
                    continue
                next_boards = [
                    {
                        "stock_length_ft": item["stock_length_ft"],
                        "cuts_ft": list(item["cuts_ft"]),
                        "kerf_total_ft": item["kerf_total_ft"],
                        "remaining_ft": item["remaining_ft"],
                    }
                    for item in current_boards
                ]
                target = next_boards[board_index]
                target["cuts_ft"].append(cut)
                target["kerf_total_ft"] += kerf
                target["remaining_ft"] -= required
                if abs(target["remaining_ft"]) < 1e-9:
                    target["remaining_ft"] = 0.0
                search(index + 1, next_boards, current_stock_lf)

            for stock_length in stocks:
                if stock_length + 1e-9 < required:
                    continue
                new_board = {
                    "stock_length_ft": stock_length,
                    "cuts_ft": [cut],
                    "kerf_total_ft": kerf,
                    "remaining_ft": stock_length - required,
                }
                if abs(new_board["remaining_ft"]) < 1e-9:
                    new_board["remaining_ft"] = 0.0
                search(index + 1, current_boards + [new_board], current_stock_lf + stock_length)

        search(0, [], 0.0)
        boards = best_boards or []
        method = "branch-and-bound (up to 12 cuts)"
    else:
        method = "best-fit-decreasing heuristic"
        for cut in ordered_cuts:
            required = cut + kerf
            fitting = [
                (board["remaining_ft"] - required, index)
                for index, board in enumerate(boards)
                if board["remaining_ft"] + 1e-9 >= required
            ]

            if fitting:
                _, board_index = min(fitting)
                board = boards[board_index]
            else:
                available = [length for length in stocks if length + 1e-9 >= required]
                if not available:
                    raise ValueError("a required cut plus kerf does not fit any available stock length")
                stock_length = min(available)
                board = {
                    "stock_length_ft": stock_length,
                    "cuts_ft": [],
                    "kerf_total_ft": 0.0,
                    "remaining_ft": stock_length,
                }
                boards.append(board)

            board["cuts_ft"].append(cut)
            board["kerf_total_ft"] += kerf
            board["remaining_ft"] -= required
            if abs(board["remaining_ft"]) < 1e-9:
                board["remaining_ft"] = 0.0

    total_cut_lf = sum(cuts)
    total_stock_lf = sum(board["stock_length_ft"] for board in boards)
    total_kerf_lf = sum(board["kerf_total_ft"] for board in boards)
    offcut_lf = sum(board["remaining_ft"] for board in boards)

    return {
        "method": method,
        "boards": boards,
        "total_cut_lf": total_cut_lf,
        "total_stock_lf": total_stock_lf,
        "total_kerf_lf": total_kerf_lf,
        "offcut_lf": offcut_lf,
    }
