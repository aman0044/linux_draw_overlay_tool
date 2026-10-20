"""Tray icon: the only always-visible sign that the app is running."""
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from drawapp.ui import icons


class Tray(QSystemTrayIcon):
    def __init__(self, app):
        super().__init__(icons.icon("pen"))
        self.setToolTip("Draw app: touch the pen to the tablet to draw")
        menu = QMenu()
        menu.addAction("Show toolbar", app.show_toolbar)
        self.pause = QAction("Pause pen capture (pen is a normal mouse)", menu, checkable=True)
        self.pause.toggled.connect(app.set_paused)
        menu.addAction(self.pause)
        menu.addSeparator()
        menu.addAction("Clear ink", app.document.clear)
        menu.addAction("Close all notes", app.close_notes)
        menu.addSeparator()
        menu.addAction("Quit", app.quit)
        self._menu = menu  # keep it alive
        self.setContextMenu(menu)
