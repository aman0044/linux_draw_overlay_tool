"""Things that can be drawn on the overlay."""
from dataclasses import dataclass, field

from drawapp.geometry import dist_point_segment

PEN = "pen"
HIGHLIGHTER = "highlighter"


@dataclass
class Stroke:
    kind: str  # PEN or HIGHLIGHTER
    color: str
    width: float
    points: list = field(default_factory=list)  # (x, y, pressure)

    def bounds(self):
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        pad = self.width
        return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad

    def hit(self, x, y, radius) -> bool:
        reach = radius + self.width / 2
        pts = self.points
        if len(pts) == 1:
            return dist_point_segment(x, y, *pts[0][:2], *pts[0][:2]) <= reach
        return any(
            dist_point_segment(x, y, a[0], a[1], b[0], b[1]) <= reach
            for a, b in zip(pts, pts[1:])
        )


@dataclass
class Arrow:
    x1: float
    y1: float
    x2: float
    y2: float
    color: str
    width: float

    def head_size(self) -> float:
        return max(14.0, self.width * 4)

    def bounds(self):
        pad = self.head_size() + self.width
        return (
            min(self.x1, self.x2) - pad,
            min(self.y1, self.y2) - pad,
            max(self.x1, self.x2) + pad,
            max(self.y1, self.y2) + pad,
        )

    def hit(self, x, y, radius) -> bool:
        return (
            dist_point_segment(x, y, self.x1, self.y1, self.x2, self.y2)
            <= radius + self.width / 2
        )
