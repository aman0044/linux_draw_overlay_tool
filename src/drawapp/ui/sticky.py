"""Sticky notes: small always-on-top windows you can type in."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QSizeGrip, QToolButton, QVBoxLayout, QWidget

_STYLE = """
#note { background: #ffe680; border: 1px solid #c9a700; }
#header { background: #ffd633; }
QPlainTextEdit { background: transparent; border: none; color: #1c1c1e; font-size: 12pt; }
QToolButton { border: none; color: #5c4b00; font-size: 12pt; font-weight: bold; }
QToolButton:hover { color: #c0392b; }
QLabel { color: #5c4b00; font-size: 9pt; }
"""


class _Header(QWidget):
    def __init__(self, window):
        super().__init__()
        self.setObjectName("header")
        self.setAttribute(Qt.WA_StyledBackground)
        self._window = window
        self._offset = None
        self.setFixedHeight(24)
        self.setCursor(Qt.SizeAllCursor)

    def mousePressEvent(self, event):
        self._offset = event.globalPosition().toPoint() - self._window.pos()

    def mouseMoveEvent(self, event):
        if self._offset is not None:
            self._window.move(event.globalPosition().toPoint() - self._offset)

    def mouseReleaseEvent(self, _):
        self._offset = None


class StickyNote(QWidget):
    closed = Signal(object)

    def __init__(self, x: int, y: int):
        super().__init__()
        self.setObjectName("note")
        self.setAttribute(Qt.WA_StyledBackground)
        # A managed window (not override-redirect) so it can take keyboard focus.
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Sticky note")
        self.setStyleSheet(_STYLE)

        header = _Header(self)
        row = QHBoxLayout(header)
        row.setContentsMargins(8, 0, 4, 0)
        row.addWidget(QLabel("Note"))
        row.addStretch()
        close = QToolButton()
        close.setText("×")
        close.setCursor(Qt.ArrowCursor)
        close.setToolTip("Delete this note")
        close.clicked.connect(self.close)
        row.addWidget(close)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("Type here…")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(self.editor)
        layout.addWidget(QSizeGrip(self), 0, Qt.AlignBottom | Qt.AlignRight)

        self.resize(220, 160)
        self.move(x, y)

    def closeEvent(self, event):
        self.closed.emit(self)
        super().closeEvent(event)
