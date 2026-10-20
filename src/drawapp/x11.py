"""One shared X connection, pumped from the Qt event loop."""
import logging

from PySide6.QtCore import QObject, QSocketNotifier, QTimer
from Xlib import display

log = logging.getLogger(__name__)


class XConnection(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.display = display.Display()
        self.root = self.display.screen().root
        self._handlers = []
        self._notifier = QSocketNotifier(self.display.fileno(), QSocketNotifier.Read, self)
        self._notifier.activated.connect(self.pump)
        # python-xlib can read events into its own queue while waiting for a
        # reply, without the socket becoming readable again; sweep for those.
        self._sweep = QTimer(self)
        self._sweep.timeout.connect(self.pump)
        self._sweep.start(100)

    def add_handler(self, handler):
        """handler(event) is called for every X event on this connection."""
        self._handlers.append(handler)

    def pump(self, *_):
        while self.display.pending_events():
            event = self.display.next_event()
            for handler in self._handlers:
                try:
                    handler(event)
                except Exception:
                    log.exception("X event handler failed")

    def flush(self):
        self.display.flush()
