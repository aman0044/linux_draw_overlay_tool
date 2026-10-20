"""Wire the pen, the tools and the windows together."""
import logging

from PySide6.QtCore import QObject, QPoint, QTimer
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from drawapp import screenshot
from drawapp.hotkeys import Hotkeys
from drawapp.model.document import Document
from drawapp.pen import mode as pen_mode
from drawapp.pen.grabber import PenGrabber
from drawapp.pen.passthrough import Passthrough
from drawapp.tools import ToolController
from drawapp.ui.overlay import Overlay
from drawapp.ui.sticky import StickyNote
from drawapp.ui.toolbar import Toolbar
from drawapp.ui.tray import Tray
from drawapp.x11 import XConnection

log = logging.getLogger(__name__)

_UI_MARGIN = 6  # pen within this many pixels of our windows counts as over them
_SCREENSHOT_SETTLE_MS = 150  # let the compositor repaint without the toolbar


class App(QObject):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.document = Document()
        self.overlay = Overlay(cfg, self.document)
        self.toolbar = Toolbar(cfg)
        self.tools = ToolController(cfg, self.document, self.overlay)
        self.notes = []

        self.x = XConnection(self)
        self.passthrough = Passthrough(self.x)
        self.mode = pen_mode.PenMode(
            pen_mode.Buttons(cfg.tip_button, cfg.hold_button, cfg.latch_button)
        )
        self.grabber = PenGrabber(self.x, cfg.device_pattern, self)
        self.grabber.on_event = self._on_pen
        self.grabber.on_lost = self._on_pen_lost

        self.tools.on_tool_changed = self._refresh_toolbar
        self.tools.on_note = self.add_note
        self.tools.on_region = self.take_screenshot
        self.document.listeners.append(self._refresh_toolbar)
        self.overlay.on_shown = self._raise_toolbar

        tb = self.toolbar
        tb.tool_selected.connect(self.tools.set_tool)
        tb.color_selected.connect(self.tools.set_color)
        tb.size_selected.connect(self.tools.set_size)
        tb.undo.connect(self.document.undo)
        tb.redo.connect(self.document.redo)
        tb.clear.connect(self.document.clear)
        tb.screenshot.connect(self.take_screenshot)
        tb.ink_toggled.connect(self.set_ink_visible)
        tb.mouse_mode_toggled.connect(self.set_mouse_mode)
        self._refresh_toolbar()

        keys = cfg.hotkeys
        self.hotkeys = Hotkeys(self.x)
        self.hotkeys.register(keys.get("undo", ""), self.document.undo)
        self.hotkeys.register(keys.get("redo", ""), self.document.redo)
        self.hotkeys.register(keys.get("clear", ""), self.document.clear)
        self.hotkeys.register(keys.get("screenshot", ""), self.take_screenshot)
        self.hotkeys.register(
            keys.get("toggle_ink", ""), lambda: self.set_ink_visible(not self.overlay.ink_visible)
        )
        self.hotkeys.register(
            keys.get("toggle_mouse_mode", ""), lambda: self.set_mouse_mode(not self.mode.latched)
        )

        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = Tray(self)
            self.tray.show()

        self._dpr = self.overlay.devicePixelRatioF() or 1.0
        self.grabber.start()

    # -- pen events ----------------------------------------------------
    def _on_pen(self, kind, button, x, y, pressure):
        # X reports device pixels; Qt windows use logical pixels.
        lx, ly = x / self._dpr, y / self._dpr
        actions = self.mode.handle(kind, button, lx, ly, pressure, self._over_ui(lx, ly))
        self._run(actions, x, y)

    def _on_pen_lost(self):
        self._run(self.mode.reset(), 0, 0)
        self.overlay.clear_hover()

    def _run(self, actions, x, y):
        for action in actions:
            name = action[0]
            if name == pen_mode.HOVER:
                self.tools.hover(action[1], action[2])
            elif name == pen_mode.DRAW_BEGIN:
                self.show_toolbar()
                self.overlay.clear_hover()
                self.tools.begin(action[1], action[2], action[3])
            elif name == pen_mode.DRAW_MOVE:
                self.tools.move(action[1], action[2], action[3])
            elif name == pen_mode.DRAW_END:
                self.tools.end()
            elif name == pen_mode.FORWARD_MOTION:
                self.overlay.clear_hover()
                self.passthrough.motion(x, y)
            elif name == pen_mode.FORWARD_BUTTON:
                self.passthrough.button(action[1])
            elif name == pen_mode.LATCH_CHANGED:
                self._mouse_mode_changed(action[1])

    def _over_ui(self, x, y) -> bool:
        point = QPoint(int(x), int(y))
        margin = _UI_MARGIN
        for window in (self.toolbar, *self.notes):
            if window.isVisible() and window.frameGeometry().adjusted(
                -margin, -margin, margin, margin
            ).contains(point):
                return True
        return False

    # -- commands ------------------------------------------------------
    def show_toolbar(self):
        if not self.toolbar.isVisible():
            self.toolbar.show()
        self._raise_toolbar()

    def set_mouse_mode(self, on: bool):
        self.mode.set_latched(on)
        self._mouse_mode_changed(on)

    def set_ink_visible(self, visible: bool):
        self.overlay.set_ink_visible(visible)
        self.toolbar.set_ink_visible(visible)
        for note in self.notes:
            note.setVisible(visible)

    def set_paused(self, paused: bool):
        self.grabber.set_paused(paused)
        if not paused and not self.grabber.active:
            self.overlay.show_toast("No pen found")

    def add_note(self, x, y):
        note = StickyNote(int(x), int(y))
        note.closed.connect(self._note_closed)
        self.notes.append(note)
        note.show()
        note.activateWindow()
        note.editor.setFocus()

    def close_notes(self):
        for note in list(self.notes):
            note.close()

    def take_screenshot(self, rect=None):
        toolbar_was_visible = self.toolbar.isVisible()
        self.toolbar.hide()
        self.overlay.hide_transients()

        def grab():
            try:
                path = screenshot.save(screenshot.capture(rect), self.cfg.screenshot_dir)
                message = f"Saved {path.name} and copied to clipboard"
            except OSError as exc:
                log.error("screenshot failed: %s", exc)
                message = f"Screenshot failed: {exc}"
            if toolbar_was_visible:
                self.show_toolbar()
            self.overlay.show_toast(message, 2500)

        QTimer.singleShot(_SCREENSHOT_SETTLE_MS, grab)

    def quit(self):
        self.shutdown()
        QApplication.quit()

    def shutdown(self):
        """Give the pen back to the system."""
        self.passthrough.release_all()
        self.grabber.stop()

    # -- internals -----------------------------------------------------
    def _mouse_mode_changed(self, on: bool):
        self.toolbar.set_mouse_mode(on)
        self.overlay.clear_hover()
        self.overlay.show_toast("Mouse mode on: pen acts as a mouse" if on else "Draw mode")

    def _note_closed(self, note):
        if note in self.notes:
            self.notes.remove(note)
        note.deleteLater()

    def _refresh_toolbar(self):
        self.toolbar.show_state(
            self.tools.tool,
            self.tools.color,
            self.tools.size_index,
            self.document.can_undo(),
            self.document.can_redo(),
        )

    def _raise_toolbar(self):
        if self.toolbar.isVisible():
            self.toolbar.raise_()
