"""Carry takeoff record rows into the BOQ export and the dimension register.

The rows are the ``QTO-`` records of docs/agent-system.md section 9. Nothing
here measures, rounds or chooses a value. A quantity row that has no number is
handed back as not exported, so it never gets a value on the way to the BOQ.

Command line, from the repo root::

    python3 -B takeoff_records.py <records.csv> <boq.csv>
"""

from __future__ import annotations

import csv
import sys
from collections.abc import Iterable, Mapping
from typing import Any

from boq import export_boq
from dimension_register import validate_register

# Columns a takeoff records file has besides the ten every record has.
TAKEOFF_COLUMNS = (
    "record_type", "item", "description", "dimension", "formula", "quantity", "unit",
    "assumptions",
)
BOQ_RECORD_TYPE = "quantity"


def _text(row: Mapping[str, Any], column: str) -> str:
    value = row.get(column)
    return "" if value is None else str(value).strip()


def _is_number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def boq_items_from_records(
    records: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, str]], list[Mapping[str, Any]]]:
    """Return (items for ``export_boq``, quantity rows left out).

    Only rows whose ``record_type`` is ``quantity`` are BOQ lines. Each needs a
    number in ``quantity``; a row without one is returned in the second list.
    The record ID becomes the item code, so every BOQ line leads back to its
    record. ``reviewer_initials`` is left empty for the estimator.
    """
    items: list[dict[str, str]] = []
    not_exported: list[Mapping[str, Any]] = []
    for row in records:
        if _text(row, "record_type") != BOQ_RECORD_TYPE:
            continue
        if not _is_number(_text(row, "quantity")):
            not_exported.append(row)
            continue
        label = ": ".join(part for part in (_text(row, "item"), _text(row, "description")) if part)
        items.append({
            "item_code": _text(row, "id"),
            "quantity": _text(row, "quantity"),
            "unit": _text(row, "unit"),
            "formula": _text(row, "formula"),
            "source_sheet": _text(row, "sheet"),
            "notes": "; ".join(part for part in (label, _text(row, "assumptions")) if part),
            "reviewer_initials": "",
        })
    return items, not_exported


def register_entries_from_records(records: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Return ``validate_register`` entries for the rows that name a ``dimension``."""
    return [
        {
            "name": _text(row, "dimension"),
            "value": _text(row, "quantity"),
            "unit": _text(row, "unit"),
            "source_sheet": _text(row, "sheet"),
        }
        for row in records
        if _text(row, "dimension")
    ]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print(__doc__)
        return 2
    with open(args[0], newline="", encoding="utf-8") as handle:
        records = list(csv.DictReader(handle))
    items, not_exported = boq_items_from_records(records)
    flags = validate_register(register_entries_from_records(records))
    path = export_boq(items, args[1])
    print(f"{len(items)} BOQ line(s) written to {path}. Each still needs the estimator's review.")
    for row in not_exported:
        print(f"NOT EXPORTED {_text(row, 'id')}: no number in quantity ({_text(row, 'status')})")
    for flag in flags:
        seen = ", ".join(
            f"{o['value']} {o['unit']} on {o['source_sheet'] or 'no sheet'}"
            for o in flag["occurrences"]
        )
        print(f"FLAG {flag['issue']} {flag['name']}: {seen}")
    return 1 if not_exported or flags else 0


if __name__ == "__main__":
    sys.exit(main())
