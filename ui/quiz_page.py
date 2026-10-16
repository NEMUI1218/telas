"""显示当前课程的 Blackboard 测验及其课时分类。"""

import html
import threading

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QSizePolicy,
)

from utils.theme import colors


class _QuizLoadSignals(QObject):
    finished = Signal(str, object, int, int)


class QuizPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self._has_loaded = False
        self._request_id = 0
        self._signals = _QuizLoadSignals(self)
        self._signals.finished.connect(self._on_quizzes_loaded)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.toolbar_widget = QWidget()
        toolbar = QHBoxLayout(self.toolbar_widget)
        toolbar.setContentsMargins(9, 0, 9, 0)
        self.status_label = QLabel()
        self.status_label.setFixedHeight(34)
        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        toolbar.addWidget(self.status_label, 1)

        self.refresh_btn = QPushButton()
        self.refresh_btn.setObjectName("secondary")
        self.refresh_btn.setFixedSize(110, 34)
        self.refresh_btn.clicked.connect(self.refresh_quizzes)
        toolbar.addWidget(self.refresh_btn)
        layout.addWidget(self.toolbar_widget)

        self.quiz_tree = QTreeWidget()
        self.quiz_tree.setColumnCount(4)
        self.quiz_tree.setAlternatingRowColors(True)
        self.quiz_tree.setIndentation(22)
        self.quiz_tree.header().setStretchLastSection(False)
        self.quiz_tree.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.quiz_tree.header().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Fixed
        )
        self.quiz_tree.header().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Fixed
        )
        self.quiz_tree.header().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Fixed
        )
        self.quiz_tree.header().resizeSection(1, 110)
        self.quiz_tree.header().resizeSection(2, 90)
        self.quiz_tree.header().resizeSection(3, 90)
        self.tree_container = QWidget()
        tree_layout = QHBoxLayout(self.tree_container)
        tree_layout.setContentsMargins(9, 0, 9, 0)
        tree_layout.setSpacing(0)
        tree_layout.addWidget(self.quiz_tree)
        layout.addWidget(self.tree_container, 1)

        self.empty_label = QLabel()
        self.empty_label.setObjectName("empty_state")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label, 1)

        self.ctx.signals.course_changed.connect(self.on_course_changed)
        self.ctx.signals.login_state.connect(self._on_login_state)
        self.ctx.signals.theme_changed.connect(self._refresh_name_links)
        self.retranslate()
        self._set_idle_state(not bool(self.ctx.current_course_id))

    def retranslate(self):
        self.refresh_btn.setText(self.ctx.tr("refresh"))
        self.empty_label.setText(self.ctx.tr("empty_state"))
        self.quiz_tree.setHeaderLabels([
            self.ctx.tr("quiz_col_name"),
            self.ctx.tr("quiz_col_attempts"),
            self.ctx.tr("quiz_col_points"),
            self.ctx.tr("col_type"),
        ])
        header_item = self.quiz_tree.headerItem()
        for column in (1, 2, 3):
            header_item.setTextAlignment(
                column, Qt.AlignmentFlag.AlignCenter
            )

    def showEvent(self, event):
        super().showEvent(event)
        if not self._has_loaded:
            self.refresh_quizzes()

    def _on_login_state(self, logged_in):
        if logged_in:
            self._has_loaded = False

    def on_course_changed(self, _course_id, _course_name):
        self.refresh_quizzes()

    def _set_idle_state(self, idle):
        self.toolbar_widget.setVisible(not idle)
        self.tree_container.setVisible(not idle)
        self.empty_label.setVisible(idle)

    def refresh_quizzes(self):
        self._has_loaded = True
        self._request_id += 1
        request_id = self._request_id
        self.quiz_tree.clear()

        course_id = str(self.ctx.current_course_id or "")
        if not course_id:
            self._set_idle_state(True)
            return

        self._set_idle_state(False)
        self.status_label.setText(self.ctx.tr("quiz_loading"))
        self.refresh_btn.setEnabled(False)
        epoch = self.ctx.account_epoch
        threading.Thread(
            target=self._load_quizzes,
            args=(course_id, request_id, epoch),
            daemon=True,
        ).start()

    def _load_quizzes(self, course_id, request_id, epoch):
        try:
            quizzes = self.ctx.api.get_course_quizzes(course_id, include_folders=True)
        except Exception as exc:
            quizzes = {"error": str(exc)}
        self._signals.finished.emit(course_id, quizzes, request_id, epoch)

    def _on_quizzes_loaded(self, course_id, quizzes, request_id, epoch):
        if request_id != self._request_id:
            return
        if epoch != self.ctx.account_epoch:
            return
        if course_id != str(self.ctx.current_course_id or ""):
            return

        self.refresh_btn.setEnabled(True)
        self.quiz_tree.clear()
        if quizzes is None or not isinstance(quizzes, dict):
            self.status_label.setText(self.ctx.tr("quiz_load_failed"))
            return

        if "error" in quizzes:
            self.status_label.setText(
                self.ctx.tr("quiz_load_error", quizzes["error"])
            )
            return

        quiz_list = quizzes.get("quizzes", [])
        folder_list = quizzes.get("folders", [])

        lessons = {}

        def ensure_lesson(path):
            if not path:
                return None
            lesson_name = path[0]
            if lesson_name not in lessons:
                lesson_item = QTreeWidgetItem([
                    lesson_name,
                    "",
                    "",
                    self.ctx.tr("type_lesson"),
                ])
                self._center_result_columns(lesson_item)
                lesson_item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    {"path": [lesson_name]},
                )
                self.quiz_tree.addTopLevelItem(lesson_item)
                lessons[lesson_name] = lesson_item
            return lessons[lesson_name]

        # 只把课程目录下的第一层文件夹作为课时显示。
        # 更深层的“授業用資料について”等资料文件夹继续由文件下载页展示。
        for folder in folder_list:
            path = folder.get("path", [])
            if len(path) == 1:
                ensure_lesson(path)

        for quiz in quiz_list:
            parent = ensure_lesson(quiz.get("path", []))
            quiz_item = QTreeWidgetItem([
                quiz.get("title") or self.ctx.tr("unnamed_quiz"),
                self._format_attempts(quiz),
                self._format_points(quiz),
                self.ctx.tr("quiz_type"),
            ])
            self._center_result_columns(quiz_item)
            quiz_item.setData(0, Qt.ItemDataRole.UserRole, quiz.get("id", ""))
            if parent is None:
                self.quiz_tree.addTopLevelItem(quiz_item)
            else:
                parent.addChild(quiz_item)
            # QTreeWidget 只有在条目已加入树后才能设置单元格控件。
            # 清空底层文字，避免它与 QLabel 重叠绘制造成重影。
            quiz_item.setText(0, "")
            self._set_name_and_url(
                quiz_item,
                quiz.get("title") or self.ctx.tr("unnamed_quiz"),
                quiz.get("url", ""),
            )

        for lesson_name, lesson_item in lessons.items():
            has_quiz = any(
                quiz.get("path") and quiz["path"][0] == lesson_name
                for quiz in quiz_list
            )
            if not has_quiz:
                lesson_item.addChild(
                    QTreeWidgetItem([
                        self.ctx.tr("no_quiz_for_lesson"),
                        "",
                        "",
                        "",
                    ])
                )
            lesson_item.setExpanded(True)

        if quiz_list:
            self.status_label.setText(
                self.ctx.tr("quiz_scan_done", len(quiz_list))
            )
        else:
            self.status_label.setText(self.ctx.tr("quiz_scan_empty"))

    def _format_attempts(self, quiz):
        if not quiz.get("attempts_known"):
            return "—"
        count = quiz.get("attempt_count", 0)
        allowed = quiz.get("attempts_allowed")
        if not quiz.get("attempts_allowed_known"):
            return "—"
        if allowed in (None, 0, -1, "0", "-1"):
            return self.ctx.tr("quiz_attempts_unlimited")
        return self.ctx.tr("quiz_attempts_format", count, allowed)

    @staticmethod
    def _center_result_columns(item):
        for column in (1, 2, 3):
            item.setTextAlignment(column, Qt.AlignmentFlag.AlignCenter)

    def _format_points(self, quiz):
        if quiz.get("points_display") == "none":
            return "—"
        possible = quiz.get("points_possible")
        if possible is None:
            return "-/-" if quiz.get("gradebook_known") else "—"
        possible = self._format_number(possible)
        earned = quiz.get("points_earned")
        if earned is not None:
            return f"{self._format_number(earned)}/{possible}"
        if quiz.get("attempts_known") and not quiz.get("attempt_count", 0):
            return f"-/{possible}"
        return "—"

    @staticmethod
    def _format_number(value):
        try:
            number = float(value)
            return str(int(number)) if number.is_integer() else str(number)
        except (TypeError, ValueError):
            return str(value)

    def _set_name_and_url(self, item, title, url):
        link_label = QLabel()
        if url:
            link_label.setTextFormat(Qt.TextFormat.RichText)
            link_label.setProperty("name_link_url", url)
            link_label.setProperty("name_link_title", title)
            self._render_name_link(link_label)
            link_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextBrowserInteraction
            )
            link_label.setOpenExternalLinks(True)
            link_label.setToolTip(url)
        else:
            link_label.setTextFormat(Qt.TextFormat.PlainText)
            link_label.setText(title)
        self.quiz_tree.setItemWidget(item, 0, link_label)

    @staticmethod
    def _render_name_link(label):
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        safe_url = html.escape(label.property("name_link_url"), quote=True)
        safe_title = html.escape(label.property("name_link_title"))
        text_color = colors()["text"]
        label.setText(
            f'<a href="{safe_url}" style="color:{text_color}; '
            f'text-decoration:none; font-weight:700;"><b>{safe_title}</b></a>'
        )

    def _refresh_name_links(self):
        for label in self.quiz_tree.findChildren(QLabel):
            if label.property("name_link_url"):
                self._render_name_link(label)
