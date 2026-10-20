"""Regenerate the README screenshots: uv run python docs/images/make_screenshots.py

Opens a sample page, drives the app with simulated pen strokes and grabs
parts of the screen. Needs an X11 session; the real pen is not used.
"""
import math, sys, tempfile
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QLabel
from drawapp import config
from drawapp.app import App
from drawapp.model.items import HIGHLIGHTER, PEN
from drawapp.pen.decode import MOTION, PRESS, RELEASE
from drawapp.tools import ARROW, REGION

OUT = Path(__file__).parent
PAGE = """<div style="font-family:sans-serif;color:#1c1c1e">
<h1 style="font-size:30px">Gradient descent</h1>
<p style="font-size:19px;line-height:150%">Gradient descent finds the minimum of a function by
repeatedly stepping against the gradient.<br>Each update moves the parameters a small amount:</p>
<p style="font-size:24px;font-family:serif">&nbsp;&nbsp;&nbsp;&theta; &larr; &theta; &minus; &eta; &nabla;L(&theta;)</p>
<p style="font-size:19px;line-height:150%">The learning rate &eta; controls the step size. Too large and the
updates overshoot;<br>too small and training crawls. A common starting point is &eta; = 0.01.</p>
<h2 style="font-size:23px">Why it works</h2>
<p style="font-size:19px;line-height:150%">The gradient points uphill, so its negative points towards lower loss.
<br>Near a minimum the gradient shrinks and the steps get smaller on their own.</p></div>"""

qa = QApplication(sys.argv[:1]); qa.setQuitOnLastWindowClosed(False)
page = QLabel(PAGE); page.setWindowFlags(Qt.FramelessWindowHint)
page.setStyleSheet("background:#fbfbfd;padding:40px 60px"); page.setAlignment(Qt.AlignTop | Qt.AlignLeft)
page.setGeometry(QGuiApplication.primaryScreen().geometry().adjusted(80, 0, 0, 0)); page.show(); page.raise_()
cfg = config.Config(); cfg.screenshot_dir = tempfile.mkdtemp()  # keep test shots out of ~/Pictures
app = App(cfg)

def stroke(points, pressure=True):
    x, y = points[0]
    app._on_pen(PRESS, 1, x, y, 0.6)
    for i, (x, y) in enumerate(points[1:]):
        app._on_pen(MOTION, 0, x, y, 0.5 + 0.4 * math.sin(i / 6) if pressure else 0.8)
    app._on_pen(RELEASE, 1, x, y, 0)

def grab(name, x, y, w, h):
    QGuiApplication.primaryScreen().grabWindow(0, x, y, w, h).save(str(OUT / name))

def draw():
    t = app.tools
    t.set_tool(HIGHLIGHTER); stroke([(570 + i * 6, 255) for i in range(54)], False)
    t.set_tool(PEN); t.set_color("#ff3b30")
    stroke([(722 + 62 * math.cos(a / 20), 289 + 22 * math.sin(a / 20)) for a in range(0, 132)])
    stroke([(530 + i * 6, 390 + 2.5 * math.sin(i * 1.3)) for i in range(42)])
    t.set_tool(ARROW); t.set_color("#0a84ff"); stroke([(1080, 420), (940, 360), (800, 300)])
    t.set_tool(PEN); t.set_color("#34c759"); t.set_size(2)
    stroke([(440, 212), (455, 228), (485, 190)])
    t.set_size(1); t.set_tool("note"); stroke([(1090, 330)])
    app.notes[0].editor.setPlainText("Try η = 0.001 and\ncompare the loss curves")
    app.overlay.clear_hover()
    app.toolbar.move(1560, 120)
    QTimer.singleShot(700, shots)

def shots():
    grab("hero.png", 80, 40, 1700, 600)
    grab("pen-highlighter.png", 100, 170, 900, 260)
    grab("arrows-notes.png", 560, 200, 760, 340)
    app.toolbar.grab().save(str(OUT / "toolbar.png"))
    app.tools.set_tool(REGION)
    app._on_pen(PRESS, 1, 190, 190, 0.5); app._on_pen(MOTION, 0, 960, 430, 0.5)
    QTimer.singleShot(400, region)

def region():
    app.overlay.clear_hover(); app.overlay.repaint()
    grab("region-select.png", 100, 150, 960, 330)
    app._on_pen(RELEASE, 1, 960, 430, 0)   # also saves a real screenshot
    QTimer.singleShot(1200, app.quit)

QTimer.singleShot(800, draw)
qa.exec()
