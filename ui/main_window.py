"""主窗口：组装 侧边导航 + 顶部栏 + 页面栈 + 日志 + 状态栏 + 轻提示。"""
import os
import threading

from PySide6.QtCore import Qt, QByteArray, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QLabel, QPushButton, QFrame, QTextEdit, QApplication, QSizePolicy, QMessageBox,
)

from utils.app_context import AppContext
from utils.theme import apply_theme
from ui.header import Header
from ui.sidebar import Sidebar
from ui.download_page import DownloadPage
from ui.quiz_page import QuizPage
from ui.settings_page import SettingsPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ctx = AppContext()
        self._log_visible = False
        # 先套主题再建界面：侧栏图标是按当前主题的颜色画的
        apply_theme(QApplication.instance(), self.ctx.settings.get("theme", "dark"))
        QApplication.instance().styleHints().colorSchemeChanged.connect(
            self._on_system_color_scheme_changed
        )
        self._build_ui()
        self._connect_signals()
        self._retranslate_all()
        self._restore_ui_state()
        self.ctx.signals.status.emit(self.ctx.tr("status_ready"))
        if not os.environ.get("BB_SKIP_AUTO_LOGIN"):
            self._try_auto_login()

    def tr(self, key, *args):
        return self.ctx.tr(key, *args)

    def _on_system_color_scheme_changed(self, _scheme):
        if self.ctx.settings.get("theme", "dark") == "system":
            apply_theme(QApplication.instance(), "system")
            self.ctx.signals.theme_changed.emit()

    # ------------------------------------------------------------- 构建
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

        self.stack.addWidget(self.download_page)  # 索引 0
        self.stack.addWidget(self.quiz_page)       # 索引 1
        self.stack.addWidget(self.settings_page)  # 索引 2

        right_layout.addWidget(self.stack, 1)

        # ---- 底栏：状态行 + 可折叠日志 ----
        # 折叠时只剩一行：开关按钮、最新一条消息、清除按钮。它同时充当状态栏。
        self.log_panel = QFrame()
        self.log_panel.setObjectName("log_panel")
        log_layout = QVBoxLayout(self.log_panel)
        log_layout.setContentsMargins(6, 4, 6, 4)
        log_layout.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        self.log_toggle_btn = QPushButton()
        self.log_toggle_btn.setObjectName("ghost")
        self.log_toggle_btn.setFixedHeight(26)
        self.log_toggle_btn.clicked.connect(self._toggle_log)
        top_row.addWidget(self.log_toggle_btn)

        self.status_label = QLabel()
        self.status_label.setObjectName("status_text")
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        # 宽度忽略内容：再长的消息也只是被裁掉，不会把窗口撑宽
        self.status_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        top_row.addWidget(self.status_label, 1)

        self.clear_log_btn = QPushButton()
        self.clear_log_btn.setObjectName("ghost")
        self.clear_log_btn.setFixedHeight(26)
        self.clear_log_btn.clicked.connect(self._clear_log)
        top_row.addWidget(self.clear_log_btn)
        log_layout.addLayout(top_row)

        self.log_area = QTextEdit()
        self.log_area.setObjectName("log_area")
        self.log_area.setReadOnly(True)
        self.log_area.setFixedHeight(130)
        log_layout.addWidget(self.log_area)
        right_layout.addWidget(self.log_panel)

        root.addWidget(right, 1)

        self.toast_label = QLabel(central)
        self.toast_label.setObjectName("toast")
        self.toast_label.hide()
        self.toast_timer = QTimer(self)
        self.toast_timer.setSingleShot(True)
        self.toast_timer.setInterval(2600)
        self.toast_timer.timeout.connect(self.toast_label.hide)

        # ---- 快捷键 ----
        QShortcut(QKeySequence("Ctrl+1"), self, lambda: self._switch_page(0))
        QShortcut(QKeySequence("Ctrl+2"), self, lambda: self._switch_page(1))
        QShortcut(QKeySequence("Ctrl+3"), self, lambda: self._switch_page(2))
        QShortcut(QKeySequence("Ctrl+L"), self, self._focus_login)
        QShortcut(QKeySequence("Ctrl+Q"), self, self.close)

    def _focus_login(self):
        if self.header.stack.currentIndex() == 0:
            self.header.user_input.setFocus()
        else:
            self.header.course_cb.setFocus()

    def _connect_signals(self):
        s = self.ctx.signals
        s.log.connect(self._append_log)
        s.status.connect(self._set_status)
        s.toast.connect(self._show_toast)
        s.set_text.connect(self._set_widget_text)
        s.clear_widget.connect(self._clear_widget)
        s.set_combo_items.connect(self._set_combo_items)
        s.set_progress.connect(self._set_progress)
        s.set_busy.connect(self._set_busy)
        s.login_state.connect(self.header.set_login_status)
        s.login_busy.connect(self.header.set_login_busy)
        s.account_info.connect(self.header.set_account)
        s.language_changed.connect(self._on_language_changed)
        s.theme_changed.connect(self.sidebar.refresh_icons)

        self.sidebar.group.idClicked.connect(self._switch_page)
        self.header.login_requested.connect(self._on_login_clicked)
        self.header.switch_requested.connect(self._on_switch_account)
        self.header.course_selected.connect(self._on_course_selected)

        self.sidebar.btn_quiz.setChecked(True)
        self.stack.setCurrentWidget(self.quiz_page)

    def _switch_page(self, idx):
        pages = [
            self.quiz_page,
            self.download_page,
            self.settings_page,
        ]

        if 0 <= idx < len(pages):
            self.stack.setCurrentWidget(pages[idx])
            self.sidebar.group.button(idx).setChecked(True)
            
    # ------------------------------------------------------------- 通用信号处理
    def _append_log(self, text):
        self.log_area.append(text)
        sb = self.log_area.verticalScrollBar()
        sb.setValue(sb.maximum())
        self._set_status(text)

    def _set_status(self, text):
        # 状态行只显示一行；多行消息取第一行
        self.status_label.setText(text.split("\n", 1)[0][:200])

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

    def _set_combo_items(self, combo, items, select_index, placeholder_key):
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(self.tr(placeholder_key))
        combo.addItems(items)
        combo.setCurrentIndex(0)
        combo.setItemData(0, False, Qt.ItemDataRole.UserRole - 1)
        combo.blockSignals(False)

    # ------------------------------------------------------------- 可折叠日志
    def _toggle_log(self):
        self._log_visible = not self._log_visible
        self._apply_log_visible()

    def _apply_log_visible(self):
        self.log_area.setVisible(self._log_visible)
        self.clear_log_btn.setVisible(self._log_visible)
        self.log_toggle_btn.setText(
            "▾  " + self.tr("log_hide") if self._log_visible else "▸  " + self.tr("log_show"))

    # ------------------------------------------------------------- 轻提示
    def _show_toast(self, text, kind="info"):
        if kind not in ("success", "error", "info"):
            kind = "info"
        self.toast_label.setText(text)
        # 底色由 utils/theme.py 按 kind 属性决定；属性变了要重新套一次样式
        self.toast_label.setProperty("kind", kind)
        self.toast_label.style().unpolish(self.toast_label)
        self.toast_label.style().polish(self.toast_label)
        self.toast_label.adjustSize()
        self._place_toast()
        self.toast_label.show()
        self.toast_timer.start()

    def _place_toast(self):
        cw = self.centralWidget()
        self.toast_label.move(
            cw.width() - self.toast_label.width() - 24,
            cw.height() - self.toast_label.height() - 24,
        )

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._apply_minimum_window_frame)

    def _apply_minimum_window_frame(self):
        # macOS 的原生标题栏不属于 QWidget 内容区；让整个外框匹配参考尺寸。
        if QApplication.platformName() == "cocoa":
            frame = self.frameGeometry()
            content = self.geometry()
            extra_width = max(0, frame.width() - content.width())
            extra_height = max(0, frame.height() - content.height())
            self.setMinimumSize(740 - extra_width, 470 - extra_height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "toast_label") and self.toast_label.isVisible():
            self._place_toast()

    # ------------------------------------------------------------- 状态持久化
    def _restore_ui_state(self):
        geo = self.ctx.settings.get("win_geo")
        if geo:
            try:
                self.restoreGeometry(QByteArray.fromBase64(geo.encode()))
            except Exception:
                pass
        # 每次启动默认折叠；运行中仍可手动展开查看完整记录。
        self._log_visible = False
        self._apply_log_visible()

    def _save_state(self):
        self.ctx.settings.set("win_geo", bytes(self.saveGeometry().toBase64()).decode())
        self.ctx.settings.set("log_visible", "1" if self._log_visible else "0")
        self.ctx.settings.save()

    def closeEvent(self, event):
        self._save_state()
        super().closeEvent(event)

    # ------------------------------------------------------------- 登录
    def _on_login_clicked(self):
        user = self.header.get_user()
        pwd = self.header.get_pwd()
        if not user or not pwd:
            self.ctx.log(self.tr("enter_credentials"))
            return
        self._run_login(user, pwd)

    def _run_login(self, user, pwd):
        self.header.set_login_busy(True)
        threading.Thread(target=self._login_thread, args=(user, pwd), daemon=True).start()

    def _login_thread(self, user, pwd):
        try:
            ok = self.ctx.api.login(user, pwd)
        except Exception as e:
            self.ctx.log(str(e))
            ok = False
        if ok:
            self.ctx.settings.set("user", user)
            self.ctx.settings.set("pwd", pwd)
            self.ctx.settings.save()
            self.ctx.signals.login_state.emit(True)
            self._publish_account()  # 先显示学籍番号，姓名随后补上
            self.ctx.signals.toast.emit(self.tr("login_ok"), "success")
        else:
            self.ctx.signals.login_state.emit(False)
            self.ctx.signals.toast.emit(self.tr("login_fail"), "error")
        self.ctx.signals.login_busy.emit(False)
        if ok:
            self._load_courses()
            epoch = self.ctx.account_epoch
            try:
                me = self.ctx.api.get_me()
                if epoch == self.ctx.account_epoch:
                    self._publish_account(me)
            except Exception as e:
                self.ctx.log(str(e))

    def _publish_account(self, me=None):
        """把「是谁登录的」发给顶栏。

        姓名取自 users/me；服务器不返回学籍番号（它的 studentId 字段是别的内容），
        所以学籍番号用登录时输入、登录成功后存下来的那个。
        """
        name = ""
        if me:
            name = " ".join(
                str(p) for p in (me.get("familyName"), me.get("givenName")) if p)
        self.ctx.signals.account_info.emit(name, self.ctx.settings.get("user", ""))

    def _on_switch_account(self):
        """切换账号：退出当前账号，忘掉存下的账号密码，回到登录框。"""
        reply = QMessageBox.question(
            self, self.tr("confirm_title"), self.tr("switch_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        # 还在路上的后台线程（拉课程、扫描、读题目）凭这个数字知道自己的结果过期了
        self.ctx.account_epoch += 1
        self.ctx.api.logout()
        self.ctx.settings.remove("user")
        self.ctx.settings.remove("pwd")
        self.ctx.settings.save()
        self.ctx.courses = {}
        self.ctx.current_course_id = ""
        self.ctx.current_course_name = ""
        self.header.reset()
        self.download_page.reset()
        self.ctx.log(self.tr("switched_out"))
        self.header.user_input.setFocus()

    def _try_auto_login(self):
        threading.Thread(target=self._auto_login_thread, daemon=True).start()

    def _auto_login_thread(self):
        if self.ctx.api.load_session():
            self.ctx.log(self.tr("session_restoring"))
            me = self.ctx.api.get_me()
            if me and me.get("id"):
                self.ctx.log(self.tr("session_ok"))
                self.ctx.signals.login_state.emit(True)
                self._publish_account(me)
                self._load_courses()
                return
            self.ctx.log(self.tr("session_expired"))
        user = self.ctx.settings.get("user", "")
        pwd = self.ctx.settings.get("pwd", "")
        if user and pwd:
            self._login_thread(user, pwd)
        else:
            self.ctx.log(self.tr("enter_credentials"))

    def _load_courses(self):
        threading.Thread(target=self._load_courses_thread, daemon=True).start()

    def _load_courses_thread(self):
        epoch = self.ctx.account_epoch
        courses = self.ctx.api.get_courses()
        if epoch != self.ctx.account_epoch:
            return  # 这期间切换了账号，结果作废
        if not courses:
            self.ctx.log(self.tr("courses_count", 0))
            return
        self.ctx.courses = courses
        self.header.set_courses(courses)
        self.ctx.log(self.tr("courses_count", len(courses)))

    def _on_course_selected(self, course_id, course_name):
        if not course_id:
            self.ctx.current_course_id = ""
            self.ctx.current_course_name = ""
            self.download_page.reset()
            self.ctx.signals.course_changed.emit("", "")
            return
        self.ctx.current_course_id = course_id
        self.ctx.current_course_name = course_name
        self.ctx.signals.course_changed.emit(course_id, course_name)

    # ------------------------------------------------------------- 多语言
    def _retranslate_all(self):
        self.setWindowTitle(self.tr("window_title"))
        self.header.retranslate()
        self.sidebar.retranslate()
        self.download_page.retranslate()
        self.quiz_page.retranslate()
        self.settings_page.retranslate()
        self.clear_log_btn.setText(self.tr("clear_log"))
        self.log_area.setPlaceholderText(self.tr("status_ready"))
        self._set_status(self.tr("status_ready"))
        self._apply_log_visible()
        self._refresh_combo_placeholders()

    def _on_language_changed(self):
        """Clear old-language logs, translate every page, then reload its data."""
        self._clear_log()
        self._retranslate_all()

        course_id = str(self.ctx.current_course_id or "")
        if not course_id:
            return

        self.download_page.course_id = course_id
        self.download_page._start_scan()
        self.quiz_page.refresh_quizzes()

    def _refresh_combo_placeholders(self):
        for combo, key in [
            (self.header.course_cb, "placeholder_course"),
        ]:
            if combo.count() > 0:
                combo.blockSignals(True)
                combo.setItemText(0, self.tr(key))
                combo.blockSignals(False)
