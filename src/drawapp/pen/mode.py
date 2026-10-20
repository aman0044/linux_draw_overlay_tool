"""Decide what each pen event means: draw on the overlay, or act as a mouse.

Pure logic, no X or Qt. Feed it pen events, get back a list of actions.

The pen acts as a mouse ("forwarding") when any of these hold:
  - the hold button is pressed (momentary),
  - mouse mode is latched on (toggled by the latch button),
  - the pen is over the app's own UI (toolbar, sticky notes).
The choice is made at tip-down and kept until tip-up, so a stroke never
turns into a drag half way through, or the other way round.
"""
from dataclasses import dataclass

from drawapp.pen.decode import MOTION, PRESS, RELEASE

# Action names
HOVER = "hover"  # (HOVER, x, y)            pen near the tablet, in draw mode
DRAW_BEGIN = "draw_begin"  # (DRAW_BEGIN, x, y, pressure)
DRAW_MOVE = "draw_move"  # (DRAW_MOVE, x, y, pressure)
DRAW_END = "draw_end"  # (DRAW_END, x, y)
FORWARD_MOTION = "forward_motion"  # (FORWARD_MOTION, x, y)
FORWARD_BUTTON = "forward_button"  # (FORWARD_BUTTON, down)
LATCH_CHANGED = "latch_changed"  # (LATCH_CHANGED, latched)

_DRAW = "draw"
_FORWARD = "forward"


@dataclass(frozen=True)
class Buttons:
    tip: int = 1
    hold: int = 2
    latch: int = 3


class PenMode:
    def __init__(self, buttons: Buttons = Buttons()):
        self.buttons = buttons
        self.latched = False
        self._hold = False
        self._route = None  # _DRAW or _FORWARD while the tip is down

    @property
    def tip_down(self) -> bool:
        return self._route is not None

    def set_latched(self, latched: bool):
        self.latched = latched

    def reset(self):
        """Forget button state, e.g. after the tablet was unplugged.

        Returns the actions needed to finish whatever was in progress.
        """
        actions = []
        if self._route == _FORWARD:
            actions.append((FORWARD_BUTTON, False))
        elif self._route == _DRAW:
            actions.append((DRAW_END, 0.0, 0.0))
        self._route = None
        self._hold = False
        return actions

    def handle(self, kind, button, x, y, pressure, over_ui: bool):
        b = self.buttons
        forwarding = self.latched or self._hold or over_ui

        if kind == MOTION:
            if self._route == _DRAW:
                return [(DRAW_MOVE, x, y, pressure)]
            if self._route == _FORWARD or forwarding:
                return [(FORWARD_MOTION, x, y)]
            return [(HOVER, x, y)]

        if kind == PRESS:
            if button == b.tip:
                if self._route is not None:
                    return []
                if forwarding:
                    self._route = _FORWARD
                    return [(FORWARD_MOTION, x, y), (FORWARD_BUTTON, True)]
                self._route = _DRAW
                return [(DRAW_BEGIN, x, y, pressure)]
            if button == b.hold:
                self._hold = True
                return [] if self.tip_down else [(FORWARD_MOTION, x, y)]
            if button == b.latch:
                self.latched = not self.latched
                return [(LATCH_CHANGED, self.latched)]
            return []

        if kind == RELEASE:
            if button == b.tip:
                route, self._route = self._route, None
                if route == _DRAW:
                    return [(DRAW_END, x, y)]
                if route == _FORWARD:
                    return [(FORWARD_MOTION, x, y), (FORWARD_BUTTON, False)]
                return []
            if button == b.hold:
                self._hold = False
            return []

        return []
