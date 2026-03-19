"""
io/csv_parser.py
================
CSV import and export for MeOS data (csvparser.cpp equivalent).

Supported formats
-----------------
  • Starters / entries:   card, first, last, club, class
  • Start list:           bib, card, first, last, club, class, start_time
  • Results:              place, bib, first, last, club, class, time, status
  • Controls / courses:   course, length, controls...

Column names are case-insensitive; column order is detected automatically.
"""
from __future__ import annotations

import csv
import io
import logging
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from models import Event, Runner, Team, Club, Class, Course, Control
from utils.time_utils import parse_time, format_time

log = logging.getLogger(__name__)


class CSVFormat(Enum):
    Auto       = "auto"
    Entries    = "entries"
    StartList  = "startlist"
    Results    = "results"
    Courses    = "courses"


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

class CSVImporter:
    """Reads CSV files and populates an Event model."""

    def __init__(self, event: Event) -> None:
        self._event = event
        self.errors: List[str] = []
        self.imported_count: int = 0

    def import_file(self, path: str | Path,
                    fmt: CSVFormat = CSVFormat.Auto,
                    encoding: str = "utf-8-sig") -> bool:
        """Import from a CSV file. Returns True on full success."""
        self.errors = []
        self.imported_count = 0
        try:
            with open(path, newline="", encoding=encoding, errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            self.errors.append(f"Cannot open file: {exc}")
            return False
        return self.import_text(text, fmt)

    def import_text(self, text: str,
                    fmt: CSVFormat = CSVFormat.Auto) -> bool:
        """Import from a CSV string. Returns True on full success."""
        self.errors = []
        self.imported_count = 0

        # Detect delimiter: semicolon or comma
        delim = ";" if text.count(";") > text.count(",") else ","

        reader = csv.DictReader(io.StringIO(text), delimiter=delim)
        try:
            rows = list(reader)
        except csv.Error as exc:
            self.errors.append(f"CSV parse error: {exc}")
            return False

        if not rows:
            return True

        # Normalise header names to lower-case
        norm_rows = [{k.lower().strip(): v.strip() for k, v in row.items()}
                     for row in rows]

        if fmt == CSVFormat.Auto:
            fmt = self._detect_format(norm_rows[0])

        if fmt == CSVFormat.Entries:
            self._import_entries(norm_rows)
        elif fmt == CSVFormat.StartList:
            self._import_startlist(norm_rows)
        elif fmt == CSVFormat.Results:
            self._import_results(norm_rows)
        elif fmt == CSVFormat.Courses:
            self._import_courses(norm_rows)
        else:
            self._import_entries(norm_rows)

        return len(self.errors) == 0

    # ------------------------------------------------------------------
    # Format detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_format(row: Dict[str, str]) -> CSVFormat:
        keys = set(row.keys())
        if any(k in keys for k in ("place", "running time", "runningtime")):
            return CSVFormat.Results
        if any(k in keys for k in ("start", "starttime", "start time")):
            return CSVFormat.StartList
        if "controls" in keys or "course" in keys:
            return CSVFormat.Courses
        return CSVFormat.Entries

    # ------------------------------------------------------------------
    # Entry import
    # ------------------------------------------------------------------

    def _import_entries(self, rows: List[Dict[str, str]]) -> None:
        ev = self._event
        for i, row in enumerate(rows, 1):
            try:
                first  = row.get("firstname", row.get("first", row.get("first name", "")))
                last   = row.get("lastname",  row.get("last",  row.get("last name",  row.get("name", ""))))
                club_n = row.get("club", row.get("organisation", ""))
                cls_n  = row.get("class", row.get("category", ""))
                card_s = row.get("card", row.get("sicard", row.get("si", "")))

                if not (first or last):
                    continue

                club = ev.add_club(club_n) if club_n else None
                cls  = ev.get_class_by_name(cls_n)
                if cls_n and cls is None:
                    cls = ev.add_class(cls_n)

                runner = ev.add_runner(
                    first_name=first, last_name=last,
                    club_id=club.id if club else 0,
                    class_id=cls.id if cls else 0,
                )
                if card_s:
                    try:
                        runner.card_number = int(card_s)
                    except ValueError:
                        pass
                self.imported_count += 1
            except Exception as exc:
                self.errors.append(f"Row {i}: {exc}")

    # ------------------------------------------------------------------
    # Start list import
    # ------------------------------------------------------------------

    def _import_startlist(self, rows: List[Dict[str, str]]) -> None:
        self._import_entries(rows)   # create runners first
        ev = self._event
        for i, row in enumerate(rows, 1):
            try:
                card_s  = row.get("card", row.get("si", ""))
                st_s    = row.get("start", row.get("starttime", row.get("start time", "")))
                bib_s   = row.get("bib", row.get("number", ""))
                if not card_s:
                    continue
                card_no = int(card_s)
                runner  = ev.get_runner_by_card(card_no)
                if runner is None:
                    continue
                if st_s:
                    runner.start_time = parse_time(st_s)
                if bib_s:
                    runner.bib = bib_s
            except Exception as exc:
                self.errors.append(f"Row {i} (startlist): {exc}")

    # ------------------------------------------------------------------
    # Results import
    # ------------------------------------------------------------------

    def _import_results(self, rows: List[Dict[str, str]]) -> None:
        from models import RunnerStatus
        self._import_entries(rows)
        ev = self._event
        for i, row in enumerate(rows, 1):
            try:
                card_s  = row.get("card", row.get("si", ""))
                time_s  = row.get("time", row.get("running time", row.get("runningtime", "")))
                st_s    = row.get("status", "")
                if not card_s:
                    continue
                runner = ev.get_runner_by_card(int(card_s))
                if runner is None:
                    continue
                if time_s:
                    runner.tmp_result.running_time = parse_time(time_s)
                if st_s:
                    runner.status = RunnerStatus.from_code(st_s)
            except Exception as exc:
                self.errors.append(f"Row {i} (results): {exc}")

    # ------------------------------------------------------------------
    # Courses import
    # ------------------------------------------------------------------

    def _import_courses(self, rows: List[Dict[str, str]]) -> None:
        ev = self._event
        for i, row in enumerate(rows, 1):
            try:
                name   = row.get("course", row.get("name", ""))
                length = int(row.get("length", row.get("distance", 0)) or 0)
                climb  = int(row.get("climb", 0) or 0)
                if not name:
                    continue
                course = ev.get_course_by_name(name)
                if course is None:
                    course = ev.add_course(name)
                course.length = length
                course.climb  = climb
                # Remaining columns treated as control numbers
                ctrl_ids: List[int] = []
                for k, v in row.items():
                    if k not in ("course", "name", "length", "distance", "climb") and v:
                        try:
                            code = int(v)
                            ctrl = _find_or_create_control(ev, code)
                            ctrl_ids.append(ctrl.id)
                        except ValueError:
                            pass
                if ctrl_ids:
                    course.control_ids = ctrl_ids
                self.imported_count += 1
            except Exception as exc:
                self.errors.append(f"Row {i} (courses): {exc}")


def _find_or_create_control(ev: Event, code: int) -> Control:
    for c in ev.controls.values():
        if c.has_number(code):
            return c
    c = ev.add_control(str(code), numbers=[code])
    return c


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

class CSVExporter:
    """Writes event data to CSV."""

    # ------------------------------------------------------------------
    # Start list
    # ------------------------------------------------------------------

    @staticmethod
    def export_startlist(event: Event, path: str | Path,
                         class_id: int = 0,
                         delimiter: str = ";") -> None:
        runners = list(event.runners.values())
        if class_id:
            runners = [r for r in runners if r.class_id == class_id]
        runners = [r for r in runners if not r.removed]
        runners.sort(key=lambda r: (r.class_id, r.start_time, r.start_no))

        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=delimiter)
            w.writerow(["Bib", "Card", "FirstName", "LastName",
                        "Club", "Class", "StartTime"])
            for r in runners:
                club  = event.clubs.get(r.club_id)
                cls   = event.classes.get(r.class_id)
                w.writerow([
                    r.bib,
                    r.card_number or "",
                    r.first_name,
                    r.last_name,
                    club.name if club else "",
                    cls.name  if cls  else "",
                    format_time(r.start_time) if r.start_time else "",
                ])

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    @staticmethod
    def export_results(event: Event, path: str | Path,
                       class_id: int = 0,
                       delimiter: str = ";") -> None:
        runners = list(event.runners.values())
        if class_id:
            runners = [r for r in runners if r.class_id == class_id]
        runners = [r for r in runners if not r.removed]
        runners.sort(key=lambda r: (r.class_id, r.result_sort_key()))

        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=delimiter)
            w.writerow(["Place", "Bib", "FirstName", "LastName",
                        "Club", "Class", "Time", "Status"])
            for r in runners:
                club = event.clubs.get(r.club_id)
                cls  = event.classes.get(r.class_id)
                w.writerow([
                    r.place or "",
                    r.bib,
                    r.first_name,
                    r.last_name,
                    club.name if club else "",
                    cls.name  if cls  else "",
                    r.get_running_time_string(),
                    r.status.to_code(),
                ])
