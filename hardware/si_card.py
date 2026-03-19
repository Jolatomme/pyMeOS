"""
hardware/si_card.py
===================
SportIdent protocol constants, CRC helpers, and card-block parsers.
Mirrors SportIdent.h / SportIdent.cpp.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List
from models.card import SICard
from models.punch import SIPunch
from utils.time_utils import TIME_UNITS_PER_SECOND

# Protocol bytes
STX    = 0x02
ETX    = 0x03
ACK    = 0x06
DLE    = 0x10
WAKEUP = 0xFF
NAK    = 0x15

# SI commands
CMD_GET_SI5     = 0xB1
CMD_GET_SI6     = 0xE1
CMD_GET_SI8     = 0xEF
CMD_SET_MS      = 0x70
CMD_GET_SYS_VAL = 0x83
CMD_SEND_PUNCH  = 0xD3

HALF_DAY_UNITS = 12 * 3600 * TIME_UNITS_PER_SECOND
FULL_DAY_UNITS = 24 * 3600 * TIME_UNITS_PER_SECOND


def calc_crc(data: bytes) -> int:
    """CRC-CCITT (init=0xFFFF, poly=0x8005) as used by SportIdent."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x8005) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def check_crc(buf: bytes) -> bool:
    if len(buf) < 2:
        return False
    expected = calc_crc(buf[:-2])
    got = (buf[-2] << 8) | buf[-1]
    return expected == got


def _time_from_bytes(hi: int, lo: int) -> int:
    raw_sec = (hi << 8) | lo
    return raw_sec * TIME_UNITS_PER_SECOND


def parse_si5(data: bytes) -> SICard:
    card = SICard()
    card.card_number  = ((data[4] & 0x01) << 16) | (data[6] << 8) | data[7]
    card.start_punch  = SIPunch(code=1, time=_time_from_bytes(data[19], data[20]))
    card.finish_punch = SIPunch(code=2, time=_time_from_bytes(data[21], data[22]))
    card.check_punch  = SIPunch(code=3, time=_time_from_bytes(data[8],  data[9]))
    n_punches = data[23] & 0x1F
    for i in range(min(n_punches, 36)):
        base = 32 + i * 3
        card.punches.append(SIPunch(code=data[base],
                                    time=_time_from_bytes(data[base+1], data[base+2])))
    return card


def parse_si6(data: bytes) -> SICard:
    card = SICard()
    card.card_number  = ((data[11] & 0x0F) << 16) | (data[12] << 8) | data[13]
    card.start_punch  = SIPunch(code=1, time=_time_from_bytes(data[26], data[27]))
    card.finish_punch = SIPunch(code=2, time=_time_from_bytes(data[22], data[23]))
    card.check_punch  = SIPunch(code=3, time=_time_from_bytes(data[30], data[31]))
    n_punches = data[21]
    for i in range(min(n_punches, 64)):
        base = 34 + i * 4
        code = (data[base] << 8) | data[base + 1]
        card.punches.append(SIPunch(code=code, time=_time_from_bytes(data[base+2], data[base+3])))
    return card


def parse_si8_9(data: bytes) -> SICard:
    card = SICard()
    card.card_number  = ((data[25] & 0x0F) << 16) | (data[26] << 8) | data[27]
    card.start_punch  = SIPunch(code=1, time=_time_from_bytes(data[14], data[15]))
    card.finish_punch = SIPunch(code=2, time=_time_from_bytes(data[18], data[19]))
    card.check_punch  = SIPunch(code=3, time=_time_from_bytes(data[10], data[11]))
    n_punches = data[22]
    for i in range(min(n_punches, 128)):
        base = 56 + i * 4
        if base + 3 >= len(data):
            break
        code = (data[base] << 8) | data[base + 1]
        card.punches.append(SIPunch(code=code, time=_time_from_bytes(data[base+2], data[base+3])))
    return card


# ---------------------------------------------------------------------------
# Aliases used by si_reader.py (for backward compat)
# ---------------------------------------------------------------------------

def get_card5_data(data: bytes) -> SICard:
    return parse_si5(data)

def get_card6_data(data: bytes) -> SICard:
    return parse_si6(data)

def get_card9_data(data: bytes) -> SICard:
    return parse_si8_9(data)


def set_crc(frame: bytearray) -> None:
    """Write the CRC of frame[:-2] into the last 2 bytes of frame."""
    crc = calc_crc(bytes(frame[:-2]))
    frame[-2] = (crc >> 8) & 0xFF
    frame[-1] = crc & 0xFF
