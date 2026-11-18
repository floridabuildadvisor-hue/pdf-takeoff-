"""Export bill-of-quantities lines to CSV in the auditable format of TAKEOFF_METHOD.md.

Every line must name the formula and the source sheet it came from. The export
does not check that a quantity is right; each line still needs the estimator's
review against the drawing.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

BOQ_COLUMNS = (
    "item_code", "quantity", "unit", "formula", "source_sheet", "notes", "reviewer_initials",
)
_REQUIRED_FOR_TRACEABILITY = ("formula", "source_sheet")


def _is_empty(value: Any) -> bool:
    return value is None or not str(value).strip()


def export_boq(items: Iterable[Mapping[str, Any]], path: str | Path) -> Path:
    """Write items to a CSV file at path and return the path.

    Raises ValueError naming the item codes whose formula or source_sheet is
    empty. Nothing is written in that case.
    """
    rows = list(items)
    problems = []
    for column in _REQUIRED_FOR_TRACEABILITY:
        codes = [str(row.get("item_code")) for row in rows if _is_empty(row.get(column))]
        if codes:
            problems.append(f"empty {column} for item code(s): {', '.join(codes)}")
    if problems:
        raise ValueError("BOQ not exported; " + "; ".join(problems))

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(BOQ_COLUMNS)
        for row in rows:
            writer.writerow(["" if row.get(column) is None else row.get(column) for column in BOQ_COLUMNS])
    return destination
