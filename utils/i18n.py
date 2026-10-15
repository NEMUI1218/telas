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
)


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
        layout.setSpacing(12)

        self.title_label = QLabel()
        self.title_label.setObjectName("pageTitle")
        layout.addWidget(self.title_label)

        toolbar = QHBoxLayout()
        self.status_label = QLabel()
        toolbar.addWidget(self.status_label)
        toolbar.addStretch()

        self.refresh_btn = QPushButton()
        self.refresh_btn.clicked.connect(self.refresh_quizzes)
        toolbar.addWidget(self.refresh_btn)
        layout.addLayout(toolbar)

        self.quiz_tree = QTreeWidget()
        self.quiz_tree.setColumnCount(3)
        self.quiz_tree.setAlternatingRowColors(True)
        self.quiz_tree.setIndentation(22)
        self.quiz_tree.header().setStretchLastSection(False)
        self.quiz_tree.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.quiz_tree.header().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.quiz_tree.header().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.quiz_tree, 1)

        self.ctx.signals.course_changed.connect(self.on_course_changed)
        self.ctx.signals.login_state.connect(self._on_login_state)
        self.ctx.signals.language_changed.connect(self.retranslate)
        self.retranslate()

    def retranslate(self):
        self.title_label.setText(self.ctx.tr("tab_quiz"))
        self.refresh_btn.setText(self.ctx.tr("refresh"))
        self.quiz_tree.setHeaderLabels([
            self.ctx.tr("quiz_col_name"),
            self.ctx.tr("col_type"),
            self.ctx.tr("col_url"),
        ])

    def showEvent(self, event):
        super().showEvent(event)
        if not self._has_loaded:
            self.refresh_quizzes()

    def _on_login_state(self, logged_in):
        if logged_in:
            self._has_loaded = False

    def on_course_changed(self, _course_id, _course_name):
        self.refresh_quizzes()

    def refresh_quizzes(self):
        self._has_loaded = True
        self._request_id += 1
        request_id = self._request_id
        self.quiz_tree.clear()

        course_id = str(self.ctx.current_course_id or "")
        if not course_id:
            self.status_label.setText(self.ctx.tr("select_course_first"))
            return

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
            quizzes = self.ctx.api.get_course_quizzes(
                course_id,
                include_folders=True,
            )
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

        def ensure_lesson(path, url=""):
            if not path:
                return None

            lesson_name = path[0]
            if lesson_name not in lessons:
                lesson_item = QTreeWidgetItem([
                    lesson_name,
                    self.ctx.tr("type_lesson"),
                ])
                lesson_item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    {"path": [lesson_name]},
                )
                self.quiz_tree.addTopLevelItem(lesson_item)
                lessons[lesson_name] = lesson_item

            lesson_item = lessons[lesson_name]
            if url:
                self._set_url_cell(lesson_item, url)
            return lesson_item

        # 只把课程目录下的第一层文件夹作为课时显示。
        # 更深层的资料文件夹由文件下载页展示。
        for folder in folder_list:
            path = folder.get("path", [])
            if len(path) == 1:
                ensure_lesson(path, folder.get("url", ""))

        for quiz in quiz_list:
            parent = ensure_lesson(quiz.get("path", []))
            quiz_item = QTreeWidgetItem([
                quiz.get("title") or self.ctx.tr("unnamed_quiz"),
                self.ctx.tr("quiz_type"),
            ])
            quiz_item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                quiz.get("id", ""),
            )
            self._set_url_cell(quiz_item, quiz.get("url", ""))

            if parent is None:
                self.quiz_tree.addTopLevelItem(quiz_item)
            else:
                parent.addChild(quiz_item)

        for lesson_name, lesson_item in lessons.items():
            has_quiz = any(
                quiz.get("path")
                and quiz["path"][0] == lesson_name
                for quiz in quiz_list
            )
            if not has_quiz:
                lesson_item.addChild(
                    QTreeWidgetItem([
                        self.ctx.tr("no_quiz_for_lesson"),
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

    def _set_url_cell(self, item, url):
        if not url:
            return

        safe_url = html.escape(url, quote=True)
        link_label = QLabel(
            f'<a href="{safe_url}">{html.escape(url)}</a>'
        )
        link_label.setTextFormat(Qt.TextFormat.RichText)
        link_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        link_label.setOpenExternalLinks(True)
        link_label.setToolTip(url)
        self.quiz_tree.setItemWidget(item, 2, link_label)
