"""Check a register of dimensions read from a plan set before they feed a takeoff.

The register is a list of entries, each with ``name``, ``value``, ``unit`` and
``source_sheet``. Validation only flags entries for the estimator's review. It
never picks which printed value to use.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def _occurrence(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "value": entry.get("value"),
        "unit": entry.get("unit"),
        "source_sheet": entry.get("source_sheet"),
    }


def validate_register(entries: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return review flags for a dimension register; an empty list means none.

    ``missing_source``: an entry has no source sheet, so it cannot be traced.
    ``conflicting_values``: entries with the same name (ignoring case and
    spacing) carry different values or units. All occurrences are listed.
    Missing-source flags come first, then conflicts in order of first appearance.
    """
    flags: list[dict[str, Any]] = []
    by_name: dict[str, list[Mapping[str, Any]]] = {}
    for entry in entries:
        name = " ".join(str(entry.get("name", "")).split())
        source = entry.get("source_sheet")
        if source is None or not str(source).strip():
            flags.append({
                "issue": "missing_source",
                "name": name,
                "occurrences": [_occurrence(entry)],
            })
        by_name.setdefault(name.lower(), []).append(entry)

    for group in by_name.values():
        distinct = {(entry.get("value"), str(entry.get("unit", "")).strip().upper()) for entry in group}
        if len(distinct) > 1:
            flags.append({
                "issue": "conflicting_values",
                "name": " ".join(str(group[0].get("name", "")).split()),
                "occurrences": [_occurrence(entry) for entry in group],
            })
    return flags
