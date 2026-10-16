"""设置页：语言、主题和下载保存设置。"""
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QComboBox, QCheckBox, QLineEdit, QPushButton, QFileDialog,
)

from utils.theme import apply_theme

LANG_MAP = ["ja", "en", "zh", "zh_TW"]


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
        layout.setContentsMargins(0, 32, 0, 0)

        self.settings_container = QWidget()
        self.settings_container.setMaximumWidth(520)
        self.settings_container.setMinimumWidth(0)
        settings_layout = QVBoxLayout(self.settings_container)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(12)

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
        self.lang_cb.addItems(["日本語", "English", "简体中文", "繁體中文"])
        self.lang_cb.setFixedHeight(32)
        lang_index = {lang: i for i, lang in enumerate(LANG_MAP)}.get(
            self.ctx.i18n.lang, 2
        )
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

        settings_layout.addWidget(self.appearance_group)

        self.download_group = QGroupBox()
        self.download_group.setMaximumWidth(520)
        download_layout = QGridLayout(self.download_group)
        download_layout.setContentsMargins(4, 0, 4, 2)
        download_layout.setHorizontalSpacing(10)
        download_layout.setVerticalSpacing(10)
        download_layout.setColumnStretch(1, 1)

        self.save_path_label = QLabel()
        self.save_path_label.setObjectName("field_label")
        download_layout.addWidget(self.save_path_label, 0, 0)

        self.save_path_input = QLineEdit()
        save_path = self.ctx.settings.get("save_path")
        if not save_path or not str(save_path).strip():
            save_path = os.path.join(
                os.path.expanduser("~"), "Downloads", "Blackboard_download"
            )
            self.ctx.settings.set("save_path", save_path)
            self.ctx.settings.save()
        self.save_path_input.setText(save_path)
        self.save_path_input.setFixedHeight(32)
        self.save_path_input.setMinimumWidth(0)
        self.save_path_input.setMaximumWidth(260)
        self.save_path_input.editingFinished.connect(self._save_path_setting)
        download_layout.addWidget(
            self.save_path_input, 0, 1, Qt.AlignmentFlag.AlignLeft
        )

        self.browse_btn = QPushButton()
        self.browse_btn.setObjectName("secondary")
        self.browse_btn.setFixedHeight(32)
        self.browse_btn.setFixedWidth(72)
        self.browse_btn.clicked.connect(self._browse_path)
        download_layout.addWidget(self.browse_btn, 0, 2)
        self.time_prefix_cb = QCheckBox()
        self.time_prefix_cb.setChecked(
            bool(self.ctx.settings.get("save_term_prefix", False))
        )
        self.time_prefix_cb.toggled.connect(self._on_time_prefix_changed)
        download_layout.addWidget(
            self.time_prefix_cb, 1, 1, 1, 2, Qt.AlignmentFlag.AlignLeft
        )

        settings_layout.addWidget(self.download_group)
        layout.addWidget(
            self.settings_container, 0,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
        )
        layout.addStretch(1)

    def retranslate(self):
        self.appearance_group.setTitle(self.tr("appearance"))
        self.lang_label.setText(self.tr("lang_label"))
        self.theme_label.setText(self.tr("theme_label"))
        self.download_group.setTitle(self.tr("download_settings"))
        separator = ":" if self.ctx.i18n.lang == "en" else "："
        self.save_path_label.setText(self.tr("save_group").rstrip(":：") + separator)
        self.browse_btn.setText(self.tr("browse"))
        self.time_prefix_cb.setText(self.tr("time_prefix"))
        self.theme_cb.blockSignals(True)
        self.theme_cb.clear()
        self.theme_cb.addItem(self.tr("theme_dark"), "dark")
        self.theme_cb.addItem(self.tr("theme_light"), "light")
        self.theme_cb.addItem(self.tr("theme_system"), "system")
        theme = self.ctx.settings.get("theme", "dark")
        index = self.theme_cb.findData(theme)
        self.theme_cb.setCurrentIndex(index if index >= 0 else 0)
        self.theme_cb.blockSignals(False)

    def _save_path_setting(self):
        self.ctx.settings.set("save_path", self.save_path_input.text().strip())
        self.ctx.settings.save()

    def _browse_path(self):
        path = QFileDialog.getExistingDirectory(
            self,
            self.tr("browse_title"),
            self.save_path_input.text().strip(),
        )
        if path:
            self.save_path_input.setText(path)
            self._save_path_setting()

    def _on_time_prefix_changed(self, checked):
        self.ctx.settings.set("save_term_prefix", bool(checked))
        self.ctx.settings.save()

    def _on_lang_changed(self, idx):
        lang = LANG_MAP[idx] if 0 <= idx < len(LANG_MAP) else "zh"
        self.ctx.i18n.set_lang(lang)
        self.ctx.settings.set("lang", lang)
        self.ctx.settings.save()
        self.ctx.signals.language_changed.emit()

    def _on_theme_changed(self, idx):
        theme = self.theme_cb.itemData(idx) or "dark"
        self.ctx.settings.set("theme", theme)
        self.ctx.settings.save()
        apply_theme(QApplication.instance(), theme)
        self.ctx.signals.theme_changed.emit()
