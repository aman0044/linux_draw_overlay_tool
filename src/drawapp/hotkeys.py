"""Global keyboard shortcuts that work while another app has focus."""
import logging

from Xlib import X, XK, error

log = logging.getLogger(__name__)

_MODIFIERS = {
    "ctrl": X.ControlMask,
    "control": X.ControlMask,
    "shift": X.ShiftMask,
    "alt": X.Mod1Mask,
    "super": X.Mod4Mask,
}
# Num Lock and Caps Lock must not stop a shortcut from matching.
_LOCK_VARIANTS = (0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask)
_RELEVANT = X.ControlMask | X.ShiftMask | X.Mod1Mask | X.Mod4Mask


def parse_hotkey(text: str):
    """'Ctrl+Alt+Z' -> (modifier mask, keysym). Raises ValueError if unusable."""
    parts = [p.strip() for p in text.split("+") if p.strip()]
    if not parts:
        raise ValueError("empty shortcut")
    mask = 0
    for name in parts[:-1]:
        try:
            mask |= _MODIFIERS[name.lower()]
        except KeyError:
            raise ValueError(f"unknown modifier {name!r}") from None
    key = parts[-1]
    if len(key) == 1:
        key = key.lower()  # the unshifted key is what sits on the keyboard
    keysym = XK.string_to_keysym(key) or XK.string_to_keysym(key.lower())
    if not keysym:
        raise ValueError(f"unknown key {key!r}")
    return mask, keysym


class Hotkeys:
    def __init__(self, xconn):
        self._x = xconn
        self._actions = {}  # (keycode, mask) -> callable
        xconn.add_handler(self._handle)

    def register(self, text: str, callback):
        if not text:
            return
        try:
            mask, keysym = parse_hotkey(text)
        except ValueError as exc:
            log.warning("shortcut %r skipped: %s", text, exc)
            return
        d = self._x.display
        keycode = d.keysym_to_keycode(keysym)
        if not keycode:
            log.warning("shortcut %r skipped: key not on this keyboard", text)
            return
        catch = error.CatchError(error.BadAccess)
        for extra in _LOCK_VARIANTS:
            self._x.root.grab_key(
                keycode, mask | extra, False, X.GrabModeAsync, X.GrabModeAsync, onerror=catch
            )
        d.sync()
        if catch.get_error():
            log.warning("shortcut %r is already used by another program", text)
            return
        self._actions[(keycode, mask)] = callback

    def _handle(self, event):
        if event.type != X.KeyPress:
            return
        callback = self._actions.get((event.detail, event.state & _RELEVANT))
        if callback:
            callback()
