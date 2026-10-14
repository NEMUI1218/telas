"""设置页：语言 + 主题。"""
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QComboBox

from utils.theme import apply_theme

LANG_MAP = ["ja", "en", "zh"]


class SettingsPage(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self._build_ui()
        self.retranslate()

    def tr(self, key, *args):
        return self.ctx.tr(key, *args)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.appearance_group = QGroupBox()
        self.appearance_group.setMaximumWidth(520)
        form_layout = QVBoxLayout(self.appearance_group)
        form_layout.setContentsMargins(4, 0, 4, 2)
        form_layout.setSpacing(10)

        lang_row = QHBoxLayout()
        self.lang_label = QLabel()
        self.lang_label.setObjectName("field_label")
        lang_row.addWidget(self.lang_label)
        lang_row.addStretch()
        self.lang_cb = QComboBox()
        self.lang_cb.setFixedWidth(160)
        self.lang_cb.addItems(["日本語", "English", "中文"])
        self.lang_cb.setFixedHeight(32)
        lang_index = {"ja": 0, "en": 1, "zh": 2}.get(self.ctx.i18n.lang, 2)
        self.lang_cb.setCurrentIndex(lang_index)
        self.lang_cb.currentIndexChanged.connect(self._on_lang_changed)
        lang_row.addWidget(self.lang_cb)
        form_layout.addLayout(lang_row)

        theme_row = QHBoxLayout()
        self.theme_label = QLabel()
        self.theme_label.setObjectName("field_label")
        theme_row.addWidget(self.theme_label)
        theme_row.addStretch()
        self.theme_cb = QComboBox()
        self.theme_cb.setFixedWidth(160)
        self.theme_cb.setFixedHeight(32)
        self.theme_cb.currentIndexChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self.theme_cb)
        form_layout.addLayout(theme_row)

        layout.addWidget(self.appearance_group)
        layout.addStretch()

    def retranslate(self):
        self.appearance_group.setTitle(self.tr("appearance"))
        self.lang_label.setText(self.tr("lang_label"))
        self.theme_label.setText(self.tr("theme_label"))
        self.theme_cb.blockSignals(True)
        self.theme_cb.clear()
        self.theme_cb.addItems([self.tr("theme_dark"), self.tr("theme_light")])
        theme = self.ctx.settings.get("theme", "dark")
        self.theme_cb.setCurrentIndex(1 if theme == "light" else 0)
        self.theme_cb.blockSignals(False)

    def _on_lang_changed(self, idx):
        lang = LANG_MAP[idx] if 0 <= idx < len(LANG_MAP) else "zh"
        self.ctx.i18n.set_lang(lang)
        self.ctx.settings.set("lang", lang)
        self.ctx.settings.save()
        self.ctx.signals.language_changed.emit()

    def _on_theme_changed(self, idx):
        theme = "light" if idx == 1 else "dark"
        self.ctx.settings.set("theme", theme)
        self.ctx.settings.save()
        apply_theme(QApplication.instance(), theme)
        self.ctx.signals.theme_changed.emit()
