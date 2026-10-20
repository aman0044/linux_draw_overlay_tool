"""User settings, read from ~/.config/drawapp/config.toml."""
import logging
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

log = logging.getLogger(__name__)

CONFIG_PATH = Path.home() / ".config" / "drawapp" / "config.toml"

DEFAULT_COLORS = ["#ff3b30", "#ffcc00", "#34c759", "#0a84ff", "#ffffff", "#1c1c1e"]

DEFAULT_HOTKEYS = {
    "undo": "Ctrl+Alt+Z",
    "redo": "Ctrl+Alt+Y",
    "clear": "Ctrl+Alt+X",
    "toggle_ink": "Ctrl+Alt+H",
    "screenshot": "Ctrl+Alt+P",
    "toggle_mouse_mode": "Ctrl+Alt+M",
}


@dataclass
class Config:
    # Regular expression matched against the X device name. Empty = first
    # pointer device that reports pressure.
    device_pattern: str = ""
    tip_button: int = 1
    hold_button: int = 2  # held: pen acts as a mouse
    latch_button: int = 3  # pressed: toggle mouse mode
    colors: list = field(default_factory=lambda: list(DEFAULT_COLORS))
    sizes: list = field(default_factory=lambda: [3.0, 6.0, 12.0])
    highlighter_scale: float = 4.0  # highlighter width = size * this
    highlighter_opacity: float = 0.35
    eraser_radius: float = 14.0
    screenshot_dir: str = "~/Pictures/Screenshots"
    hotkeys: dict = field(default_factory=lambda: dict(DEFAULT_HOTKEYS))


def parse(data: dict) -> Config:
    """Build a Config from parsed TOML, ignoring anything unusable."""
    cfg = Config()
    known = {f.name: f for f in fields(Config)}
    for key, value in data.items():
        if key not in known:
            log.warning("config: unknown setting %r ignored", key)
            continue
        default = getattr(cfg, key)
        if key == "hotkeys":
            if isinstance(value, dict):
                cfg.hotkeys.update({k: str(v) for k, v in value.items() if k in DEFAULT_HOTKEYS})
            continue
        if isinstance(default, float) and isinstance(value, int) and not isinstance(value, bool):
            value = float(value)
        if isinstance(default, list):
            if not (isinstance(value, list) and value):
                log.warning("config: %r must be a non-empty list, ignored", key)
                continue
            if key == "sizes":
                try:
                    value = [float(v) for v in value]
                except (TypeError, ValueError):
                    log.warning("config: %r must be numbers, ignored", key)
                    continue
        elif type(value) is not type(default):
            log.warning("config: %r has the wrong type, ignored", key)
            continue
        setattr(cfg, key, value)
    return cfg


def load(path: Path = CONFIG_PATH) -> Config:
    if not path.exists():
        return Config()
    try:
        with open(path, "rb") as f:
            return parse(tomllib.load(f))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        log.warning("config: could not read %s (%s); using defaults", path, exc)
        return Config()
