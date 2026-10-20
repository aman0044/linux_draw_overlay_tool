"""Throwaway spike: transparent, always-on-top, click-through overlay + screen grab.

Run: uv run python spikes/overlay_window.py
Shows a red diagonal line over the desktop for a moment, checks that the
window takes no input, grabs the screen and checks the line is in the grab.
"""
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget
from Xlib import display
from Xlib.ext import shape


class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.X11BypassWindowManagerHint
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(QGuiApplication.primaryScreen().geometry())

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(255, 0, 0), 12))
        p.drawLine(200, 200, 600, 600)


app = QApplication(sys.argv)
print("platform:", app.platformName())
w = Overlay()
w.show()


def check():
    d = display.Display()
    win = d.create_resource_object("window", int(w.winId()))
    rects = win.shape_get_rectangles(shape.SK.Input).rectangles
    print("input rectangles (0 = click-through):", len(rects))
    shot = QGuiApplication.primaryScreen().grabWindow(0).toImage()
    on, off = QColor(shot.pixel(400, 400)), QColor(shot.pixel(400, 300))
    print("grab size:", shot.width(), shot.height())
    print("pixel on line:", on.getRgb(), " pixel off line:", off.getRgb())
    print("ink captured:", on.red() > 200 and on.green() < 60 and off.getRgb() != on.getRgb())
    app.quit()


QTimer.singleShot(800, check)
app.exec()
