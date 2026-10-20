"""Take the pen away from the system cursor and deliver its events to us.

An XInput2 grab on the pen device detaches it from the mouse pointer for as
long as we hold it. If this process dies, X releases the grab by itself.
"""
import logging

from PySide6.QtCore import QObject, QTimer
from Xlib import X
from Xlib.ext import ge, xinput

from drawapp.geometry import normalize
from drawapp.pen.decode import decode_device_event
from drawapp.pen.device import find_pen

log = logging.getLogger(__name__)

_EVENT_MASK = xinput.ButtonPressMask | xinput.ButtonReleaseMask | xinput.MotionMask
_GRAB_SUCCESS = 0
_RETRY_MS = 2000

# XIHierarchyEvent flags that mean a device came or went.
_SLAVE_ADDED = 1 << 2
_SLAVE_REMOVED = 1 << 3
_DEVICE_ENABLED = 1 << 6
_DEVICE_DISABLED = 1 << 7
_PLUG_FLAGS = _SLAVE_ADDED | _SLAVE_REMOVED | _DEVICE_ENABLED | _DEVICE_DISABLED


class PenGrabber(QObject):
    def __init__(self, xconn, pattern: str = "", parent=None):
        super().__init__(parent)
        self._x = xconn
        self._pattern = pattern
        self._device = None
        self._paused = False
        self._pressure = 0.0
        # Called as on_event(kind, button, x, y, pressure) for every pen event.
        self.on_event = lambda *args: None
        # Called with no arguments when the pen is lost (unplugged or paused).
        self.on_lost = lambda: None

        d = xconn.display
        self._opcode = d.query_extension(xinput.extname).major_opcode
        d.xinput_query_version()
        # Keep pen event payloads as raw bytes; see pen/decode.py.
        for evtype in (xinput.ButtonPress, xinput.ButtonRelease, xinput.Motion):
            d.display.ge_event_data.pop((self._opcode, evtype), None)
        xconn.root.xinput_select_events([(xinput.AllDevices, xinput.HierarchyChangedMask)])
        xconn.add_handler(self._handle)

        self._retry = QTimer(self)
        self._retry.setSingleShot(True)
        self._retry.timeout.connect(self._acquire)

    @property
    def active(self) -> bool:
        return self._device is not None

    @property
    def paused(self) -> bool:
        return self._paused

    def start(self):
        self._acquire()

    def set_paused(self, paused: bool):
        self._paused = paused
        if paused:
            self._release()
        else:
            self._acquire()

    def stop(self):
        self._retry.stop()
        self._release()

    # -- internals -----------------------------------------------------
    def _acquire(self):
        if self._paused or self._device is not None:
            return
        d = self._x.display
        device = find_pen(d, self._pattern)
        if device is None:
            log.info("no pen found; waiting for one to be plugged in")
            return
        reply = self._x.root.xinput_grab_device(
            device.deviceid, X.CurrentTime, xinput.GrabModeAsync, xinput.GrabModeAsync,
            False, _EVENT_MASK,
        )
        if reply.status != _GRAB_SUCCESS:
            log.warning("could not grab %s (status %d); retrying", device.name, reply.status)
            self._retry.start(_RETRY_MS)
            return
        self._device = device
        self._pressure = 0.0
        log.info("pen captured: %s (device %d)", device.name, device.deviceid)
        self._x.pump()

    def _release(self):
        if self._device is None:
            return
        try:
            self._x.display.xinput_ungrab_device(self._device.deviceid, X.CurrentTime)
            self._x.display.sync()
        except Exception:
            log.debug("ungrab failed", exc_info=True)
        self._device = None
        self.on_lost()

    def _handle(self, event):
        if event.type != ge.GenericEventCode or event.extension != self._opcode:
            return
        if event.evtype == xinput.HierarchyChanged:
            if event.data.flags & _PLUG_FLAGS:
                # Defer: we are inside the event pump and about to make requests.
                QTimer.singleShot(0, self._rescan)
            return
        device = self._device
        if device is None or not isinstance(event.data, (bytes, bytearray)):
            return
        raw = decode_device_event(event.evtype, event.data)
        if raw is None:
            return
        if device.pressure_valuator in raw.valuators:
            self._pressure = normalize(
                raw.valuators[device.pressure_valuator], device.pressure_min, device.pressure_max
            )
        if raw.button:
            log.debug("pen %s button %d at %.0f,%.0f pressure %.2f",
                      raw.kind, raw.button, raw.x, raw.y, self._pressure)
        self.on_event(raw.kind, raw.button, raw.x, raw.y, self._pressure)

    def _rescan(self):
        current = find_pen(self._x.display, self._pattern)
        if self._device is not None and (current is None or current.deviceid != self._device.deviceid):
            log.info("pen went away")
            self._device = None
            self.on_lost()
        if self._device is None:
            self._acquire()
