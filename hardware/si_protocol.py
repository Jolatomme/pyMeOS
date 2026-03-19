"""
hardware/si_protocol.py
========================
SportIdent serial protocol constants, CRC calculation, and low-level frame
parsing.  Pure Python – no C extension required.

References:
  • SportIdent Communication Protocol documentation
  • MeOS SportIdent.cpp (CRC algorithm, frame structure)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import struct

# ---------------------------------------------------------------------------
# Protocol byte constants
# ---------------------------------------------------------------------------
STX    = 0x02
ETX    = 0x03
ACK    = 0x06
DLE    = 0x10
WAKEUP = 0xFF
NAK    = 0x15

# Commands
CMD_GET_SYSTEM_VALUE = 0x83
CMD_GET_BACKUP       = 0x81
CMD_READ_CARD5       = 0xB1
CMD_READ_CARD6       = 0xE1
CMD_READ_CARD9       = 0xEF   # SI9/p/SIAC
CMD_TRANSMIT_RECORD  = 0xD3   # Extended punch (auto-send)
CMD_OLD_PUNCH        = 0x53   # Old-mode punch

# Station modes
MODE_CONTROL = 2
MODE_START   = 3
MODE_FINISH  = 4
MODE_READOUT = 5
MODE_CHECK   = 10
MODE_CLEAR   = 7

# SI Card series
SERIES_SICARD5   = 1
SERIES_SICARD6   = 6
SERIES_SICARD9   = 9
SERIES_SICARD10  = 10
SERIES_SICARD11  = 11

# Default baud rates
BAUD_38400 = 38400
BAUD_4800  = 4800


# ---------------------------------------------------------------------------
# CRC (direct port of MeOS SportIdent.cpp CalcCRC)
# ---------------------------------------------------------------------------

def calc_crc(data: bytes | bytearray) -> int:
    """Calculate the 16-bit SportIdent CRC.

    >>> calc_crc(bytes([0x83, 0x02, 0x70, 0x06]))
    ...   # exact value depends on input
    """
    if len(data) < 2:
        return 0

    data = bytearray(data)
    crc: int = (data[0] << 8) | data[1]

    if len(data) == 2:
        return crc

    n_words = len(data) >> 1
    idx = 2

    for k in range(n_words - 1, 0, -1):
        if k > 1:
            value = (data[idx] << 8) | data[idx + 1]
            idx += 2
        else:
            # If the number of bytes is odd, pad with 0
            value = (data[idx] << 8) if (len(data) & 1) else 0

        for _ in range(16):
            if crc & 0x8000:
                crc = ((crc << 1) & 0xFFFF)
                if value & 0x8000:
                    crc += 1
                crc ^= 0x8005
            else:
                crc = ((crc << 1) & 0xFFFF)
                if value & 0x8000:
                    crc += 1
            value = (value << 1) & 0xFFFF

    return crc & 0xFFFF


def set_crc(frame: bytearray) -> None:
    """Append the 2-byte CRC to *frame* (modifies in place).
    frame[0] must be the first payload byte (length at frame[1]).
    """
    length = frame[1]
    crc = calc_crc(bytes(frame[:length + 2]))
    if len(frame) < length + 4:
        frame.extend([0, 0])
    frame[length + 2] = (crc >> 8) & 0xFF
    frame[length + 3] = crc & 0xFF


def check_crc(data: bytes | bytearray, max_len: int = 256) -> bool:
    """Return True if the CRC embedded in *data* is valid."""
    if len(data) < 4:
        return False
    length = min(int(data[1]), max_len)
    if len(data) < length + 4:
        return False
    crc = calc_crc(bytes(data[:length + 2]))
    return data[length + 2] == ((crc >> 8) & 0xFF) and \
           data[length + 3] == (crc & 0xFF)


# ---------------------------------------------------------------------------
# Card number decode helpers
# ---------------------------------------------------------------------------

def get_card_number(series: int, short_no: int) -> int:
    """Reconstruct full card number from series byte and short number.

    Mirrors the logic in MeOS MonitorSI():
      series 1–4 → shortNo + 100000 * series
      series ≥ 5 → combined
    """
    if 1 <= series <= 4:
        return short_no + 100_000 * series
    # Extended card number (SI9+)
    return short_no


def get_ext_card_number(data: bytes, offset: int = 0) -> int:
    """Extract a 3-byte extended card number from a buffer."""
    # bytes: [series][hi][lo]
    s = data[offset]
    hi = data[offset + 1]
    lo = data[offset + 2]
    if 1 <= s <= 4:
        return ((hi << 8) | lo) + 100_000 * s
    return (s << 16) | (hi << 8) | lo


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

TIME_UNITS_PER_SECOND = 10
_HALF_DAY = 12 * 3600 * TIME_UNITS_PER_SECOND


def decode_si_time(high_byte: int, low_bytes: int, sub_second: int = 0,
                   use_subsecond: bool = False) -> int:
    """Convert raw SI time bytes to internal time units.

    Parameters
    ----------
    high_byte   : top time byte (bit 0 = AM/PM flag for 12h mode)
    low_bytes   : time in seconds (2 bytes, big-endian)
    sub_second  : 1/256 s fraction (SIAC extended format)
    """
    t = low_bytes * TIME_UNITS_PER_SECOND
    if high_byte & 0x01:
        t += _HALF_DAY
    if use_subsecond and sub_second:
        tenth = ((100 * sub_second) // 256 + 4) // 10
        t += tenth
    return t


# ---------------------------------------------------------------------------
# Frame builders
# ---------------------------------------------------------------------------

def build_wakeup_frame() -> bytes:
    """Build the initial WAKEUP + STX + identify frame."""
    frame = bytearray([
        WAKEUP, STX, STX,
        0xF0,   # cmd
        0x01,   # len
        0x4D,   # data
        0x00, 0x00,  # CRC placeholder
        ETX
    ])
    set_crc(frame[2:])
    return bytes(frame)


def build_get_system_request(address: int = 0x70, count: int = 6) -> bytes:
    """Build a 'get system value' request frame."""
    frame = bytearray([
        STX,
        CMD_GET_SYSTEM_VALUE,
        0x02,            # length
        address & 0xFF,
        count & 0xFF,
        0x00, 0x00,      # CRC
        ETX,
    ])
    set_crc(frame[1:])
    return bytes(frame)


# ---------------------------------------------------------------------------
# Station data
# ---------------------------------------------------------------------------

@dataclass
class StationData:
    """Mirrors C++ SI_StationData."""
    station_number: int = 0
    station_mode: int = 0
    extended: bool = False
    hand_shake: bool = False
    auto_send: bool = False
    radio_channel: int = 0


def parse_station_data(buf: bytes | bytearray, offset: int = 0) -> Optional[StationData]:
    """Parse station configuration bytes from a response frame.

    Returns None if the CRC is invalid.
    """
    if not check_crc(buf[offset + 1:], 256):
        return None
    sd = StationData()
    addr = 0x70
    sd.station_number = ((buf[offset + 3] << 8) | buf[offset + 4]) & 511
    pr = buf[offset + 6 + 4 + addr] if offset + 6 + 4 + addr < len(buf) else 0
    mo = buf[offset + 6 + 1 + addr] if offset + 6 + 1 + addr < len(buf) else 0
    sd.extended   = bool(pr & 0x01)
    sd.hand_shake = bool(pr & 0x04)
    sd.auto_send  = bool(pr & 0x02)
    sd.station_mode = mo & 0x0F
    return sd
