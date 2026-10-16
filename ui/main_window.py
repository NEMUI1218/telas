"""主窗口：页面组装、导航、日志及账号控制器接入。"""

import os

from PySide6.QtCore import Qt, QByteArray, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QMainWindow,
)

from utils.app_context import AppContext
from utils.theme import apply_theme

from ui.account_controller import AccountController
from ui.account_dialog import AccountDialog
from ui.header import Header
from ui.sidebar import Sidebar
from ui.download_page import DownloadPage
from ui.quiz_page import QuizPage
from ui.settings_page import SettingsPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.ctx = AppContext()
        self.account_controller = AccountController(self.ctx, self)

        self._account_dialog = None
        self._log_visible = False

        app = QApplication.instance()

        apply_theme(
            app,
            self.ctx.settings.get("theme", "dark"),
        )

        app.styleHints().colorSchemeChanged.connect(
            self._on_system_color_scheme_changed
        )

        self._build_ui()
        self._connect_signals()
        self._retranslate_all()
        self._restore_ui_state()

        self.ctx.signals.status.emit(
            self.tr("status_ready")
        )

        if not os.environ.get("BB_SKIP_AUTO_LOGIN"):
            self.account_controller.auto_login()

    def tr(self, key, *args):
        return self.ctx.tr(key, *args)

    # ---------------------------------------------------------
    # 界面
    # ---------------------------------------------------------

    def _build_ui(self):
        self.setWindowTitle(self.tr("window_title"))
        self.setMinimumSize(740, 470)

        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar(self.ctx)
        root.addWidget(self.sidebar)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(20, 16, 20, 14)
        right_layout.setSpacing(14)

        self.header = Header(self.ctx)
        right_layout.addWidget(self.header)

        self.stack = QStackedWidget()

        self.download_page = DownloadPage(self.ctx)
        self.quiz_page = QuizPage(self.ctx)
        self.settings_page = SettingsPage(self.ctx)

        self.stack.addWidget(self.download_page)
        self.stack.addWidget(self.quiz_page)
        self.stack.addWidget(self.settings_page)

        right_layout.addWidget(self.stack, 1)

        self._build_log_panel(right_layout)

        root.addWidget(right, 1)

        self.toast_label = QLabel(central)
        self.toast_label.setObjectName("toast")
        self.toast_label.hide()

        self.toast_timer = QTimer(self)
        self.toast_timer.setSingleShot(True)
        self.toast_timer.setInterval(2600)
        self.toast_timer.timeout.connect(
            self.toast_label.hide
        )

        QShortcut(
            QKeySequence("Ctrl+1"),
            self,
            lambda: self._switch_page(0),
        )
        QShortcut(
            QKeySequence("Ctrl+2"),
            self,
            lambda: self._switch_page(1),
        )
        QShortcut(
            QKeySequence("Ctrl+3"),
            self,
            lambda: self._switch_page(2),
        )
        QShortcut(
            QKeySequence("Ctrl+L"),
            self,
            self._focus_login,
        )
        QShortcut(
            QKeySequence("Ctrl+Q"),
            self,
            self.close,
        )

    def _build_log_panel(self, parent_layout):
        self.log_panel = QFrame()
        self.log_panel.setObjectName("log_panel")

        layout = QVBoxLayout(self.log_panel)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        row = QHBoxLayout()
        row.setSpacing(6)

        self.log_toggle_btn = QPushButton()
        self.log_toggle_btn.setObjectName("ghost")
        self.log_toggle_btn.setFixedHeight(26)
        self.log_toggle_btn.clicked.connect(
            self._toggle_log
        )
        row.addWidget(self.log_toggle_btn)

        self.status_label = QLabel()
        self.status_label.setObjectName("status_text")
        self.status_label.setTextFormat(
            Qt.TextFormat.PlainText
        )
        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        row.addWidget(self.status_label, 1)

        self.clear_log_btn = QPushButton()
        self.clear_log_btn.setObjectName("ghost")
        self.clear_log_btn.setFixedHeight(26)
        self.clear_log_btn.clicked.connect(
            self._clear_log
        )
        row.addWidget(self.clear_log_btn)

        layout.addLayout(row)

        self.log_area = QTextEdit()
        self.log_area.setObjectName("log_area")
        self.log_area.setReadOnly(True)
        self.log_area.setFixedHeight(130)

        layout.addWidget(self.log_area)
        parent_layout.addWidget(self.log_panel)

    # ---------------------------------------------------------
    # 信号
    # ---------------------------------------------------------

    def _connect_signals(self):
        s = self.ctx.signals
        account = self.account_controller

        # 通用信号
        s.log.connect(self._append_log)
        s.status.connect(self._set_status)
        s.toast.connect(self._show_toast)

        s.set_text.connect(self._set_widget_text)
        s.clear_widget.connect(self._clear_widget)
        s.set_combo_items.connect(self._set_combo_items)
        s.set_progress.connect(self._set_progress)
        s.set_busy.connect(self._set_busy)

        s.language_changed.connect(
            self._on_language_changed
        )
        s.theme_changed.connect(
            self.sidebar.refresh_icons
        )

        # 账号控制器 → 原有全局信号
        account.login_state.connect(
            s.login_state.emit
        )
        account.login_busy.connect(
            s.login_busy.emit
        )
        account.account_info.connect(
            s.account_info.emit
        )

        # 原有全局信号 → 顶栏
        s.login_state.connect(
            self.header.set_login_status
        )
        s.login_busy.connect(
            self.header.set_login_busy
        )
        s.account_info.connect(
            self.header.set_account
        )

        # 账号控制器 → 主窗口
        account.courses_loaded.connect(
            self._on_courses_loaded
        )
        account.login_result.connect(
            self._on_login_result
        )
        account.message.connect(
            self._on_account_message
        )
        account.login_state.connect(
            self._on_login_state_changed
        )
        account.login_busy.connect(
            self._on_login_busy_changed
        )

        # 顶栏 → 账号控制器
        self.header.login_requested.connect(
            self._open_login_dialog
        )
        self.header.switch_requested.connect(
            self._switch_account
        )
        self.header.logout_requested.connect(
            self._logout_account
        )

        # 导航和课程
        self.sidebar.group.idClicked.connect(
            self._switch_page
        )
        self.header.course_selected.connect(
            self._on_course_selected
        )

        self.sidebar.btn_quiz.setChecked(True)
        self.stack.setCurrentWidget(self.quiz_page)

    # ---------------------------------------------------------
    # 页面导航
    # ---------------------------------------------------------

    def _switch_page(self, idx):
        pages = [
            self.quiz_page,
            self.download_page,
            self.settings_page,
        ]

        if 0 <= idx < len(pages):
            self.stack.setCurrentWidget(pages[idx])

            button = self.sidebar.group.button(idx)
            if button is not None:
                button.setChecked(True)

    def _focus_login(self):
        if self.account_controller.logged_in:
            self.header.course_cb.setFocus()
        else:
            self._open_login_dialog()

    # ---------------------------------------------------------
    # 账号弹窗
    # ---------------------------------------------------------

    def _open_login_dialog(self):
        if self.account_controller.busy:
            return

        if self._account_dialog is not None:
            self._account_dialog.raise_()
            self._account_dialog.activateWindow()
            return

        dialog = AccountDialog(self.ctx, self)
        self._account_dialog = dialog

        dialog.login_requested.connect(
            self.account_controller.login
        )

        try:
            result = dialog.exec()
        finally:
            self._account_dialog = None
            dialog.deleteLater()

        # 切换账号时取消：恢复原账号
        if (
            result != QDialog.DialogCode.Accepted
            and self.account_controller.switching
        ):
            self.account_controller.cancel_switch()

    def _on_login_busy_changed(self, busy):
        if self._account_dialog is not None:
            self._account_dialog.set_login_busy(busy)

    def _on_login_result(self, ok, message):
        dialog = self._account_dialog

        if dialog is not None:
            if ok:
                dialog.login_succeeded()
            else:
                dialog.login_failed(message)
            return

        if not ok:
            self.ctx.signals.toast.emit(
                message or self.tr("login_fail"),
                "error",
            )

    def _on_login_state_changed(self, logged_in):
        if logged_in:
            return

        self.header.reset()
        self.download_page.reset()

        self.ctx.current_course_id = ""
        self.ctx.current_course_name = ""

        self.ctx.signals.course_changed.emit("", "")

    def _on_account_message(self, key):
        message = self.tr(key)

        self.ctx.log(message)

        if key in (
            "login_ok",
            "session_ok",
            "logout_success",
        ):
            self.ctx.signals.toast.emit(
                message,
                "success",
            )

        elif key in (
            "restore_failed",
            "restore_unavailable",
        ):
            self.ctx.signals.toast.emit(
                message,
                "error",
            )

    # ---------------------------------------------------------
    # 切换账号
    # ---------------------------------------------------------

    def _switch_account(self):
        if self.account_controller.busy:
            return

        if not self.account_controller.begin_switch():
            return

        self._open_login_dialog()

    # ---------------------------------------------------------
    # 退出登录
    # ---------------------------------------------------------

    def _logout_account(self):
        if self.account_controller.busy:
            return

        if not self._confirm_logout():
            return

        self.account_controller.logout()

    def _confirm_logout(self):
        """自定义确认弹窗，保证确定在左、取消在右。"""

        dialog = QDialog(self)
        dialog.setModal(True)
        dialog.setWindowTitle(
            self.tr("logout_confirm_title")
        )
        dialog.setMinimumWidth(360)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(16)

        title = QLabel(
            self.tr("logout_confirm")
        )
        title.setWordWrap(True)

        font = title.font()
        font.setBold(True)
        title.setFont(font)

        layout.addWidget(title)

        warning = QLabel(
            self.tr("logout_warning")
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)

        buttons = QHBoxLayout()
        buttons.addStretch()

        confirm_btn = QPushButton(
            self.tr("confirm")
        )
        cancel_btn = QPushButton(
            self.tr("cancel")
        )

        confirm_btn.setMinimumWidth(82)
        cancel_btn.setMinimumWidth(82)

        # 明确指定顺序：左确定、右取消
        buttons.addWidget(confirm_btn)
        buttons.addWidget(cancel_btn)

        layout.addLayout(buttons)

        confirm_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)

        cancel_btn.setDefault(True)

        return (
            dialog.exec()
            == QDialog.DialogCode.Accepted
        )

    # ---------------------------------------------------------
    # 课程
    # ---------------------------------------------------------

    def _on_courses_loaded(self, courses):
        self.header.set_courses(courses)

    def _on_course_selected(self, course_id, course_name):
        course_id = str(course_id or "")
        course_name = str(course_name or "")

        if not course_id:
            self.ctx.current_course_id = ""
            self.ctx.current_course_name = ""

            self.download_page.reset()
            self.ctx.signals.course_changed.emit("", "")
            return

        self.ctx.current_course_id = course_id
        self.ctx.current_course_name = course_name

        self.ctx.signals.course_changed.emit(
            course_id,
            course_name,
        )

    # ---------------------------------------------------------
    # 日志与通用 UI
    # ---------------------------------------------------------

    def _append_log(self, text):
        self.log_area.append(text)

        scrollbar = self.log_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

        self._set_status(text)

    def _set_status(self, text):
        self.status_label.setText(
            str(text).split("\n", 1)[0][:200]
        )

    def _clear_log(self):
        self.log_area.clear()

    @staticmethod
    def _set_widget_text(widget, text):
        widget.setText(text)

    @staticmethod
    def _clear_widget(widget):
        widget.clear()

    @staticmethod
    def _set_progress(bar, value, fmt=None):
        if value < 0:
            bar.setValue(0)
            bar.setVisible(False)
        else:
            bar.setValue(value)
            bar.setVisible(True)

            if fmt:
                bar.setFormat(fmt)

    @staticmethod
    def _set_busy(widget, busy):
        if widget is not None:
            widget.setEnabled(not busy)

    def _set_combo_items(
        self,
        combo,
        items,
        select_index,
        placeholder_key,
    ):
        combo.blockSignals(True)
        combo.clear()

        combo.addItem(
            self.tr(placeholder_key)
        )
        combo.addItems(items)
        combo.setCurrentIndex(0)

        combo.setItemData(
            0,
            False,
            Qt.ItemDataRole.UserRole - 1,
        )

        combo.blockSignals(False)

    # ---------------------------------------------------------
    # 日志面板
    # ---------------------------------------------------------

    def _toggle_log(self):
        self._log_visible = not self._log_visible
        self._apply_log_visible()

    def _apply_log_visible(self):
        self.log_area.setVisible(
            self._log_visible
        )
        self.clear_log_btn.setVisible(
            self._log_visible
        )

        self.log_toggle_btn.setText(
            "▾  " + self.tr("log_hide")
            if self._log_visible
            else "▸  " + self.tr("log_show")
        )

    # ---------------------------------------------------------
    # Toast
    # ---------------------------------------------------------

    def _show_toast(self, text, kind="info"):
        if kind not in (
            "success",
            "error",
            "info",
        ):
            kind = "info"

        self.toast_label.setText(text)
        self.toast_label.setProperty(
            "kind",
            kind,
        )

        style = self.toast_label.style()
        style.unpolish(self.toast_label)
        style.polish(self.toast_label)

        self.toast_label.adjustSize()
        self._place_toast()
        self.toast_label.show()

        self.toast_timer.start()

    def _place_toast(self):
        central = self.centralWidget()

        self.toast_label.move(
            central.width()
            - self.toast_label.width()
            - 24,

            central.height()
            - self.toast_label.height()
            - 24,
        )

    # ---------------------------------------------------------
    # 国际化
    # ---------------------------------------------------------

    def _retranslate_all(self):
        self.setWindowTitle(
            self.tr("window_title")
        )

        self.header.retranslate()
        self.sidebar.retranslate()
        self.download_page.retranslate()
        self.quiz_page.retranslate()
        self.settings_page.retranslate()

        self.clear_log_btn.setText(
            self.tr("clear_log")
        )
        self.log_area.setPlaceholderText(
            self.tr("status_ready")
        )

        self._set_status(
            self.tr("status_ready")
        )
        self._apply_log_visible()

    def _on_language_changed(self):
        self._clear_log()
        self._retranslate_all()

        course_id = str(
            self.ctx.current_course_id or ""
        )

        if not course_id:
            return

        self.download_page.course_id = course_id
        self.download_page._start_scan()
        self.quiz_page.refresh_quizzes()

    # ---------------------------------------------------------
    # 主题
    # ---------------------------------------------------------

    def _on_system_color_scheme_changed(self, _scheme):
        if (
            self.ctx.settings.get("theme", "dark")
            == "system"
        ):
            apply_theme(
                QApplication.instance(),
                "system",
            )

            self.ctx.signals.theme_changed.emit()

    # ---------------------------------------------------------
    # 窗口状态
    # ---------------------------------------------------------

    def _restore_ui_state(self):
        geometry = self.ctx.settings.get("win_geo")

        if geometry:
            try:
                self.restoreGeometry(
                    QByteArray.fromBase64(
                        geometry.encode()
                    )
                )
            except Exception:
                pass

        self._log_visible = False
        self._apply_log_visible()

    def _save_state(self):
        geometry = bytes(
            self.saveGeometry().toBase64()
        ).decode()

        self.ctx.settings.set(
            "win_geo",
            geometry,
        )

        self.ctx.settings.set(
            "log_visible",
            "1" if self._log_visible else "0",
        )

        self.ctx.settings.save()

    def showEvent(self, event):
        super().showEvent(event)

        QTimer.singleShot(
            0,
            self._apply_minimum_window_frame,
        )

    def _apply_minimum_window_frame(self):
        if QApplication.platformName() != "cocoa":
            return

        frame = self.frameGeometry()
        content = self.geometry()

        extra_width = max(
            0,
            frame.width() - content.width(),
        )
        extra_height = max(
            0,
            frame.height() - content.height(),
        )

        self.setMinimumSize(
            740 - extra_width,
            470 - extra_height,
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if (
            hasattr(self, "toast_label")
            and self.toast_label.isVisible()
        ):
            self._place_toast()

    def closeEvent(self, event):
        self._save_state()

        self.account_controller.shutdown()

        super().closeEvent(event)
