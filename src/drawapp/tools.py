"""Turn pen strokes into edits, depending on the selected tool.

No Qt here. `view` is anything with set_active(item), set_region(rect),
set_hover(x, y, radius, color) and dirty(bounds); the overlay implements it.
"""
from drawapp.model.items import HIGHLIGHTER, PEN, Arrow, Stroke

ARROW = "arrow"
ERASER = "eraser"
NOTE = "note"
REGION = "region"

DRAWING_TOOLS = (PEN, HIGHLIGHTER, ARROW)
ONE_SHOT_TOOLS = (NOTE, REGION)  # switch back to the previous tool after use

_MIN_ARROW_LENGTH = 8.0
_MIN_REGION_SIDE = 8.0


def _union(a, b):
    return min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])


class ToolController:
    def __init__(self, cfg, document, view):
        self.cfg = cfg
        self.document = document
        self.view = view
        self.tool = PEN
        self.size_index = min(1, len(cfg.sizes) - 1)
        colors = cfg.colors
        self.colors = {PEN: colors[0], HIGHLIGHTER: colors[min(1, len(colors) - 1)], ARROW: colors[0]}
        self._previous = PEN
        self._item = None  # stroke or arrow being drawn
        self._start = None
        self._last = None
        self._busy = False
        self.on_tool_changed = lambda: None
        self.on_note = lambda x, y: None  # drop a sticky note here
        self.on_region = lambda rect: None  # screenshot this (x0, y0, x1, y1)

    # -- settings ------------------------------------------------------
    def set_tool(self, tool):
        if tool == self.tool:
            return
        if self.tool not in ONE_SHOT_TOOLS:
            self._previous = self.tool
        self.tool = tool
        self.on_tool_changed()

    def set_color(self, color):
        target = self.tool if self.tool in DRAWING_TOOLS else PEN
        self.colors[target] = color
        if self.tool not in DRAWING_TOOLS:
            self.set_tool(PEN)
        self.on_tool_changed()

    def set_size(self, index):
        self.size_index = max(0, min(index, len(self.cfg.sizes) - 1))
        self.on_tool_changed()

    @property
    def color(self):
        return self.colors.get(self.tool, self.colors[PEN])

    @property
    def width(self):
        size = self.cfg.sizes[self.size_index]
        return size * self.cfg.highlighter_scale if self.tool == HIGHLIGHTER else size

    def hover_radius(self):
        if self.tool == ERASER:
            return self.cfg.eraser_radius
        if self.tool in DRAWING_TOOLS:
            return max(self.width / 2, 2.0)
        return 4.0

    # -- pen gestures --------------------------------------------------
    def hover(self, x, y):
        self.view.set_hover(x, y, self.hover_radius(), self.color)

    def begin(self, x, y, pressure):
        self._busy = True
        self._start = self._last = (x, y)
        tool = self.tool
        if tool in (PEN, HIGHLIGHTER):
            self._item = Stroke(tool, self.color, self.width, [(x, y, pressure)])
            self.view.set_active(self._item)
            self.view.dirty(self._item.bounds())
        elif tool == ARROW:
            self._item = Arrow(x, y, x, y, self.color, self.width)
            self.view.set_active(self._item)
        elif tool == ERASER:
            self.document.begin_group()
            self._erase(x, y)
        if tool in (ERASER, NOTE, REGION):
            self.hover(x, y)

    def move(self, x, y, pressure):
        if not self._busy or (x, y) == self._last:
            return
        tool = self.tool
        if tool in (PEN, HIGHLIGHTER):
            pad = self._item.width
            lx, ly = self._last
            self._item.points.append((x, y, pressure))
            self.view.dirty((min(lx, x) - pad, min(ly, y) - pad, max(lx, x) + pad, max(ly, y) + pad))
        elif tool == ARROW:
            before = self._item.bounds()
            self._item.x2, self._item.y2 = x, y
            self.view.dirty(_union(before, self._item.bounds()))
        elif tool == ERASER:
            self._erase(x, y)
            self.hover(x, y)
        elif tool == REGION:
            self.view.set_region(self._region(x, y))
        self._last = (x, y)

    def end(self):
        if not self._busy:
            return
        self._busy = False
        tool, item = self.tool, self._item
        self._item = None
        self.view.set_active(None)
        if tool in (PEN, HIGHLIGHTER):
            self.document.add(item)
        elif tool == ARROW:
            dx, dy = item.x2 - item.x1, item.y2 - item.y1
            if (dx * dx + dy * dy) ** 0.5 >= _MIN_ARROW_LENGTH:
                self.document.add(item)
            else:
                self.view.dirty(item.bounds())
        elif tool == ERASER:
            self.document.end_group()
        elif tool == NOTE:
            self.set_tool(self._previous)
            self.on_note(*self._start)
        elif tool == REGION:
            rect = self._region(*self._last)
            self.view.set_region(None)
            self.set_tool(self._previous)
            if rect[2] - rect[0] >= _MIN_REGION_SIDE and rect[3] - rect[1] >= _MIN_REGION_SIDE:
                self.on_region(rect)

    # -- internals -----------------------------------------------------
    def _erase(self, x, y):
        hits = self.document.items_at(x, y, self.cfg.eraser_radius)
        if hits:
            self.document.erase(hits)

    def _region(self, x, y):
        sx, sy = self._start
        return min(sx, x), min(sy, y), max(sx, x), max(sy, y)
