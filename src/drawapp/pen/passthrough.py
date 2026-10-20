"""Make the pen behave like a mouse by replaying it onto the system cursor."""
from Xlib import X
from Xlib.ext import xtest

LEFT_BUTTON = 1


class Passthrough:
    def __init__(self, xconn):
        self._x = xconn
        self._down = False
        self._last = None

    def motion(self, x: float, y: float):
        # Pressure and tilt changes also arrive as motion. Replaying a cursor
        # move that goes nowhere would still count as activity and keep the
        # screen awake, so only send real moves.
        point = (int(round(x)), int(round(y)))
        if point == self._last:
            return
        self._last = point
        xtest.fake_input(self._x.display, X.MotionNotify, x=point[0], y=point[1])
        self._x.flush()

    def button(self, down: bool):
        if down == self._down:
            return
        self._down = down
        kind = X.ButtonPress if down else X.ButtonRelease
        xtest.fake_input(self._x.display, kind, LEFT_BUTTON)
        self._x.flush()

    def release_all(self):
        self.button(False)
