"""顶部栏：账号状态、账号菜单、学期筛选与课程选择。"""

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QComboBox,
    QHBoxLayout,
    QVBoxLayout,
    QMenu,
    QSizePolicy,
)


class ElidedLabel(QLabel):
    """空间不足时省略文字，悬停显示完整内容。"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._full_text = ""

        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setMinimumWidth(0)
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )

    def set_full_text(self, text):
        self._full_text = str(text or "")
        self.setToolTip(self._full_text)
        self._refresh()

    def full_text(self):
        return self._full_text

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self):
        self.setText(
            self.fontMetrics().elidedText(
                self._full_text,
                Qt.TextElideMode.ElideRight,
                max(0, self.width()),
            )
        )


class Header(QWidget):
    """主窗口顶部栏。

    只负责界面展示与信号发送。
    不直接登录、不操作会话、不保存密码。
    """

    login_requested = Signal()
    switch_requested = Signal()
    logout_requested = Signal()

    course_selected = Signal(str, str)
    courses_loaded = Signal(object)

    def __init__(self, ctx, parent=None):
        super().__init__(parent)

        self.ctx = ctx
        self.courses = {}

        self._logged_in = False
        self._login_busy = False
        self._compact = False

        self._build_ui()

        self.courses_loaded.connect(
            self._populate_courses
        )

        self.retranslate()

    def tr(self, key, *args):
        return self.ctx.tr(key, *args)

    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------

    def _build_ui(self):
        self.setMinimumWidth(0)

        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Fixed,
        )

        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(0, 0, 0, 0)
        self.root.setSpacing(8)

        # 第一行
        self.top_row = QHBoxLayout()
        self.top_row.setContentsMargins(0, 0, 0, 0)
        self.top_row.setSpacing(8)

        self.account_widget = QWidget()
        self.account_widget.setMinimumWidth(0)

        self.account_layout = QHBoxLayout(
            self.account_widget
        )
        self.account_layout.setContentsMargins(
            0, 0, 0, 0
        )
        self.account_layout.setSpacing(8)

        # 登录状态按钮
        self.status_badge = QPushButton()
        self.status_badge.setObjectName(
            "login_status"
        )
        self.status_badge.setFixedHeight(32)
        self.status_badge.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.account_layout.addWidget(
            self.status_badge
        )

        # 姓名 / 学籍番号
        self.account_label = ElidedLabel()
        self.account_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter
            | Qt.AlignmentFlag.AlignLeft
        )

        self.account_layout.addWidget(
            self.account_label,
            1,
        )

        self.top_row.addWidget(
            self.account_widget,
            1,
        )

        # 学期和课程选择容器
        self.selector_widget = QWidget()
        self.selector_widget.setMinimumWidth(0)

        self.selector_layout = QHBoxLayout(
            self.selector_widget
        )
        self.selector_layout.setContentsMargins(
            0, 0, 0, 0
        )
        self.selector_layout.setSpacing(8)

        self.prefix_label = QLabel()
        self.course_label = QLabel()

        self.prefix_cb = QComboBox()
        self.prefix_cb.setFixedHeight(32)
        self.prefix_cb.setMinimumWidth(105)
        self.prefix_cb.setMaximumWidth(180)

        self.course_cb = QComboBox()
        self.course_cb.setFixedHeight(32)
        self.course_cb.setMinimumWidth(130)
        self.course_cb.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.selector_layout.addWidget(
            self.prefix_label
        )
        self.selector_layout.addWidget(
            self.prefix_cb
        )
        self.selector_layout.addWidget(
            self.course_label
        )
        self.selector_layout.addWidget(
            self.course_cb,
            1,
        )

        self.top_row.addWidget(
            self.selector_widget,
            2,
        )

        self.root.addLayout(self.top_row)

        # 第二行：窄窗口时使用
        self.compact_row = QHBoxLayout()
        self.compact_row.setContentsMargins(
            0, 0, 0, 0
        )
        self.compact_row.setSpacing(0)

        self.root.addLayout(self.compact_row)

        # 账号菜单
        self.account_menu = QMenu(self)

        self.login_action = (
            self.account_menu.addAction("")
        )
        self.switch_action = (
            self.account_menu.addAction("")
        )
        self.logout_action = (
            self.account_menu.addAction("")
        )

        self.status_badge.setMenu(
            self.account_menu
        )

        # 信号
        self.login_action.triggered.connect(
            self.login_requested.emit
        )

        self.switch_action.triggered.connect(
            self.switch_requested.emit
        )

        self.logout_action.triggered.connect(
            self.logout_requested.emit
        )

        self.prefix_cb.currentIndexChanged.connect(
            self._rebuild_course_options
        )

        self.course_cb.currentIndexChanged.connect(
            self._on_course_changed
        )

        self._update_badge()
        self._update_menu()

    # ---------------------------------------------------------
    # 登录状态
    # ---------------------------------------------------------

    def set_login_status(self, ok):
        self._logged_in = bool(ok)

        if not ok:
            self.account_label.set_full_text("")

        self._update_badge()
        self._update_menu()

    def set_login_busy(self, busy):
        self._login_busy = bool(busy)

        self.status_badge.setEnabled(
            not self._login_busy
        )

    def set_account(self, name, login_id):
        parts = [
            str(part).strip()
            for part in (name, login_id)
            if part and str(part).strip()
        ]

        self.account_label.set_full_text(
            " · ".join(parts)
        )

    def _update_badge(self):
        key = (
            "logged_in"
            if self._logged_in
            else "logged_out"
        )

        self.status_badge.setText(
            "●  " + self.tr(key) + "  ▾"
        )

        self.status_badge.setProperty(
            "state",
            "on" if self._logged_in else "off",
        )

        self.status_badge.style().unpolish(
            self.status_badge
        )
        self.status_badge.style().polish(
            self.status_badge
        )

    def _update_menu(self):
        self.login_action.setVisible(
            not self._logged_in
        )

        self.switch_action.setVisible(
            self._logged_in
        )

        self.logout_action.setVisible(
            self._logged_in
        )

    # ---------------------------------------------------------
    # 课程
    # ---------------------------------------------------------

    def set_courses(self, courses):
        """可从后台线程调用，通过信号更新界面。"""

        self.courses_loaded.emit(
            courses or {}
        )

    @staticmethod
    def _term_prefix(course_name):
        match = re.match(
            r"^\s*(\d{4}(?:年度)?\s*(?:前期|後期|后期))",
            str(course_name),
        )

        if not match:
            return None

        return re.sub(
            r"\s+",
            "",
            match.group(1),
        )

    @classmethod
    def _display_course_name(cls, course_name):
        if cls._term_prefix(course_name) is None:
            return course_name

        return re.sub(
            r"^\s*\d{4}(?:年度)?\s*(?:前期|後期|后期)\s*",
            "",
            course_name,
        ).strip()

    def _populate_courses(self, courses):
        self.courses = dict(courses or {})

        names = list(self.courses)

        terms = {
            term
            for name in names
            if (
                term := self._term_prefix(name)
            ) is not None
        }

        terms = sorted(
            terms,
            key=lambda term: (
                int(
                    re.search(
                        r"\d{4}",
                        term,
                    ).group()
                ),
                2
                if (
                    "後期" in term
                    or "后期" in term
                )
                else 1,
            ),
            reverse=True,
        )

        self.prefix_cb.blockSignals(True)
        self.prefix_cb.clear()

        self.prefix_cb.addItem(
            self.tr("all_terms"),
            "",
        )

        for term in terms:
            self.prefix_cb.addItem(
                term,
                term,
            )

        if any(
            self._term_prefix(name) is None
            for name in names
        ):
            self.prefix_cb.addItem(
                self.tr("other_term"),
                "__other__",
            )

        # 默认显示最近学期
        self.prefix_cb.setCurrentIndex(
            1 if terms else 0
        )

        self.prefix_cb.blockSignals(False)

        self._rebuild_course_options()

    def _rebuild_course_options(self, *_):
        term = (
            self.prefix_cb.currentData()
            or ""
        )

        if term == "__other__":
            names = [
                name
                for name in self.courses
                if self._term_prefix(name) is None
            ]

        elif term:
            names = [
                name
                for name in self.courses
                if self._term_prefix(name) == term
            ]

        else:
            names = list(self.courses)

        old_name = (
            self.course_cb.currentData()
            if self.course_cb.currentIndex() > 0
            else None
        )

        self.course_cb.blockSignals(True)
        self.course_cb.clear()

        self.course_cb.addItem(
            self.tr("placeholder_course"),
            None,
        )

        for name in names:
            self.course_cb.addItem(
                self._display_course_name(name),
                name,
            )

        if old_name in names:
            self.course_cb.setCurrentIndex(
                names.index(old_name) + 1
            )
        else:
            self.course_cb.setCurrentIndex(0)

        self.course_cb.blockSignals(False)

        self._on_course_changed()

    def _on_course_changed(self, *_):
        name = self.course_cb.currentData()

        if not name or name not in self.courses:
            self.course_selected.emit("", "")
            return

        course = self.courses[name]

        if isinstance(course, dict):
            course_id = course.get("id", "")
        else:
            course_id = course

        self.course_selected.emit(
            str(course_id),
            str(name),
        )

    # ---------------------------------------------------------
    # 重置
    # ---------------------------------------------------------

    def reset(self):
        self.courses = {}

        self.set_login_status(False)
        self.set_account("", "")

        self.prefix_cb.blockSignals(True)
        self.course_cb.blockSignals(True)

        self.prefix_cb.clear()
        self.course_cb.clear()

        self.prefix_cb.blockSignals(False)
        self.course_cb.blockSignals(False)

        self.prefix_cb.addItem(
            self.tr("all_terms"),
            "",
        )

        self.course_cb.addItem(
            self.tr("placeholder_course"),
            None,
        )

        self.course_selected.emit("", "")

    # ---------------------------------------------------------
    # 国际化
    # ---------------------------------------------------------

    def retranslate(self):
        tr = self.ctx.tr

        self.login_action.setText(
            tr("login_account")
        )

        self.switch_action.setText(
            tr("switch_account")
        )

        self.logout_action.setText(
            tr("logout")
        )

        self.prefix_label.setText(
            tr("prefix_filter")
        )

        self.course_label.setText(
            tr("course_name")
        )

        for index in range(
            self.prefix_cb.count()
        ):
            data = self.prefix_cb.itemData(index)

            if data == "":
                self.prefix_cb.setItemText(
                    index,
                    tr("all_terms"),
                )

            elif data == "__other__":
                self.prefix_cb.setItemText(
                    index,
                    tr("other_term"),
                )

        if self.course_cb.count():
            self.course_cb.setItemText(
                0,
                tr("placeholder_course"),
            )

        self._update_badge()
        self._update_menu()

    # ---------------------------------------------------------
    # 响应式布局
    # ---------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)

        self._update_responsive_layout()

    def _update_responsive_layout(self):
        """窗口较窄时将课程选择移动到第二行。"""

        compact = self.width() < 650

        if compact == self._compact:
            return

        self._compact = compact

        if compact:
            self.top_row.removeWidget(
                self.selector_widget
            )

            self.compact_row.addWidget(
                self.selector_widget
            )

        else:
            self.compact_row.removeWidget(
                self.selector_widget
            )

            self.top_row.addWidget(
                self.selector_widget,
                2,
            )

        self.updateGeometry()
