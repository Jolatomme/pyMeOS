"""
Orienteering time utilities.

MeOS internally stores times in *tenth-of-seconds* (timeUnitsPerSecond = 10).
A value of 0 means "no time set".  Negative values are not used.

Public helpers
--------------
  encode(seconds: float | int) -> int      convert seconds to internal units
  decode(units: int) -> float              internal units -> seconds (float)
  format_time(units, sub_second) -> str    "H:MM:SS" or "H:MM:SS.d"
  parse_time(s: str) -> int                "H:MM:SS[.d]" -> internal units
  time_diff(a, b) -> int                   b - a  (both in internal units)
"""

from __future__ import annotations

__all__ = [
    "TIME_UNITS_PER_SECOND",
    "NO_TIME",
    "encode",
    "decode",
    "format_time",
    "parse_time",
    "time_diff",
    "format_seconds",
    "parse_time_seconds",
]

TIME_UNITS_PER_SECOND: int = 10   # 1 internal unit = 0.1 s
NO_TIME: int = 0                   # sentinel for "time not set"

_HOUR  = 3600 * TIME_UNITS_PER_SECOND
_MIN   = 60   * TIME_UNITS_PER_SECOND
_SEC   = TIME_UNITS_PER_SECOND


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

def encode(seconds: float | int) -> int:
    """Convert seconds (float or int) to internal time units.

    >>> encode(90.5)
    905
    >>> encode(0)
    0
    """
    return int(round(seconds * TIME_UNITS_PER_SECOND))


def decode(units: int) -> float:
    """Convert internal time units to seconds.

    >>> decode(905)
    90.5
    """
    return units / TIME_UNITS_PER_SECOND


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_time(units: int, sub_second: bool = False) -> str:
    """Format internal time units to a human-readable string.

    Returns "" when units == NO_TIME (0).

    >>> format_time(36010)      # 1:00:01
    '1:00:01'
    >>> format_time(36015, True)  # 1:00:01.5
    '1:00:01.5'
    """
    if units == NO_TIME:
        return ""
    if units < 0:
        sign = "-"
        units = -units
    else:
        sign = ""

    hours   = units // _HOUR
    units  %= _HOUR
    minutes = units // _MIN
    units  %= _MIN
    seconds = units // _SEC
    tenths  = units %  _SEC

    if hours:
        base = f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        base = f"{minutes}:{seconds:02d}"

    if sub_second:
        return f"{sign}{base}.{tenths}"
    return f"{sign}{base}"


def format_seconds(total_seconds: int) -> str:
    """Format an integer number of whole seconds (no tenths).

    >>> format_seconds(3661)
    '1:01:01'
    """
    return format_time(total_seconds * TIME_UNITS_PER_SECOND)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_time(s: str) -> int:
    """Parse a time string to internal units.

    Accepts "[[H:]MM:]SS[.d]" where d is tenths of seconds.
    Returns NO_TIME (0) for empty or invalid input.

    >>> parse_time("1:00:01")
    36010
    >>> parse_time("1:00:01.5")
    36015
    >>> parse_time("01:30")
    900
    """
    s = s.strip()
    if not s:
        return NO_TIME
    try:
        tenths = 0
        if "." in s:
            main, frac = s.rsplit(".", 1)
            tenths = int(frac[:1])   # only first decimal digit
            s = main
        parts = s.split(":")
        if len(parts) == 3:
            h, m, sec = int(parts[0]), int(parts[1]), int(parts[2])
        elif len(parts) == 2:
            h, m, sec = 0, int(parts[0]), int(parts[1])
        else:
            h, m, sec = 0, 0, int(parts[0])
        return (h * 3600 + m * 60 + sec) * TIME_UNITS_PER_SECOND + tenths
    except (ValueError, IndexError):
        return NO_TIME


def parse_time_seconds(s: str) -> int:
    """Parse a time string to whole seconds (ignoring tenths).

    >>> parse_time_seconds("1:01:01")
    3661
    """
    units = parse_time(s)
    return units // TIME_UNITS_PER_SECOND


# ---------------------------------------------------------------------------
# Arithmetic
# ---------------------------------------------------------------------------

def time_diff(start: int, finish: int) -> int:
    """Return finish - start in internal units.

    If either value is NO_TIME, returns NO_TIME.

    >>> time_diff(100, 500)
    400
    """
    if start == NO_TIME or finish == NO_TIME:
        return NO_TIME
    return finish - start
