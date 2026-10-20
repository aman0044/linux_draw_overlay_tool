import math
import struct

import pytest

from drawapp import config
from drawapp.geometry import arrow_head, dist_point_segment, normalize, pressure_width
from drawapp.hotkeys import parse_hotkey
from drawapp.model.document import Document
from drawapp.model.items import PEN, Arrow, Stroke
from drawapp.pen import mode as m
from drawapp.pen.decode import MOTION, PRESS, RELEASE, decode_device_event
from drawapp.tools import ARROW, ERASER, NOTE, REGION, ToolController


# -- geometry ----------------------------------------------------------
def test_normalize_clamps():
    assert normalize(1023.5, 0, 2047) == pytest.approx(0.5)
    assert normalize(-5, 0, 10) == 0
    assert normalize(50, 0, 10) == 1
    assert normalize(1, 3, 3) == 0


def test_pressure_width_has_floor():
    assert pressure_width(10, 0) == pytest.approx(3.5)
    assert pressure_width(10, 1) == pytest.approx(10)


def test_dist_point_segment():
    assert dist_point_segment(5, 3, 0, 0, 10, 0) == pytest.approx(3)
    assert dist_point_segment(-4, 3, 0, 0, 10, 0) == pytest.approx(5)
    assert dist_point_segment(3, 4, 0, 0, 0, 0) == pytest.approx(5)


def test_arrow_head_is_symmetric_behind_tip():
    left, right = arrow_head(0, 0, 100, 0, 20)
    assert left[0] == pytest.approx(right[0])
    assert left[0] < 100
    assert left[1] == pytest.approx(-right[1])
    assert math.hypot(100 - left[0], left[1]) == pytest.approx(20)


# -- event decoding ----------------------------------------------------
def _event_bytes(detail, x, y, valuators, buttons_len=1):
    """Build an XI2 device event payload (after the 10-byte GE header)."""
    mask = 0
    for number in valuators:
        mask |= 1 << number
    data = bytearray(70)
    struct.pack_into("=HII", data, 0, 22, 1000, detail)
    struct.pack_into("=ii", data, 22, int(x * 65536), int(y * 65536))
    struct.pack_into("=HH", data, 38, buttons_len, 1)
    data += bytes(4 * buttons_len)
    data += mask.to_bytes(4, "little")
    for number in sorted(valuators):
        value = valuators[number]
        integral = math.floor(value)
        data += struct.pack("=iI", integral, int((value - integral) * 2**32))
    return bytes(data)


def test_decode_motion_with_pressure():
    ev = decode_device_event(6, _event_bytes(0, 640.5, 360.25, {0: 5.0, 2: 1023.5}))
    assert ev.kind == MOTION and ev.button == 0
    assert (ev.x, ev.y) == (640.5, 360.25)
    assert ev.valuators == {0: 5.0, 2: 1023.5}


def test_decode_buttons_and_negative_valuator():
    press = decode_device_event(4, _event_bytes(1, 10, 20, {3: -12.5}))
    assert press.kind == PRESS and press.button == 1
    assert press.valuators[3] == pytest.approx(-12.5)
    assert decode_device_event(5, _event_bytes(2, 0, 0, {})).kind == RELEASE


def test_decode_ignores_other_events_and_short_data():
    assert decode_device_event(11, _event_bytes(0, 0, 0, {})) is None
    assert decode_device_event(6, b"\x00" * 10) is None


# -- pen mode ----------------------------------------------------------
def test_tip_draws_by_default():
    pm = m.PenMode()
    assert pm.handle(MOTION, 0, 5, 5, 0, False) == [(m.HOVER, 5, 5)]
    assert pm.handle(PRESS, 1, 5, 5, 0.4, False) == [(m.DRAW_BEGIN, 5, 5, 0.4)]
    assert pm.handle(MOTION, 0, 6, 6, 0.5, False) == [(m.DRAW_MOVE, 6, 6, 0.5)]
    assert pm.handle(RELEASE, 1, 7, 7, 0, False) == [(m.DRAW_END, 7, 7)]
    assert not pm.tip_down


def test_hold_button_makes_pen_a_mouse():
    pm = m.PenMode()
    assert pm.handle(PRESS, 2, 1, 1, 0, False) == [(m.FORWARD_MOTION, 1, 1)]
    assert pm.handle(MOTION, 0, 2, 2, 0, False) == [(m.FORWARD_MOTION, 2, 2)]
    assert pm.handle(PRESS, 1, 2, 2, 0.5, False) == [(m.FORWARD_MOTION, 2, 2), (m.FORWARD_BUTTON, True)]
    # Letting go of the hold button mid-drag must not drop the drag.
    assert pm.handle(RELEASE, 2, 3, 3, 0.5, False) == []
    assert pm.handle(MOTION, 0, 4, 4, 0.5, False) == [(m.FORWARD_MOTION, 4, 4)]
    assert pm.handle(RELEASE, 1, 4, 4, 0, False) == [(m.FORWARD_MOTION, 4, 4), (m.FORWARD_BUTTON, False)]
    assert pm.handle(MOTION, 0, 5, 5, 0, False) == [(m.HOVER, 5, 5)]


def test_stroke_keeps_drawing_when_hold_pressed_or_ui_crossed():
    pm = m.PenMode()
    pm.handle(PRESS, 1, 0, 0, 0.5, False)
    assert pm.handle(PRESS, 2, 1, 1, 0.5, False) == []
    assert pm.handle(MOTION, 0, 2, 2, 0.5, True) == [(m.DRAW_MOVE, 2, 2, 0.5)]


def test_over_own_ui_forwards():
    pm = m.PenMode()
    assert pm.handle(MOTION, 0, 1, 1, 0, True) == [(m.FORWARD_MOTION, 1, 1)]
    assert pm.handle(PRESS, 1, 1, 1, 0.3, True)[-1] == (m.FORWARD_BUTTON, True)
    # A drag that started on the toolbar keeps forwarding outside it.
    assert pm.handle(MOTION, 0, 500, 500, 0.3, False) == [(m.FORWARD_MOTION, 500, 500)]


def test_latch_button_toggles_mouse_mode():
    pm = m.PenMode()
    assert pm.handle(PRESS, 3, 0, 0, 0, False) == [(m.LATCH_CHANGED, True)]
    assert pm.handle(MOTION, 0, 1, 1, 0, False) == [(m.FORWARD_MOTION, 1, 1)]
    assert pm.handle(PRESS, 3, 0, 0, 0, False) == [(m.LATCH_CHANGED, False)]
    assert pm.handle(MOTION, 0, 1, 1, 0, False) == [(m.HOVER, 1, 1)]


def test_custom_buttons_and_reset():
    pm = m.PenMode(m.Buttons(tip=1, hold=3, latch=2))
    pm.handle(PRESS, 3, 0, 0, 0, False)
    pm.handle(PRESS, 1, 0, 0, 0.5, False)
    assert pm.reset() == [(m.FORWARD_BUTTON, False)]
    assert pm.handle(MOTION, 0, 1, 1, 0, False) == [(m.HOVER, 1, 1)]
    pm.handle(PRESS, 1, 0, 0, 0.5, False)
    assert pm.reset()[0][0] == m.DRAW_END


# -- document ----------------------------------------------------------
def _stroke(x):
    return Stroke(PEN, "#f00", 4, [(x, 0, 1), (x, 100, 1)])


def test_add_undo_redo():
    doc = Document()
    changes = []
    doc.listeners.append(lambda: changes.append(1))
    a, b = _stroke(0), _stroke(50)
    doc.add(a)
    doc.add(b)
    doc.undo()
    assert doc.items == [a] and doc.can_redo()
    doc.redo()
    assert doc.items == [a, b]
    doc.undo()
    doc.add(_stroke(99))
    assert not doc.can_redo()
    assert len(changes) == 6


def test_clear_is_one_undo_step_and_keeps_order():
    doc = Document()
    items = [_stroke(i * 50) for i in range(4)]
    for it in items:
        doc.add(it)
    doc.clear()
    assert doc.items == []
    doc.undo()
    assert all(a is b for a, b in zip(doc.items, items)) and len(doc.items) == 4


def test_grouped_erase_undoes_in_one_step_in_original_order():
    doc = Document()
    a, b, c, d = (_stroke(i * 50) for i in range(4))
    for it in (a, b, c, d):
        doc.add(it)
    doc.begin_group()
    doc.erase([c])
    doc.erase([a, d])
    doc.erase([])
    doc.end_group()
    assert doc.items == [b]
    doc.undo()
    assert [id(i) for i in doc.items] == [id(i) for i in (a, b, c, d)]
    doc.redo()
    assert doc.items == [b]


def test_empty_group_adds_no_undo_step():
    doc = Document()
    doc.begin_group()
    doc.end_group()
    assert not doc.can_undo()


def test_hit_testing():
    doc = Document()
    s = _stroke(10)
    arrow = Arrow(100, 100, 200, 100, "#f00", 4)
    dot = Stroke(PEN, "#f00", 4, [(300, 300, 1)])
    for it in (s, arrow, dot):
        doc.add(it)
    assert doc.items_at(14, 50, 5) == [s]
    assert doc.items_at(150, 104, 5) == [arrow]
    assert doc.items_at(303, 300, 5) == [dot]
    assert doc.items_at(500, 500, 5) == []


# -- tools -------------------------------------------------------------
class FakeView:
    def __init__(self):
        self.active = None
        self.region = None
        self.hovered = None
        self.dirtied = []

    def set_active(self, item):
        self.active = item

    def set_region(self, rect):
        self.region = rect

    def set_hover(self, *args):
        self.hovered = args

    def dirty(self, bounds):
        self.dirtied.append(bounds)


def _controller():
    doc, view = Document(), FakeView()
    return ToolController(config.Config(), doc, view), doc, view


def test_pen_stroke_is_committed_on_end():
    tc, doc, view = _controller()
    tc.begin(0, 0, 0.5)
    assert view.active is not None and doc.items == []
    tc.move(10, 10, 0.6)
    tc.move(10, 10, 0.6)  # duplicate point dropped
    tc.end()
    assert view.active is None
    assert len(doc.items) == 1 and len(doc.items[0].points) == 2
    assert doc.items[0].color == tc.colors[PEN]


def test_highlighter_is_wider_and_remembers_its_own_color():
    tc, doc, _ = _controller()
    tc.set_tool("highlighter")
    tc.set_color("#00ff00")
    assert tc.width == tc.cfg.sizes[tc.size_index] * tc.cfg.highlighter_scale
    tc.set_tool(PEN)
    assert tc.color != "#00ff00"


def test_short_arrow_is_dropped_long_arrow_kept():
    tc, doc, _ = _controller()
    tc.set_tool(ARROW)
    tc.begin(0, 0, 1)
    tc.move(2, 2, 1)
    tc.end()
    assert doc.items == []
    tc.begin(0, 0, 1)
    tc.move(80, 0, 1)
    tc.end()
    assert isinstance(doc.items[0], Arrow) and doc.items[0].x2 == 80


def test_eraser_drag_is_one_undo_step():
    tc, doc, _ = _controller()
    doc.add(_stroke(10))
    doc.add(_stroke(60))
    tc.set_tool(ERASER)
    tc.begin(10, 50, 1)
    tc.move(60, 50, 1)
    tc.end()
    assert doc.items == []
    doc.undo()
    assert len(doc.items) == 2


def test_note_and_region_are_one_shot():
    tc, _, view = _controller()
    notes, regions = [], []
    tc.on_note = lambda x, y: notes.append((x, y))
    tc.on_region = regions.append
    tc.set_tool(ARROW)
    tc.set_tool(NOTE)
    tc.begin(30, 40, 1)
    tc.end()
    assert notes == [(30, 40)] and tc.tool == ARROW
    tc.set_tool(REGION)
    tc.begin(100, 100, 1)
    tc.move(20, 40, 1)
    assert view.region == (20, 40, 100, 100)
    tc.end()
    assert regions == [(20, 40, 100, 100)] and view.region is None and tc.tool == ARROW
    tc.set_tool(REGION)
    tc.begin(5, 5, 1)
    tc.end()
    assert len(regions) == 1  # a tap is not a region


def test_choosing_a_color_with_eraser_switches_to_pen():
    tc, _, _ = _controller()
    tc.set_tool(ERASER)
    tc.set_color("#123456")
    assert tc.tool == PEN and tc.color == "#123456"


# -- config and hotkeys ------------------------------------------------
def test_config_parse_keeps_good_values_and_ignores_bad():
    cfg = config.parse({
        "hold_button": 3,
        "eraser_radius": 20,
        "colors": [],
        "sizes": [2, 5],
        "screenshot_dir": 7,
        "nonsense": 1,
        "hotkeys": {"undo": "Super+Z", "bogus": "X"},
    })
    assert cfg.hold_button == 3
    assert cfg.eraser_radius == 20.0
    assert cfg.colors == config.DEFAULT_COLORS
    assert cfg.sizes == [2.0, 5.0]
    assert cfg.screenshot_dir == "~/Pictures/Screenshots"
    assert cfg.hotkeys["undo"] == "Super+Z" and "bogus" not in cfg.hotkeys
    assert cfg.hotkeys["redo"] == "Ctrl+Alt+Y"


def test_config_load_missing_or_broken_file(tmp_path):
    assert config.load(tmp_path / "none.toml") == config.Config()
    bad = tmp_path / "bad.toml"
    bad.write_text("this is = not [ toml")
    assert config.load(bad) == config.Config()


def test_parse_hotkey():
    from Xlib import X, XK
    assert parse_hotkey("Ctrl+Alt+Z") == (X.ControlMask | X.Mod1Mask, XK.string_to_keysym("z"))
    assert parse_hotkey("super + F5")[0] == X.Mod4Mask
    for bad in ("", "Hyper+Z", "Ctrl+NotAKey"):
        with pytest.raises(ValueError):
            parse_hotkey(bad)
