"""顶部栏：账号状态菜单 + 学期与课程选择。

保留原有的：
1. 课程框十个全角字符宽度
2. 学期框固定宽度
3. 姓名和学籍番号完整显示
4. 根据实际内容宽度自动换行
5. 学期筛选和课程选择逻辑
"""

import re

from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtWidgets import (
    QWidget,
    QBoxLayout,
    QLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QSizePolicy,
    QStyle,
    QStyleOptionComboBox,
    QMenu,
)


class ElidedLabel(QLabel):
    """账号信息标签。

    保留原来的完整文字与悬停提示接口。
    账号信息优先完整显示，由外层布局负责换行。
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._full_text = ""

        self.setTextFormat(
            Qt.TextFormat.PlainText
        )

        self.setWordWrap(False)

        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Preferred,
        )

    def set_full_text(self, text):
        self._full_text = str(text or "")

        self.setText(self._full_text)
        self.setToolTip(self._full_text)

        self.updateGeometry()

    def full_text(self):
        return self._full_text


class Header(QWidget):

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

        self._compact = True
        self._updating_layout = False

        self._build_ui()

        self.courses_loaded.connect(
            self._populate_courses
        )

        self.retranslate()

    def tr(self, key, *args):
        return self.ctx.tr(key, *args)

    # =========================================================
    # UI
    # =========================================================

    def _build_ui(self):

        # 保留原来的 QBoxLayout
        # 它可以在横向和纵向之间动态切换

        root = QBoxLayout(
            QBoxLayout.Direction.TopToBottom,
            self,
        )

        root.setContentsMargins(0, 0, 9, 0)
        root.setSpacing(8)

        root.setSizeConstraint(
            QLayout.SizeConstraint.SetNoConstraint
        )

        self._root_layout = root

        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Fixed,
        )

        # -----------------------------------------------------
        # 账号区域
        # -----------------------------------------------------

        self.account_widget = QWidget()

        self.account_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        account_layout = QHBoxLayout(
            self.account_widget
        )

        account_layout.setContentsMargins(
            0, 0, 0, 0
        )

        account_layout.setSpacing(8)

        # 登录状态
        self.status_badge = QPushButton()

        self.status_badge.setObjectName(
            "login_status"
        )

        self.status_badge.setFixedHeight(32)

        self.status_badge.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.status_badge.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )

        account_layout.addWidget(
            self.status_badge
        )

        # 姓名和学籍番号
        self.account_label = ElidedLabel()

        self.account_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )

        account_layout.addWidget(
            self.account_label
        )

        account_layout.addStretch(1)

        root.addWidget(
            self.account_widget,
            1,
        )

        # -----------------------------------------------------
        # 账号菜单
        # -----------------------------------------------------

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

        self.login_action.triggered.connect(
            self.login_requested.emit
        )

        self.switch_action.triggered.connect(
            self.switch_requested.emit
        )

        self.logout_action.triggered.connect(
            self.logout_requested.emit
        )

        # -----------------------------------------------------
        # 学期选择
        # -----------------------------------------------------

        self.prefix_label = QLabel()

        self.prefix_label.setObjectName(
            "field_label"
        )

        self.prefix_cb = QComboBox()

        self.prefix_cb.setFixedHeight(32)

        self.prefix_cb.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy
            .AdjustToMinimumContentsLengthWithIcon
        )

        self.prefix_cb.setMinimumContentsLength(6)

        self.prefix_cb.currentIndexChanged.connect(
            self._on_prefix_changed
        )

        # -----------------------------------------------------
        # 课程选择
        # -----------------------------------------------------

        self.course_label = QLabel()

        self.course_label.setObjectName(
            "field_label"
        )

        self.course_cb = QComboBox()

        self.course_cb.setFixedHeight(32)

        self.course_cb.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy
            .AdjustToMinimumContentsLengthWithIcon
        )

        # 恢复原来的十字符设定
        self.course_cb.setMinimumContentsLength(10)

        self.course_cb.currentIndexChanged.connect(
            self._on_course_index_changed
        )

        # -----------------------------------------------------
        # 共用课程选择区域
        # -----------------------------------------------------

        self._course_controls = QWidget()

        course_layout = QHBoxLayout(
            self._course_controls
        )

        course_layout.setContentsMargins(
            0, 0, 0, 0
        )

        course_layout.setSpacing(16)

        for index, (label, combo) in enumerate(
            (
                (self.prefix_label, self.prefix_cb),
                (self.course_label, self.course_cb),
            )
        ):

            label.setSizePolicy(
                QSizePolicy.Policy.Fixed,
                QSizePolicy.Policy.Preferred,
            )

            pair = QWidget()

            pair_layout = QHBoxLayout(pair)

            pair_layout.setContentsMargins(
                0, 0, 0, 0
            )

            pair_layout.setSpacing(6)

            pair_layout.addWidget(label)
            pair_layout.addWidget(combo, 1)

            course_layout.addWidget(
                pair,
                index,
            )

            if index == 0:
                self._term_pair = pair
            else:
                self._course_pair = pair

        root.addWidget(
            self._course_controls,
            0,
            Qt.AlignmentFlag.AlignRight,
        )

        self._update_badge_text()
        self._update_menu()

    # =========================================================
    # 课程选择框宽度
    # =========================================================

    @staticmethod
    def _combo_text_width(combo, sample):
        """计算文字、箭头、边框和内边距的实际宽度。"""

        combo.ensurePolished()

        option = QStyleOptionComboBox()

        option.initFrom(combo)

        option.editable = combo.isEditable()
        option.frame = True

        option.rect = QRect(
            0,
            0,
            1000,
            combo.height(),
        )

        text_rect = combo.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxEditField,
            combo,
        )

        decoration_width = (
            option.rect.width()
            - text_rect.width()
        )

        return (
            combo.fontMetrics().horizontalAdvance(
                sample
            )
            + decoration_width
        )

    def _update_selector_widths(self):
        """恢复原来的固定宽度算法。"""

        # 学期：2026後期
        term_width = self._combo_text_width(
            self.prefix_cb,
            "2026後期",
        )

        # 课程：十个全角字符
        course_width = self._combo_text_width(
            self.course_cb,
            "漢" * 10,
        )

        self.prefix_cb.setFixedWidth(
            term_width
        )

        self.course_cb.setFixedWidth(
            course_width
        )

        self.prefix_label.ensurePolished()
        self.course_label.ensurePolished()

        term_pair_width = (
            self.prefix_label.sizeHint().width()
            + 6
            + term_width
        )

        course_label_width = (
            self.course_label.sizeHint().width()
            + 6
        )

        self._term_pair.setFixedWidth(
            term_pair_width
        )

        self._course_pair.setFixedWidth(
            course_label_width
            + course_width
        )

        self._course_controls.setFixedWidth(
            term_pair_width
            + 16
            + course_label_width
            + course_width
        )

        self._course_controls.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )

        self._root_layout.setStretch(0, 1)
        self._root_layout.setStretch(1, 0)

        self._root_layout.setAlignment(
            self._course_controls,
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter,
        )

        self._update_responsive_layout()

    # =========================================================
    # 响应式布局
    # =========================================================

    def _update_responsive_layout(self):
        """根据账号完整文字和课程框实际宽度决定是否换行。"""

        if self._updating_layout:
            return

        self._updating_layout = True

        try:
            account_layout = (
                self.account_widget.layout()
            )

            account_layout.invalidate()

            # 使用完整账号信息的实际宽度
            account_width = (
                account_layout.sizeHint().width()
            )

            gap = (
                self.prefix_label
                .fontMetrics()
                .horizontalAdvance("　　")
            )

            margins = (
                self._root_layout.contentsMargins()
            )

            available_width = (
                self.width()
                - margins.left()
                - margins.right()
            )

            required_width = (
                account_width
                + gap
                + self._course_controls.minimumWidth()
            )

            # 不再使用固定的 650px 判断
            compact = (
                available_width < required_width
            )

            changed = (
                compact != self._compact
            )

            if changed:
                self._compact = compact

                self._root_layout.setDirection(
                    QBoxLayout.Direction.TopToBottom
                    if compact
                    else QBoxLayout.Direction.LeftToRight
                )

            self._root_layout.setSpacing(
                8 if compact else gap
            )

            if changed:
                self.updateGeometry()

        finally:
            self._updating_layout = False

    def resizeEvent(self, event):
        super().resizeEvent(event)

        self._update_responsive_layout()

    # =========================================================
    # 账号状态
    # =========================================================

    def _update_badge_text(self):
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

        style = self.status_badge.style()

        style.unpolish(self.status_badge)
        style.polish(self.status_badge)

        self.status_badge.updateGeometry()

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

    def set_login_status(self, ok):
        self._logged_in = bool(ok)

        if not ok:
            self.account_label.set_full_text("")

        self._update_badge_text()
        self._update_menu()

        self._update_responsive_layout()

    def set_login_busy(self, busy):
        self._login_busy = bool(busy)

        self.status_badge.setEnabled(
            not busy
        )

    def set_account(self, name, login_id):
        """完整显示姓名和学籍番号。"""

        parts = [
            str(part).strip()
            for part in (name, login_id)
            if part and str(part).strip()
        ]

        self.account_label.set_full_text(
            " · ".join(parts)
        )

        self._update_responsive_layout()

    # =========================================================
    # 重置
    # =========================================================

    def reset(self):
        self.set_login_status(False)

        self.set_account("", "")

        self.courses = {}

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

    # =========================================================
    # 课程
    # =========================================================

    def set_courses(self, courses):
        self.courses_loaded.emit(
            courses or {}
        )

    @staticmethod
    def _term_prefix(course_name):
        match = re.match(
            r"^\s*(\d{4}(?:年度)?\s*(?:前期|後期|后期))",
            str(course_name),
        )

        return (
            re.sub(r"\s+", "", match.group(1))
            if match
            else None
        )

    @classmethod
    def _display_course_name(cls, course_name):
        """去掉学期前缀，但保留完整课程名称。"""

        if cls._term_prefix(course_name) is None:
            return course_name

        return re.sub(
            r"^\s*\d{4}(?:年度)?\s*(?:前期|後期|后期)\s*",
            "",
            course_name,
        ).strip()

    def _populate_courses(self, courses):
        self.courses = dict(courses or {})

        names = list(self.courses.keys())

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

        # 默认最近学期
        self.prefix_cb.setCurrentIndex(
            1 if terms else 0
        )

        self.prefix_cb.blockSignals(False)

        self._rebuild_course_options()

    def _rebuild_course_options(self):
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
            else ""
        )

        self.course_cb.blockSignals(True)
        self.course_cb.clear()

        self.course_cb.addItem(
            self.tr("placeholder_course"),
            None,
        )

        for name in names:
            # 显示完整课程名，选择框保持固定宽度
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

        if old_name and old_name not in names:
            self.course_selected.emit("", "")

    def _on_prefix_changed(self, _index):
        self._rebuild_course_options()

    def _on_course_index_changed(self, *_):
        idx = self.course_cb.currentIndex()

        if idx <= 0:
            self.course_selected.emit("", "")
            return

        name = self.course_cb.currentData()

        if name not in self.courses:
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

    # =========================================================
    # 国际化
    # =========================================================

    def retranslate(self):
        self.course_label.setText(
            self.tr("course_name")
        )

        self.prefix_label.setText(
            self.tr("prefix_filter")
        )

        self.login_action.setText(
            self.tr("login_account")
        )

        self.switch_action.setText(
            self.tr("switch_account")
        )

        self.logout_action.setText(
            self.tr("logout")
        )

        if self.prefix_cb.count():
            self.prefix_cb.setItemText(
                0,
                self.tr("all_terms"),
            )

            for index in range(
                1,
                self.prefix_cb.count(),
            ):
                if (
                    self.prefix_cb.itemData(index)
                    == "__other__"
                ):
                    self.prefix_cb.setItemText(
                        index,
                        self.tr("other_term"),
                    )

        if self.course_cb.count():
            self.course_cb.setItemText(
                0,
                self.tr("placeholder_course"),
            )

        self._update_badge_text()

        # 语言切换后重新计算真实宽度
        self._update_selector_widths()
