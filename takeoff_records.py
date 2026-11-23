"""Carry takeoff record rows into the BOQ export and the dimension register.

The rows are the ``QTO-`` records of docs/agent-system.md section 9. Nothing
here measures, rounds or chooses a value. A quantity row that has no number is
handed back as not exported, so it never gets a value on the way to the BOQ.

A quantity row is one of three things:

- exported: a plain number, a unit from the rulebook list, a formula, a sheet
  and a ``QTO-<number>`` ID used once;
- unresolved: ``quantity`` is empty. That is the agreed way to hold a quantity
  open, so it is listed and left out;
- defective: anything else, such as ``nan``, ``1e3``, text in ``quantity``, or
  a number with no unit. The command line writes no BOQ while one exists.

Command line, from the repo root::

    python3 -B takeoff_records.py <records.csv> <boq.csv>

Every BOQ line has two more columns after the seven of ``boq.py``:
``source_revision``, the revision the record cites, and ``boq_status``, which
starts ``DRAFT`` or ``PARTIAL DRAFT`` on every line, so a line copied out of
the file still says what it came from. The command also writes
``<boq.csv>.STATUS.txt``, which says whether the BOQ is whole, partial or not
written. When no BOQ is written, a BOQ of that name from an earlier run is
renamed ``<boq.csv>.SUPERSEDED``, so it cannot pass for this run's result. No
BOQ it writes is a reviewed one: every ``reviewer_initials`` is empty.
"""

from __future__ import annotations

import csv
import io
import os
import re
import sys
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from boq import export_boq
from dimension_register import validate_register

# Columns a takeoff records file has besides the ten every record has.
TAKEOFF_COLUMNS = (
    "record_type", "item", "description", "dimension", "formula", "quantity", "unit",
    "assumptions",
)
BOQ_RECORD_TYPE = "quantity"
# The only record types a takeoff file may use. A closed list, so a row cannot be
# kept out of every check by a type that reads like "quantity" and is not.
RECORD_TYPES = ("input", "calc", "deduction", "scale", "comparison", "alternative", "quantity")
# Columns the command line cannot work without.
NEEDED_COLUMNS = ("id", "record_type", "quantity", "unit", "formula", "sheet")
_RUNS_IN_A_SPREADSHEET = ("=", "+", "-", "@")
# docs/agent-system.md section 9, "Units". Written exactly like this.
ALLOWED_UNITS = (
    "LF", "SF", "SY", "CF", "CY", "EA", "LS", "LB", "TON", "GAL", "SQ", "BF", "MBF",
)
EXTRA_BOQ_COLUMNS = ("source_revision", "boq_status")
STATUS_SUFFIX = ".STATUS.txt"
SUPERSEDED_SUFFIX = ".SUPERSEDED"


def _text(row: Mapping[str, Any], column: str) -> str:
    value = row.get(column)
    return "" if value is None else str(value).strip()


# Digits with an optional decimal part, as an estimator writes a quantity. No
# sign, exponent, separator or word: float() would also take "nan", "inf",
# "1e3", "1_000" and digits from other scripts.
_PLAIN_NUMBER = re.compile(r"(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)")
_RECORD_ID = re.compile(r"QTO-[0-9]+")


def _visible(text: str) -> str:
    """The text without spacing and without characters that print nothing."""
    return "".join(c for c in text if not c.isspace() and unicodedata.category(c) != "Cf")


def _is_number(text: str) -> bool:
    return _PLAIN_NUMBER.fullmatch(text) is not None


def _raw_id(row: Mapping[str, Any]) -> str:
    value = row.get("id")
    return "" if value is None else str(value)


def _id_key(row: Mapping[str, Any]) -> Any:
    """The ID as a person reads it: QTO-3, QTO-03 and QTO-003 are one ID."""
    raw = _raw_id(row)
    if _RECORD_ID.fullmatch(raw):
        return ("QTO", int(raw[len("QTO-"):]))
    return raw


def _runs_in_a_spreadsheet(text: str) -> bool:
    """True when the first printing character is = + - @ or a wide form of one."""
    first = _visible(text)[:1]
    return unicodedata.normalize("NFKC", first).startswith(_RUNS_IN_A_SPREADSHEET)


def is_quantity_lookalike(row: Mapping[str, Any]) -> bool:
    """True when ``record_type`` reads as quantity to a person but is not that text.

    ``Quantity``, ``quantity.`` or ``quantity`` with an invisible character
    would be skipped as "not a quantity row" and never checked.
    """
    raw = row.get("record_type")
    raw = "" if raw is None else str(raw)
    if raw.strip() == BOQ_RECORD_TYPE:
        return False
    letters = "".join(c for c in unicodedata.normalize("NFKC", raw) if c.isalpha())
    return letters.casefold() == BOQ_RECORD_TYPE


def read_records(path: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    """Read a records CSV. Return (rows, problems with the file itself).

    A problem is anything that would let two readers see different rows: bytes
    that are not UTF-8, a NUL, an unclosed quote, a column named twice, or a row
    with more or fewer cells than the header. A byte order mark is accepted and dropped.
    """
    try:
        text = Path(path).read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError as error:
        return [], [f"the file is not UTF-8 text ({error.reason} at byte {error.start})"]
    except OSError as error:
        return [], [f"the file could not be read ({error.strerror})"]
    if "\x00" in text:
        return [], ["the file has a NUL character"]
    try:
        # newline="" leaves row ends to the csv module, which ends a row only at
        # CR or LF. str.splitlines would also cut at U+2028 and its like and
        # turn the rest of a cell into a row. strict refuses an unclosed quote.
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        rows = list(reader)
    except csv.Error as error:
        return [], [f"the file is not readable as CSV ({error})"]
    columns = reader.fieldnames or []
    problems = [f"the column '{name}' is named {count} times"
                for name, count in Counter(columns).items() if count > 1]
    for number, row in enumerate(rows, start=2):
        if None in row or any(value is None for value in row.values()):
            problems.append(f"line {number} does not have {len(columns)} cells like the header")
    return [{k: v for k, v in row.items() if k is not None} for row in rows], problems


def quantity_row_problems(row: Mapping[str, Any]) -> list[str]:
    """Return what stops one ``quantity`` row from being a BOQ line.

    An empty list means the row is usable, or that its ``quantity`` is empty,
    which holds it open and is not a defect. This looks at the row alone: an ID
    used twice is found by ``boq_items_from_records``. It checks the form of
    the row, never whether the number is right.
    """
    problems = []
    if not _RECORD_ID.fullmatch(_raw_id(row)):
        problems.append(f"the ID '{_raw_id(row)}' is not QTO-<number>")
    quantity = _text(row, "quantity")
    if not quantity:
        return problems
    if not _is_number(quantity):
        problems.append(f"quantity '{quantity}' is not a plain number")
    unit = _text(row, "unit")
    if not _visible(unit):
        problems.append("no unit")
    elif unit not in ALLOWED_UNITS:
        problems.append(f"unit '{unit}' is not one of: {', '.join(ALLOWED_UNITS)}")
    if not _visible(_text(row, "formula")):
        problems.append("no formula")
    if not _visible(_text(row, "sheet")):
        problems.append("no source sheet")
    # The BOQ is a CSV that is opened in a spreadsheet. A cell that starts with
    # one of these is run there as a formula. The notes cell starts with the
    # first of item, description and assumptions that has text.
    label = next((c for c in ("item", "description", "assumptions") if _text(row, c)), "item")
    for column in ("formula", "sheet", "revision", label):
        if _runs_in_a_spreadsheet(_text(row, column)):
            problems.append(f"{column} starts with '{_visible(_text(row, column))[0]}', "
                            "which a spreadsheet runs as a formula")
    return problems


def boq_items_from_records(
    records: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, str]], list[Mapping[str, Any]]]:
    """Return (items for ``export_boq``, quantity rows left out).

    Only rows whose ``record_type`` is ``quantity`` are BOQ lines. A row is left
    out, and returned in the second list, when ``quantity`` is empty or is not a
    plain number, when its unit is empty or not in ``ALLOWED_UNITS``, or when its
    ID is not ``QTO-<number>`` or is used by another row, also when the other
    row writes the number another way (``QTO-3`` and ``QTO-003``). So is any row whose
    ``record_type`` is not in ``RECORD_TYPES``. A row with no formula or no sheet is passed on,
    because ``export_boq`` refuses the whole export for it. The record ID
    becomes the item code, so every BOQ line leads back to its record.
    ``reviewer_initials`` is left empty for the estimator.
    """
    rows = list(records)
    used = Counter(_id_key(row) for row in rows)
    items: list[dict[str, str]] = []
    not_exported: list[Mapping[str, Any]] = []
    for row in rows:
        if _text(row, "record_type") not in RECORD_TYPES:
            not_exported.append(row)
            continue
        if _text(row, "record_type") != BOQ_RECORD_TYPE:
            continue
        if (
            not _RECORD_ID.fullmatch(_raw_id(row))
            or used[_id_key(row)] > 1
            or not _is_number(_text(row, "quantity"))
            or _text(row, "unit") not in ALLOWED_UNITS
        ):
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


def rejected_quantity_rows(records: Iterable[Mapping[str, Any]]) -> list[tuple[str, str]]:
    """Return (ID, problems) for each defective ``quantity`` row, in file order."""
    rows = list(records)
    used = Counter(_raw_id(row) for row in rows)
    same_number = Counter(_id_key(row) for row in rows)
    rejected = []
    for row in rows:
        if _text(row, "record_type") not in RECORD_TYPES:
            rejected.append((_raw_id(row), f"record_type '{row.get('record_type')}' is not "
                             f"one of: {', '.join(RECORD_TYPES)}"))
            continue
        if _text(row, "record_type") != BOQ_RECORD_TYPE:
            continue
        problems = quantity_row_problems(row)
        if used[_raw_id(row)] > 1:
            problems.append("the ID is used more than once")
        elif same_number[_id_key(row)] > 1:
            problems.append("another row has the same ID number written another way")
        if problems:
            rejected.append((_raw_id(row), "; ".join(problems)))
    return rejected


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


def _refused_paths(records_path: Path, boq_path: Path, status_path: Path,
                   superseded_path: Path) -> str:
    """Why these paths cannot be used, or an empty string."""
    paths = (records_path, boq_path, status_path, superseded_path)
    different = ("the records file, the BOQ, its status file and its superseded copy must be "
                 "four different files")
    if len({path.resolve() for path in paths}) != 4:
        return different
    # Two spellings can be one file: another case or another Unicode form of the
    # name on some disks, or a second name given to the file (a hard link).
    existing = [path for path in paths if path.exists()]
    for at, path in enumerate(existing):
        if any(os.path.samefile(path, other) for other in existing[at + 1:]):
            return different
    for path in (boq_path, status_path, superseded_path):
        if path.is_symlink():
            return f"{path.name} is a link; give the real path"
        if path.is_dir():
            return f"{path.name} is a folder"
        if path.is_file() and path.stat().st_nlink > 1:
            return (f"{path.name} has a second name somewhere (a hard link), so writing it "
                    "would change that file too")
    return ""


def _build(records_path: str, boq_path: Path) -> tuple[list[str], list[str]]:
    """Write the BOQ if the records allow it. Return (status lines, flag lines)."""
    records, file_problems = read_records(records_path)
    if not file_problems and records:
        missing = [column for column in NEEDED_COLUMNS if column not in records[0]]
        if missing:
            file_problems.append("the header has no column named " + ", ".join(missing))
    quantity_rows = [row for row in records if _text(row, "record_type") == BOQ_RECORD_TYPE]
    superseded = boq_path.with_name(boq_path.name + SUPERSEDED_SUFFIX)
    flags = validate_register(register_entries_from_records(records))
    flag_lines = [
        f"FLAG {flag['issue']} {flag['name']}: " + ", ".join(
            f"{o['value']} {o['unit']} on {o['source_sheet'] or 'no sheet'}"
            for o in flag["occurrences"])
        for flag in flags
    ]
    rejected = rejected_quantity_rows(records)

    if file_problems or rejected or not quantity_rows:
        lines = [f"NOT WRITTEN. No BOQ was written to {boq_path.name} from {records_path}."]
        lines += [f"REJECTED the records file: {problem}" for problem in file_problems]
        if not file_problems and not quantity_rows:
            lines.append("The records have no row whose record_type is quantity.")
        lines += [f"REJECTED {record}: {problems}" for record, problems in rejected]
        if boq_path.is_file():
            boq_path.replace(superseded)
            lines.append(f"A {boq_path.name} from an earlier run was renamed {superseded.name}. "
                         "It does not match these records.")
        lines.append("Correct the records and run the command again.")
    else:
        items, not_exported = boq_items_from_records(records)
        by_id = {_text(row, "id"): row for row in quantity_rows}
        if not_exported:
            boq_status = (f"PARTIAL DRAFT: {len(items)} of {len(quantity_rows)} quantity rows, "
                          "not reviewed")
        else:
            boq_status = f"DRAFT: all {len(items)} quantity rows, not reviewed"
        for item in items:
            item["source_revision"] = _text(by_id[item["item_code"]], "revision")
            item["boq_status"] = boq_status
            if not item["source_revision"]:
                flag_lines.append(f"FLAG no_revision {item['item_code']}: the record cites no "
                                  "revision for its sheet")
        export_boq(items, boq_path, extra_columns=EXTRA_BOQ_COLUMNS)
        if not_exported:
            lines = [
                f"PARTIAL DRAFT. {boq_path.name} has {len(items)} of {len(quantity_rows)} "
                "quantity rows. It is not a complete BOQ and it is not reviewed.",
            ]
            lines += [
                f"NOT EXPORTED {_text(row, 'id')}: no number in quantity ({_text(row, 'status')})"
                for row in not_exported
            ]
        else:
            lines = [
                f"DRAFT. {boq_path.name} has all {len(items)} quantity rows. It is not reviewed: "
                "each line still needs the estimator's review and initials.",
            ]
    return lines, flag_lines


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print(__doc__)
        return 2
    boq_path = Path(args[1])
    status_path = boq_path.with_name(boq_path.name + STATUS_SUFFIX)
    superseded_path = boq_path.with_name(boq_path.name + SUPERSEDED_SUFFIX)
    try:
        refused = _refused_paths(Path(args[0]), boq_path, status_path, superseded_path)
    except (OSError, RuntimeError) as error:
        refused = f"the paths could not be read ({error})"
    if refused:
        print(f"REFUSED. Nothing was read or written: {refused}.")
        return 2
    try:
        lines, flag_lines = _build(args[0], boq_path)
    except OSError as error:
        lines = [f"NOT WRITTEN. No BOQ was written to {boq_path.name}: {error.strerror}."]
        flag_lines = []
        try:
            if boq_path.is_file():
                boq_path.replace(superseded_path)
                lines.append(f"A {boq_path.name} from an earlier run was renamed "
                             f"{superseded_path.name}.")
        except OSError:
            lines.append(f"A {boq_path.name} from an earlier run may still be in the folder. "
                         "It is not this run's result.")
    lines += flag_lines
    print("\n".join(lines))
    try:
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as error:
        print(f"The status file {status_path.name} could not be written: {error.strerror}.")
        return 1
    return 0 if lines[0].startswith("DRAFT") and not flag_lines else 1


if __name__ == "__main__":
    sys.exit(main())
