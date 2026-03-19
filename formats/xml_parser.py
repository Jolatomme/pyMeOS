"""
formats/xml_parser.py
=====================
MeOS XML file format – load and save.

Supports **two formats**:

1. **Real MeOS format** (root ``<meosdata>``) – produced by the original
   MeOS application.  Files typically end in ``.meosxml`` or ``.xml``.
   *Load only* – this is the authoritative competition source.

2. **PyMeOS native format** (root ``<MeOS>``) – a simpler XML dialect used
   internally by PyMeOS for save/restore.  Fully round-trips.

The format is detected automatically from the root tag.

Time conventions in real MeOS files
-------------------------------------
* ``<ZeroTime>``         – absolute seconds since midnight for the race day.
* ``<Start>`` (runner)   – start time in seconds **relative to zero time**.
* ``<FirstStart>``       – class first start, seconds relative to zero time.
* ``<StartInterval>``    – seconds between start slots.
* PyMeOS stores all times in **tenths of seconds** (×10).
* Conversion: ``internal = (zero_s + relative_s) × TIME_UNITS_PER_SECOND``

MeOS Runner name convention
---------------------------
``<Name>LASTNAME, Firstname</Name>`` (comma-separated).
Fallback: ``Firstname LASTNAME`` (space-separated, last token = family name).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

try:
    from lxml import etree as ET
except ImportError:
    import xml.etree.ElementTree as ET  # type: ignore[assignment]

from models import (
    Event, Runner, Team, Class, Course, Control, Club, Card,
    RunnerStatus, ControlStatus, ClassType, StartType, Sex,
)
from utils.time_utils import NO_TIME, TIME_UNITS_PER_SECOND

log = logging.getLogger(__name__)

_S = TIME_UNITS_PER_SECOND  # 10 — seconds → internal units multiplier


# ===========================================================================
# Public API
# ===========================================================================

def save_event_xml(event: Event, path: str) -> None:
    """Serialize *event* to a PyMeOS native XML file (``<MeOS>`` root)."""
    root = ET.Element("MeOS")
    root.set("version", "5.0")

    ev_el = ET.SubElement(root, "Event")
    ev_el.set("name",    event.name)
    ev_el.set("date",    event.date)
    ev_el.set("zero",    str(event.zero_time))
    ev_el.set("org",     event.organiser)
    ev_el.set("country", event.country)

    # Controls
    ctrls_el = ET.SubElement(root, "Controls")
    for c in event.controls.values():
        if c.removed:
            continue
        el = ET.SubElement(ctrls_el, "Control")
        el.set("id",      str(c.id))
        el.set("name",    c.name)
        el.set("status",  str(c.status.value))
        el.set("numbers", ",".join(str(n) for n in c.numbers))
        el.set("tadj",    str(c.time_adjustment))

    # Courses
    for c in event.courses.values():
        if c.removed:
            continue
        el = ET.SubElement(root, "Course")
        el.set("id",    str(c.id))
        el.set("name",  c.name)
        el.set("len",   str(c.length))
        el.set("climb", str(c.climb))
        el.set("cids",  json.dumps(c.control_ids))

    # Classes
    for c in event.classes.values():
        if c.removed:
            continue
        el = ET.SubElement(root, "Class")
        el.set("id",    str(c.id))
        el.set("name",  c.name)
        el.set("crsid", str(c.course_id))
        el.set("type",  c.class_type.value)
        el.set("st",    str(c.start_type.value))
        el.set("fs",    str(c.first_start))
        el.set("si",    str(c.start_interval))
        el.set("fee",   str(c.entry_fee))

    # Clubs
    for c in event.clubs.values():
        if c.removed:
            continue
        el = ET.SubElement(root, "Club")
        el.set("id",    str(c.id))
        el.set("name",  c.name)
        el.set("short", c.short_name)
        el.set("cntry", c.country)

    # Runners
    for r in event.runners.values():
        if r.removed:
            continue
        el = ET.SubElement(root, "Runner")
        el.set("id",     str(r.id))
        el.set("fn",     r.first_name)
        el.set("ln",     r.last_name)
        el.set("club",   str(r.club_id))
        el.set("cls",    str(r.class_id))
        el.set("card",   str(r.card_number))
        el.set("st",     str(r.start_time))
        el.set("ft",     str(r.finish_time))
        el.set("status", str(r.status.value))
        el.set("bib",    r.bib)
        el.set("sno",    str(r.start_no))
        el.set("sex",    r.sex.value)
        el.set("nat",    r.nationality)

    # Teams
    for t in event.teams.values():
        if t.removed:
            continue
        el = ET.SubElement(root, "Team")
        el.set("id",   str(t.id))
        el.set("name", t.name)
        el.set("club", str(t.club_id))
        el.set("cls",  str(t.class_id))
        el.set("rids", json.dumps(t.runner_ids))
        el.set("bib",  t.bib)

    Path(path).write_bytes(
        ET.tostring(root, encoding="utf-8", xml_declaration=True)
    )
    log.info("Saved event '%s' to %s", event.name, path)


def load_event_xml(path: str) -> Optional[Event]:
    """
    Deserialize a MeOS XML file into an Event.

    Detects the format automatically from the root tag:
    * ``<meosdata>`` → real MeOS format
    * ``<MeOS>``     → PyMeOS native format
    """
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception as exc:
        log.error("Cannot parse '%s': %s", path, exc)
        return None

    tag = root.tag.lower()
    if tag == "meosdata":
        log.info("Loading real MeOS format from %s", path)
        return _load_meosdata(root)
    elif tag == "meos":
        log.info("Loading PyMeOS native format from %s", path)
        return _load_pymeos(root)
    else:
        log.error("Unknown root element <%s> in %s", root.tag, path)
        return None


# ===========================================================================
# Shared helpers
# ===========================================================================

def _child_text(el, tag: str, default: str = "") -> str:
    """Text content of the first *tag* child element, or *default*."""
    if el is None:
        return default
    child = el.find(tag)
    if child is None or child.text is None:
        return default
    return child.text.strip()


def _child_int(el, tag: str, default: int = 0) -> int:
    """Integer text of the first *tag* child element, or *default*."""
    try:
        return int(_child_text(el, tag, str(default)))
    except (ValueError, TypeError):
        return default


def _odata_text(el, tag: str, default: str = "") -> str:
    """Text content of ``<oData>/<tag>`` inside *el*, or *default*."""
    if el is None:
        return default
    return _child_text(el.find("oData"), tag, default)


def _odata_int(el, tag: str, default: int = 0) -> int:
    try:
        return int(_odata_text(el, tag, str(default)))
    except (ValueError, TypeError):
        return default


def _attr_int(el, attr: str, default: int = 0) -> int:
    try:
        return int(el.get(attr, default))
    except (ValueError, TypeError):
        return default


def _parse_runner_name(name_str: str):
    """
    Parse a MeOS runner ``<Name>`` into ``(first_name, last_name)``.

    Handles:
    * ``"LASTNAME, Firstname"``   – comma present
    * ``"Firstname LASTNAME"``    – no comma, last token = family name
    """
    if not name_str:
        return "", ""
    name_str = name_str.strip()
    if "," in name_str:
        parts = name_str.split(",", 1)
        last  = parts[0].strip().title()
        first = parts[1].strip()
    else:
        parts = name_str.split()
        if len(parts) >= 2:
            last  = parts[-1].title()
            first = " ".join(parts[:-1])
        else:
            first = name_str
            last  = ""
    return first, last


def _parse_sex(s: str) -> Sex:
    s = (s or "").strip().upper()
    if s in ("M", "H", "MALE"):
        return Sex.Male
    if s in ("F", "D", "FEMALE"):
        return Sex.Female
    return Sex.Unknown


def _parse_runner_status(s: str) -> RunnerStatus:
    if not s:
        return RunnerStatus.Unknown
    s = s.strip().upper()
    _map = {
        "OK": RunnerStatus.OK,        "1":  RunnerStatus.OK,
        "MP": RunnerStatus.MP,        "3":  RunnerStatus.MP,
        "DNF": RunnerStatus.DNF,      "4":  RunnerStatus.DNF,
        "DNS": RunnerStatus.DNS,      "20": RunnerStatus.DNS,
        "DQ":  RunnerStatus.DQ,       "5":  RunnerStatus.DQ,
        "OOC": RunnerStatus.OutOfCompetition, "15": RunnerStatus.OutOfCompetition,
        "MAX": RunnerStatus.MAX,      "6":  RunnerStatus.MAX,
        "NT":  RunnerStatus.NoTiming, "2":  RunnerStatus.NoTiming,
        "CANCEL": RunnerStatus.CANCEL, "21": RunnerStatus.CANCEL,
    }
    return _map.get(s, RunnerStatus.Unknown)


def _parse_class_type(s: str) -> ClassType:
    s = (s or "").strip().lower()
    if "relay" in s or "relais" in s:
        return ClassType.Relay
    if "patrol" in s or "patrouille" in s:
        return ClassType.Patrol
    if "rogain" in s:
        return ClassType.Rogaining
    return ClassType.Individual


# ===========================================================================
# Real MeOS format loader  (<meosdata>)
# ===========================================================================

def _load_meosdata(root) -> Event:
    """Parse a ``<meosdata>`` document into an Event model."""
    event = Event()

    # ── Event-level metadata ────────────────────────────────────────────
    event.name       = _child_text(root, "Name")
    event.date       = _child_text(root, "Date")
    event.organiser  = _odata_text(root, "Organizer")
    event.annotation = _odata_text(root, "Annotation")

    zero_s           = _child_int(root, "ZeroTime", 0)
    event.zero_time  = zero_s * _S      # seconds → internal units

    # ── Controls ────────────────────────────────────────────────────────
    # Build a control-station-number → Control map for course resolution.
    number_to_ctrl: dict[int, Control] = {}

    ctrl_list = root.find("ControlList")
    if ctrl_list is not None:
        for el in ctrl_list.findall("Control"):
            c    = Control()
            c.id = _child_int(el, "Id")

            # Parse SI station numbers
            numbers_str = _child_text(el, "Numbers", "")
            numbers: list[int] = []
            for part in numbers_str.replace(";", ",").split(","):
                part = part.strip()
                if part:
                    try:
                        numbers.append(int(part))
                    except ValueError:
                        pass
            c.numbers = numbers if numbers else [c.id]
            # Use explicit Name if present, otherwise the SI number
            c.name = _child_text(el, "Name") or str(c.numbers[0])

            c.time_adjustment = _odata_int(el, "TimeAdjust", 0)
            c.event = event
            event.controls[c.id] = c
            for n in c.numbers:
                number_to_ctrl[n] = c

    # ── Courses ─────────────────────────────────────────────────────────
    course_list = root.find("CourseList")
    if course_list is not None:
        for el in course_list.findall("Course"):
            c        = Course()
            c.id     = _child_int(el, "Id")
            c.name   = _child_text(el, "Name") or f"Course {c.id}"
            c.length = _child_int(el, "Length")
            c.climb  = _odata_int(el, "Climb")

            # <Controls> is semicolon-separated SI station numbers,
            # with a trailing semicolon:  "79;80;81;82;"
            controls_str = _child_text(el, "Controls", "")
            ctrl_ids: list[int] = []
            for part in controls_str.split(";"):
                part = part.strip()
                if not part:
                    continue
                try:
                    num = int(part)
                except ValueError:
                    continue
                ctrl = number_to_ctrl.get(num)
                if ctrl is None:
                    # Create a stub control for any unknown SI number
                    ctrl = Control(name=str(num), numbers=[num])
                    ctrl.id = event._next_id("control")
                    ctrl.event = event
                    event.controls[ctrl.id] = ctrl
                    number_to_ctrl[num] = ctrl
                    log.debug("Created stub control %d for course %s", num, c.name)
                ctrl_ids.append(ctrl.id)
            c.control_ids = ctrl_ids

            c.event = event
            event.courses[c.id] = c

    # ── Classes ─────────────────────────────────────────────────────────
    class_list = root.find("ClassList")
    if class_list is not None:
        for el in class_list.findall("Class"):
            c           = Class()
            c.id        = _child_int(el, "Id")
            c.name      = _child_text(el, "Name") or f"Class {c.id}"
            c.course_id = _child_int(el, "Course")

            # FirstStart / StartInterval are seconds relative to zero time.
            # Convert to absolute internal units.
            first_start_rel_s = _odata_int(el, "FirstStart", 0)
            c.first_start     = (zero_s + first_start_rel_s) * _S

            interval_s       = _odata_int(el, "StartInterval", 0)
            c.start_interval = interval_s * _S

            c.entry_fee  = _odata_int(el, "ClassFee", 0)
            c.start_type = StartType.Drawn
            c.class_type = _parse_class_type(_odata_text(el, "ClassType"))

            c.event = event
            event.classes[c.id] = c

    # ── Clubs ───────────────────────────────────────────────────────────
    club_list = root.find("ClubList")
    if club_list is not None:
        for el in club_list.findall("Club"):
            c            = Club()
            c.id         = _child_int(el, "Id")
            c.name       = _child_text(el, "Name") or f"Club {c.id}"
            c.short_name = _odata_text(el, "ShortName")
            c.country    = _odata_text(el, "Country")
            try:
                c.ext_id = int(_odata_text(el, "ExtId", "0"))
            except ValueError:
                c.ext_id = 0
            c.event = event
            event.clubs[c.id] = c

    # ── Runners ─────────────────────────────────────────────────────────
    runner_list = root.find("RunnerList")
    if runner_list is not None:
        for el in runner_list.findall("Runner"):
            r    = Runner()
            r.id = _child_int(el, "Id")

            first, last  = _parse_runner_name(_child_text(el, "Name"))
            r.first_name = first
            r.last_name  = last

            r.card_number = _child_int(el, "CardNo")
            r.start_no    = _child_int(el, "StartNo")
            r.club_id     = _child_int(el, "Club")
            r.class_id    = _child_int(el, "Class")
            r.bib         = _child_text(el, "Bib") or (str(r.start_no) if r.start_no else "")

            # <Start> = seconds relative to zero time → absolute internal units
            start_rel_s = _child_int(el, "Start", 0)
            if start_rel_s:
                abs_start     = (zero_s + start_rel_s) * _S
                r.start_time   = abs_start
                r.t_start_time = abs_start
            else:
                r.start_time   = NO_TIME
                r.t_start_time = NO_TIME

            # <FinishTime> = seconds relative to zero time (post-race)
            finish_rel_s  = _child_int(el, "FinishTime", 0)
            r.finish_time = (zero_s + finish_rel_s) * _S if finish_rel_s else NO_TIME

            r.status   = _parse_runner_status(_child_text(el, "Status"))
            r.t_status = r.status

            r.sex         = _parse_sex(_odata_text(el, "Sex"))
            r.nationality = _odata_text(el, "Nationality")
            try:
                r.ext_id = int(_odata_text(el, "ExtId", "0"))
            except ValueError:
                r.ext_id = 0

            r.event = event
            event.runners[r.id] = r

    # ── Teams ───────────────────────────────────────────────────────────
    team_list = root.find("TeamList")
    if team_list is not None:
        for el in team_list.findall("Team"):
            t          = Team()
            t.id       = _child_int(el, "Id")
            t.name     = _child_text(el, "Name") or f"Team {t.id}"
            t.club_id  = _child_int(el, "Club")
            t.class_id = _child_int(el, "Class")
            t.bib      = _child_text(el, "Bib")

            # Leg runner IDs: <Runners>id1;id2;</Runners>
            runners_str = _child_text(el, "Runners", "")
            rids: list[int] = []
            for part in runners_str.split(";"):
                part = part.strip()
                if part:
                    try:
                        rids.append(int(part))
                    except ValueError:
                        pass
            t.runner_ids = rids

            t.event = event
            event.teams[t.id] = t

    event._recalc_free_ids()
    log.info(
        "Loaded '%s': %d controls, %d courses, %d classes, "
        "%d clubs, %d runners, %d teams",
        event.name,
        len(event.controls), len(event.courses), len(event.classes),
        len(event.clubs), len(event.runners), len(event.teams),
    )
    return event


# ===========================================================================
# PyMeOS native format loader  (<MeOS>)
# ===========================================================================

def _load_pymeos(root) -> Event:
    """Parse a ``<MeOS>`` (PyMeOS native) document into an Event model."""
    event = Event()

    ev = root.find("Event")
    if ev is not None:
        event.name      = ev.get("name", "")
        event.date      = ev.get("date", "")
        event.zero_time = _attr_int(ev, "zero")
        event.organiser = ev.get("org",  "")
        event.country   = ev.get("country", "")

    # Controls (inside a <Controls> wrapper)
    for el in root.iter("Control"):
        c = Control()
        c.id   = _attr_int(el, "id")
        c.name = el.get("name", "")
        try:
            c.status = ControlStatus(_attr_int(el, "status"))
        except ValueError:
            c.status = ControlStatus.OK
        nums_str  = el.get("numbers", "")
        c.numbers = [int(x) for x in nums_str.split(",") if x.strip()]
        c.time_adjustment = _attr_int(el, "tadj")
        c.event = event
        event.controls[c.id] = c

    # Courses
    for el in root.iter("Course"):
        c = Course()
        c.id     = _attr_int(el, "id")
        c.name   = el.get("name", "")
        c.length = _attr_int(el, "len")
        c.climb  = _attr_int(el, "climb")
        try:
            c.control_ids = json.loads(el.get("cids", "[]"))
        except Exception:
            c.control_ids = []
        c.event = event
        event.courses[c.id] = c

    # Classes
    for el in root.iter("Class"):
        c = Class()
        c.id        = _attr_int(el, "id")
        c.name      = el.get("name", "")
        c.course_id = _attr_int(el, "crsid")
        try:
            c.class_type = ClassType(el.get("type", "individual"))
        except ValueError:
            c.class_type = ClassType.Individual
        try:
            c.start_type = StartType(_attr_int(el, "st", 2))
        except ValueError:
            c.start_type = StartType.Drawn
        c.first_start    = _attr_int(el, "fs")
        c.start_interval = _attr_int(el, "si")
        c.entry_fee      = _attr_int(el, "fee")
        c.event = event
        event.classes[c.id] = c

    # Clubs
    for el in root.iter("Club"):
        c = Club()
        c.id         = _attr_int(el, "id")
        c.name       = el.get("name", "")
        c.short_name = el.get("short", "")
        c.country    = el.get("cntry", "")
        c.event = event
        event.clubs[c.id] = c

    # Runners
    for el in root.iter("Runner"):
        r = Runner()
        r.id          = _attr_int(el, "id")
        r.first_name  = el.get("fn", "")
        r.last_name   = el.get("ln", "")
        r.club_id     = _attr_int(el, "club")
        r.class_id    = _attr_int(el, "cls")
        r.card_number = _attr_int(el, "card")
        r.start_time  = _attr_int(el, "st", NO_TIME)
        r.finish_time = _attr_int(el, "ft", NO_TIME)
        try:
            r.status = RunnerStatus(_attr_int(el, "status"))
        except ValueError:
            r.status = RunnerStatus.Unknown
        r.t_status    = r.status
        r.bib         = el.get("bib", "")
        r.start_no    = _attr_int(el, "sno")
        r.sex         = _parse_sex(el.get("sex", ""))
        r.nationality = el.get("nat", "")
        r.event = event
        event.runners[r.id] = r

    # Teams
    for el in root.iter("Team"):
        t = Team()
        t.id       = _attr_int(el, "id")
        t.name     = el.get("name", "")
        t.club_id  = _attr_int(el, "club")
        t.class_id = _attr_int(el, "cls")
        t.bib      = el.get("bib", "")
        try:
            t.runner_ids = json.loads(el.get("rids", "[]"))
        except Exception:
            t.runner_ids = []
        t.event = event
        event.teams[t.id] = t

    event._recalc_free_ids()
    return event
