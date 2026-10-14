"""左侧导航栏：模块切换（文件下载 / 设置）。"""
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QButtonGroup, QLabel

from ui.icons import nav_icon


class Sidebar(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setObjectName("sidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(210)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 18, 12, 16)
        layout.setSpacing(4)

        self.title_label = QLabel()
        self.title_label.setObjectName("app_title")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.btn_download = QPushButton()
        self.btn_settings = QPushButton()
        self._nav_buttons = [
            (self.btn_download, "download", "tab_download"),
            (self.btn_settings, "settings", "tab_settings"),
        ]

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for idx, (btn, _icon, _key) in enumerate(self._nav_buttons):
            btn.setObjectName("nav_btn")
            btn.setCheckable(True)
            btn.setFixedHeight(38)
            btn.setIconSize(QSize(18, 18))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.group.addButton(btn, idx)
            layout.addWidget(btn)

        layout.addStretch()
        self.refresh_icons()
        self.retranslate()

    def tr(self, key, *args):
        return self.ctx.tr(key, *args)

    def refresh_icons(self):
        """图标颜色跟随主题，切换主题后要重画。"""
        for btn, icon, _key in self._nav_buttons:
            btn.setIcon(nav_icon(icon))

    def retranslate(self):
        self.title_label.setText(self.tr("window_title"))
        for btn, _icon, key in self._nav_buttons:
            btn.setText(" " + self.tr(key))
