"""
io/iof30.py
===========
IOF XML 3.0 import and export (iof30interface.cpp equivalent).

Supports:
  • CourseData   – courses and controls
  • EntryList    – entries (runners / teams)
  • StartList    – assigned start times
  • ResultList   – results

Uses lxml for fast, standards-compliant XML handling.
"""
from __future__ import annotations

import logging
from typing import Optional, List
from datetime import datetime, timezone

try:
    from lxml import etree as ET
except ImportError:
    import xml.etree.ElementTree as ET  # type: ignore[assignment]

from models import (
    Event, Runner, Team, Class, Course, Control, Club,
    RunnerStatus, ControlStatus, ClassType, Sex,
)
from utils.time_utils import format_time, parse_time, NO_TIME, TIME_UNITS_PER_SECOND

logger = logging.getLogger(__name__)

IOF_NS  = "http://www.orienteering.org/datastandard/3.0"
IOF_XSD = "http://www.orienteering.org/datastandard/3.0 IOF.xsd"


def _ns(tag: str) -> str:
    return f"{{{IOF_NS}}}{tag}"


def _text(el, tag: str, default: str = "") -> str:
    child = el.find(_ns(tag))
    return (child.text or "").strip() if child is not None else default


def _attr(el, name: str, default: str = "") -> str:
    return el.get(name, default)


def _iof_time(units: int) -> str:
    """Format internal units as ISO 8601 duration string (PTxH xM xS)."""
    if units == NO_TIME or units == 0:
        return ""
    secs = units / TIME_UNITS_PER_SECOND
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    s = secs % 60
    if h:
        return f"PT{h}H{m}M{s:.1f}S"
    elif m:
        return f"PT{m}M{s:.1f}S"
    return f"PT{s:.1f}S"


def _parse_iof_time(s: str) -> int:
    """Parse ISO 8601 duration to internal units."""
    if not s or s == "PT":
        return NO_TIME
    import re
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?", s)
    if not m:
        return NO_TIME
    h   = int(m.group(1) or 0)
    mn  = int(m.group(2) or 0)
    sec = float(m.group(3) or 0.0)
    return int((h * 3600 + mn * 60 + sec) * TIME_UNITS_PER_SECOND)


def _make_root(element_name: str) -> ET._Element:
    root = ET.Element(_ns(element_name))
    root.set("xmlns", IOF_NS)
    root.set("iofVersion", "3.0")
    root.set("createTime", datetime.now(timezone.utc).replace(tzinfo=None).isoformat())
    root.set("creator", "PyMeOS")
    return root


# ===========================================================================
# EXPORT
# ===========================================================================

def export_course_data(event: Event) -> bytes:
    """Export courses and controls as IOF 3.0 CourseData XML."""
    root = _make_root("CourseData")

    # Event element
    ev_el = ET.SubElement(root, _ns("Event"))
    ET.SubElement(ev_el, _ns("Name")).text = event.name

    # Controls
    rat_ctrl = ET.SubElement(root, _ns("RaceCourseData"))
    for ctrl in event.controls.values():
        if ctrl.removed:
            continue
        c_el = ET.SubElement(rat_ctrl, _ns("Control"))
        ET.SubElement(c_el, _ns("Id")).text = str(ctrl.min_number())
        if ctrl.rogaining_points:
            ET.SubElement(c_el, _ns("Score")).text = str(ctrl.rogaining_points)

    # Courses
    for course in event.courses.values():
        if course.removed:
            continue
        co_el = ET.SubElement(rat_ctrl, _ns("Course"))
        ET.SubElement(co_el, _ns("Name")).text = course.name
        if course.length:
            ET.SubElement(co_el, _ns("Length")).text = str(course.length)
        if course.climb:
            ET.SubElement(co_el, _ns("Climb")).text = str(course.climb)
        for cid in course.control_ids:
            ctrl = event.controls.get(cid)
            if ctrl is None:
                continue
            cc_el = ET.SubElement(co_el, _ns("CourseControl"))
            cc_el.set("type", "Control")
            ET.SubElement(cc_el, _ns("Control")).text = str(ctrl.min_number())

    return ET.tostring(root, encoding="UTF-8", xml_declaration=True)


def export_entry_list(event: Event) -> bytes:
    """Export EntryList XML."""
    root = _make_root("EntryList")
    ev_el = ET.SubElement(root, _ns("Event"))
    ET.SubElement(ev_el, _ns("Name")).text = event.name

    for runner in event.runners.values():
        if runner.removed:
            continue
        pe = ET.SubElement(root, _ns("PersonEntry"))
        p_el = ET.SubElement(pe, _ns("Person"))
        if runner.sex != Sex.Unknown:
            p_el.set("sex", runner.sex.value)
        name_el = ET.SubElement(p_el, _ns("Name"))
        ET.SubElement(name_el, _ns("Family")).text = runner.last_name
        ET.SubElement(name_el, _ns("Given")).text  = runner.first_name

        club = event.clubs.get(runner.club_id)
        if club:
            org_el = ET.SubElement(pe, _ns("Organisation"))
            ET.SubElement(org_el, _ns("Name")).text = club.name

        cls = event.classes.get(runner.class_id)
        if cls:
            cls_el = ET.SubElement(pe, _ns("Class"))
            ET.SubElement(cls_el, _ns("Name")).text = cls.name

        if runner.card_number:
            c_el = ET.SubElement(pe, _ns("ControlCard"))
            c_el.text = str(runner.card_number)

    return ET.tostring(root, encoding="UTF-8", xml_declaration=True)


def export_result_list(event: Event) -> bytes:
    """Export ResultList XML."""
    root = _make_root("ResultList")
    ev_el = ET.SubElement(root, _ns("Event"))
    ET.SubElement(ev_el, _ns("Name")).text = event.name

    # Group runners by class
    by_class: dict[int, list] = {}
    for r in event.runners.values():
        if not r.removed:
            by_class.setdefault(r.class_id, []).append(r)

    for class_id, runners in by_class.items():
        cls = event.classes.get(class_id)
        if cls is None:
            continue
        cr_el = ET.SubElement(root, _ns("ClassResult"))
        cls_el = ET.SubElement(cr_el, _ns("Class"))
        ET.SubElement(cls_el, _ns("Name")).text = cls.name

        runners.sort(key=lambda r: r.result_sort_key())

        for runner in runners:
            pr_el = ET.SubElement(cr_el, _ns("PersonResult"))
            p_el  = ET.SubElement(pr_el, _ns("Person"))
            name_el = ET.SubElement(p_el, _ns("Name"))
            ET.SubElement(name_el, _ns("Family")).text = runner.last_name
            ET.SubElement(name_el, _ns("Given")).text  = runner.first_name

            club = event.clubs.get(runner.club_id)
            if club:
                org_el = ET.SubElement(pr_el, _ns("Organisation"))
                ET.SubElement(org_el, _ns("Name")).text = club.name

            res_el = ET.SubElement(pr_el, _ns("Result"))
            ET.SubElement(res_el, _ns("BibNumber")).text = runner.bib or str(runner.start_no)
            if runner.start_time not in (NO_TIME, 0):
                ET.SubElement(res_el, _ns("StartTime")).text = format_time(runner.start_time)
            if runner.finish_time not in (NO_TIME, 0):
                ET.SubElement(res_el, _ns("FinishTime")).text = format_time(runner.finish_time)
            rt = runner.get_running_time()
            if rt not in (NO_TIME, 0):
                ET.SubElement(res_el, _ns("Time")).text = str(rt // TIME_UNITS_PER_SECOND)
            ET.SubElement(res_el, _ns("ResultStatus")).text = _status_to_iof(runner.status)
            if runner.place:
                ET.SubElement(res_el, _ns("Position")).text = str(runner.place)

    return ET.tostring(root, encoding="UTF-8", xml_declaration=True)


def _status_to_iof(status: RunnerStatus) -> str:
    _map = {
        RunnerStatus.OK:              "OK",
        RunnerStatus.DNS:             "DidNotStart",
        RunnerStatus.DNF:             "DidNotFinish",
        RunnerStatus.MP:              "MissingPunch",
        RunnerStatus.DQ:              "Disqualified",
        RunnerStatus.MAX:             "OverTime",
        RunnerStatus.OutOfCompetition:"NotCompeting",
        RunnerStatus.NoTiming:        "NotCompeting",
    }
    return _map.get(status, "Inactive")


# ===========================================================================
# IMPORT
# ===========================================================================

def import_entry_list(xml_bytes: bytes, event: Event) -> int:
    """Import runners from an IOF 3.0 EntryList.

    Returns the number of runners imported.
    """
    root = ET.fromstring(xml_bytes)
    count = 0
    for pe in root.iter(_ns("PersonEntry")):
        name_el  = pe.find(f".//{_ns('Name')}")
        family   = _text(name_el, "Family") if name_el is not None else ""
        given    = _text(name_el, "Given")  if name_el is not None else ""

        org_el   = pe.find(_ns("Organisation"))
        club_name= _text(org_el, "Name") if org_el is not None else ""

        cls_el   = pe.find(_ns("Class"))
        cls_name = _text(cls_el, "Name") if cls_el is not None else ""

        card_el  = pe.find(_ns("ControlCard"))
        card_no  = int(card_el.text) if card_el is not None and card_el.text else 0

        club_id = event.add_club(club_name).id if club_name else 0
        cls_obj = event.get_class_by_name(cls_name)
        class_id = cls_obj.id if cls_obj else (
            event.add_class(cls_name).id if cls_name else 0
        )

        runner = event.add_runner(given, family, club_id, class_id)
        runner.card_number = card_no
        count += 1

    return count


def import_course_data(xml_bytes: bytes, event: Event) -> dict:
    """Import courses and controls from an IOF 3.0 CourseData document.

    Returns a dict with 'controls' and 'courses' counts.
    """
    root = ET.fromstring(xml_bytes)
    n_controls = 0
    n_courses  = 0

    # Parse controls (build a code→Control map for later reference)
    code_to_ctrl: dict[str, Control] = {}
    for rc_el in root.iter(_ns("RaceCourseData")):
        for c_el in rc_el.findall(_ns("Control")):
            code_str = _text(c_el, "Id")
            if not code_str:
                continue
            try:
                code = int(code_str)
            except ValueError:
                continue
            ctrl = event.add_control(numbers=[code])
            code_to_ctrl[code_str] = ctrl
            n_controls += 1

        for co_el in rc_el.findall(_ns("Course")):
            name   = _text(co_el, "Name")
            length = int(_text(co_el, "Length", "0") or 0)
            climb  = int(_text(co_el, "Climb",  "0") or 0)

            course = event.add_course(name)
            course.length = length
            course.climb  = climb

            for cc_el in co_el.findall(_ns("CourseControl")):
                code_str = _text(cc_el, "Control")
                ctrl = code_to_ctrl.get(code_str)
                if ctrl:
                    course.control_ids.append(ctrl.id)

            n_courses += 1

    return {"controls": n_controls, "courses": n_courses}


# ---------------------------------------------------------------------------
# Convenience wrappers used by main_window.py
# ---------------------------------------------------------------------------

def import_iof30(path: str, event: "Event") -> None:
    """Import an IOF XML 3.0 file (entry list or course data) into *event*."""
    with open(path, "rb") as fh:
        data = fh.read()
    root = ET.fromstring(data)
    tag  = root.tag.split("}")[-1] if "}" in root.tag else root.tag
    if tag == "EntryList":
        import_entry_list(data, event)
    elif tag in ("CourseData", "RaceCourseData"):
        import_course_data(data, event)
    elif tag == "ResultList":
        logger.warning("ResultList import not yet implemented")
    else:
        logger.warning("Unknown IOF root element: %s", tag)


def export_result_list_to_file(event: "Event", path: str) -> None:
    """Write IOF 3.0 ResultList XML to *path*."""
    xml_bytes = export_result_list(event)
    with open(path, "wb") as fh:
        fh.write(xml_bytes)
