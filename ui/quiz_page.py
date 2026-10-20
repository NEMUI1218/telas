"""显示当前课程的 Blackboard 测验及其课时分类。"""

import html
import re
import threading

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QCheckBox,
    QDialog,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QSizePolicy,
)

from utils.theme import colors


class _QuizLoadSignals(QObject):
    finished = Signal(str, object, int, int)


class _TermQuizLoadSignals(QObject):
    finished = Signal(str, object, int, int)


class QuizPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self._has_loaded = False
        self._request_id = 0
        self._loaded_quizzes = []
        self._loaded_folders = []
        self._course_quizzes = []
        self._course_folders = []
        self._management_quizzes = []
        self._management_courses = []
        self._management_mode = False
        self._management_view = "unfinished"
        self._quiz_checkboxes = {}
        self._signals = _QuizLoadSignals(self)
        self._signals.finished.connect(self._on_quizzes_loaded)
        self._term_signals = _TermQuizLoadSignals(self)
        self._term_signals.finished.connect(self._on_term_quizzes_loaded)

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

        self.unfinished_btn = QPushButton()
        self.unfinished_btn.setObjectName("secondary")
        self.unfinished_btn.setFixedSize(120, 34)
        self.unfinished_btn.clicked.connect(self._open_management)
        toolbar.addWidget(self.unfinished_btn)

        self.refresh_btn = QPushButton()
        self.refresh_btn.setObjectName("secondary")
        self.refresh_btn.setFixedSize(110, 34)
        self.refresh_btn.clicked.connect(self.refresh_quizzes)
        toolbar.addWidget(self.refresh_btn)
        layout.addWidget(self.toolbar_widget)

        self.quiz_tree = QTreeWidget()
        self.quiz_tree.setColumnCount(5)
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
        self.quiz_tree.header().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Fixed
        )
        self.quiz_tree.header().resizeSection(1, 145)
        self.quiz_tree.header().resizeSection(2, 110)
        self.quiz_tree.header().resizeSection(3, 90)
        self.quiz_tree.header().resizeSection(4, 90)
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

        self._build_management_dialog()

        self.ctx.signals.course_changed.connect(self.on_course_changed)
        self.ctx.signals.login_state.connect(self._on_login_state)
        self.ctx.signals.theme_changed.connect(self._refresh_name_links)
        self.retranslate()
        self._set_idle_state(not bool(self.ctx.current_course_id))

    def retranslate(self):
        self.refresh_btn.setText(self.ctx.tr("refresh"))
        self.empty_label.setText(self.ctx.tr("empty_state"))
        self.unfinished_btn.setText(self.ctx.tr("quiz_unfinished_tasks"))
        self.management_dialog.setWindowTitle(
            self.ctx.tr("quiz_unfinished_tasks")
        )
        self.management_refresh_btn.setText(self.ctx.tr("refresh"))
        self.management_back_btn.setText(self.ctx.tr("back"))
        self.quiz_tree.setHeaderLabels([
            self.ctx.tr("quiz_col_name"),
            self.ctx.tr("quiz_col_due_date"),
            self.ctx.tr("quiz_col_attempts"),
            self.ctx.tr("quiz_col_points"),
            self.ctx.tr("col_type"),
        ])
        header_item = self.quiz_tree.headerItem()
        for column in (1, 2, 3, 4):
            header_item.setTextAlignment(
                column, Qt.AlignmentFlag.AlignCenter
            )
        self.management_tree.setHeaderLabels([
            self.ctx.tr("quiz_col_name"),
            self.ctx.tr("quiz_col_due_date"),
            self.ctx.tr("quiz_col_attempts"),
            self.ctx.tr("quiz_col_points"),
            self.ctx.tr("col_type"),
        ])
        management_header_item = self.management_tree.headerItem()
        for column in (1, 2, 3, 4):
            management_header_item.setTextAlignment(
                column, Qt.AlignmentFlag.AlignCenter
            )
        self._update_management_view_text()

    def _build_management_dialog(self):
        self.management_dialog = QDialog(self)
        self.management_dialog.setModal(True)
        self.management_dialog.resize(980, 620)
        self.management_dialog.finished.connect(
            self._on_management_dialog_closed
        )

        dialog_layout = QVBoxLayout(self.management_dialog)
        dialog_layout.setContentsMargins(9, 9, 9, 9)
        dialog_layout.setSpacing(10)

        self.management_title_label = QLabel()
        title_font = self.management_title_label.font()
        title_font.setPointSize(title_font.pointSize() + 3)
        title_font.setBold(True)
        self.management_title_label.setFont(title_font)
        dialog_layout.addWidget(self.management_title_label)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(8)

        self.management_term_filter = QComboBox()
        self.management_term_filter.setFixedWidth(140)
        self.management_term_filter.setFixedHeight(34)
        self.management_term_filter.currentIndexChanged.connect(
            self._refresh_term_quizzes
        )
        controls.addWidget(self.management_term_filter)

        self.management_toggle_btn = QPushButton()
        self.management_toggle_btn.setObjectName("secondary")
        self.management_toggle_btn.setFixedSize(110, 34)
        self.management_toggle_btn.clicked.connect(
            self._toggle_management_view
        )
        controls.addWidget(self.management_toggle_btn)
        controls.addStretch(1)

        self.batch_archive_btn = QPushButton()
        self.batch_archive_btn.setFixedSize(110, 34)
        self.batch_archive_btn.setEnabled(False)
        self.batch_archive_btn.clicked.connect(self._archive_checked)
        controls.addWidget(self.batch_archive_btn)

        self.management_refresh_btn = QPushButton()
        self.management_refresh_btn.setObjectName("secondary")
        self.management_refresh_btn.setFixedSize(110, 34)
        self.management_refresh_btn.clicked.connect(
            self._refresh_term_quizzes
        )
        controls.addWidget(self.management_refresh_btn)

        self.management_back_btn = QPushButton()
        self.management_back_btn.setObjectName("secondary")
        self.management_back_btn.setFixedSize(110, 34)
        self.management_back_btn.clicked.connect(
            self.management_dialog.reject
        )
        controls.addWidget(self.management_back_btn)
        dialog_layout.addLayout(controls)

        self.management_status_label = QLabel()
        self.management_status_label.setFixedHeight(24)
        dialog_layout.addWidget(self.management_status_label)

        self.management_tree = QTreeWidget()
        self.management_tree.setColumnCount(5)
        self.management_tree.setAlternatingRowColors(True)
        self.management_tree.setIndentation(22)
        management_header = self.management_tree.header()
        management_header.setStretchLastSection(False)
        management_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column, width in ((1, 145), (2, 110), (3, 90), (4, 90)):
            management_header.setSectionResizeMode(
                column, QHeaderView.ResizeMode.Fixed
            )
            management_header.resizeSection(column, width)
        dialog_layout.addWidget(self.management_tree, 1)

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

        self._course_quizzes = quizzes.get("quizzes", [])
        self._course_folders = quizzes.get("folders", [])
        if not self._management_mode:
            self._populate_quiz_tree()
        self.status_label.clear()

    def _populate_quiz_tree(self, *_args):
        tree = self.management_tree if self._management_mode else self.quiz_tree
        tree.clear()
        self._quiz_checkboxes = {}
        filter_name = self._management_view
        source_quizzes = (
            self._management_quizzes
            if self._management_mode
            else self._course_quizzes
        )
        source_folders = self._course_folders
        if not self._management_mode:
            quiz_list = [
                quiz for quiz in source_quizzes
                if not self._is_quiz_archived(quiz)
            ]
        elif filter_name == "archived":
            quiz_list = [
                quiz for quiz in source_quizzes
                if self._is_quiz_archived(quiz)
            ]
        else:
            quiz_list = [
                quiz for quiz in source_quizzes
                if not self._is_quiz_archived(quiz)
                and self._is_unfinished(quiz)
            ]

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
                    "",
                    self.ctx.tr("type_lesson"),
                ])
                self._center_result_columns(lesson_item)
                lesson_item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    {"path": [lesson_name]},
                )
                tree.addTopLevelItem(lesson_item)
                lessons[lesson_name] = lesson_item
            return lessons[lesson_name]

        if self._management_mode:
            for course in self._management_courses:
                ensure_lesson([course["label"]])

        # 只把课程目录下的第一层文件夹作为课时显示。
        # 更深层的“授業用資料について”等资料文件夹继续由文件下载页展示。
        if not self._management_mode:
            for folder in source_folders:
                path = folder.get("path", [])
                if len(path) == 1:
                    ensure_lesson(path)

        for quiz in quiz_list:
            parent = ensure_lesson(quiz.get("path", []))
            quiz_item = QTreeWidgetItem([
                quiz.get("title") or self.ctx.tr("unnamed_quiz"),
                quiz.get("due_date") or "—",
                self._format_attempts(quiz),
                self._format_points(quiz),
                self.ctx.tr("quiz_type"),
            ])
            self._center_result_columns(quiz_item)
            quiz_item.setData(0, Qt.ItemDataRole.UserRole, quiz.get("id", ""))
            if parent is None:
                tree.addTopLevelItem(quiz_item)
            else:
                parent.addChild(quiz_item)
            # QTreeWidget 只有在条目已加入树后才能设置单元格控件。
            # 清空底层文字，避免它与 QLabel 重叠绘制造成重影。
            quiz_item.setText(0, "")
            self._set_name_and_url(
                quiz_item,
                quiz.get("title") or self.ctx.tr("unnamed_quiz"),
                quiz.get("url", ""),
                checkable=self._management_mode,
                course_id=quiz.get("course_id"),
                tree=tree,
            )

        for lesson_name, lesson_item in lessons.items():
            has_quiz = any(
                quiz.get("path") and quiz["path"][0] == lesson_name
                for quiz in quiz_list
            )
            if not has_quiz:
                lesson_item.addChild(
                    QTreeWidgetItem([
                        self.ctx.tr(
                            "no_archived_for_course"
                            if self._management_mode
                            and filter_name == "archived"
                            else "no_unfinished_for_course"
                            if self._management_mode
                            else "no_quiz_for_lesson"
                        ),
                        "",
                        "",
                        "",
                        "",
                    ])
                )
            lesson_item.setExpanded(
                has_quiz if self._management_mode else True
            )
        self._update_batch_archive_button()

    def _archived_quiz_ids(self, course_id=None):
        archived = self.ctx.settings.get("archived_quizzes")
        if archived is None:
            archived = self.ctx.settings.get("ignored_quizzes", {})
        if not isinstance(archived, dict):
            return set()
        course_ids = archived.get(str(
            course_id or self.ctx.current_course_id or ""
        ), [])
        if not isinstance(course_ids, list):
            return set()
        return {str(quiz_id) for quiz_id in course_ids}

    def _is_quiz_archived(self, quiz):
        course_id = quiz.get("course_id") or self.ctx.current_course_id
        return str(quiz.get("id", "")) in self._archived_quiz_ids(course_id)

    def _open_management(self):
        if self.management_dialog.isVisible():
            self.management_dialog.raise_()
            self.management_dialog.activateWindow()
            return
        self._management_mode = True
        self._management_view = "unfinished"
        self._update_management_view_text()
        self._populate_term_options()
        self.management_dialog.open()

    def _on_management_dialog_closed(self, _result):
        self._management_mode = False
        self._request_id += 1
        self.management_tree.clear()
        self._quiz_checkboxes = {}

    def _set_management_view(self, view_name):
        self._management_view = view_name
        self._update_management_view_text()
        self._populate_quiz_tree()

    def _toggle_management_view(self):
        self._set_management_view(
            "archived"
            if self._management_view == "unfinished"
            else "unfinished"
        )

    def _update_management_view_text(self):
        archived = self._management_view == "archived"
        self.management_title_label.setText(self.ctx.tr(
            "quiz_archived_list" if archived else "quiz_unfinished_tasks"
        ))
        self.management_toggle_btn.setText(self.ctx.tr(
            "quiz_filter_unfinished" if archived else "quiz_filter_archived"
        ))
        self._update_batch_archive_button()

    @staticmethod
    def _term_prefix(course_name):
        match = re.match(
            r"^\s*(\d{4}(?:年度)?\s*(?:前期|後期|后期))",
            str(course_name),
        )
        return re.sub(r"\s+", "", match.group(1)) if match else None

    @classmethod
    def _display_course_name(cls, course_name):
        if cls._term_prefix(course_name) is None:
            return str(course_name)
        return re.sub(
            r"^\s*\d{4}(?:年度)?\s*(?:前期|後期|后期)\s*",
            "",
            str(course_name),
        ).strip()

    def _populate_term_options(self):
        terms = {
            term
            for name in self.ctx.courses
            if (term := self._term_prefix(name)) is not None
        }
        terms = sorted(
            terms,
            key=lambda term: (
                int(re.search(r"\d{4}", term).group()),
                2 if "後期" in term or "后期" in term else 1,
            ),
            reverse=True,
        )
        current_term = self._term_prefix(self.ctx.current_course_name)
        self.management_term_filter.blockSignals(True)
        self.management_term_filter.clear()
        for term in terms:
            self.management_term_filter.addItem(term, term)
        if any(self._term_prefix(name) is None for name in self.ctx.courses):
            self.management_term_filter.addItem(
                self.ctx.tr("other_term"), "__other__"
            )
        selected_index = self.management_term_filter.findData(current_term)
        self.management_term_filter.setCurrentIndex(
            selected_index if selected_index >= 0 else 0
        )
        self.management_term_filter.blockSignals(False)
        self._refresh_term_quizzes()

    def _courses_for_management_term(self, term):
        courses = []
        for name, course in self.ctx.courses.items():
            matches = (
                self._term_prefix(name) is None
                if term == "__other__"
                else self._term_prefix(name) == term
            )
            if not matches:
                continue
            course_id = course.get("id", "") if isinstance(course, dict) else course
            if course_id:
                courses.append((str(course_id), str(name)))
        return courses

    def _refresh_term_quizzes(self, *_args):
        if not self._management_mode:
            return
        term = self.management_term_filter.currentData()
        courses = self._courses_for_management_term(term)
        self._request_id += 1
        request_id = self._request_id
        self._management_quizzes = []
        self.management_tree.clear()
        self.management_status_label.setText(
            self.ctx.tr("quiz_term_loading")
        )
        self.management_term_filter.setEnabled(False)
        self.management_toggle_btn.setEnabled(False)
        self.batch_archive_btn.setEnabled(False)
        self.management_refresh_btn.setEnabled(False)
        epoch = self.ctx.account_epoch
        threading.Thread(
            target=self._load_term_quizzes,
            args=(str(term or ""), courses, request_id, epoch),
            daemon=True,
        ).start()

    def _load_term_quizzes(self, term, courses, request_id, epoch):
        combined = []
        course_items = []
        errors = 0
        for course_id, course_name in courses:
            course_label = self._display_course_name(course_name)
            course_items.append({
                "id": course_id,
                "name": course_name,
                "label": course_label,
            })
            try:
                result = self.ctx.api.get_course_quizzes(
                    course_id, include_folders=True
                )
            except Exception:
                result = None
            if not isinstance(result, dict):
                errors += 1
                continue
            for quiz in result.get("quizzes", []):
                if not isinstance(quiz, dict):
                    continue
                quiz = dict(quiz)
                quiz["course_id"] = course_id
                quiz["course_name"] = course_name
                quiz["path"] = [course_label] + list(quiz.get("path", []))
                combined.append(quiz)
        payload = {
            "quizzes": combined,
            "course_items": course_items,
            "errors": errors,
            "courses": len(courses),
        }
        self._term_signals.finished.emit(term, payload, request_id, epoch)

    def _on_term_quizzes_loaded(self, term, payload, request_id, epoch):
        if request_id != self._request_id or epoch != self.ctx.account_epoch:
            return
        if not self._management_mode:
            return
        if term != str(self.management_term_filter.currentData() or ""):
            return
        self.management_term_filter.setEnabled(True)
        self.management_toggle_btn.setEnabled(True)
        self.management_refresh_btn.setEnabled(True)
        self._management_quizzes = payload.get("quizzes", [])
        self._management_courses = payload.get("course_items", [])
        self._populate_quiz_tree()
        if payload.get("errors"):
            self.management_status_label.setText(self.ctx.tr(
                "quiz_term_partial_error",
                payload["errors"],
                payload.get("courses", 0),
            ))
        else:
            self.management_status_label.clear()

    def _archive_checked(self):
        checked_items = {
            key for key, checkbox in self._quiz_checkboxes.items()
            if checkbox.isChecked()
        }
        if not checked_items:
            return

        archived = self.ctx.settings.get("archived_quizzes")
        if archived is None:
            archived = self.ctx.settings.get("ignored_quizzes", {})
        if not isinstance(archived, dict):
            archived = {}
        restoring = self._management_view == "archived"
        for course_id, quiz_id in checked_items:
            archived_ids = {
                str(item) for item in archived.get(course_id, [])
            }
            if restoring:
                archived_ids.discard(quiz_id)
            else:
                archived_ids.add(quiz_id)
            if archived_ids:
                archived[course_id] = sorted(archived_ids)
            else:
                archived.pop(course_id, None)
        self.ctx.settings.set("archived_quizzes", archived)
        self.ctx.settings.remove("ignored_quizzes")
        self.ctx.settings.save()
        self._populate_quiz_tree()

    def _update_batch_archive_button(self):
        restoring = self._management_view == "archived"
        self.batch_archive_btn.setText(self.ctx.tr(
            "quiz_remove" if restoring else "quiz_archive"
        ))
        self.batch_archive_btn.setEnabled(
            any(checkbox.isChecked() for checkbox in self._quiz_checkboxes.values())
        )

    @staticmethod
    def _is_unfinished(quiz):
        if quiz.get("points_display") == "completion":
            return quiz.get("completion_recorded") is not True
        return quiz.get("points_earned") is None

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
        for column in (1, 2, 3, 4):
            item.setTextAlignment(column, Qt.AlignmentFlag.AlignCenter)

    def _format_points(self, quiz):
        if quiz.get("points_display") == "completion":
            return "✓" if quiz.get("completion_recorded") is True else "—"
        if quiz.get("points_display") == "none":
            return "—"
        possible = quiz.get("points_possible")
        if possible is None:
            return "-/-" if quiz.get("gradebook_known") else "—"
        possible = self._format_number(possible)
        earned = quiz.get("points_earned")
        if earned is not None:
            return f"{self._format_number(earned)}/{possible}"
        return f"—/{possible}"

    @staticmethod
    def _format_number(value):
        try:
            number = float(value)
            return str(int(number)) if number.is_integer() else str(number)
        except (TypeError, ValueError):
            return str(value)

    def _set_name_and_url(
        self, item, title, url, checkable=False, course_id=None, tree=None
    ):
        cell = QWidget()
        cell_layout = QHBoxLayout(cell)
        cell_layout.setContentsMargins(0, 0, 0, 0)
        cell_layout.setSpacing(8)
        if checkable:
            checkbox = QCheckBox()
            quiz_id = str(item.data(0, Qt.ItemDataRole.UserRole) or "")
            course_id = str(
                course_id or self.ctx.current_course_id or ""
            )
            checkbox.stateChanged.connect(self._update_batch_archive_button)
            self._quiz_checkboxes[(course_id, quiz_id)] = checkbox
            cell_layout.addWidget(checkbox)

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
        cell_layout.addWidget(link_label)
        cell_layout.addStretch(1)
        (tree or self.quiz_tree).setItemWidget(item, 0, cell)

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
        labels = self.quiz_tree.findChildren(QLabel)
        labels += self.management_tree.findChildren(QLabel)
        for label in labels:
            if label.property("name_link_url"):
                self._render_name_link(label)
