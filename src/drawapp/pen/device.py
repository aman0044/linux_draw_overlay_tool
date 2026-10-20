"""Find the pen among the X input devices."""
import re
from dataclasses import dataclass

from Xlib.ext import xinput

PRESSURE_LABEL = "Abs Pressure"


@dataclass(frozen=True)
class PenDevice:
    deviceid: int
    name: str
    pressure_valuator: int
    pressure_min: float
    pressure_max: float


def find_pen(display, pattern: str = "") -> PenDevice | None:
    """First pointer device with a pressure axis whose name matches pattern."""
    regex = re.compile(pattern, re.IGNORECASE) if pattern else None
    for dev in display.xinput_query_device(xinput.AllDevices).devices:
        # A device we have grabbed is reported as floating.
        if dev.use not in (xinput.SlavePointer, xinput.FloatingSlave) or not dev.enabled:
            continue
        if regex and not regex.search(dev.name):
            continue
        for cls in dev.classes:
            if cls.type != xinput.ValuatorClass or not cls.label:
                continue
            if display.get_atom_name(cls.label) == PRESSURE_LABEL:
                return PenDevice(dev.deviceid, dev.name, cls.number, cls.min, cls.max)
    return None
