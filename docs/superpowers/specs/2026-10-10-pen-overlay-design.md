# Pen overlay: draw over any app with the Huion tablet

## Context

You want a screen-annotation tool driven by your Huion H950P: touch the pen to the tablet and you are drawing on top of whatever app is open, with highlighter, arrows, sticky notes and screenshots. The project folder is empty, so this is a new app.

What you decided:

- **Use:** a mix of live explaining, study notes and review. Ink is temporary by default, with easy screenshot export.
- **Pen vs mouse:** the pen does both. Tip down draws; holding a pen side-button passes the pen through to the app underneath.
- **Ink lifetime:** ink and notes stay on screen, above all apps, until you clear or undo them. They do not follow scrolling.
- **Stack:** Python + Qt (PySide6) overlay.

What the machine gives us (checked):

- Ubuntu 24.04, **X11** session, GNOME 46, arm64, one 1920x1080 monitor.
- X sees the pen as `HUION Huion Tablet_H950P Pen Pen (0)` (libinput driver) with X/Y, pressure 0-2047, tilt, 7 buttons.
- `uv` is installed. No Qt bindings yet. You are not in the `input` group, so we read the pen through X, not `/dev/input`.

My assumptions (say so if wrong):

- Sticky notes hold **typed** text (keyboard), not handwriting.
- X11 only. On a Wayland session the app exits with a clear message.
- One monitor for v1; tablet express keys are not used in v1.

## How it works

The key problem: the pen and the mouse share one cursor, but you want the pen to draw while the mouse still clicks through. The answer is to take the pen away from the cursor.

1. **The app owns the pen.** It runs in the background from login and holds an X Input 2 grab on the pen device only. A grabbed pen stops moving the system cursor and sends its events (position, pressure, tilt, buttons) straight to the app. The mouse is untouched.
2. **The overlay never takes mouse input.** A full-screen, transparent, always-on-top window paints the ink. Its X input region is empty, so mouse clicks always fall through to the app below.
3. **Tip down = draw.** Nothing is visible until the first touch. On hover the overlay draws a small tool cursor; on tip down it starts a stroke and shows the toolbar.
4. **Side button = be a mouse.** While the lower side button is held, the app forwards pen motion and tip clicks to the system cursor with XTest. The upper side button latches this "mouse mode" on and off.
5. **Pen over our own UI acts as a mouse automatically.** When the pen is over the toolbar or a sticky note, events are forwarded the same way, so the pen can press buttons and drag notes.
6. **Fail-safe.** If the app crashes or quits, X drops the grab and the pen is a normal mouse again.

## Features (v1)

| Tool | Behaviour |
| --- | --- |
| Pen | Pressure-sensitive stroke, colour and size from toolbar |
| Highlighter | Wide, semi-transparent, flat stroke; no darkening where it overlaps itself |
| Arrow | Drag from tail to head; straight line with arrowhead |
| Eraser | Removes whole strokes/arrows it touches |
| Sticky note | Tap to drop a note; type text; drag to move; close button |
| Screenshot | Full screen or pen-dragged region, ink and notes included; saved to `~/Pictures/Screenshots/` and copied to clipboard |
| Undo / redo / clear | Toolbar buttons and global hotkeys |
| Hide / show ink | Toggle without losing anything |

Also: tray icon (pause, quit), autostart entry, config file at `~/.config/drawapp/config.toml` (colours, sizes, hotkeys, device name pattern, button mapping).

## Layout

```
pyproject.toml              uv project; deps: PySide6, python-xlib; dev: pytest
src/drawapp/
  __main__.py               start-up, single-instance lock, wiring
  config.py                 load/validate config.toml with defaults
  pen/device.py             find the pen by name, read valuator ranges, handle hotplug
  pen/grabber.py            XI2 grab + event decode -> PenSample(x, y, pressure, tilt, buttons)
  pen/passthrough.py        XTest forwarding of motion and clicks
  pen/mode.py               pure state machine: idle / hover / drawing / passthrough / latched
  model/items.py            Stroke, Arrow, StickyNote dataclasses
  model/document.py         item list, undo/redo, clear, hit-testing for the eraser
  tools.py                  turns pen samples into document edits per active tool
  ui/overlay.py             transparent window, cached ink layer, dirty-rect repaint
  ui/toolbar.py             floating palette (tools, colours, size, undo, clear, screenshot)
  ui/sticky.py              sticky note window
  ui/tray.py                tray icon
  screenshot.py             capture, region select, save, clipboard
  hotkeys.py                global hotkeys via XGrabKey
packaging/drawapp.desktop   autostart entry
tests/                      pytest for the pure modules
```

The X event connection is watched with a `QSocketNotifier` on the Qt main loop, so there are no threads.

## Build order

0. **Set up.** `git init`, uv project, save this design as `docs/superpowers/specs/2026-10-10-pen-overlay-design.md`.
1. **Spike the three risky pieces** (throwaway scripts in `spikes/`):
   - PySide6 installs on arm64 and shows a transparent, click-through, always-on-top window under GNOME. Fallback: apt `python3-pyside6`.
   - python-xlib can grab the pen device and decode position and pressure. Fallback: detach the device from the master pointer and select its events on the root window.
   - Holding the side button and forwarding with XTest behaves like a real mouse.
   I stop and report if a fallback also fails.
2. **Pen input.** `pen/` modules; `mode.py` and coordinate/pressure mapping are test-first.
3. **Overlay + pen tool.** Draw pressure strokes over the desktop; undo, redo, clear.
4. **Toolbar + highlighter, arrow, eraser.**
5. **Sticky notes.**
6. **Screenshot** (full and region). If the screen grab misses the transparent overlay, compose ink onto the grab manually.
7. **Hotkeys, tray, config, autostart, README.**

## Verification

- `uv run pytest`: mode state machine, coordinate mapping, document undo/redo, eraser hit-testing, arrow geometry, config parsing.
- I can start the app and check windows, toolbar, mouse click-through and screenshots myself.
- **I cannot move your pen.** After steps 1, 3 and 6 I will ask you to try a short checklist:
  - Touch pen to tablet with a browser open: a stroke appears and the toolbar shows.
  - Mouse still clicks links under the ink.
  - Hold the lower side button: the pen moves the cursor and clicks the app.
  - Pen can press toolbar buttons and drag a sticky note.
  - Screenshot file contains the ink; clipboard paste works.
  - Kill the app: the pen is a normal mouse again.
  - Unplug and replug the tablet: drawing works again without a restart.
