"""Check the evidence packages in a project folder (docs/agent-system.md section 9).

It checks three things, and keeps them apart:

- File integrity. The listed files still have their recorded sha256, every
  received file is in the document inventory, and no path leaves the project.
- Records. Every record has its columns and a valid ID, and every printed
  string reads back from its source at the recorded place.
- The chain. Every ``based_on`` link leads to a record of an earlier or the
  same stage, no link runs in a circle, every quantity with a number leads
  back to a place on a drawing, and every BOQ line matches a quantity record.

It does not check that a quantity is right and it does not recompute formulas:
the package's own recompute command and the estimator's review do that. Linked
IDs show that a path exists, not that the right thing was measured. A crop
image is checked for existence only; nothing here compares it with its sheet.

Command line, from the repo root (reads only)::

    python3 -B evidence_package.py <project folder> [--seals <file>]

It prints one ``SEAL`` line for each received file and for each package's
``SHA256SUMS``. A hash shows that a file still matches a digest. It does not
show that the file or the digest was right to begin with, and a file changed
together with every hash list that names it cannot be told from the project
files alone. So the ``SEAL`` lines are kept where no agent can write (the
owner's decision report) and passed back with ``--seals <file>``, or
``--seals -`` to read them from standard input. docs/agent-system.md section 9
has the procedure.

The exit code is 0 with no findings and 1 with any.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

from boq import BOQ_COLUMNS
from takeoff_records import (
    BOQ_RECORD_TYPE, EXTRA_BOQ_COLUMNS, RECORD_TYPES, TAKEOFF_COLUMNS,
    _visible, quantity_row_problems, read_records,
)

WORK_FOLDER = "02_Working"
RECEIVED_FOLDER = "01_Received"
INVENTORY_AGENT = "pdf-drawing-specialist"
REPORT_AGENT = "report-proposal-specialist"
BOQ_FILE_NAME = "boq.csv"
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
# Order of the stages. A record may be based on its own stage or an earlier one.
STAGES = {
    "pdf-drawing-specialist": 0,
    "architectural-plan-reviewer": 1,
    "structural-plan-reviewer": 1,
    "mep-civil-reviewer": 1,
    "quantity-takeoff-agent": 2,
    "cost-estimator": 3,
    "report-proposal-specialist": 4,
}
SCOPE_STAGE = 1
INPUT_RECORD_TYPE = "input"
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
_DIGEST = re.compile(r"[0-9a-f]{64}")
_PAGE = re.compile(r"[1-9][0-9]{0,6}")
_IMAGE_SIGNATURES = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")


def _is_file(path: Path | None) -> bool:
    """``Path.is_file`` that answers False where the file system raises."""
    try:
        return path is not None and path.is_file()
    except OSError:
        return False
_BBOX_PADDING_PT = 0.5


def _normalize(text: Any) -> str:
    """Collapse spacing and typographic quotes, which differ between PDF fonts."""
    text = str(text).replace("’", "'").replace("”", '"').replace("“", '"')
    return " ".join(text.split())


def _folded_name(name: str) -> str:
    """A file name with letter case and Unicode composition ignored, to compare spellings."""
    return unicodedata.normalize("NFC", name).casefold()


def _sha256(path: Path) -> str:
    """The sha256 of a file, or a text that matches no digest if it cannot be read."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        return f"<could not be read: {error.strerror}>"


class _Checker:
    def __init__(self, project: Path):
        self.project = project
        self.findings: list[dict[str, str]] = []
        self.counts = {"hashed_files": 0, "records": 0, "links": 0, "read_back": 0,
                       "crops_not_compared": 0, "boq_lines": 0}
        self.rows: list[tuple[str, dict[str, str]]] = []
        self.ids: set[str] = set()
        self.owner: dict[str, str] = {}
        self.by_id: dict[str, dict[str, str]] = {}
        self.duplicates: set[str] = set()
        self.numbers: dict[tuple[str, int], str] = {}
        self.manifests: dict[str, set[str]] = {}
        self.seals: dict[str, str] = {}
        self.root = project.resolve()
        self.links: dict[str, list[str]] = {}
        self._ancestors: dict[str, frozenset[str]] = {}
        self._names: dict[Path, set[str]] = {}
        self._folded: dict[Path, set[str]] = {}
        self._documents: dict[Path, Any] = {}

    def report(self, package: str, check: str, detail: str, record: str = "") -> None:
        self.findings.append(
            {"package": package, "check": check, "record": record, "detail": detail})

    def close(self) -> None:
        for document in self._documents.values():
            document.close()

    def inside(self, relative: str) -> Path | None:
        """The file a project-relative path names, or None if it leaves the project.

        Only the plain form is taken: names joined by ``/``, with no ``..``,
        ``.``, empty name, backslash, ``~`` or NUL, so one file has one spelling
        and a path cannot be read two ways. Links are followed before the test,
        so a link inside the project to a file outside it is refused too, and
        so is a loop of links. A name spelled in another letter case than the
        folder lists is refused. The file does not have to exist.
        """
        parts = relative.split("/")
        if (not relative or "\x00" in relative or "\\" in relative
                or relative.startswith("~") or any(part in ("", ".", "..") for part in parts)):
            return None
        try:
            resolved = (self.root / relative).resolve()
            if not resolved.is_relative_to(self.root):
                return None
            # On a file system that ignores letter case, "A.pdf" and "a.pdf" open
            # the same file; on one that does not, "A.pdf" names a file that is not
            # there. Either way only the spelling the folder lists is taken, and a
            # name that matches a listed one once letter case is ignored is refused,
            # so the check gives the same answer on every file system.
            folder = self.project
            for part in parts:
                if folder not in self._names:
                    names = set(os.listdir(folder)) if folder.is_dir() else set()
                    self._names[folder] = names
                    self._folded[folder] = {_folded_name(name) for name in names}
                if part not in self._names[folder] and (
                        os.path.lexists(folder / part)
                        or _folded_name(part) in self._folded[folder]):
                    return None
                folder = folder / part
        except (OSError, RuntimeError, ValueError):
            # A loop of links, a name too long for the file system, and the like.
            return None
        return resolved

    # --- files -----------------------------------------------------------

    def check_files(self, folder: Path) -> None:
        package = folder.name
        if self.inside(folder.relative_to(self.project).as_posix()) is None:
            self.report(package, "path_outside_project",
                        f"{folder.relative_to(self.project).as_posix()} is a link out of the "
                        "project; not read")
            return
        if package not in ID_PREFIXES:
            self.report(package, "unknown_folder",
                        "the folder is not named for an agent that writes files")
        for name in EVIDENCE_FILES:
            if not _is_file(folder / name):
                self.report(package, "missing_file", f"{name} is not in {folder.name}/")
        sums = folder / "SHA256SUMS"
        if not _is_file(sums):
            return
        if self.inside(sums.relative_to(self.project).as_posix()) is None:
            self.report(package, "path_outside_project",
                        "SHA256SUMS is a link out of the project; not read")
            return
        self.seals[sums.relative_to(self.project).as_posix()] = _sha256(sums)
        listed = self.manifests.setdefault(package, set())
        try:
            text = sums.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            self.report(package, "bad_manifest_line", f"SHA256SUMS could not be read ({error})")
            return
        for line in text.split("\n"):
            if not line.strip():
                continue
            digest, separator, relative = line.partition("  ")
            relative = relative.strip().removeprefix("*")
            if not separator or not relative or not _DIGEST.fullmatch(digest.strip()):
                self.report(package, "bad_manifest_line",
                            f"'{line}' is not a sha256, two spaces and a path")
                continue
            listed.add(relative)
            path = self.inside(relative)
            if path is None:
                self.report(package, "path_outside_project",
                            f"{relative}: SHA256SUMS lists a path that is not a plain path "
                            "inside the project; not read")
                continue
            self.counts["hashed_files"] += 1
            if not _is_file(path):
                self.report(package, "hash_mismatch", f"{relative}: listed but not found")
            elif _sha256(path) != digest.strip():
                self.report(package, "hash_mismatch",
                            f"{relative}: changed after it was hashed, or cannot be read")
        for path in sorted(folder.rglob("*")):
            relative = path.relative_to(self.project).as_posix()
            if _is_file(path) and path != sums and relative not in listed:
                self.report(package, "unlisted_file", f"{relative} is not in SHA256SUMS")

    def check_inventory(self) -> None:
        """Every received file is in the document inventory's SHA256SUMS."""
        received = self.project / RECEIVED_FOLDER
        files = sorted(
            path.relative_to(self.project).as_posix()
            for path in received.rglob("*") if _is_file(path)
        ) if received.is_dir() else []
        for relative in files:
            path = self.inside(relative)
            if path is not None:
                self.seals[relative] = _sha256(path)
        if not files:
            return
        if INVENTORY_AGENT not in self.manifests:
            self.report(INVENTORY_AGENT, "no_inventory",
                        f"{RECEIVED_FOLDER}/ has {len(files)} file(s) and no {INVENTORY_AGENT} "
                        "SHA256SUMS lists them")
            return
        for relative in files:
            if relative not in self.manifests[INVENTORY_AGENT]:
                self.report(INVENTORY_AGENT, "received_not_inventoried",
                            f"{relative} is not in the {INVENTORY_AGENT} SHA256SUMS")

    def check_seals(self, expected: dict[str, str]) -> None:
        """Compare each received file and each SHA256SUMS with a recorded hash."""
        for relative in sorted(set(expected) | set(self.seals)):
            package = Path(relative).parent.name
            if relative not in expected:
                self.report(package, "seal_missing", f"{relative} has no recorded seal")
            elif relative not in self.seals:
                self.report(package, "seal_missing", f"{relative} has a recorded seal and is gone")
            elif expected[relative] != self.seals[relative]:
                self.report(package, "seal_mismatch",
                            f"{relative} changed after its seal was recorded")

    # --- records ---------------------------------------------------------

    def load_records(self, folder: Path) -> None:
        package = folder.name
        if self.inside(folder.relative_to(self.project).as_posix()) is None:
            return
        paths = [folder / name for name in RECORD_FILE_NAMES if _is_file(folder / name)]
        if not paths:
            self.report(package, "no_records",
                        "no " + " or ".join(RECORD_FILE_NAMES) + f" in {folder.name}/")
        for path in paths:
            if self.inside(path.relative_to(self.project).as_posix()) is None:
                self.report(package, "path_outside_project",
                            f"{path.name} is a link out of the project; not read")
                continue
            rows, problems = read_records(path)
            for problem in problems:
                self.report(package, "unreadable_records", f"{path.name}: {problem}")
            if not rows:
                continue
            columns = list(rows[0])
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
                number = re.fullmatch(re.escape(prefix) + r"([0-9]{1,9})", record)
                if not number:
                    self.report(package, "bad_id", f"expected {prefix}<number>", record)
                if record in self.ids:
                    self.duplicates.add(record)
                    self.report(package, "duplicate_id", "the ID is used more than once", record)
                elif number:
                    # QTO-7, QTO-07 and QTO-007 read as one ID to a person.
                    same = self.numbers.setdefault((prefix, int(number.group(1))), record)
                    if same != record:
                        self.report(package, "duplicate_id",
                                    f"the same number as {same}, written another way", record)
                self.ids.add(record)
                self.owner.setdefault(record, package)
                self.by_id.setdefault(record, row)
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

        self.check_link_types(package, record, row, [link for link in links if link in self.ids])

        if package == TAKEOFF_AGENT and value("record_type") == BOQ_RECORD_TYPE:
            self.check_quantity(package, record, row)
        elif (package == TAKEOFF_AGENT and "record_type" in row
              and value("record_type") not in RECORD_TYPES):
            self.report(package, "bad_record_type",
                        f"record_type '{row.get('record_type')}' is not one of: "
                        + ", ".join(RECORD_TYPES), record)

        if "page" in row and value("page") and not _PAGE.fullmatch(value("page")):
            self.report(package, "bad_page",
                        f"page '{value('page')[:40]}' is not a page number written in digits",
                        record)

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

    # --- the chain -------------------------------------------------------

    def links_of(self, record: str) -> list[str]:
        if record not in self.links:
            row = self.by_id.get(record, {})
            self.links[record] = [
                link for link in _SEPARATORS.split((row.get("based_on") or "").strip())
                if link in self.ids]
        return self.links[record]

    def ancestors(self, record: str) -> frozenset[str]:
        """The record and every record it is based on, directly or not."""
        if record not in self._ancestors:
            seen: set[str] = set()
            stack = [record]
            while stack:
                current = stack.pop()
                if current not in seen:
                    seen.add(current)
                    stack.extend(self.links_of(current))
            self._ancestors[record] = frozenset(seen)
        return self._ancestors[record]

    def check_link_types(self, package: str, record: str, row: dict[str, str],
                         links: list[str]) -> None:
        stage = STAGES.get(package)
        for link in links:
            target = self.owner[link]
            if stage is not None and STAGES.get(target, -1) > stage:
                self.report(package, "wrong_link_type",
                            f"based on {link}, a record of a later stage ({target})", record)
            elif (package == target == TAKEOFF_AGENT and link != record
                  and (row.get("record_type") or "").strip() == INPUT_RECORD_TYPE
                  and (self.by_id[link].get("record_type") or "").strip() != INPUT_RECORD_TYPE):
                self.report(package, "wrong_link_type",
                            f"an input row is a printed value; it is based on {link}, "
                            "a calculated row", record)

    def check_cycles(self) -> None:
        """Report each circle of ``based_on`` links once, at its lowest ID.

        One pass over the links (Tarjan's strongly connected components, written
        without recursion), so a long circle costs no more than a long chain.
        """
        index: dict[str, int] = {}
        low: dict[str, int] = {}
        on_stack: set[str] = set()
        stack: list[str] = []
        circles: list[list[str]] = []
        for start in sorted(self.ids):
            if start in index:
                continue
            work = [(start, iter(self.links_of(start)))]
            index[start] = low[start] = len(index)
            stack.append(start)
            on_stack.add(start)
            while work:
                node, links = work[-1]
                for link in links:
                    if link not in index:
                        index[link] = low[link] = len(index)
                        stack.append(link)
                        on_stack.add(link)
                        work.append((link, iter(self.links_of(link))))
                        break
                    if link in on_stack:
                        low[node] = min(low[node], index[link])
                else:
                    work.pop()
                    if work:
                        low[work[-1][0]] = min(low[work[-1][0]], low[node])
                    if low[node] == index[node]:
                        circle = []
                        while True:
                            member = stack.pop()
                            on_stack.discard(member)
                            circle.append(member)
                            if member == node:
                                break
                        if len(circle) > 1 or node in self.links_of(node):
                            circles.append(sorted(circle))
        for circle in sorted(circles):
            shown = ", ".join(circle[:12]) + (f" and {len(circle) - 12} more"
                                              if len(circle) > 12 else "")
            self.report(self.owner[circle[0]], "cyclic_based_on",
                        "based_on runs in a circle: " + shown, circle[0])

    def has_drawing_evidence(self, record: str) -> bool:
        row = self.by_id[record]
        bbox = (row.get("bbox") or "").strip()
        if not (row.get("file") or "").strip() or bbox == SEE_BASED_ON or bbox.startswith("none"):
            return False
        if _COORDINATES.fullmatch(bbox):
            return True
        return not _LINE.fullmatch(bbox) and self.is_image(self.inside(bbox))

    @staticmethod
    def is_image(path: Path | None) -> bool:
        """True for a file that starts like a PNG or a JPEG. Its content is not judged."""
        if not _is_file(path):
            return False
        try:
            with path.open("rb") as handle:
                return handle.read(8).startswith(_IMAGE_SIGNATURES)
        except OSError:
            return False

    def check_quantity(self, package: str, record: str, row: dict[str, str]) -> None:
        """A quantity row with a number: its parts, and the path back to a drawing."""
        if not (row.get("quantity") or "").strip():
            return
        problems = [p for p in quantity_row_problems(row) if not p.startswith("the ID")]
        if not _visible(row.get("revision") or ""):
            problems.append("no revision")
        if problems:
            self.report(package, "incomplete_quantity", "; ".join(problems), record)
        behind = self.ancestors(record)
        if not any(self.has_drawing_evidence(r) for r in behind):
            self.report(package, "no_drawing_evidence",
                        "no record behind this quantity gives a place on a drawing "
                        "(x0,y0,x1,y1 or a crop image)", record)
        has_scope = any(STAGES.get(name) == SCOPE_STAGE for name in self.owner.values())
        if has_scope and not any(STAGES.get(self.owner[r]) == SCOPE_STAGE for r in behind):
            self.report(package, "no_scope_record",
                        "the project has a scope register and no record behind this "
                        "quantity is one of its rows", record)

    def check_revisions(self) -> None:
        """One page has one revision. The document inventory's rows are the reference.

        This compares what the records say with each other. Whether a sheet is
        the current revision of the set is for the plan reviewer and the owner.
        """
        reference: dict[tuple[str, str], str] = {}
        ordered = sorted(self.rows, key=lambda item: item[0] != INVENTORY_AGENT)
        for package, row in ordered:
            page = (row.get("page") or "").strip()
            revision = (row.get("revision") or "").strip()
            if not page or not revision:
                continue
            key = ((row.get("file") or "").strip(), page)
            if reference.setdefault(key, revision) != revision:
                self.report(package, "revision_differs",
                            f"revision '{revision}' for page {page}, but another record "
                            f"has '{reference[key]}' for the same page",
                            (row.get("id") or "").strip())

    def check_boq(self) -> None:
        """Every BOQ line matches one quantity record, and none is left out."""
        relative = f"{WORK_FOLDER}/{REPORT_AGENT}/{BOQ_FILE_NAME}"
        if not os.path.lexists(self.project / relative):
            return
        path = self.inside(relative)
        if path is None:
            self.report(REPORT_AGENT, "path_outside_project",
                        f"{BOQ_FILE_NAME} is a link out of the project; not read")
            return
        if not _is_file(path):
            return
        lines, problems = read_records(path)
        for problem in problems:
            self.report(REPORT_AGENT, "unreadable_records", f"{path.name}: {problem}")
        missing = [c for c in BOQ_COLUMNS + EXTRA_BOQ_COLUMNS if lines and c not in lines[0]]
        if missing:
            self.report(REPORT_AGENT, "boq_missing_column", f"{path.name}: {', '.join(missing)}")
            return
        quantity_rows = {
            record: row for record, row in self.by_id.items()
            if self.owner[record] == TAKEOFF_AGENT and record not in self.duplicates
            and (row.get("record_type") or "").strip() == BOQ_RECORD_TYPE
        }
        seen: set[str] = set()
        for line in lines:
            self.counts["boq_lines"] += 1
            code = (line.get("item_code") or "").strip()
            if code not in quantity_rows or code in seen:
                self.report(REPORT_AGENT, "boq_no_record",
                            "the line is listed twice" if code in seen else
                            "no quantity record in the takeoff has this ID", code)
                continue
            seen.add(code)
            row = quantity_rows[code]
            differs = [
                f"{column} '{(line.get(column) or '').strip()}' but the record has "
                f"'{(row.get(source) or '').strip()}'"
                for column, source in (("quantity", "quantity"), ("unit", "unit"),
                                       ("formula", "formula"), ("source_sheet", "sheet"),
                                       ("source_revision", "revision"))
                if (line.get(column) or "").strip() != (row.get(source) or "").strip()
            ]
            if differs:
                self.report(REPORT_AGENT, "boq_differs", "; ".join(differs), code)
        numbered = 0
        for record, row in quantity_rows.items():
            if (row.get("quantity") or "").strip():
                numbered += 1
                if record not in seen:
                    self.report(REPORT_AGENT, "boq_missing_line",
                                "this quantity record has a number and no BOQ line", record)
        total = len(quantity_rows)
        expected = (f"DRAFT: all {total} quantity rows, not reviewed" if numbered == total else
                    f"PARTIAL DRAFT: {numbered} of {total} quantity rows, not reviewed")
        wrong = sorted({(line.get("boq_status") or "").strip() for line in lines}
                       - {expected})
        if wrong:
            self.report(REPORT_AGENT, "boq_status_wrong",
                        f"boq_status must be exactly '{expected}' on every line; found: "
                        + "; ".join(f"'{text[:80]}'" for text in wrong))

    # --- sources ---------------------------------------------------------

    def check_source(self, package: str, record: str, row: dict[str, str], links: list[str]) -> None:
        bbox = (row.get("bbox") or "").strip()
        printed = row.get("as_printed") or ""
        file_name = (row.get("file") or "").strip()

        if file_name:
            if self.inside(file_name) is None:
                self.report(package, "path_outside_project",
                            f"file '{file_name}' is outside the project; not read", record)
                return
            if package in self.manifests and file_name not in self.manifests[package]:
                self.report(package, "source_not_hashed",
                            f"file '{file_name}' is not in this package's SHA256SUMS", record)

        if SEE_BASED_ON in (bbox, printed.strip()):
            if bbox != printed.strip() or not links:
                self.report(package, "bad_bbox",
                            f"'{SEE_BASED_ON}' goes in both as_printed and bbox, with a based_on link",
                            record)
            return

        coordinates = _COORDINATES.fullmatch(bbox)
        if coordinates:
            if printed.strip() == DRAWN:
                # Nothing to read back, but the page it is drawn on has to open.
                opened = self.read_pdf_text(file_name, row.get("page") or "", ("0",) * 4)
                if opened.startswith("<could not read"):
                    self.report(package, "bad_bbox",
                                f"'{DRAWN}' cites a page that does not open: {opened}", record)
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
            digits = line.group(1)
            found = (self.read_text_line(file_name, int(digits)) if len(digits) <= 9
                     else f"<{file_name} has no such line>")
            if _normalize(found) != _normalize(printed):
                self.report(package, "read_back_mismatch",
                            f"as_printed '{printed}' but the source reads '{found}'", record)
            return

        if bbox.startswith("none"):
            if not bbox[len("none"):].strip(" :"):
                self.report(package, "bad_bbox", "'none' needs its reason", record)
            return

        if bbox and self.inside(bbox) is None:
            self.report(package, "path_outside_project",
                        f"bbox '{bbox}' is a path outside the project", record)
        elif not bbox or not self.is_image(self.inside(bbox)):
            self.report(package, "bad_bbox",
                        f"'{bbox}' is not x0,y0,x1,y1, 'line <n>', '{SEE_BASED_ON}', "
                        "'none: <reason>' or the path of a PNG or JPEG crop image", record)
        else:
            # The image exists. Whether it shows the cited place is not checked here.
            self.counts["crops_not_compared"] += 1

    def read_pdf_text(self, file_name: str, page: str, coordinates: tuple[str, ...]) -> str:
        # Imported here, so the checks that read no PDF run without the library.
        try:
            import pypdfium2 as pdfium
        except ImportError as error:
            return f"<could not read {file_name} page {page}: pypdfium2 is not installed ({error})>"
        try:
            path = self.inside(file_name)
            if path is None:
                raise ValueError("the path is outside the project")
            if path not in self._documents:
                self._documents[path] = pdfium.PdfDocument(str(path))
            textpage = self._documents[path][int(float(page)) - 1].get_textpage()
            x0, y0, x1, y1 = (float(number) for number in coordinates)
            return textpage.get_text_bounded(
                left=x0 - _BBOX_PADDING_PT, bottom=y0 - _BBOX_PADDING_PT,
                right=x1 + _BBOX_PADDING_PT, top=y1 + _BBOX_PADDING_PT,
            )
        except (OSError, ValueError, OverflowError, IndexError, pdfium.PdfiumError) as error:
            return f"<could not read {file_name} page {page}: {error}>"

    def read_text_line(self, file_name: str, number: int) -> str:
        try:
            path = self.inside(file_name)
            if path is None:
                raise OSError("the path is outside the project")
            lines = path.read_text(encoding="utf-8").splitlines()
            return lines[number - 1] if number >= 1 else f"<{file_name} has no line {number}>"
        except (OSError, IndexError, UnicodeDecodeError) as error:
            return f"<could not read {file_name} line {number}: {error}>"


def check_project(project_dir: str | Path, seals: dict[str, str] | None = None) -> dict[str, Any]:
    """Check every package in ``<project_dir>/02_Working`` and return the result.

    The result has ``packages`` (the folder names checked), ``counts`` (hashed
    files, records, links, strings read back, crop images found but not
    compared, and BOQ lines), ``seals`` (the sha256 of each ``SHA256SUMS``, by
    its project-relative path) and ``findings``. Each finding has ``package``,
    ``check``, ``record`` and ``detail``. An empty ``findings`` list means every
    check here passed; it is not a review of the quantities.

    ``seals`` is an earlier result's ``seals``. When given, a ``SHA256SUMS``
    that changed since is reported. Without it, a package whose files and
    ``SHA256SUMS`` were both rewritten cannot be told from an honest one.
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
        checker.check_inventory()
        if seals is not None:
            checker.check_seals(seals)
        for package, row in checker.rows:
            checker.check_row(package, row)
        checker.check_cycles()
        checker.check_revisions()
        checker.check_boq()
    finally:
        checker.close()
    return {
        "packages": [folder.name for folder in folders],
        "counts": checker.counts,
        "seals": checker.seals,
        "findings": checker.findings,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    seals = None
    seal_conflicts: set[str] = set()
    if "--seals" in args:
        at = args.index("--seals")
        if at + 1 >= len(args):
            print(__doc__)
            return 2
        seals = {}
        source = args[at + 1]
        try:
            text = (sys.stdin.read() if source == "-"
                    else Path(source).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as error:
            print(f"The seals file {source} could not be read: {error}")
            return 2
        for line in text.splitlines():
            digest, _, relative = line.removeprefix("SEAL ").partition("  ")
            relative, digest = relative.strip(), digest.strip()
            if relative and seals.setdefault(relative, digest) != digest:
                seal_conflicts.add(relative)
        del args[at:at + 2]
    if len(args) != 1:
        print(__doc__)
        return 2
    result = check_project(args[0], seals)
    # Two recorded seals for one path: nothing says which is the owner's, so
    # neither is taken as the baseline without saying so.
    for relative in sorted(seal_conflicts):
        result["findings"].append({
            "package": Path(relative).parent.name, "check": "seal_conflict", "record": "",
            "detail": f"{relative} has two different recorded seals; keep the owner's one",
        })
    if not result["packages"]:
        print(f"No package folders found in {Path(args[0]) / WORK_FOLDER}.")
        return 1
    counts = result["counts"]
    print(f"Packages: {', '.join(result['packages'])}")
    print(f"Checked: {counts['hashed_files']} hashed files, {counts['records']} records, "
          f"{counts['links']} based_on links, {counts['read_back']} strings read back.")
    if counts["boq_lines"]:
        print(f"Checked: {counts['boq_lines']} BOQ line(s) against the quantity records.")
    if counts["crops_not_compared"]:
        print(f"Not checked: {counts['crops_not_compared']} crop image(s) exist but were not "
              "compared with their sheet. A person has to look at each one.")
    for relative, digest in sorted(result["seals"].items()):
        print(f"SEAL {digest}  {relative}")
    for finding in result["findings"]:
        record = f" {finding['record']}" if finding["record"] else ""
        print(f"FINDING [{finding['package']}] {finding['check']}{record}: {finding['detail']}")
    print(f"Findings: {len(result['findings'])}. "
          "This checks file integrity and traceability only. "
          "It does not check that a quantity is right.")
    return 1 if result["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
