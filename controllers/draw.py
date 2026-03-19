"""
controllers/draw.py
===================
Start time drawing / assignment (oEventDraw equivalent).

Supports:
  • Sequential draw (fixed interval, optional scramble)
  • Club-separation algorithm
  • Pursuit start (based on previous results)
"""
from __future__ import annotations

import random
from typing import List, Optional

from models import Event, Runner, Class, StartType
from utils.time_utils import NO_TIME


def assign_start_times(
    event: Event,
    class_id: int,
    first_start: int,
    interval: int,
    scramble: bool = True,
    separate_clubs: bool = False,
    n_before_interval: int = 1,
    seed: Optional[int] = None,
) -> List[Runner]:
    """
    Assign start times to all runners in *class_id*.

    Parameters
    ----------
    event           : the event model
    class_id        : which class to draw
    first_start     : start time of slot 0 (internal units)
    interval        : time between slots (internal units)
    scramble        : if True, randomise runner order
    separate_clubs  : if True, try to avoid same-club runners in adjacent slots
    n_before_interval : runners per start slot
    seed            : RNG seed for reproducibility
    """
    runners = [r for r in event.runners.values()
               if r.class_id == class_id and not r.removed
               and r.status not in (RunnerStatus_DNS := (
                   __import__("models").RunnerStatus.DNS,
                   __import__("models").RunnerStatus.CANCEL,
               ))]

    if not runners:
        return []

    rng = random.Random(seed)

    if scramble:
        if separate_clubs:
            runners = _scramble_separate_clubs(runners, rng)
        else:
            rng.shuffle(runners)

    for idx, runner in enumerate(runners):
        slot = idx // max(1, n_before_interval)
        runner.start_time = first_start + slot * interval
        runner.start_no   = idx + 1
        runner.mark_changed()

    return runners


def assign_pursuit_starts(
    event: Event,
    class_id: int,
    nominal_first: int,
    winner_time: Optional[int] = None,
) -> List[Runner]:
    """
    Assign pursuit start times based on time-behind-leader.

    The leader starts at *nominal_first*; every other runner starts
    leader_time + their_time_behind.
    """
    from models import RunnerStatus
    from controllers.result import compute_class_results

    runners = compute_class_results(event, class_id)
    if not runners:
        return []

    # Find the winner's time
    leader_time = None
    for r in runners:
        if r.status == RunnerStatus.OK and r.get_running_time() != NO_TIME:
            leader_time = r.get_running_time()
            break

    if leader_time is None:
        return runners

    for runner in runners:
        if runner.status != RunnerStatus.OK:
            continue
        rt = runner.get_running_time()
        if rt == NO_TIME:
            continue
        gap = rt - leader_time
        runner.start_time = nominal_first + max(0, gap)
        runner.mark_changed()

    return runners


def _scramble_separate_clubs(runners: List[Runner], rng: random.Random) -> List[Runner]:
    """Shuffle runners, attempting to keep same-club runners apart."""
    rng.shuffle(runners)
    n = len(runners)

    # Simple two-pass improvement: swap if same club adjacent
    improved = True
    passes = 0
    while improved and passes < 10:
        improved = False
        passes += 1
        for i in range(n - 1):
            if (runners[i].club_id != 0 and
                    runners[i].club_id == runners[i + 1].club_id):
                # Try to find a swap candidate further ahead
                for j in range(i + 2, min(i + 10, n)):
                    if runners[j].club_id != runners[i].club_id:
                        runners[i + 1], runners[j] = runners[j], runners[i + 1]
                        improved = True
                        break
    return runners


def draw_lots(
    event: Event,
    class_id: int,
) -> List[Runner]:
    """Assign bib numbers in random order (no time assignment)."""
    from models import RunnerStatus
    runners = [r for r in event.runners.values()
               if r.class_id == class_id and not r.removed]
    random.shuffle(runners)
    for idx, r in enumerate(runners, start=1):
        r.start_no = idx
        r.mark_changed()
    return runners
