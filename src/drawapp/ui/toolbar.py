"""The floating palette: tools, colours, sizes and actions."""
from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QButtonGroup, QGridLayout, QToolButton, QVBoxLayout, QWidget

from drawapp.model.items import HIGHLIGHTER, PEN
from drawapp.tools import ARROW, ERASER, NOTE, REGION
from drawapp.ui import icons

_BUTTON = 36
_STYLE = """
QToolButton { border: none; border-radius: 8px; background: transparent; }
QToolButton:hover { background: rgba(255, 255, 255, 28); }
QToolButton:pressed { background: rgba(255, 255, 255, 50); }
QToolButton:checked { background: rgba(10, 132, 255, 200); }
QToolTip { color: #f5f5f7; background: #2c2c2e; border: 1px solid #48484a; padding: 3px 6px; }
"""

_TOOLS = [
    (PEN, "pen", "Pen"),
    (HIGHLIGHTER, "highlighter", "Highlighter"),
    (ARROW, "arrow", "Arrow"),
    (ERASER, "eraser", "Eraser"),
    (NOTE, "note", "Sticky note: tap where it should go"),
    (REGION, "region", "Screenshot a region: drag over it"),
]


class _Swatch(QAbstractButton):
    """A round colour or size button."""

    def __init__(self, color: str, dot: float, tip: str):
        super().__init__()
        self.color = color
        self._dot = dot
        self.setCheckable(True)
        self.setFixedSize(_BUTTON, 30)
        self.setToolTip(tip)

    def set_color(self, color: str):
        self.color = color
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        center = self.rect().center() + QPoint(1, 1)
        if self.isChecked():
            p.setPen(QPen(QColor("#0a84ff"), 2))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(center, self._dot / 2 + 4, self._dot / 2 + 4)
        p.setPen(QPen(QColor(255, 255, 255, 90), 1))
        p.setBrush(QColor(self.color))
        p.drawEllipse(center, self._dot / 2, self._dot / 2)


class _Grip(QWidget):
    """Drag here to move the toolbar."""

    def __init__(self, window):
        super().__init__()
        self._window = window
        self._offset = None
        self.setFixedHeight(16)
        self.setCursor(Qt.SizeAllCursor)
        self.setToolTip("Drag to move")

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 90))
        w = 28
        p.drawRoundedRect((self.width() - w) // 2, 6, w, 4, 2, 2)

    def mousePressEvent(self, event):
        self._offset = event.globalPosition().toPoint() - self._window.pos()

    def mouseMoveEvent(self, event):
        if self._offset is not None:
            self._window.move(event.globalPosition().toPoint() - self._offset)

    def mouseReleaseEvent(self, _):
        self._offset = None


class Toolbar(QWidget):
    tool_selected = Signal(str)
    color_selected = Signal(str)
    size_selected = Signal(int)
    undo = Signal()
    redo = Signal()
    clear = Signal()
    screenshot = Signal()
    ink_toggled = Signal(bool)
    mouse_mode_toggled = Signal(bool)

    def __init__(self, cfg):
        super().__init__()
        # Unmanaged so it never steals keyboard focus from the app being annotated.
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet(_STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 8)
        outer.setSpacing(6)
        outer.addWidget(_Grip(self))

        self._tools = QButtonGroup(self)
        self._tool_buttons = {}
        grid = self._grid(outer)
        for i, (tool, icon_name, tip) in enumerate(_TOOLS):
            button = self._button(icon_name, tip, checkable=True)
            self._tools.addButton(button)
            self._tool_buttons[tool] = button
            button.clicked.connect(lambda _=False, t=tool: self.tool_selected.emit(t))
            grid.addWidget(button, i // 2, i % 2)

        self._colors = QButtonGroup(self)
        grid = self._grid(outer)
        for i, color in enumerate(cfg.colors):
            swatch = _Swatch(color, 18, color)
            self._colors.addButton(swatch)
            swatch.clicked.connect(lambda _=False, c=color: self.color_selected.emit(c))
            grid.addWidget(swatch, i // 2, i % 2)

        self._sizes = QButtonGroup(self)
        self._size_swatches = []
        grid = self._grid(outer)
        biggest = max(cfg.sizes)
        for i, size in enumerate(cfg.sizes):
            dot = 5 + 13 * size / biggest
            swatch = _Swatch("#ececf1", dot, f"Size {size:g}")
            self._sizes.addButton(swatch)
            self._size_swatches.append(swatch)
            swatch.clicked.connect(lambda _=False, n=i: self.size_selected.emit(n))
            grid.addWidget(swatch, i // 2, i % 2)

        grid = self._grid(outer)
        self._undo = self._button("undo", "Undo")
        self._redo = self._button("redo", "Redo")
        clear = self._button("trash", "Clear all ink")
        shot = self._button("camera", "Screenshot the whole screen")
        self._eye = self._button("eye", "Show or hide ink", checkable=True)
        self._mouse = self._button("mouse", "Mouse mode: pen acts as a mouse", checkable=True)
        close = self._button("close", "Hide this toolbar (touch the pen to bring it back)")
        self._eye.setChecked(True)
        self._undo.clicked.connect(self.undo)
        self._redo.clicked.connect(self.redo)
        clear.clicked.connect(self.clear)
        shot.clicked.connect(self.screenshot)
        self._eye.clicked.connect(self.ink_toggled)
        self._mouse.clicked.connect(self.mouse_mode_toggled)
        close.clicked.connect(self.hide)
        for i, button in enumerate((self._undo, self._redo, clear, shot, self._eye, self._mouse, close)):
            grid.addWidget(button, i // 2, i % 2)

        self.adjustSize()
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.left() + 16, screen.top() + (screen.height() - self.height()) // 2)

    # -- state shown on the toolbar -----------------------------------
    def show_state(self, tool, color, size_index, can_undo, can_redo):
        button = self._tool_buttons.get(tool)
        if button:
            button.setChecked(True)
        for swatch in self._colors.buttons():
            swatch.setChecked(swatch.color.lower() == color.lower())
        for i, swatch in enumerate(self._size_swatches):
            swatch.setChecked(i == size_index)
            swatch.set_color(color if tool in (PEN, HIGHLIGHTER, ARROW) else "#ececf1")
        self._undo.setEnabled(can_undo)
        self._redo.setEnabled(can_redo)

    def set_mouse_mode(self, on: bool):
        self._mouse.setChecked(on)

    def set_ink_visible(self, visible: bool):
        self._eye.setChecked(visible)

    # -- internals -----------------------------------------------------
    def _grid(self, outer):
        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(grid)
        return grid

    def _button(self, icon_name, tip, checkable=False):
        button = QToolButton()
        button.setIcon(icons.icon(icon_name))
        button.setIconSize(QSize(icons.SIZE, icons.SIZE))
        button.setFixedSize(_BUTTON, _BUTTON)
        button.setToolTip(tip)
        button.setCheckable(checkable)
        button.setFocusPolicy(Qt.NoFocus)
        return button

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.setBrush(QColor(28, 28, 30, 238))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 14, 14)
