"""
models/card.py
==============
A physical SI card read-out (oCard / SICard equivalent).

An SICard holds raw hardware data; a Card is the domain-model version
that lives in the event's card list.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

from .base import Base
from .punch import Punch, SIPunch
from .enums import SpecialPunchType
from utils.time_utils import NO_TIME, format_time

if TYPE_CHECKING:
    from .runner import Runner
    from .event import Event


# ---------------------------------------------------------------------------
# Raw hardware card (mirrors C++ SICard struct)
# ---------------------------------------------------------------------------

MAX_SI_PUNCHES = 192


@dataclass
class SICard:
    """Raw SportIdent card data as received from the hardware reader."""

    card_number: int = 0
    start_punch: SIPunch = field(default_factory=SIPunch)
    finish_punch: SIPunch = field(default_factory=SIPunch)
    check_punch: SIPunch = field(default_factory=SIPunch)
    punches: List[SIPunch] = field(default_factory=list)
    first_name: str = ""
    last_name: str = ""
    club: str = ""
    mili_volt: int = 0       # SIAC battery voltage
    read_out_time: str = ""
    punch_only: bool = False
    runner_id: int = 0       # 0 = normal card; >0 = manual time input
    relative_finish_time: int = 0
    status_ok: bool = False
    status_dnf: bool = False
    is_debug_card: bool = False

    def empty(self) -> bool:
        return self.card_number == 0

    def is_manual_input(self) -> bool:
        return self.runner_id != 0

    def get_first_time(self) -> int:
        """Return earliest recorded time (start, check, or first intermediate)."""
        times = []
        if self.start_punch.time > 0:
            times.append(self.start_punch.time)
        if self.check_punch.time > 0:
            times.append(self.check_punch.time)
        for p in self.punches:
            if p.time > 0:
                times.append(p.time)
                break
        return min(times) if times else NO_TIME

    def analyse_hour12_time(self, zero_time: int) -> None:
        self.start_punch.analyse_hour12_time(zero_time)
        self.finish_punch.analyse_hour12_time(zero_time)
        self.check_punch.analyse_hour12_time(zero_time)
        for p in self.punches:
            p.analyse_hour12_time(zero_time)


# ---------------------------------------------------------------------------
# Domain card (lives in oEvent.Cards)
# ---------------------------------------------------------------------------

@dataclass
class Card(Base):
    """Processed SI card that belongs to an event."""

    card_number: int = 0
    punches: List[Punch] = field(default_factory=list)
    mili_volt: int = 0
    battery_date: int = 0
    # Unique read-out identifier (to distinguish re-reads of the same card)
    read_id: int = 0
    # The runner this card is assigned to (id or 0)
    owner_runner_id: int = 0

    def __post_init__(self) -> None:
        super().__init__()

    # ------------------------------------------------------------------
    # Punch access helpers
    # ------------------------------------------------------------------

    def get_start_time(self) -> int:
        """Return the start punch time, or NO_TIME."""
        for p in self.punches:
            if p.is_start():
                return p.time
        return NO_TIME

    def get_finish_time(self) -> int:
        for p in self.punches:
            if p.is_finish():
                return p.time
        return NO_TIME

    def get_check_time(self) -> int:
        for p in self.punches:
            if p.is_check():
                return p.time
        return NO_TIME

    def get_punch_by_code(self, code: int) -> Optional[Punch]:
        """Return the first punch with the given code, or None."""
        for p in self.punches:
            if p.type_code == code:
                return p
        return None

    # ------------------------------------------------------------------
    # Populate from raw SICard
    # ------------------------------------------------------------------

    @classmethod
    def from_si_card(cls, si: SICard, event: Optional["Event"] = None) -> "Card":
        """Convert a raw SICard hardware read into a domain Card."""
        card = cls()
        card._event = event
        card.card_number = si.card_number
        card.mili_volt   = si.mili_volt
        card.read_id     = id(si)  # use object id as unique read id

        punches: List[Punch] = []
        idx = 0

        if si.check_punch.time > 0:
            p = Punch()
            p.type_code  = SpecialPunchType.Check
            p.time_raw   = si.check_punch.time
            p.card_index = idx
            punches.append(p)
            idx += 1

        if si.start_punch.time > 0:
            p = Punch()
            p.type_code  = SpecialPunchType.Start
            p.time_raw   = si.start_punch.time
            p.card_index = idx
            punches.append(p)
            idx += 1

        for raw_punch in si.punches:
            if raw_punch.code == 0 and raw_punch.time == 0:
                continue
            p = Punch()
            p.type_code  = raw_punch.code
            p.time_raw   = raw_punch.time
            p.card_index = idx
            punches.append(p)
            idx += 1

        if si.finish_punch.time > 0:
            p = Punch()
            p.type_code  = SpecialPunchType.Finish
            p.time_raw   = si.finish_punch.time
            p.card_index = idx
            punches.append(p)

        card.punches = punches
        return card

    # ------------------------------------------------------------------
    # Voltage helper
    # ------------------------------------------------------------------

    def get_voltage_string(self) -> str:
        if self.mili_volt <= 0:
            return ""
        v = self.mili_volt / 1000.0
        return f"{v:.2f} V"

    # ------------------------------------------------------------------
    # Base interface
    # ------------------------------------------------------------------

    def get_info(self) -> str:
        return f"Card {self.card_number} ({len(self.punches)} punches)"

    def remove(self) -> None:
        self._removed = True
        self.mark_changed()

    def can_remove(self) -> bool:
        return self.owner_runner_id == 0
