"""
models/enums.py
===============
All shared enumerations translated from the C++ headers.
"""
from __future__ import annotations
from enum import IntEnum, Enum


class RunnerStatus(IntEnum):
    """Corresponds to RunnerStatus in oRunner.h"""
    Unknown         = 0
    OK              = 1
    NoTiming        = 2
    MP              = 3   # Mispunch
    DNF             = 4   # Did Not Finish
    DQ              = 5   # Disqualified
    MAX             = 6   # Overtime
    DNS             = 20  # Did Not Start
    CANCEL          = 21  # Cancelled entry
    OutOfCompetition= 15
    NotCompeting    = 99

    @classmethod
    def from_code(cls, code: str) -> "RunnerStatus":
        _map = {
            "OK":  cls.OK, "MP": cls.MP, "DNF": cls.DNF,
            "DQ":  cls.DQ, "DNS": cls.DNS, "OOC": cls.OutOfCompetition,
            "MAX": cls.MAX, "NT": cls.NoTiming, "NP": cls.NotCompeting,
            "CC":  cls.CANCEL,
        }
        return _map.get(code.upper(), cls.Unknown)

    def to_code(self) -> str:
        _map = {
            RunnerStatus.OK:              "OK",
            RunnerStatus.MP:              "MP",
            RunnerStatus.DNF:             "DNF",
            RunnerStatus.DQ:              "DQ",
            RunnerStatus.DNS:             "DNS",
            RunnerStatus.OutOfCompetition:"OOC",
            RunnerStatus.MAX:             "MAX",
            RunnerStatus.NoTiming:        "NT",
            RunnerStatus.NotCompeting:    "NP",
            RunnerStatus.CANCEL:          "CC",
            RunnerStatus.Unknown:         "?",
        }
        return _map.get(self, "?")

    def is_result_status(self) -> bool:
        return self in (RunnerStatus.OK, RunnerStatus.OutOfCompetition,
                        RunnerStatus.NoTiming)

    def has_time(self) -> bool:
        return self in (RunnerStatus.OK, RunnerStatus.OutOfCompetition)


# Order map used for sorting – lower value = better position
RUNNER_STATUS_ORDER: dict[RunnerStatus, int] = {
    RunnerStatus.OK:              0,
    RunnerStatus.NoTiming:        1,
    RunnerStatus.OutOfCompetition:2,
    RunnerStatus.MP:              10,
    RunnerStatus.DNF:             11,
    RunnerStatus.DQ:              12,
    RunnerStatus.MAX:             13,
    RunnerStatus.DNS:             20,
    RunnerStatus.CANCEL:          21,
    RunnerStatus.NotCompeting:    30,
    RunnerStatus.Unknown:         99,
}


class SortOrder(Enum):
    """Corresponds to SortOrder enum in oRunner.h"""
    ClassStartTime       = "ClassStartTime"
    ClassTeamLeg         = "ClassTeamLeg"
    ClassResult          = "ClassResult"
    ClassDefaultResult   = "ClassDefaultResult"
    ClassCourseResult    = "ClassCourseResult"
    ClassTotalResult     = "ClassTotalResult"
    ClassFinishTime      = "ClassFinishTime"
    ClassStartTimeClub   = "ClassStartTimeClub"
    ClassPoints          = "ClassPoints"
    ClassLiveResult      = "ClassLiveResult"
    SortByName           = "SortByName"
    SortByLastName       = "SortByLastName"
    SortByFinishTime     = "SortByFinishTime"
    SortByStartTime      = "SortByStartTime"
    SortByBib            = "SortByBib"
    CourseResult         = "CourseResult"
    CourseStartTime      = "CourseStartTime"
    SortByEntryTime      = "SortByEntryTime"
    ClubClassStartTime   = "ClubClassStartTime"
    Custom               = "Custom"


class ControlStatus(Enum):
    """Corresponds to oControl::ControlStatus"""
    OK              = 0
    Bad             = 1
    Multiple        = 2
    Start           = 4
    Finish          = 5
    Rogaining       = 6
    NoTiming        = 7
    Optional        = 8
    BadNoTiming     = 9
    RogainingReq    = 10
    Check           = 11

    def is_special(self) -> bool:
        return self in (ControlStatus.Start, ControlStatus.Finish,
                        ControlStatus.Check)


class StartType(IntEnum):
    """Corresponds to StartTypes in oClass.h"""
    Time    = 0
    Change  = 1
    Drawn   = 2
    Pursuit = 3


class LegType(IntEnum):
    """Corresponds to LegTypes in oClass.h"""
    Normal           = 0
    Parallel         = 1
    Extra            = 2
    Sum              = 3
    Ignore           = 4
    ParallelOptional = 5
    Group            = 6


class BibMode(IntEnum):
    """Corresponds to BibMode in oClass.h"""
    Undefined = -1
    Same      = 0
    Add       = 1
    Free      = 2
    Leg       = 3


class Sex(Enum):
    Unknown = "unknown"
    Male    = "M"
    Female  = "F"


class ClassType(Enum):
    """High-level class meta types."""
    Normal      = "normal"
    Patrol      = "patrol"
    Relay       = "relay"
    Individual  = "individual"
    Rogaining   = "rogaining"


class SpecialPunchType(IntEnum):
    """Corresponds to oPunch::SpecialPunch"""
    Unused  = 0
    Start   = 1
    Finish  = 2
    Check   = 3
    HiredCard = 11111


class SubSecond(Enum):
    """Whether to display sub-second (tenth) precision."""
    Off   = "off"
    On    = "on"
    Auto  = "auto"


class DynamicRunnerStatus(Enum):
    Inactive = "inactive"
    Active   = "active"
    Finished = "finished"


class TransferFlag(IntEnum):
    """Corresponds to oAbstractRunner::TransferFlags"""
    New             = 1
    UpdateCard      = 2
    Specified       = 4
    FeeSpecified    = 8
    UpdateClass     = 16
    UpdateName      = 32
    AutoDNS         = 64
    AddedViaAPI     = 128
    OutsideComp     = 256
    NoTiming        = 512
    NoDatabase      = 1024
    PayBeforeResult = 2048
    Unnamed         = 4096
