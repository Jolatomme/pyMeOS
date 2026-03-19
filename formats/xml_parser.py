"""
io/xml_parser.py
================
MeOS native XML file format (.mexml) – load and save.

The format is a simple tagged XML with one element per domain object.
"""
from __future__ import annotations

import json
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
from utils.time_utils import NO_TIME


def save_event_xml(event: Event, path: str) -> None:
    """Serialize *event* to a MeOS native XML file."""
    root = ET.Element("MeOS")
    root.set("version", "5.0")

    ev = ET.SubElement(root, "Event")
    ev.set("name",   event.name)
    ev.set("date",   event.date)
    ev.set("zero",   str(event.zero_time))
    ev.set("org",    event.organiser)
    ev.set("country",event.country)

    # Controls
    ctrls = ET.SubElement(root, "Controls")
    for c in event.controls.values():
        if c.removed: continue
        el = ET.SubElement(ctrls, "Control")
        el.set("id",     str(c.id))
        el.set("name",   c.name)
        el.set("status", str(c.status.value))
        el.set("numbers",",".join(str(n) for n in c.numbers))
        el.set("tadj",   str(c.time_adjustment))

    # Courses
    for c in event.courses.values():
        if c.removed: continue
        el = ET.SubElement(root, "Course")
        el.set("id",  str(c.id))
        el.set("name",c.name)
        el.set("len", str(c.length))
        el.set("climb",str(c.climb))
        el.set("cids",json.dumps(c.control_ids))

    # Classes
    for c in event.classes.values():
        if c.removed: continue
        el = ET.SubElement(root, "Class")
        el.set("id",   str(c.id))
        el.set("name", c.name)
        el.set("crsid",str(c.course_id))
        el.set("type", c.class_type.value)
        el.set("st",   str(c.start_type.value))
        el.set("fs",   str(c.first_start))
        el.set("si",   str(c.start_interval))
        el.set("fee",  str(c.entry_fee))

    # Clubs
    for c in event.clubs.values():
        if c.removed: continue
        el = ET.SubElement(root, "Club")
        el.set("id",   str(c.id))
        el.set("name", c.name)
        el.set("short",c.short_name)
        el.set("cntry",c.country)

    # Runners
    for r in event.runners.values():
        if r.removed: continue
        el = ET.SubElement(root, "Runner")
        el.set("id",    str(r.id))
        el.set("fn",    r.first_name)
        el.set("ln",    r.last_name)
        el.set("club",  str(r.club_id))
        el.set("cls",   str(r.class_id))
        el.set("card",  str(r.card_number))
        el.set("st",    str(r.start_time))
        el.set("ft",    str(r.finish_time))
        el.set("status",str(r.status.value))
        el.set("bib",   r.bib)
        el.set("sno",   str(r.start_no))

    # Teams
    for t in event.teams.values():
        if t.removed: continue
        el = ET.SubElement(root, "Team")
        el.set("id",   str(t.id))
        el.set("name", t.name)
        el.set("club", str(t.club_id))
        el.set("cls",  str(t.class_id))
        el.set("rids", json.dumps(t.runner_ids))
        el.set("bib",  t.bib)

    tree = ET.ElementTree(root)
    Path(path).write_bytes(
        ET.tostring(root, encoding="utf-8", xml_declaration=True)
    )


def load_event_xml(path: str) -> Optional[Event]:
    """Deserialize a MeOS native XML file into an Event."""
    try:
        root = ET.parse(path).getroot()
    except Exception:
        return None

    event = Event()

    ev = root.find("Event")
    if ev is not None:
        event.name      = ev.get("name", "")
        event.date      = ev.get("date", "")
        event.zero_time = int(ev.get("zero", "0"))
        event.organiser = ev.get("org",  "")
        event.country   = ev.get("country", "")

    def _int(el, attr, default=0):
        try:
            return int(el.get(attr, default))
        except (ValueError, TypeError):
            return default

    # Controls
    for el in root.iter("Control"):
        c = Control()
        c.id   = _int(el, "id")
        c.name = el.get("name", "")
        try:
            c.status = ControlStatus(_int(el, "status"))
        except ValueError:
            c.status = ControlStatus.OK
        nums = el.get("numbers", "")
        c.numbers = [int(x) for x in nums.split(",") if x.strip()]
        c.time_adjustment = _int(el, "tadj")
        c.event = event
        event.controls[c.id] = c

    # Courses
    for el in root.iter("Course"):
        c = Course()
        c.id     = _int(el, "id")
        c.name   = el.get("name", "")
        c.length = _int(el, "len")
        c.climb  = _int(el, "climb")
        try:
            c.control_ids = json.loads(el.get("cids", "[]"))
        except Exception:
            c.control_ids = []
        c.event = event
        event.courses[c.id] = c

    # Classes
    for el in root.iter("Class"):
        c = Class()
        c.id      = _int(el, "id")
        c.name    = el.get("name", "")
        c.course_id = _int(el, "crsid")
        try:
            c.class_type = ClassType(el.get("type", "individual"))
        except ValueError:
            c.class_type = ClassType.Individual
        try:
            c.start_type = StartType(_int(el, "st", 2))
        except ValueError:
            c.start_type = StartType.Drawn
        c.first_start    = _int(el, "fs")
        c.start_interval = _int(el, "si")
        c.entry_fee      = _int(el, "fee")
        c.event = event
        event.classes[c.id] = c

    # Clubs
    for el in root.iter("Club"):
        c = Club()
        c.id         = _int(el, "id")
        c.name       = el.get("name", "")
        c.short_name = el.get("short", "")
        c.country    = el.get("cntry", "")
        c.event = event
        event.clubs[c.id] = c

    # Runners
    for el in root.iter("Runner"):
        r = Runner()
        r.id          = _int(el, "id")
        r.first_name  = el.get("fn", "")
        r.last_name   = el.get("ln", "")
        r.club_id     = _int(el, "club")
        r.class_id    = _int(el, "cls")
        r.card_number = _int(el, "card")
        r.start_time  = _int(el, "st", NO_TIME)
        r.finish_time = _int(el, "ft", NO_TIME)
        try:
            r.status = RunnerStatus(_int(el, "status"))
        except ValueError:
            r.status = RunnerStatus.Unknown
        r.bib      = el.get("bib", "")
        r.start_no = _int(el, "sno")
        r.event = event
        event.runners[r.id] = r

    # Teams
    for el in root.iter("Team"):
        t = Team()
        t.id      = _int(el, "id")
        t.name    = el.get("name", "")
        t.club_id = _int(el, "club")
        t.class_id= _int(el, "cls")
        t.bib     = el.get("bib", "")
        try:
            t.runner_ids = json.loads(el.get("rids", "[]"))
        except Exception:
            t.runner_ids = []
        t.event = event
        event.teams[t.id] = t

    event._recalc_free_ids()
    return event
