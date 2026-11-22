"""Check the evidence packages in a project folder (docs/agent-system.md section 9).

It checks that each package can be traced: the listed files still have their
recorded sha256, every record has its columns and a valid ID, every
``based_on`` link leads to a record, and every printed string reads back from
its source at the recorded place. It does not check that a quantity is right
and it does not recompute formulas: the package's own recompute command and
the estimator's review do that.

Command line, from the repo root (reads only)::

    python3 -B evidence_package.py <project folder>

The exit code is 0 with no findings and 1 with any.
"""

from __future__ import annotations

import csv
import hashlib
import re
import sys
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium

from takeoff_records import TAKEOFF_COLUMNS

WORK_FOLDER = "02_Working"
REVIEW_FOLDER = "review"
RECORD_FILE_NAMES = ("records.csv", "register.csv")
EVIDENCE_FILES = ("commands.txt", "SHA256SUMS", "CHECK.md")
REQUIRED_COLUMNS = (
    "id", "based_on", "file", "page", "sheet", "revision", "as_printed", "bbox",
    "method", "status",
)
ID_PREFIXES = {
    "pdf-drawing-specialist": "DOC-",
    "architectural-plan-reviewer": "ARC-",
    "structural-plan-reviewer": "STR-",
    "mep-civil-reviewer": "MEP-",
    "quantity-takeoff-agent": "QTO-",
    "cost-estimator": "EST-",
    "report-proposal-specialist": "RPT-",
}
TAKEOFF_AGENT = "quantity-takeoff-agent"
METHODS = (
    "native_text", "ocr_text", "vector_geometry", "image_interpretation", "human_verified",
)
CHECKED = "checked against source"
NOT_CHECKED = "not checked"
SEE_BASED_ON = "see based_on"
DRAWN = "drawn"

_COORDINATES = re.compile(r"\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*")
_LINE = re.compile(r"line (\d+)")
_SEPARATORS = re.compile(r"[\s,;|]+")
_BBOX_PADDING_PT = 0.5


def _normalize(text: Any) -> str:
    """Collapse spacing and typographic quotes, which differ between PDF fonts."""
    text = str(text).replace("’", "'").replace("”", '"').replace("“", '"')
    return " ".join(text.split())


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class _Checker:
    def __init__(self, project: Path):
        self.project = project
        self.findings: list[dict[str, str]] = []
        self.counts = {"hashed_files": 0, "records": 0, "links": 0, "read_back": 0}
        self.rows: list[tuple[str, dict[str, str]]] = []
        self.ids: set[str] = set()
        self._documents: dict[Path, pdfium.PdfDocument] = {}

    def report(self, package: str, check: str, detail: str, record: str = "") -> None:
        self.findings.append(
            {"package": package, "check": check, "record": record, "detail": detail})

    def close(self) -> None:
        for document in self._documents.values():
            document.close()

    # --- files -----------------------------------------------------------

    def check_files(self, folder: Path) -> None:
        package = folder.name
        if package not in ID_PREFIXES:
            self.report(package, "unknown_folder",
                        "the folder is not named for an agent that writes files")
        for name in EVIDENCE_FILES:
            if not (folder / name).is_file():
                self.report(package, "missing_file", f"{name} is not in {folder.name}/")
        sums = folder / "SHA256SUMS"
        if not sums.is_file():
            return
        listed = set()
        for line in sums.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            digest, _, relative = line.partition("  ")
            relative = relative.strip().lstrip("*")
            listed.add(relative)
            self.counts["hashed_files"] += 1
            path = self.project / relative
            if not path.is_file():
                self.report(package, "hash_mismatch", f"{relative}: listed but not found")
            elif _sha256(path) != digest.strip():
                self.report(package, "hash_mismatch", f"{relative}: changed after it was hashed")
        for path in sorted(folder.rglob("*")):
            relative = path.relative_to(self.project).as_posix()
            if path.is_file() and path != sums and relative not in listed:
                self.report(package, "unlisted_file", f"{relative} is not in SHA256SUMS")

    # --- records ---------------------------------------------------------

    def load_records(self, folder: Path) -> None:
        package = folder.name
        paths = [folder / name for name in RECORD_FILE_NAMES if (folder / name).is_file()]
        if not paths:
            self.report(package, "no_records",
                        "no " + " or ".join(RECORD_FILE_NAMES) + f" in {folder.name}/")
        for path in paths:
            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
                columns = reader.fieldnames or []
            required = REQUIRED_COLUMNS + (TAKEOFF_COLUMNS if package == TAKEOFF_AGENT else ())
            missing = [column for column in required if column not in columns]
            if missing:
                self.report(package, "missing_column", f"{path.name}: {', '.join(missing)}")
            if "id" not in columns:
                continue
            prefix = ID_PREFIXES.get(package, "")
            for row in rows:
                record = (row.get("id") or "").strip()
                self.counts["records"] += 1
                if not re.fullmatch(re.escape(prefix) + r"\d+", record):
                    self.report(package, "bad_id", f"expected {prefix}<number>", record)
                if record in self.ids:
                    self.report(package, "duplicate_id", "the ID is used more than once", record)
                self.ids.add(record)
                self.rows.append((package, row))

    def check_row(self, package: str, row: dict[str, str]) -> None:
        record = (row.get("id") or "").strip()
        value = lambda column: (row.get(column) or "").strip()  # noqa: E731

        links = [link for link in _SEPARATORS.split(value("based_on")) if link]
        self.counts["links"] += len(links)
        unresolved = [link for link in links if link not in self.ids]
        if unresolved:
            self.report(package, "unresolved_based_on",
                        "no record has the ID " + ", ".join(unresolved), record)

        if "method" in row and value("method") not in METHODS:
            self.report(package, "bad_method",
                        f"'{value('method')}' is not one of: {', '.join(METHODS)}", record)

        if "status" in row:
            status = value("status")
            reason = status[len(NOT_CHECKED):].strip(" :") if status.startswith(NOT_CHECKED) else ""
            if status != CHECKED and not reason:
                self.report(package, "bad_status",
                            f"expected '{CHECKED}' or '{NOT_CHECKED}: <reason>'", record)

        if "bbox" in row and "as_printed" in row:
            self.check_source(package, record, row, links)

    def check_source(self, package: str, record: str, row: dict[str, str], links: list[str]) -> None:
        bbox = (row.get("bbox") or "").strip()
        printed = row.get("as_printed") or ""
        file_name = (row.get("file") or "").strip()

        if SEE_BASED_ON in (bbox, printed.strip()):
            if bbox != printed.strip() or not links:
                self.report(package, "bad_bbox",
                            f"'{SEE_BASED_ON}' goes in both as_printed and bbox, with a based_on link",
                            record)
            return

        coordinates = _COORDINATES.fullmatch(bbox)
        if coordinates:
            if printed.strip() == DRAWN:
                return
            self.counts["read_back"] += 1
            found = self.read_pdf_text(file_name, row.get("page") or "", coordinates.groups())
            if _normalize(found) != _normalize(printed):
                self.report(package, "read_back_mismatch",
                            f"as_printed '{printed}' but the source reads '{found}'", record)
            return

        line = _LINE.fullmatch(bbox)
        if line:
            self.counts["read_back"] += 1
            found = self.read_text_line(file_name, int(line.group(1)))
            if _normalize(found) != _normalize(printed):
                self.report(package, "read_back_mismatch",
                            f"as_printed '{printed}' but the source reads '{found}'", record)
            return

        if bbox.startswith("none"):
            if not bbox[len("none"):].strip(" :"):
                self.report(package, "bad_bbox", "'none' needs its reason", record)
            return

        if not bbox or not (self.project / bbox).is_file():
            self.report(package, "bad_bbox",
                        f"'{bbox}' is not x0,y0,x1,y1, 'line <n>', '{SEE_BASED_ON}', "
                        "'none: <reason>' or the path of a crop image", record)

    def read_pdf_text(self, file_name: str, page: str, coordinates: tuple[str, ...]) -> str:
        path = self.project / file_name
        try:
            if path not in self._documents:
                self._documents[path] = pdfium.PdfDocument(str(path))
            textpage = self._documents[path][int(float(page)) - 1].get_textpage()
            x0, y0, x1, y1 = (float(number) for number in coordinates)
            return textpage.get_text_bounded(
                left=x0 - _BBOX_PADDING_PT, bottom=y0 - _BBOX_PADDING_PT,
                right=x1 + _BBOX_PADDING_PT, top=y1 + _BBOX_PADDING_PT,
            )
        except (OSError, ValueError, IndexError, pdfium.PdfiumError) as error:
            return f"<could not read {file_name} page {page}: {error}>"

    def read_text_line(self, file_name: str, number: int) -> str:
        try:
            lines = (self.project / file_name).read_text(encoding="utf-8").splitlines()
            return lines[number - 1] if number >= 1 else f"<{file_name} has no line {number}>"
        except (OSError, IndexError, UnicodeDecodeError) as error:
            return f"<could not read {file_name} line {number}: {error}>"


def check_project(project_dir: str | Path) -> dict[str, Any]:
    """Check every package in ``<project_dir>/02_Working`` and return the result.

    The result has ``packages`` (the folder names checked), ``counts`` (hashed
    files, records, links and strings read back) and ``findings``. Each finding
    has ``package``, ``check``, ``record`` and ``detail``. An empty ``findings``
    list means every check here passed; it is not a review of the quantities.
    """
    project = Path(project_dir)
    work = project / WORK_FOLDER
    folders = sorted(
        path for path in work.iterdir() if path.is_dir() and path.name != REVIEW_FOLDER
    ) if work.is_dir() else []
    checker = _Checker(project)
    try:
        for folder in folders:
            checker.check_files(folder)
            checker.load_records(folder)
        for package, row in checker.rows:
            checker.check_row(package, row)
    finally:
        checker.close()
    return {
        "packages": [folder.name for folder in folders],
        "counts": checker.counts,
        "findings": checker.findings,
    }


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(__doc__)
        return 2
    result = check_project(args[0])
    if not result["packages"]:
        print(f"No package folders found in {Path(args[0]) / WORK_FOLDER}.")
        return 1
    counts = result["counts"]
    print(f"Packages: {', '.join(result['packages'])}")
    print(f"Checked: {counts['hashed_files']} hashed files, {counts['records']} records, "
          f"{counts['links']} based_on links, {counts['read_back']} strings read back.")
    for finding in result["findings"]:
        record = f" {finding['record']}" if finding["record"] else ""
        print(f"FINDING [{finding['package']}] {finding['check']}{record}: {finding['detail']}")
    print(f"Findings: {len(result['findings'])}. "
          "This checks traceability only. It does not check that a quantity is right.")
    return 1 if result["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
