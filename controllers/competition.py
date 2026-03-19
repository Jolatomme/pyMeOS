"""
controllers/competition.py
==========================
High-level competition controller (TabCompetition + oEvent business logic).

Responsibilities:
  • Create / open / save competitions (XML or DB)
  • Process incoming SI card reads
  • Trigger result computation
  • Provide a clean API for views
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Callable, List

try:
    from PySide6.QtCore import QObject, Signal
    _QT = True
except ImportError:
    _QT = False

    class _FakeSignal:
        """No-op signal for non-Qt environments."""
        def emit(self, *a, **kw): pass
        def connect(self, *a, **kw): pass
        def disconnect(self, *a, **kw): pass

    class QObject:  # type: ignore
        def __init__(self, parent=None): pass

    def Signal(*types):  # type: ignore
        """Return a descriptor that gives each instance its own _FakeSignal."""
        attr = f"_sig_{id(types)}"
        class _Desc:
            def __set_name__(self, owner, name):
                self._name = "_fake_" + name
            def __get__(self, obj, objtype=None):
                if obj is None:
                    return self
                if not hasattr(obj, self._name):
                    object.__setattr__(obj, self._name, _FakeSignal())
                return getattr(obj, self._name)
        return _Desc()

from models import Event, Runner, Card, RunnerStatus
from models.card import SICard, Card as DomainCard
from hardware.si_reader import SICardReadEvent, SIPunchEvent
from controllers.result import evaluate_card, compute_class_results
from persistence import EventRepository, init_db
from utils.time_utils import NO_TIME

logger = logging.getLogger(__name__)


class CompetitionController(QObject):
    """
    Central controller bridging the model (Event) with the views.

    Signals
    -------
    runner_updated(runner_id)   – a runner's result changed
    card_processed(card_id)     – a card was read and matched
    event_loaded()              – a new event was loaded
    event_saved()               – the event was saved
    status_message(str)         – informational message for the status bar
    """

    runner_updated  = Signal(int)
    card_processed  = Signal(int)
    event_loaded    = Signal()
    event_saved     = Signal()
    status_message  = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._event: Event = Event()
        self._repo: EventRepository = EventRepository()

    # ------------------------------------------------------------------
    # Event access
    # ------------------------------------------------------------------

    @property
    def event(self) -> Event:
        return self._event

    # ------------------------------------------------------------------
    # Create / Open / Save
    # ------------------------------------------------------------------

    def new_event(self, name: str = "New Competition") -> None:
        """Create a blank competition."""
        from datetime import date
        self._event = Event()
        self._event.name = name
        self._event.date = date.today().isoformat()
        self.event_loaded.emit()
        self.status_message.emit(f"New competition '{name}' created.")

    def open_event_from_db(self, event_id: int, db_url: str = "sqlite:///pymeos.db") -> bool:
        """Load a competition from the database."""
        init_db(db_url)
        ev = self._repo.load_event(event_id)
        if ev is None:
            self.status_message.emit(f"Event {event_id} not found in database.")
            return False
        self._event = ev
        self.event_loaded.emit()
        self.status_message.emit(f"Loaded '{ev.name}' from database.")
        return True

    def save_event_to_db(self, db_url: str = "sqlite:///pymeos.db") -> bool:
        """Persist the current competition to the database."""
        try:
            init_db(db_url)
            eid = self._repo.save_event(self._event)
            self.event_saved.emit()
            self.status_message.emit(f"Competition saved (id={eid}).")
            return True
        except Exception as exc:
            logger.exception("save_event_to_db failed")
            self.status_message.emit(f"Save failed: {exc}")
            return False

    def open_event_from_xml(self, path: str) -> bool:
        """Load a competition from a MeOS native XML file."""
        try:
            from formats.xml_parser import load_event_xml
            ev = load_event_xml(path)
            if ev is None:
                return False
            self._event = ev
            self.event_loaded.emit()
            self.status_message.emit(f"Loaded '{ev.name}' from {path}.")
            return True
        except Exception as exc:
            logger.exception("open_event_from_xml failed")
            self.status_message.emit(f"Load failed: {exc}")
            return False

    def save_event_to_xml(self, path: str) -> bool:
        """Save the competition to a MeOS native XML file."""
        try:
            from formats.xml_parser import save_event_xml
            save_event_xml(self._event, path)
            self.event_saved.emit()
            self.status_message.emit(f"Competition saved to {path}.")
            return True
        except Exception as exc:
            logger.exception("save_event_to_xml failed")
            self.status_message.emit(f"Save failed: {exc}")
            return False

    # ------------------------------------------------------------------
    # SI card handling
    # ------------------------------------------------------------------

    def on_card_read(self, ev: SICardReadEvent) -> None:
        """Slot: called when the SI reader emits a new card."""
        si_card = ev.card
        logger.info("Card read: %d from %s", si_card.card_number, ev.port)

        # 1. Find the domain card or create a new one
        domain_card = DomainCard.from_si_card(si_card, self._event)
        domain_card.id = self._event._next_id("card")
        self._event.cards[domain_card.id] = domain_card

        # 2. Find the runner with this card number
        runner = self._event.get_runner_by_card(si_card.card_number)
        if runner is None:
            logger.warning("No runner found for card %d", si_card.card_number)
            # Card stored but unmatched
            self._event._notify("cards_changed", domain_card)
            self.card_processed.emit(domain_card.id)
            self.status_message.emit(
                f"Card {si_card.card_number} read – no matching runner."
            )
            return

        # 3. Assign card to runner
        runner.card_id     = domain_card.id
        domain_card.owner_runner_id = runner.id

        # 4. Run evaluation
        evaluate_card(runner, domain_card, self._event)

        # 5. Re-sort class
        compute_class_results(self._event, runner.class_id)

        # 6. Emit change notifications
        self._event._notify("runners_changed", runner)
        self._event._notify("cards_changed", domain_card)
        self.runner_updated.emit(runner.id)
        self.card_processed.emit(domain_card.id)
        self.status_message.emit(
            f"Card {si_card.card_number} → {runner.name}: {runner.t_status.name}"
        )

    def on_punch_received(self, ev: SIPunchEvent) -> None:
        """Slot: called when a pass-through punch arrives."""
        logger.debug("Punch: card=%d code=%d time=%d",
                     ev.card_number, ev.code, ev.time)
        # Store as free punch (partial implementation)
        self._event._notify("punch_received", ev)

    # ------------------------------------------------------------------
    # Manual operations
    # ------------------------------------------------------------------

    def set_runner_status(self, runner_id: int, status: RunnerStatus) -> bool:
        runner = self._event.runners.get(runner_id)
        if runner is None:
            return False
        runner.set_status(status)
        compute_class_results(self._event, runner.class_id)
        self._event._notify("runners_changed", runner)
        self.runner_updated.emit(runner_id)
        return True

    def set_runner_start_time(self, runner_id: int, time_str: str) -> bool:
        runner = self._event.runners.get(runner_id)
        if runner is None:
            return False
        runner.set_start_time_from_string(time_str)
        compute_class_results(self._event, runner.class_id)
        self.runner_updated.emit(runner_id)
        return True

    def set_runner_finish_time(self, runner_id: int, time_str: str) -> bool:
        runner = self._event.runners.get(runner_id)
        if runner is None:
            return False
        runner.set_finish_time_from_string(time_str)
        compute_class_results(self._event, runner.class_id)
        self.runner_updated.emit(runner_id)
        return True

    def add_runner(self, first_name: str, last_name: str,
                   club_name: str = "", class_name: str = "",
                   card_number: int = 0) -> Optional[Runner]:
        ev = self._event
        club_id  = ev.add_club(club_name).id   if club_name  else 0
        class_id = ev.get_class_by_name(class_name)
        class_id = class_id.id if class_id else (ev.add_class(class_name).id if class_name else 0)

        runner = ev.add_runner(first_name, last_name, club_id, class_id)
        runner.card_number = card_number
        self.status_message.emit(f"Runner {runner.name} added.")
        return runner

    def delete_runner(self, runner_id: int) -> bool:
        ok = self._event.remove_runner(runner_id)
        if ok:
            self.status_message.emit(f"Runner {runner_id} removed.")
        return ok

    # ------------------------------------------------------------------
    # Draw (start time assignment)
    # ------------------------------------------------------------------

    def draw_starts(self, class_id: int, first_start: int,
                    interval: int, scramble: bool = True) -> None:
        """Assign start times to runners in *class_id*."""
        from controllers.draw import assign_start_times
        assign_start_times(self._event, class_id, first_start,
                           interval, scramble)
        self.status_message.emit("Start list drawn.")
        self._event._notify("runners_changed", None)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_statistics(self) -> dict:
        return self._event.statistics()

    def recalculate_all_results(self) -> None:
        """Recalculate results for every class in the active event."""
        from controllers.result import compute_all_results
        compute_all_results(self._event)
        self.status_message.emit("All results recalculated.")
