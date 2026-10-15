"""用 QPainter 画的线条图标，不依赖任何图片文件。颜色取自当前主题。"""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

from utils.theme import colors

_UNIT = 20      # 图标按 20×20 的坐标画
_SCALE = 3      # 实际画成 60×60，交给 QIcon 缩小，高分屏上不发虚


def _download(p):
    p.drawPolyline([QPointF(10, 3), QPointF(10, 12.5)])
    p.drawPolyline([QPointF(6, 8.5), QPointF(10, 12.5), QPointF(14, 8.5)])
    p.drawPolyline([QPointF(4, 13.5), QPointF(4, 16.5), QPointF(16, 16.5), QPointF(16, 13.5)])

def _quiz(p):
    # 画一张带勾选标记的试卷
    p.drawPolyline([
        QPointF(5, 3),
        QPointF(13, 3),
        QPointF(16, 6),
        QPointF(16, 10),
    ])
    p.drawPolyline([
        QPointF(13, 3),
        QPointF(13, 6),
        QPointF(16, 6),
    ])
    p.drawLine(QPointF(7, 8), QPointF(11, 8))
    p.drawLine(QPointF(7, 11), QPointF(10, 11))
    p.drawPolyline([
        QPointF(8, 15),
        QPointF(10, 17),
        QPointF(14, 13),
    ])
    
def _settings(p):
    for y, x in ((5, 7), (10, 13), (15, 9)):
        p.drawLine(QPointF(3, y), QPointF(x - 2, y))
        p.drawLine(QPointF(x + 2, y), QPointF(17, y))
        p.drawEllipse(QPointF(x, y), 2, 2)


_PAINTERS = {
    "download": _download,
    "quiz": _quiz,
    "settings": _settings,
}

def _pixmap(name, color):
    pm = QPixmap(_UNIT * _SCALE, _UNIT * _SCALE)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(_SCALE, _SCALE)
    pen = QPen(QColor(color))
    pen.setWidthF(1.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    _PAINTERS[name](p)
    p.end()
    return pm


def nav_icon(name):
    """侧栏导航图标：未选中用次要文字色，选中用强调色。"""
    c = colors()
    icon = QIcon()
    icon.addPixmap(_pixmap(name, c["muted"]), QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(_pixmap(name, c["accent_text"]), QIcon.Mode.Normal, QIcon.State.On)
    return icon
