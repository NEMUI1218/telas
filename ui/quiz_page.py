"""按课程分组显示测验，并读取测验说明与题目信息。"""

import json
import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QDialog,
    QDialogButtonBox,
    QPlainTextEdit,
)

from utils.app_context import AppContext


class _QuizScanSignals(QObject):
    finished = Signal(int, int, object)


class QuizPage(QWidget):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self._has_loaded = False
        self._scan_id = 0
        self._scan_thread = None
        self._scan_signals = _QuizScanSignals(self)
        self._scan_signals.finished.connect(self._show_course_results)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.title_label = QLabel()
        self.title_label.setObjectName("pageTitle")
        layout.addWidget(self.title_label)

        toolbar = QHBoxLayout()
        self.status_label = QLabel()
        toolbar.addWidget(self.status_label)
        toolbar.addStretch()

        self.refresh_btn = QPushButton("刷新")
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
        self.quiz_tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.quiz_tree, 1)

        self.ctx.signals.course_changed.connect(self.on_course_changed)

        self.retranslate()

    def retranslate(self):
        self.title_label.setText(self.ctx.tr("tab_quiz"))
        self.refresh_btn.setText("刷新")
        self.quiz_tree.setHeaderLabels(["课程 / 测验", "类型"])

    def showEvent(self, event):
        super().showEvent(event)
        if not self._has_loaded:
            self.refresh_quizzes()

    def on_course_changed(self, _course_id, _course_name):
        # 页面按全部课程分组展示；切换顶栏课程后同步刷新数据。
        self.refresh_quizzes()

    def refresh_quizzes(self):
        courses = list(self.ctx.courses.items())
        self.quiz_tree.clear()

        if not courses:
            self._has_loaded = False
            self.status_label.setText("请先登录并加载课程。")
            return

        self._has_loaded = True
        self._scan_id += 1
        scan_id = self._scan_id
        account_epoch = self.ctx.account_epoch
        course_specs = []

        for course_name, course in courses:
            course_id = str(course.get("id", ""))
            root = QTreeWidgetItem([course_name, "课程"])
            root.setData(0, Qt.ItemDataRole.UserRole, course_id)
            self.quiz_tree.addTopLevelItem(root)
            root.addChild(QTreeWidgetItem(["正在读取测试作业…", ""]))
            root.setExpanded(True)
            course_specs.append((course_id, course_name))

        self.status_label.setText(f"正在读取 {len(courses)} 门课程的测试作业…")
        self.refresh_btn.setEnabled(False)
        self._scan_thread = threading.Thread(
            target=self._scan_courses,
            args=(scan_id, account_epoch, course_specs),
            daemon=True,
        )
        self._scan_thread.start()

    def _scan_courses(self, scan_id, account_epoch, course_specs):
        results = []

        for course_id, course_name in course_specs:
            if account_epoch != self.ctx.account_epoch:
                break

            try:
                quizzes = self.ctx.api.get_course_quizzes(course_id)
            except Exception as e:
                self.ctx.log(
                    f"读取课程“{course_name}”测试作业失败：{type(e).__name__}"
                )
                quizzes = None

            results.append((course_id, course_name, quizzes))

        self._scan_signals.finished.emit(scan_id, account_epoch, results)

    def _show_course_results(self, scan_id, account_epoch, results):
        if scan_id != self._scan_id:
            return

        self.refresh_btn.setEnabled(True)

        if account_epoch != self.ctx.account_epoch:
            self.quiz_tree.clear()
            self._has_loaded = False
            self.status_label.setText("账号已切换，请重新加载课程。")
            return

        total_quizzes = 0
        failed_courses = 0

        for index, (course_id, _course_name, quizzes) in enumerate(results):
            if index >= self.quiz_tree.topLevelItemCount():
                continue

            course_item = self.quiz_tree.topLevelItem(index)
            course_item.takeChildren()

            if quizzes is None:
                failed_courses += 1
                course_item.addChild(
                    QTreeWidgetItem(["读取测试作业失败，请刷新重试", ""])
                )
            elif not quizzes:
                course_item.addChild(
                    QTreeWidgetItem(["此课时未发现测试作业", ""])
                )
            else:
                for quiz in quizzes:
                    if not isinstance(quiz, dict):
                        continue
                    test_item = QTreeWidgetItem([
                        quiz.get("title") or "未命名测验",
                        "测试",
                    ])
                    test_item.setData(0, Qt.ItemDataRole.UserRole, quiz)
                    test_item.setData(0, Qt.ItemDataRole.UserRole + 1, course_id)
                    course_item.addChild(test_item)
                    total_quizzes += 1

            course_item.setExpanded(True)

        if failed_courses:
            self.status_label.setText(
                f"已读取 {total_quizzes} 个测试作业；"
                f"{failed_courses} 门课程读取失败。"
            )
        else:
            self.status_label.setText(
                f"已读取 {len(results)} 门课程，共 {total_quizzes} 个测试作业。"
            )

        self.quiz_tree.expandAll()

    def _on_item_double_clicked(self, item, _column):
        quiz = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(quiz, dict):
            self.show_quiz_details(item)

    def show_quiz_details(self, item):
        """读取并显示所选测验的说明与题目信息。"""
        quiz = item.data(0, Qt.ItemDataRole.UserRole) or {}
        course_id = item.data(0, Qt.ItemDataRole.UserRole + 1) or ""
        assessment_id = quiz.get("assessment_id") or quiz.get("id", "")
        quiz_data = {
            "title": quiz.get("title", "未命名测验"),
            "assessment_id": assessment_id,
            "instructions": quiz.get("instructions", ""),
            "questions": None,
        }

        if course_id and assessment_id:
            self.status_label.setText("正在读取题目信息…")
            self.quiz_tree.setEnabled(False)

            try:
                questions = self.ctx.api.get_quiz_questions(
                    course_id,
                    assessment_id,
                )

                if questions is not None:
                    full_questions = []
                    for question in questions:
                        question_id = question.get("id")
                        full_question = None
                        if question_id:
                            full_question = self.ctx.api.get_quiz_question(
                                course_id,
                                assessment_id,
                                question_id,
                            )
                        full_questions.append(full_question or question)
                    quiz_data["questions"] = full_questions
            except Exception as e:
                self.ctx.log(
                    f"读取题目信息失败（{type(e).__name__}）：{e}"
                )
            finally:
                self.quiz_tree.setEnabled(True)
                self.status_label.setText("课程测试作业列表已读取")

        dialog = QDialog(self)
        dialog.setWindowTitle(quiz_data["title"])
        dialog.resize(720, 560)
        dialog_layout = QVBoxLayout(dialog)

        details = QPlainTextEdit()
        details.setReadOnly(True)
        details.setPlainText(
            json.dumps(quiz_data, ensure_ascii=False, indent=2)
        )
        dialog_layout.addWidget(details)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        buttons.rejected.connect(dialog.reject)
        dialog_layout.addWidget(buttons)
        dialog.exec()
