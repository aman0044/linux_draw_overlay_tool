"""The full-screen transparent window that shows the ink.

It never takes input: mouse clicks fall through to the apps below, and pen
events reach the app through the X grab, not through this window.
"""
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from drawapp.ui.render import paint_item

_HOVER_TIMEOUT_MS = 1200


class Overlay(QWidget):
    def __init__(self, cfg, document):
        super().__init__()
        self._cfg = cfg
        self._doc = document
        self._layer = None  # committed items, painted once
        self._rendered = []  # the items currently in _layer
        self._active = None
        self._region = None
        self._hover = None  # (x, y, radius, color)
        self._toast = ""
        self.ink_visible = True
        self.on_shown = lambda: None

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.X11BypassWindowManagerHint
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setGeometry(QGuiApplication.primaryScreen().geometry())

        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self.clear_hover)
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(lambda: self.show_toast(""))

        document.listeners.append(self._document_changed)

    # -- view interface used by ToolController ------------------------
    def set_active(self, item):
        self._active = item
        if item is not None:
            self.ink_visible = True
        self._sync()

    def set_region(self, rect):
        self._region = rect
        self._sync()
        self.update()

    def set_hover(self, x, y, radius, color):
        old = self._hover
        self._hover = (x, y, radius, color)
        self._hover_timer.start(_HOVER_TIMEOUT_MS)
        self._sync()
        for h in (old, self._hover):
            if h:
                r = h[2] + 4
                self.update(QRectF(h[0] - r, h[1] - r, 2 * r, 2 * r).toAlignedRect())

    def dirty(self, bounds):
        x0, y0, x1, y1 = bounds
        self.update(QRectF(x0 - 2, y0 - 2, x1 - x0 + 4, y1 - y0 + 4).toAlignedRect())

    # -- other controls ------------------------------------------------
    def clear_hover(self):
        self._hover_timer.stop()
        if self._hover is not None:
            self._hover = None
            self._sync()
            self.update()

    def set_ink_visible(self, visible: bool):
        self.ink_visible = visible
        self._sync()
        self.update()

    def show_toast(self, text: str, ms: int = 1800):
        self._toast = text
        if text:
            self._toast_timer.start(ms)
        self._sync()
        self.update()

    def hide_transients(self):
        """Remove everything that must not appear in a screenshot."""
        self._toast_timer.stop()
        self._toast = ""
        self._region = None
        self.clear_hover()
        self._sync()
        self.repaint()

    # -- internals -----------------------------------------------------
    def _document_changed(self):
        self._sync()
        self.update()

    def _sync(self):
        """Only keep the window mapped while there is something to show."""
        has_ink = self.ink_visible and (self._doc.items or self._active is not None)
        wanted = bool(has_ink or self._hover or self._region or self._toast)
        if wanted and not self.isVisible():
            self.show()
            self.on_shown()
        elif not wanted and self.isVisible():
            self.hide()

    def _refresh_layer(self):
        items = self._doc.items
        dpr = self.devicePixelRatioF()
        size = self.size() * dpr
        fresh = self._layer is None or self._layer.size() != size
        kept = len(self._rendered)
        appended = (
            not fresh
            and len(items) >= kept
            and all(a is b for a, b in zip(items, self._rendered))
        )
        if appended and len(items) == kept:
            return
        if not appended:
            self._layer = QPixmap(size)
            self._layer.setDevicePixelRatio(dpr)
            self._layer.fill(Qt.transparent)
            kept = 0
        painter = QPainter(self._layer)
        painter.setRenderHint(QPainter.Antialiasing)
        for item in items[kept:]:
            paint_item(painter, item, self._cfg.highlighter_opacity)
        painter.end()
        self._rendered = list(items)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setClipRect(event.rect())
        painter.setRenderHint(QPainter.Antialiasing)
        if self.ink_visible:
            self._refresh_layer()
            painter.drawPixmap(0, 0, self._layer)
            if self._active is not None:
                paint_item(painter, self._active, self._cfg.highlighter_opacity)
        if self._region:
            x0, y0, x1, y1 = self._region
            rect = QRectF(x0, y0, x1 - x0, y1 - y0)
            painter.fillRect(rect, QColor(10, 132, 255, 40))
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(255, 255, 255), 1.5, Qt.DashLine))
            painter.drawRect(rect)
        if self._hover:
            x, y, radius, color = self._hover
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(0, 0, 0, 160), 3))
            painter.drawEllipse(QRectF(x - radius, y - radius, 2 * radius, 2 * radius))
            painter.setPen(QPen(QColor(color), 1.5))
            painter.drawEllipse(QRectF(x - radius, y - radius, 2 * radius, 2 * radius))
        if self._toast:
            self._paint_toast(painter)

    def _paint_toast(self, painter):
        font = QFont()
        font.setPointSize(11)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        w = metrics.horizontalAdvance(self._toast) + 36
        h = metrics.height() + 18
        rect = QRectF((self.width() - w) / 2, self.height() - h - 64, w, h)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(28, 28, 30, 230))
        painter.drawRoundedRect(rect, h / 2, h / 2)
        painter.setPen(QColor(245, 245, 247))
        painter.drawText(rect, Qt.AlignCenter, self._toast)
