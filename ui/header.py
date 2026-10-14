"""顶部栏：登录框（页0）/ 已登录状态（页1） + 课程选择。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QStackedWidget,
    QSizePolicy,
)


class ElidedLabel(QLabel):
    """放不下时用省略号截断的标签，完整内容在悬停提示里。

    宽度忽略内容：再长的姓名也不会把顶栏撑宽。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_text = ""
        # 姓名来自服务器，按纯文本显示
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def set_full_text(self, text):
        self._full_text = text
        self.setToolTip(text)
        self._refresh()

    def full_text(self):
        return self._full_text

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self):
        self.setText(self.fontMetrics().elidedText(
            self._full_text, Qt.TextElideMode.ElideRight, max(0, self.width())))


class Header(QWidget):
    login_requested = Signal()
    switch_requested = Signal()
    course_selected = Signal(str, str)  # (course_id, course_name)

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.courses = {}
        self._logged_in = False
        self._build_ui()
        self.retranslate()

    def tr(self, key, *args):
        return self.ctx.tr(key, *args)

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setFixedHeight(32)
        # 登录后这一格要放下「已登录 + 姓名 · 学籍番号 + 切换账号」，
        # 所以多出来的宽度由它和课程下拉框按 3:2 分
        root.addWidget(self.stack, 3)

        # ---- 页 0：登录 ----
        login_page = QWidget()
        login_layout = QHBoxLayout(login_page)
        login_layout.setContentsMargins(0, 0, 0, 0)
        login_layout.setSpacing(8)

        # 用户名和密码不单独放标签，用输入框里的占位文字和悬停提示代替：
        # 日文、英文的标签较长，带标签时登录栏在最小窗口宽度下放不下。
        self.user_input = QLineEdit()
        self.user_input.setFixedWidth(150)
        self.user_input.setFixedHeight(32)
        if self.ctx.settings.get("user"):
            self.user_input.setText(self.ctx.settings.get("user"))
        login_layout.addWidget(self.user_input)

        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_input.setFixedWidth(150)
        self.pwd_input.setFixedHeight(32)
        if self.ctx.settings.get("pwd"):
            self.pwd_input.setText(self.ctx.settings.get("pwd"))
        self.pwd_input.returnPressed.connect(self.login_requested.emit)
        login_layout.addWidget(self.pwd_input)

        self.login_btn = QPushButton()
        self.login_btn.setFixedHeight(32)
        self.login_btn.setMinimumWidth(88)
        self.login_btn.clicked.connect(self.login_requested.emit)
        login_layout.addWidget(self.login_btn)
        login_layout.addStretch()

        # ---- 页 1：已登录 ----
        logged_in_page = QWidget()
        logged_layout = QHBoxLayout(logged_in_page)
        logged_layout.setContentsMargins(0, 0, 0, 0)
        logged_layout.setSpacing(8)

        self.status_badge = QLabel()
        self.status_badge.setObjectName("status_badge")
        logged_layout.addWidget(self.status_badge)

        # 是谁登录的：「姓名 · 学籍番号」。占满这一页剩下的宽度，放不下就截断。
        self.account_label = ElidedLabel()
        logged_layout.addWidget(self.account_label, 1)

        self.switch_btn = QPushButton()
        self.switch_btn.setObjectName("ghost")
        self.switch_btn.setFixedHeight(28)
        self.switch_btn.clicked.connect(self.switch_requested.emit)
        logged_layout.addWidget(self.switch_btn)

        # ---- 共用课程选择（放在 stack 之后） ----
        self.course_label = QLabel()
        self.course_label.setObjectName("field_label")
        self.course_cb = QComboBox()
        self.course_cb.setFixedHeight(32)
        self.course_cb.setMinimumWidth(200)
        self.course_cb.setMaximumWidth(400)
        self.course_cb.currentIndexChanged.connect(self._on_course_index_changed)

        self.stack.addWidget(login_page)        # page 0
        self.stack.addWidget(logged_in_page)    # page 1
        self.stack.setCurrentIndex(0)

        # 课程选择始终可见，追加到 stack 右侧
        root.addSpacing(16)
        root.addWidget(self.course_label)
        root.addSpacing(8)
        root.addWidget(self.course_cb, 2)

    def retranslate(self):
        # 文案键带着结尾的冒号（"用户名:"），做占位文字时去掉
        for widget, key in ((self.user_input, "username"), (self.pwd_input, "password")):
            text = self.tr(key).rstrip(":： ")
            widget.setPlaceholderText(text)
            widget.setToolTip(text)
        self.course_label.setText(self.tr("course"))
        self.switch_btn.setText(self.tr("switch_account"))
        if self.login_btn.isEnabled():
            self.login_btn.setText(self.tr("login_btn"))
        self._update_badge_text()

    def _update_badge_text(self):
        key = "logged_in" if self._logged_in else "logged_out"
        self.status_badge.setText("●  " + self.tr(key))
        # 颜色由 utils/theme.py 按 state 属性决定；属性变了要重新套一次样式
        self.status_badge.setProperty("state", "on" if self._logged_in else "off")
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)

    def set_login_status(self, ok):
        self._logged_in = ok
        self._update_badge_text()
        if not ok:
            self.account_label.set_full_text("")
        self.stack.setCurrentIndex(1 if ok else 0)

    def reset(self):
        """切换账号：回到未登录的初始状态，清空账号显示、输入框和课程列表。"""
        self.set_login_status(False)
        self.user_input.clear()
        self.pwd_input.clear()
        self.courses = {}
        self.course_cb.blockSignals(True)
        self.course_cb.clear()
        self.course_cb.blockSignals(False)

    def set_account(self, name, login_id):
        """登录后显示是谁：姓名和学籍番号，哪个有就显示哪个。"""
        parts = [p.strip() for p in (name, login_id) if p and p.strip()]
        self.account_label.set_full_text(" · ".join(parts))

    def set_login_busy(self, busy):
        self.login_btn.setEnabled(not busy)
        self.login_btn.setText(self.tr("login_busy") if busy else self.tr("login_btn"))

    def set_courses(self, courses):
        self.courses = courses
        self.ctx.signals.set_combo_items.emit(
            self.course_cb, list(courses.keys()), -1, "placeholder_course")

    def _on_course_index_changed(self):
        idx = self.course_cb.currentIndex()
        if idx <= 0:
            return
        name = self.course_cb.currentText()
        if name in self.courses:
            self.course_selected.emit(self.courses[name]["id"], name)

    def get_user(self):
        return self.user_input.text().strip()

    def get_pwd(self):
        return self.pwd_input.text()
