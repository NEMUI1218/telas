"""显示当前课程的 Blackboard 测验及其课时分类。"""

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
        self.quiz_tree.setColumnCount(2)
        self.quiz_tree.setAlternatingRowColors(True)
        self.quiz_tree.setIndentation(22)
        self.quiz_tree.header().setStretchLastSection(False)
        self.quiz_tree.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.quiz_tree.header().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        layout.addWidget(self.quiz_tree, 1)

        self.ctx.signals.course_changed.connect(self.on_course_changed)
        self.ctx.signals.login_state.connect(self._on_login_state)
        self.ctx.signals.language_changed.connect(self.retranslate)
        self.retranslate()

    def retranslate(self):
        self.title_label.setText(self.ctx.tr("tab_quiz"))
        self.refresh_btn.setText("刷新")
        self.quiz_tree.setHeaderLabels(["课程 / 测验", "类型"])

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
        course_name = self.ctx.current_course_name or ""
        if not course_id:
            self.status_label.setText("请先从主界面选择课程。")
            return

        self.status_label.setText(f"正在读取“{course_name}”的测验…")
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
            error = "请查看 API 日志。"
            self.status_label.setText(f"测验读取失败：{error}")
            return

        if "error" in quizzes:
            self.status_label.setText(f"测验读取失败：{quizzes['error']}")
            return

        quiz_list = quizzes.get("quizzes", [])
        folder_list = quizzes.get("folders", [])

        course_name = self.ctx.current_course_name or ""
        course_item = QTreeWidgetItem([course_name, "课程"])
        course_item.setData(0, Qt.ItemDataRole.UserRole, course_id)
        self.quiz_tree.addTopLevelItem(course_item)

        folders = {}
        for folder in folder_list:
            parent = course_item
            accumulated = []
            for folder_name in folder.get("path", []):
                accumulated.append(folder_name)
                key = tuple(accumulated)
                if key not in folders:
                    folder_item = QTreeWidgetItem([folder_name, "课时"])
                    folder_item.setData(
                        0,
                        Qt.ItemDataRole.UserRole,
                        {"path": list(key)},
                    )
                    parent.addChild(folder_item)
                    folders[key] = folder_item
                parent = folders[key]

        for quiz in quiz_list:
            parent = course_item
            accumulated = []
            for folder_name in quiz.get("path", []):
                accumulated.append(folder_name)
                key = tuple(accumulated)
                if key not in folders:
                    folder_item = QTreeWidgetItem([folder_name, "课时"])
                    folder_item.setData(
                        0,
                        Qt.ItemDataRole.UserRole,
                        {"path": list(key)},
                    )
                    parent.addChild(folder_item)
                    folders[key] = folder_item
                parent = folders[key]

            quiz_item = QTreeWidgetItem([
                quiz.get("title") or "未命名测验",
                "测试",
            ])
            quiz_item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                quiz.get("id", ""),
            )
            parent.addChild(quiz_item)

        course_item.setExpanded(True)
        self.quiz_tree.expandAll()

        for key, folder_item in folders.items():
            contains_quiz = any(
                tuple(quiz.get("path", [])[:len(key)]) == key
                for quiz in quiz_list
            )
            if not contains_quiz:
                folder_item.addChild(
                    QTreeWidgetItem(["此课时未发现测试作业", ""])
                )

        if quiz_list:
            self.status_label.setText(
                f"扫描完成，共找到 {len(quiz_list)} 个测验。"
            )
        else:
            if not folders:
                course_item.addChild(
                    QTreeWidgetItem(["此课时未发现测试作业", ""])
                )
            self.status_label.setText("扫描完成，当前课程没有测验。")
        course_item.setExpanded(True)
