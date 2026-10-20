"""Pure geometry helpers shared by the model and the renderer."""
import math


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def normalize(value: float, lo: float, hi: float) -> float:
    """Map value from [lo, hi] to [0, 1], clamped."""
    if hi <= lo:
        return 0.0
    return clamp01((value - lo) / (hi - lo))


def pressure_width(base: float, pressure: float) -> float:
    """Stroke width for a pressure in [0, 1]; never thinner than 35% of base."""
    return base * (0.35 + 0.65 * clamp01(pressure))


def dist_point_segment(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(px - ax, py - ay)
    t = clamp01(((px - ax) * dx + (py - ay) * dy) / length_sq)
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def arrow_head(x1, y1, x2, y2, size: float, spread_deg: float = 28.0):
    """The two barb end points of an arrowhead whose tip is (x2, y2)."""
    angle = math.atan2(y2 - y1, x2 - x1)
    spread = math.radians(spread_deg)
    left = (x2 - size * math.cos(angle - spread), y2 - size * math.sin(angle - spread))
    right = (x2 - size * math.cos(angle + spread), y2 - size * math.sin(angle + spread))
    return left, right
