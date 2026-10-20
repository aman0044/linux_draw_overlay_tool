"""Paint model items with QPainter."""
import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen, QPolygonF

from drawapp.geometry import arrow_head, pressure_width
from drawapp.model.items import HIGHLIGHTER, Arrow, Stroke


def paint_item(painter, item, highlighter_opacity: float):
    if isinstance(item, Stroke):
        if item.kind == HIGHLIGHTER:
            _paint_highlighter(painter, item, highlighter_opacity)
        else:
            _paint_pen(painter, item)
    elif isinstance(item, Arrow):
        _paint_arrow(painter, item)


def _paint_pen(painter, stroke):
    color = QColor(stroke.color)
    pts = stroke.points
    if len(pts) == 1:
        x, y, pressure = pts[0]
        r = pressure_width(stroke.width, pressure) / 2
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(QPointF(x, y), r, r)
        return
    pen = QPen(color)
    pen.setCapStyle(Qt.RoundCap)
    for a, b in zip(pts, pts[1:]):
        pen.setWidthF(pressure_width(stroke.width, (a[2] + b[2]) / 2))
        painter.setPen(pen)
        painter.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))


def _paint_highlighter(painter, stroke, opacity):
    color = QColor(stroke.color)
    color.setAlphaF(opacity)
    pts = stroke.points
    # One path, stroked once: overlapping parts of the same stroke do not darken.
    path = QPainterPath(QPointF(pts[0][0], pts[0][1]))
    if len(pts) == 1:
        path.lineTo(pts[0][0] + 0.1, pts[0][1])
    for x, y, _ in pts[1:]:
        path.lineTo(x, y)
    pen = QPen(color, stroke.width)
    pen.setCapStyle(Qt.SquareCap if len(pts) == 1 else Qt.FlatCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(path)


def _paint_arrow(painter, arrow):
    color = QColor(arrow.color)
    length = math.hypot(arrow.x2 - arrow.x1, arrow.y2 - arrow.y1)
    if length < 1:
        return
    head = min(arrow.head_size(), length)
    left, right = arrow_head(arrow.x1, arrow.y1, arrow.x2, arrow.y2, head)
    # Stop the shaft inside the head so its round cap does not blunt the tip.
    t = 1 - (head * 0.7) / length
    shaft_end = QPointF(arrow.x1 + (arrow.x2 - arrow.x1) * t, arrow.y1 + (arrow.y2 - arrow.y1) * t)
    pen = QPen(color, arrow.width)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.drawLine(QPointF(arrow.x1, arrow.y1), shaft_end)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(color))
    painter.drawPolygon(QPolygonF([QPointF(arrow.x2, arrow.y2), QPointF(*left), QPointF(*right)]))
