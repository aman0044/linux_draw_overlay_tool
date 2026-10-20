"""Toolbar icons, drawn with QPainter so the app ships no image files."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

SIZE = 24
_FG = QColor("#ececf1")


def _pen(width=1.8, color=_FG):
    pen = QPen(color, width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def _poly(*points):
    return QPolygonF([QPointF(x, y) for x, y in points])


def _draw_pen(p):
    p.setPen(_pen())
    p.drawPolygon(_poly((5, 19), (6.5, 14.5), (16, 5), (19, 8), (9.5, 17.5)))
    p.drawLine(QPointF(14, 7), QPointF(17, 10))


def _draw_highlighter(p):
    p.setPen(_pen(6, QColor(255, 204, 0, 170)))
    p.drawLine(QPointF(5, 18), QPointF(19, 18))
    p.setPen(_pen())
    p.drawPolygon(_poly((8, 14), (15, 4), (19, 7), (12, 16.5)))
    p.drawLine(QPointF(8, 14), QPointF(7, 17))


def _draw_arrow(p):
    p.setPen(_pen(2))
    p.drawLine(QPointF(5, 19), QPointF(18, 6))
    p.drawPolyline(_poly((10, 6), (18, 6), (18, 14)))


def _draw_eraser(p):
    p.setPen(_pen())
    p.drawPolygon(_poly((4, 15), (13, 6), (19, 12), (12, 19), (8, 19)))
    p.drawLine(QPointF(9, 10), QPointF(15, 16))
    p.drawLine(QPointF(12, 19), QPointF(20, 19))


def _draw_note(p):
    p.setPen(_pen())
    p.drawPolygon(_poly((5, 5), (19, 5), (19, 14), (14, 19), (5, 19)))
    p.drawPolyline(_poly((19, 14), (14, 14), (14, 19)))
    p.drawLine(QPointF(8, 9), QPointF(16, 9))


def _draw_region(p):
    p.setPen(QPen(_FG, 1.8, Qt.DashLine))
    p.drawRect(QRectF(4.5, 6.5, 15, 11))


def _draw_camera(p):
    p.setPen(_pen())
    p.drawRoundedRect(QRectF(3.5, 7.5, 17, 11.5), 2, 2)
    p.drawPolyline(_poly((8.5, 7.5), (10, 5), (14, 5), (15.5, 7.5)))
    p.drawEllipse(QPointF(12, 13.2), 3, 3)


def _curved_arrow(p, mirror):
    p.setPen(_pen(2))
    if mirror:
        p.translate(SIZE, 0)
        p.scale(-1, 1)
    path = QPainterPath(QPointF(6, 10))
    path.lineTo(14, 10)
    path.cubicTo(19.5, 10, 19.5, 18, 14, 18)
    path.lineTo(9, 18)
    p.drawPath(path)
    p.drawPolyline(_poly((9.5, 6), (5.5, 10), (9.5, 14)))


def _draw_undo(p):
    _curved_arrow(p, False)


def _draw_redo(p):
    _curved_arrow(p, True)


def _draw_trash(p):
    p.setPen(_pen())
    p.drawLine(QPointF(5, 7), QPointF(19, 7))
    p.drawPolyline(_poly((9.5, 7), (10, 4.5), (14, 4.5), (14.5, 7)))
    p.drawPolygon(_poly((6.5, 7), (17.5, 7), (16.5, 19.5), (7.5, 19.5)))
    p.drawLine(QPointF(10.3, 10.5), QPointF(10.6, 16))
    p.drawLine(QPointF(13.7, 10.5), QPointF(13.4, 16))


def _draw_eye(p):
    p.setPen(_pen())
    path = QPainterPath(QPointF(3, 12))
    path.quadTo(12, 2.5, 21, 12)
    path.quadTo(12, 21.5, 3, 12)
    p.drawPath(path)
    p.setBrush(QBrush(_FG))
    p.drawEllipse(QPointF(12, 12), 2.6, 2.6)


def _draw_mouse(p):
    p.setPen(_pen(1.6))
    p.drawPolygon(_poly((7, 3.5), (7, 18), (10.7, 14.6), (13.2, 20.3), (15.6, 19.2), (13.1, 13.7), (18, 13.4)))


def _draw_close(p):
    p.setPen(_pen(2))
    p.drawLine(QPointF(7, 7), QPointF(17, 17))
    p.drawLine(QPointF(17, 7), QPointF(7, 17))


_DRAWERS = {
    "pen": _draw_pen,
    "highlighter": _draw_highlighter,
    "arrow": _draw_arrow,
    "eraser": _draw_eraser,
    "note": _draw_note,
    "region": _draw_region,
    "camera": _draw_camera,
    "undo": _draw_undo,
    "redo": _draw_redo,
    "trash": _draw_trash,
    "eye": _draw_eye,
    "mouse": _draw_mouse,
    "close": _draw_close,
}


def icon(name: str, dpr: float = 2.0) -> QIcon:
    pixmap = QPixmap(int(SIZE * dpr), int(SIZE * dpr))
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(Qt.NoBrush)
    _DRAWERS[name](painter)
    painter.end()
    return QIcon(pixmap)
