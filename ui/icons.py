"""用 QPainter 绘制线条图标，不依赖图片文件。颜色取自当前主题。"""

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

from utils.theme import colors


_UNIT = 20
_SCALE = 3


def _download(p):
    p.drawLine(QPointF(10, 3), QPointF(10, 12.5))
    p.drawPolyline([
        QPointF(6, 8.5),
        QPointF(10, 12.5),
        QPointF(14, 8.5),
    ])
    p.drawPolyline([
        QPointF(4, 13.5),
        QPointF(4, 16.5),
        QPointF(16, 16.5),
        QPointF(16, 13.5),
    ])


def _quiz(p):
    """试卷加勾选标记。"""
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
    painter_func = _PAINTERS.get(name)
    if painter_func is None:
        raise ValueError(f"未知导航图标: {name}")

    pixmap = QPixmap(_UNIT * _SCALE, _UNIT * _SCALE)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(_SCALE, _SCALE)

        pen = QPen(QColor(color))
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        painter_func(painter)
    finally:
        painter.end()

    return pixmap


def nav_icon(name):
    """侧栏导航图标：未选中使用次要文字色，选中使用强调色。"""
    theme_colors = colors()

    icon = QIcon()
    icon.addPixmap(
        _pixmap(name, theme_colors["muted"]),
        QIcon.Mode.Normal,
        QIcon.State.Off,
    )
    icon.addPixmap(
        _pixmap(name, theme_colors["accent_text"]),
        QIcon.Mode.Normal,
        QIcon.State.On,
    )
    return icon
