"""Grab the screen (ink included), save it and copy it to the clipboard."""
from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QGuiApplication


def capture(rect=None):
    """Grab the whole screen, or (x0, y0, x1, y1) in screen coordinates."""
    screen = QGuiApplication.primaryScreen()
    if rect is None:
        return screen.grabWindow(0)
    x0, y0, x1, y1 = (int(round(v)) for v in rect)
    return screen.grabWindow(0, x0, y0, x1 - x0, y1 - y0)


def save(pixmap, directory: str, now: datetime | None = None) -> Path:
    """Write the pixmap as a PNG and put it on the clipboard. Returns the path."""
    folder = Path(directory).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now()).strftime("%Y-%m-%d_%H-%M-%S")
    path = folder / f"drawapp_{stamp}.png"
    counter = 2
    while path.exists():
        path = folder / f"drawapp_{stamp}_{counter}.png"
        counter += 1
    if not pixmap.save(str(path), "PNG"):
        raise OSError(f"could not write {path}")
    QGuiApplication.clipboard().setPixmap(pixmap)
    return path
