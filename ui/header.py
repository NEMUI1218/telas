"""顶部栏：账号状态菜单 + 学期和课程选择。"""

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
    """显示账号姓名与学号，空间不足时省略，悬停显示完整内容。"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._full_text = ""

        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(False)

        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred,
        )

    def set_full_text(self, text):
        self._full_text = str(text or "")
        self.setToolTip(self._full_text)
        self._refresh()
        self.updateGeometry()

    def full_text(self):
        return self._full_text

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

        self._compact = True
        self._updating_layout = False

        self._build_ui()

        self.courses_loaded.connect(self._populate_courses)

        self.retranslate()

    def tr(self, key, *args):
        return self.ctx.tr(key, *args)

    # =========================================================
    # UI
    # =========================================================

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

        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Fixed,
        )

        # =====================================================
        # 账号区域
        # =====================================================

        self.account_widget = QWidget()
        self.account_widget.setFixedHeight(32)

        self.account_widget.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Fixed,
        )

        account_layout = QHBoxLayout(self.account_widget)

        account_layout.setContentsMargins(9, 0, 0, 0)
        account_layout.setSpacing(0)

        # =====================================================
        # 登录状态徽章
        # =====================================================

        self.status_badge = QPushButton()

        self.status_badge.setObjectName("status_badge")

        self.status_badge.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.status_badge.setFixedHeight(28)

        self.status_badge.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )

        self.status_badge.clicked.connect(
            self._on_status_clicked
        )

        account_layout.addWidget(self.status_badge)
        account_layout.addSpacing(8)

        # =====================================================
        # 姓名和学号
        # =====================================================

        self.account_label = ElidedLabel()

        self.account_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )

        account_layout.addWidget(self.account_label)
        account_layout.addStretch(1)

        root.addWidget(self.account_widget, 1)

        # =====================================================
        # 账号菜单
        # =====================================================

        self.account_menu = QMenu(self)

        self.switch_action = self.account_menu.addAction("")
        self.logout_action = self.account_menu.addAction("")

        self.switch_action.triggered.connect(
            self.switch_requested.emit
        )

        self.logout_action.triggered.connect(
            self.logout_requested.emit
        )

        # =====================================================
        # 学期
        # =====================================================

        self.prefix_label = QLabel()
        self.prefix_label.setObjectName("field_label")

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

        # =====================================================
        # 课程
        # =====================================================

        self.course_label = QLabel()
        self.course_label.setObjectName("field_label")

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

        # =====================================================
        # 课程选择区域
        # =====================================================

        self._course_controls = QWidget()

        course_layout = QHBoxLayout(self._course_controls)

        course_layout.setContentsMargins(0, 0, 0, 0)
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

            pair_layout.setContentsMargins(0, 0, 0, 0)
            pair_layout.setSpacing(6)

            pair_layout.addWidget(label)
            pair_layout.addWidget(combo, 1)

            course_layout.addWidget(pair, index)

            if index == 0:
                self._term_pair = pair
            else:
                self._course_pair = pair

        root.addWidget(
            self._course_controls,
            0,
            Qt.AlignmentFlag.AlignRight,
        )

        self._update_account_visibility()

    # =========================================================
    # 登录状态徽章
    # =========================================================

    def _update_badge_text(self):

        key = (
            "logged_in"
            if self._logged_in
            else "logged_out"
        )

        self.status_badge.setText(
            "●  " + self.tr(key)
        )

        state = "on" if self._logged_in else "off"

        self.status_badge.setProperty("state", state)

        if self._logged_in:

            background = "#103D2B"
            foreground = "#34D399"
            hover = "#185239"
            pressed = "#0B3021"

        else:

            background = "#451F25"
            foreground = "#FB7185"
            hover = "#592830"
            pressed = "#35171C"

        self.status_badge.setStyleSheet(
            f"""
            QPushButton#status_badge {{
                background-color: {background};
                color: {foreground};
                border: none;
                border-radius: 14px;
                padding: 0px 12px;
                font-weight: 600;
                text-align: center;
            }}

            QPushButton#status_badge:hover {{
                background-color: {hover};
            }}

            QPushButton#status_badge:pressed {{
                background-color: {pressed};
            }}

            QPushButton#status_badge:disabled {{
                opacity: 0.6;
            }}
            """
        )

        self.status_badge.style().unpolish(
            self.status_badge
        )

        self.status_badge.style().polish(
            self.status_badge
        )

        # 按当前语言重新计算按钮宽度
        self.status_badge.setFixedWidth(
            self.status_badge.sizeHint().width()
        )

        self.status_badge.updateGeometry()
        self.status_badge.update()

    def _on_status_clicked(self):

        if self._login_busy:
            return

        if not self._logged_in:

            self.login_requested.emit()
            return

        # 已登录：点击状态徽章展开账号菜单
        self.account_menu.popup(
            self.status_badge.mapToGlobal(
                self.status_badge.rect().bottomLeft()
            )
        )

    # =========================================================
    # 账号状态
    # =========================================================

    def _update_account_visibility(self):

        self.account_label.setVisible(
            self._logged_in
        )

        self.switch_action.setVisible(
            self._logged_in
        )

        self.logout_action.setVisible(
            self._logged_in
        )

    def set_login_status(self, ok):

        self._logged_in = bool(ok)

        if not self._logged_in:
            self.account_label.set_full_text("")

        self._update_badge_text()
        self._update_account_visibility()
        self._update_responsive_layout()

    def set_login_busy(self, busy):

        self._login_busy = bool(busy)

        self.status_badge.setEnabled(
            not self._login_busy
        )

        self._update_responsive_layout()

    def set_account(self, name, login_id):

        parts = [
            str(p).strip()
            for p in (name, login_id)
            if p and str(p).strip()
        ]

        self.account_label.set_full_text(
            " · ".join(parts)
        )

        self._update_responsive_layout()

    # =========================================================
    # 课程框宽度
    # =========================================================

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
            combo.fontMetrics().horizontalAdvance(sample)
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

        self.prefix_cb.setFixedWidth(term_width)
        self.course_cb.setFixedWidth(course_width)

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
            course_label_width + course_width
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

        if self._updating_layout:
            return

        self._updating_layout = True

        try:

            account_layout = self.account_widget.layout()
            account_layout.invalidate()

            account_width = (
                account_layout.sizeHint().width()
            )

            gap = (
                self.prefix_label
                .fontMetrics()
                .horizontalAdvance("　　")
            )

            margins = self._root_layout.contentsMargins()

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

    # =========================================================
    # 重置
    # =========================================================

    def reset(self):

        self.set_login_status(False)

        self.account_label.set_full_text("")
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

        if match:
            return re.sub(
                r"\s+",
                "",
                match.group(1),
            )

        return None

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

        self.courses = courses or {}

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
                    re.search(r"\d{4}", term).group()
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
            self.prefix_cb.addItem(term, term)

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

        if name in self.courses:

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
        self._update_selector_widths()
