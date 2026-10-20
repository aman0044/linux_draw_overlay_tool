"""Draw over any app with a pen tablet."""
import argparse
import logging
import os
import signal
import sys
from pathlib import Path

AUTOSTART_PATH = Path.home() / ".config" / "autostart" / "drawapp.desktop"

_DESKTOP_ENTRY = """[Desktop Entry]
Type=Application
Name=Draw app
Comment=Draw over any app with the pen tablet
Exec={command}
Terminal=false
X-GNOME-Autostart-enabled=true
"""


def install_autostart():
    # The installed package starts through a launcher script that sets itself
    # in the environment; a source checkout starts through its own Python.
    command = os.environ.get("DRAWAPP_LAUNCHER") or f"{sys.executable} -m drawapp"
    AUTOSTART_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUTOSTART_PATH.write_text(_DESKTOP_ENTRY.format(command=command))
    print(f"Draw app will start at login ({AUTOSTART_PATH})")


def uninstall_autostart():
    AUTOSTART_PATH.unlink(missing_ok=True)
    print("Draw app will no longer start at login")


def main() -> int:
    parser = argparse.ArgumentParser(prog="drawapp", description=__doc__)
    parser.add_argument("--debug", action="store_true", help="log pen and device details")
    parser.add_argument("--install-autostart", action="store_true", help="start at login")
    parser.add_argument("--uninstall-autostart", action="store_true", help="stop starting at login")
    args = parser.parse_args()

    if args.install_autostart:
        install_autostart()
        return 0
    if args.uninstall_autostart:
        uninstall_autostart()
        return 0

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if os.environ.get("XDG_SESSION_TYPE") == "wayland" or not os.environ.get("DISPLAY"):
        print("drawapp needs an X11 session; on Wayland it cannot capture the pen.", file=sys.stderr)
        return 1
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

    # Imported here so --help and the autostart commands work without a display.
    from PySide6.QtCore import QDir, QLockFile, QTimer
    from PySide6.QtWidgets import QApplication

    from drawapp import config
    from drawapp.app import App

    qt_app = QApplication(sys.argv[:1])
    qt_app.setApplicationName("drawapp")
    qt_app.setQuitOnLastWindowClosed(False)

    lock = QLockFile(QDir.tempPath() + f"/drawapp-{os.getuid()}.lock")
    if not lock.tryLock(0):
        print("drawapp is already running.", file=sys.stderr)
        return 1

    app = App(config.load())
    qt_app.aboutToQuit.connect(app.shutdown)

    signal.signal(signal.SIGINT, lambda *_: qt_app.quit())
    signal.signal(signal.SIGTERM, lambda *_: qt_app.quit())
    # Python only runs signal handlers between bytecodes; wake it up regularly.
    heartbeat = QTimer()
    heartbeat.timeout.connect(lambda: None)
    heartbeat.start(250)

    return qt_app.exec()
