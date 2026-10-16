"""顶部栏：账号状态下拉菜单 + 课程选择。"""

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
    """放不下时用省略号截断，完整内容显示在悬停提示中。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_text = ""
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred,
        )

    def set_full_text(self, text):
        self._full_text = text
        self.setToolTip(text)
        self._refresh()
        self.updateGeometry()

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setWidth(
            self.fontMetrics().horizontalAdvance(self._full_text)
        )
        return hint

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        hint.setWidth(0)
        return hint

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

        self._build_ui()

        self.courses_loaded.connect(
            self._populate_courses
        )

        self.retranslate()

    def tr(self, key, *args):
        return self.ctx.tr(key, *args)

    def _menu_text(self, zh, ja, en):
        """根据当前语言返回账号菜单文字。"""
        lang = str(
            self.ctx.settings.get("lang", "zh")
        ).lower()

        if lang.startswith("ja"):
            return ja

        if lang.startswith("en"):
            return en

        return zh

    def _build_ui(self):

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
        self._compact = True
        self._updating_layout = False

        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Fixed,
        )

        # ==================================================
        # 账号状态区域
        # ==================================================

        self.account_widget = QWidget()

        account_layout = QHBoxLayout(
            self.account_widget
        )

        account_layout.setContentsMargins(
            9, 0, 0, 0
        )

        account_layout.setSpacing(8)

        # 账号状态按钮
        self.status_badge = QPushButton()

        self.status_badge.setObjectName(
            "status_badge"
        )

        self.status_badge.setFixedHeight(30)

        self.status_badge.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.status_badge.clicked.connect(
            self._show_account_menu
        )

        account_layout.addWidget(
            self.status_badge
        )

        # 姓名和学号
        self.account_label = ElidedLabel()

        account_layout.addWidget(
            self.account_label
        )

        account_layout.addStretch(1)

        root.addWidget(
            self.account_widget,
            1,
        )

        # ==================================================
        # 课程选择区域
        # ==================================================

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

        self.course_cb.setMinimumContentsLength(10)

        self.course_cb.currentIndexChanged.connect(
            self._on_course_index_changed
        )

        # 课程选择布局
        self._course_controls = QWidget()

        course_layout = QHBoxLayout(
            self._course_controls
        )

        course_layout.setContentsMargins(
            0, 0, 0, 0
        )

        course_layout.setSpacing(16)

        for index, (label, combo) in enumerate((
            (self.prefix_label, self.prefix_cb),
            (self.course_label, self.course_cb),
        )):

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

    # ==================================================
    # 账号菜单
    # ==================================================

    def _show_account_menu(self):

        if self._login_busy:
            return

        menu = QMenu(self)

        if self._logged_in:

            switch_action = menu.addAction(
                self._menu_text(
                    "切换账号",
                    "アカウントを切り替える",
                    "Switch account",
                )
            )

            logout_action = menu.addAction(
                self._menu_text(
                    "退出登录",
                    "ログアウト",
                    "Log out",
                )
            )

        else:

            login_action = menu.addAction(
                self._menu_text(
                    "登录账号",
                    "ログイン",
                    "Log in",
                )
            )

        position = self.status_badge.mapToGlobal(
            self.status_badge.rect().bottomLeft()
        )

        selected = menu.exec(position)

        if selected is None:
            return

        if self._logged_in:

            if selected == switch_action:
                self.switch_requested.emit()

            elif selected == logout_action:
                self.logout_requested.emit()

        else:

            if selected == login_action:
                self.login_requested.emit()

    # ==================================================
    # 账号状态
    # ==================================================

    def _update_badge_text(self):

        key = (
            "logged_in"
            if self._logged_in
            else "logged_out"
        )

        text = "●  " + self.tr(key) + "  ▾"

        self.status_badge.setText(text)

        state = (
            "on"
            if self._logged_in
            else "off"
        )

        self.status_badge.setProperty(
            "state",
            state,
        )

        # 使用原主题中的状态样式
        self.status_badge.style().unpolish(
            self.status_badge
        )

        self.status_badge.style().polish(
            self.status_badge
        )

        # 兼容原主题只针对 QLabel 定义颜色的情况。
        # 保留按钮本身的主题背景、边框等样式。
        color = (
            "#238b53"
            if self._logged_in
            else "#d84a4a"
        )

        self.status_badge.setStyleSheet(
            f"color: {color};"
            "background: transparent;"
            "border: none;"
            "padding: 0 4px;"
            "text-align: left;"
        )

        self._update_responsive_layout()

    def set_login_status(self, ok):

        self._logged_in = bool(ok)

        if not ok:
            self.account_label.set_full_text("")

        self._update_badge_text()

    def set_account(self, name, login_id):
        """显示姓名和学籍番号。"""

        parts = [
            p.strip()
            for p in (name, login_id)
            if p and p.strip()
        ]

        self.account_label.set_full_text(
            " · ".join(parts)
        )

        self._update_responsive_layout()

    def set_login_busy(self, busy):

        self._login_busy = bool(busy)

        self.status_badge.setEnabled(
            not busy
        )

    def reset(self):
        """清空账号显示和课程列表。"""

        self.set_login_status(False)

        self.account_label.set_full_text("")

        self.courses = {}

        self.prefix_cb.blockSignals(True)
        self.prefix_cb.clear()
        self.prefix_cb.blockSignals(False)

        self.course_cb.blockSignals(True)
        self.course_cb.clear()
        self.course_cb.blockSignals(False)

        self._update_responsive_layout()

    # ==================================================
    # 课程选择器宽度
    # ==================================================

    @staticmethod
    def _combo_text_width(combo, sample):

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

        term_width = self._combo_text_width(
            self.prefix_cb,
            "2026後期",
        )

        course_width = self._combo_text_width(
            self.course_cb,
            "漢" * 10,
        )

        self.prefix_cb.setFixedWidth(
            term_width
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

        self.course_cb.setFixedWidth(
            course_width
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

    # ==================================================
    # 响应式布局
    # ==================================================

    def _update_responsive_layout(self):

        if self._updating_layout:
            return

        self._updating_layout = True

        try:

            account_layout = (
                self.account_widget.layout()
            )

            account_layout.invalidate()

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

    # ==================================================
    # 多语言
    # ==================================================

    def retranslate(self):

        self.course_label.setText(
            self.tr("course_name")
        )

        self.prefix_label.setText(
            self.tr("prefix_filter")
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

        self._update_selector_widths()

    # ==================================================
    # 课程相关逻辑
    # ==================================================

    def set_courses(self, courses):

        self.courses_loaded.emit(
            courses or {}
        )

    @staticmethod
    def _term_prefix(course_name):

        match = re.match(
            r"^\s*(\d{4}(?:年度)?\s*(?:前期|後期|后期))",
            course_name,
        )

        return (
            re.sub(r"\s+", "", match.group(1))
            if match
            else None
        )

    @classmethod
    def _display_course_name(
        cls,
        course_name,
    ):

        if cls._term_prefix(course_name) is None:
            return course_name

        return re.sub(
            r"^\s*\d{4}(?:年度)?\s*(?:前期|後期|后期)\s*",
            "",
            course_name,
        ).strip()

    def _populate_courses(self, courses):

        self.courses = courses

        names = list(courses.keys())

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
            self.tr("placeholder_course")
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

        if (
            old_name
            and old_name not in names
        ):

            self.course_selected.emit(
                "",
                "",
            )

    def _on_prefix_changed(
        self,
        _index,
    ):

        self._rebuild_course_options()

    def _on_course_index_changed(self):

        idx = (
            self.course_cb.currentIndex()
        )

        if idx <= 0:

            self.course_selected.emit(
                "",
                "",
            )

            return

        name = (
            self.course_cb.currentData()
        )

        if name in self.courses:

            self.course_selected.emit(
                self.courses[name]["id"],
                name,
            )
