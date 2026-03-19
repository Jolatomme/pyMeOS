"""
tests/conftest.py
=================
Shared pytest fixtures and configuration for all PyMeOS tests.
"""
import sys
from pathlib import Path

# Ensure project root is on path for all tests
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from models import Event, Runner, Class, Course, Control, Club, RunnerStatus
from utils.time_utils import encode, NO_TIME


# ---------------------------------------------------------------------------
# Qt application fixture (required for all QWidget / QObject tests)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qapp_args():
    return ["--platform", "offscreen"]   # headless CI-friendly


# ---------------------------------------------------------------------------
# Common model fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def empty_event():
    """A fresh Event with no data."""
    return Event()


@pytest.fixture
def event_with_runners():
    """Event with 2 classes, 1 course, 5 runners per class."""
    ev = Event()
    ev.name = "Fixture Event"

    c31 = ev.add_control("31", [31])
    c32 = ev.add_control("32", [32])

    course = ev.add_course("Medium")
    course.control_ids = [c31.id, c32.id]
    course.length = 4000

    club = ev.add_club("Test Club")

    for cls_name in ("M21", "W21"):
        cls = ev.add_class(cls_name)
        cls.course_id = course.id
        for i in range(5):
            r = ev.add_runner(
                f"{cls_name}_Runner{i}", "Test",
                club_id=club.id, class_id=cls.id
            )
            r.card_number = hash(cls_name + str(i)) % 900000 + 100000
            r.start_time  = encode(3600 + i * 120)

    return ev


@pytest.fixture
def event_with_results(event_with_runners):
    """event_with_runners + all runners have OK results."""
    ev = event_with_runners
    from models.card import Card, SICard
    from models.punch import SIPunch
    from models.enums import SpecialPunchType

    for runner in ev.runners.values():
        si = SICard()
        si.card_number   = runner.card_number
        si.start_punch   = SIPunch(code=1, time=runner.start_time)
        # Punch all controls on the course
        cls    = ev.classes.get(runner.class_id)
        course = ev.courses.get(cls.course_id) if cls else None
        if course:
            for i, cid in enumerate(course.control_ids):
                ctrl = ev.controls.get(cid)
                if ctrl and ctrl.numbers:
                    si.punches.append(SIPunch(
                        code=ctrl.numbers[0],
                        time=runner.start_time + encode(300 * (i + 1))
                    ))
        finish_t = runner.start_time + encode(3723)
        si.finish_punch = SIPunch(code=2, time=finish_t)

        card = Card.from_si_card(si, ev)
        card.id = ev._next_id("card")
        ev.cards[card.id] = card
        runner.card_id    = card.id
        runner.finish_time = finish_t
        runner.t_start_time = runner.start_time
        runner.t_status    = RunnerStatus.OK
        runner.status      = RunnerStatus.OK

    return ev


# ---------------------------------------------------------------------------
# Persistence fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def in_memory_db():
    """Initialise an in-memory SQLite database for each test."""
    from persistence import init_db
    init_db("sqlite:///:memory:")
    yield
    # teardown happens automatically (in-memory DB is dropped)
