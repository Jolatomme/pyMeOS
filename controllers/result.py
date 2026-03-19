"""
controllers/result.py
=====================
Result calculation engine (GeneralResult / oEventResult equivalent).

Responsibilities:
  • evaluate_card()          – match card punches to course, set t_status / times
  • compute_class_results()  – evaluate all runners, sort, assign places
  • compute_team_results()   – sum leg times for relay teams
  • compute_all_results()    – run both for every class in the event

All time values are in internal units (1 unit = 0.1 s).
"""
from __future__ import annotations

from typing import List, Dict, Optional

from models import (
    Event, Runner, Team, Class, Course, Control, Card,
    RunnerStatus, ControlStatus, SpecialPunchType,
    RUNNER_STATUS_ORDER,
)
from models.runner import TempResult
from utils.time_utils import NO_TIME


# ---------------------------------------------------------------------------
# Card evaluation (single runner)
# ---------------------------------------------------------------------------

def evaluate_card(runner: Runner, card: Optional[Card], event: Event) -> None:
    """
    Evaluate *card* against the runner's assigned course.

    Sets runner.t_status, runner.t_start_time, and runner.finish_time in-place.
    Does *not* touch runner.status (the manually-set status).
    """
    # ── Respect manually-set terminal statuses ──────────────────────────
    if runner.status in (RunnerStatus.DNS, RunnerStatus.CANCEL,
                         RunnerStatus.DQ, RunnerStatus.NotCompeting):
        runner.t_status = runner.status
        runner.mark_changed()
        return

    if card is None:
        runner.t_status = RunnerStatus.Unknown
        runner.mark_changed()
        return

    # ── Resolve course ──────────────────────────────────────────────────
    cls = event.classes.get(runner.class_id)
    course_id = runner.course_id or (cls.course_id if cls else 0)
    course = event.courses.get(course_id) if course_id else None

    # ── Start time ──────────────────────────────────────────────────────
    start_time = _find_start_time(runner, card)
    if start_time != NO_TIME:
        runner.t_start_time = start_time

    # ── Finish time ─────────────────────────────────────────────────────
    finish_time = _find_finish_time(card)
    if finish_time != NO_TIME:
        runner.finish_time = finish_time

    # ── Control validation ──────────────────────────────────────────────
    if course and course.control_ids:
        status = _check_controls(card, course, event)
    else:
        status = RunnerStatus.OK

    # ── DNF: controls OK but no finish punch ────────────────────────────
    if status == RunnerStatus.OK and runner.finish_time == NO_TIME:
        status = RunnerStatus.DNF

    # ── Apply override from manually-set status ─────────────────────────
    if runner.status == RunnerStatus.DNF:
        status = RunnerStatus.DNF

    runner.t_status = status

    # ── Cache running time in tmp_result ───────────────────────────────
    if runner.t_status == RunnerStatus.OK and runner.t_start_time not in (NO_TIME, 0):
        rt = (runner.finish_time - runner.t_start_time
              if runner.finish_time != NO_TIME else NO_TIME)
        runner.tmp_result.running_time = rt
        runner.tmp_result.status       = runner.t_status
        runner.tmp_result.start_time   = runner.t_start_time
    else:
        runner.tmp_result.status       = runner.t_status
        runner.tmp_result.running_time = NO_TIME

    runner.mark_changed()


def _find_start_time(runner: Runner, card: Card) -> int:
    """Return effective start time: drawn start → card start punch → check punch."""
    if runner.start_time not in (NO_TIME, 0):
        return runner.start_time
    for p in card.punches:
        if p.is_start():
            return p.time
    for p in card.punches:
        if p.is_check():
            return p.time
    return NO_TIME


def _find_finish_time(card: Card) -> int:
    for p in card.punches:
        if p.is_finish():
            return p.time
    return NO_TIME


def _check_controls(card: Card, course: Course, event: Event) -> RunnerStatus:
    """
    Greedy sequential match of punched codes to required course controls.

    Returns RunnerStatus.OK if all controls were punched in order,
    RunnerStatus.MP otherwise.
    """
    # Collect punched codes (exclude start/finish/check)
    punched: List[int] = []
    for p in card.punches:
        if not (p.is_start() or p.is_finish() or p.is_check()):
            punched.append(p.type_code)

    pos = 0
    for ctrl_id in course.control_ids:
        ctrl = event.controls.get(ctrl_id)
        if ctrl is None or ctrl.is_special():
            continue
        # Find the first occurrence of any of this control's codes from pos
        found = False
        for j in range(pos, len(punched)):
            if punched[j] in ctrl.numbers:
                pos = j + 1
                found = True
                break
        if not found:
            return RunnerStatus.MP

    return RunnerStatus.OK


# ---------------------------------------------------------------------------
# Class-level result calculation
# ---------------------------------------------------------------------------

def _get_card_for_runner(runner: Runner, event: Event) -> Optional[Card]:
    """Find the best card for a runner (by card_id, then by card_number)."""
    if runner.card_id:
        card = event.cards.get(runner.card_id)
        if card and not card.removed:
            return card
    if runner.card_number:
        return next(
            (c for c in event.cards.values()
             if c.card_number == runner.card_number and not c.removed),
            None,
        )
    return None


def compute_class_results(event: Event, class_id: int) -> List[Runner]:
    """
    Evaluate all runners in *class_id*, sort by result, assign places.

    Returns the sorted runner list.
    """
    runners = [r for r in event.runners.values()
               if r.class_id == class_id and not r.removed]

    # Evaluate each runner's card
    for runner in runners:
        card = _get_card_for_runner(runner, event)
        evaluate_card(runner, card, event)

    # Sort: status order → running time → name
    runners.sort(key=lambda r: r.result_sort_key())

    # Assign places (OK runners only)
    place = 0
    prev_rt: Optional[int] = None
    tied_place = 1
    for idx, r in enumerate(runners, start=1):
        if r.t_status not in (RunnerStatus.OK,
                               RunnerStatus.OutOfCompetition,
                               RunnerStatus.NoTiming):
            r.place = 0
            r.tmp_result.place = 0
            continue

        rt = r.get_running_time()
        if rt == NO_TIME:
            r.place = 0
            r.tmp_result.place = 0
            continue

        place += 1
        if rt == prev_rt:
            r.place = tied_place   # tie
        else:
            tied_place = place
            r.place    = place
        r.tmp_result.place = r.place
        prev_rt = rt

    event._notify("results_changed", class_id)
    return runners


def compute_all_results(event: Event) -> None:
    """Evaluate all runner cards and compute results for every class."""
    for class_id in list(event.classes):
        compute_class_results(event, class_id)


# ---------------------------------------------------------------------------
# Relay team results
# ---------------------------------------------------------------------------

def compute_team_results(event: Event, class_id: int) -> List[Team]:
    """
    Compute relay team results by summing leg running times.

    Evaluates each runner's card first.
    Returns the sorted team list.
    """
    teams = [t for t in event.teams.values()
             if t.class_id == class_id and not t.removed]

    for team in teams:
        total_time = 0
        team_status = RunnerStatus.OK

        for runner_id in team.runner_ids:
            runner = event.runners.get(runner_id)
            if runner is None:
                team_status = RunnerStatus.DNS
                break

            # Evaluate runner's card
            card = _get_card_for_runner(runner, event)
            evaluate_card(runner, card, event)

            rt = runner.get_running_time()
            if rt == NO_TIME or runner.t_status != RunnerStatus.OK:
                worst = RUNNER_STATUS_ORDER.get(runner.t_status, 99)
                best  = RUNNER_STATUS_ORDER.get(team_status, 0)
                team_status = (runner.t_status
                               if worst > best else team_status)
                # DNS if unknown
                if team_status == RunnerStatus.Unknown:
                    team_status = RunnerStatus.DNS
                break
            total_time += rt

        team.t_status     = team_status
        team.t_total_time = total_time if team_status == RunnerStatus.OK else NO_TIME

    # Sort
    teams.sort(key=lambda t: t.result_sort_key())

    # Assign places
    prev_time: Optional[int] = None
    tied_place = 1
    place = 0
    for idx, t in enumerate(teams, start=1):
        if t.t_status != RunnerStatus.OK or t.t_total_time == NO_TIME:
            t.place = 0
            continue
        place += 1
        if t.t_total_time == prev_time:
            t.place = tied_place
        else:
            tied_place = place
            t.place    = place
        prev_time = t.t_total_time

    event._notify("results_changed", class_id)
    return teams
