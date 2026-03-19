from .si_card import (
    calc_crc, check_crc, set_crc,
    STX, ETX, ACK, DLE, WAKEUP, NAK,
)
from .si_reader import SICardReadEvent, SIPunchEvent, PortInfo

try:
    from .si_reader import SIReaderManager as SIReader
except Exception:
    SIReader = None  # type: ignore

__all__ = [
    "calc_crc", "check_crc", "set_crc",
    "STX", "ETX", "ACK", "DLE", "WAKEUP", "NAK",
    "SIReader", "SICardReadEvent", "SIPunchEvent", "PortInfo",
]
