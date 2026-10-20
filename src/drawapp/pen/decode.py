"""Decode XInput2 device events from raw bytes.

python-xlib's own struct for these events stops before the valuators, which
is where pressure lives, so we read the wire format directly. `data` is the
event payload after the 10-byte generic event header.
"""
import struct
from dataclasses import dataclass

MOTION = "motion"
PRESS = "press"
RELEASE = "release"

# XInput2 event types
_XI_BUTTON_PRESS = 4
_XI_BUTTON_RELEASE = 5
_XI_MOTION = 6
_KINDS = {_XI_BUTTON_PRESS: PRESS, _XI_BUTTON_RELEASE: RELEASE, _XI_MOTION: MOTION}

_ROOT_XY_OFFSET = 22
_LENGTHS_OFFSET = 38
_MASKS_OFFSET = 70


@dataclass(frozen=True)
class RawPenEvent:
    kind: str  # MOTION, PRESS or RELEASE
    button: int  # button number for PRESS/RELEASE, 0 for MOTION
    x: float  # root window pixels
    y: float
    valuators: dict  # valuator number -> value; only those that changed


def decode_device_event(evtype: int, data: bytes) -> RawPenEvent | None:
    kind = _KINDS.get(evtype)
    if kind is None or len(data) < _MASKS_OFFSET:
        return None
    (detail,) = struct.unpack_from("=I", data, 6)
    root_x, root_y = struct.unpack_from("=ii", data, _ROOT_XY_OFFSET)
    buttons_len, valuators_len = struct.unpack_from("=HH", data, _LENGTHS_OFFSET)
    offset = _MASKS_OFFSET + buttons_len * 4
    mask = int.from_bytes(data[offset:offset + valuators_len * 4], "little")
    offset += valuators_len * 4
    valuators = {}
    for number in range(valuators_len * 32):
        if mask >> number & 1:
            integral, frac = struct.unpack_from("=iI", data, offset)
            valuators[number] = integral + frac / 2**32
            offset += 8
    return RawPenEvent(
        kind=kind,
        button=0 if kind == MOTION else detail,
        x=root_x / 65536,
        y=root_y / 65536,
        valuators=valuators,
    )
