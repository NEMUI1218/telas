"""测验识别页面。

当前阶段只验证页面显示、课程切换和刷新交互。
暂不调用 Blackboard API。
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
)

from utils.app_context import AppContext


class QuizPage(QWidget):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx

        self.course_id = ""
        self.course_name = ""
        self._has_loaded = False

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 页面标题
        self.title_label = QLabel()
        self.title_label.setObjectName("pageTitle")
        layout.addWidget(self.title_label)

        # 当前课程
        self.course_label = QLabel()
        self.course_label.setWordWrap(True)
        layout.addWidget(self.course_label)

        # 工具栏
        toolbar = QHBoxLayout()

        self.status_label = QLabel()
        toolbar.addWidget(self.status_label)

        toolbar.addStretch()

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_quizzes)
        toolbar.addWidget(self.refresh_btn)

        layout.addLayout(toolbar)

        # 测验列表
        self.quiz_list = QListWidget()
        self.quiz_list.setAlternatingRowColors(True)
        layout.addWidget(self.quiz_list)

        # 空状态提示
        self.empty_label = QLabel()
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        # 监听现有的课程切换信号
        self.ctx.signals.course_changed.connect(self.on_course_changed)

        self.retranslate()
        self._update_course_label()
        self._update_empty_state()

    def retranslate(self):
        """更新页面文字。"""
        self.title_label.setText(self.ctx.tr("tab_quiz"))
        self.refresh_btn.setText("刷新")
        self.empty_label.setText("进入页面后，点击刷新即可测试列表显示。")

    def showEvent(self, event):
        """每次页面显示时，首次进入或重新进入均尝试刷新。"""
        super().showEvent(event)

        if not self._has_loaded:
            self.refresh_quizzes()

    def on_course_changed(self, course_id, course_name):
        """课程切换后更新页面，并自动刷新。"""
        self.course_id = course_id or ""
        self.course_name = course_name or ""

        self._update_course_label()
        self.refresh_quizzes()

    def _update_course_label(self):
        """显示当前选择的课程。"""
        if self.course_name:
            self.course_label.setText(f"当前课程：{self.course_name}")
        else:
            self.course_label.setText("请先选择一门课程。")

    def _update_empty_state(self):
        """根据列表内容显示或隐藏空状态提示。"""
        is_empty = self.quiz_list.count() == 0
        self.empty_label.setVisible(is_empty)

    def refresh_quizzes(self):
        """使用测试数据刷新列表，不调用 API。"""
        self._has_loaded = True
        self.quiz_list.clear()

        if not self.course_id:
            self.status_label.setText("尚未选择课程")
            self.empty_label.setText("请先选择一门课程，再刷新测验列表。")
            self._update_empty_state()
            return

        # 临时测试数据：用于确认页面能正常显示。
        # 下一阶段接入 API 后，会替换为 Blackboard 返回的真实测验。
        demo_quizzes = [
            "测验名称示例 1",
            "测验名称示例 2",
            "测验名称示例 3",
        ]

        for title in demo_quizzes:
            item = QListWidgetItem(title)
            self.quiz_list.addItem(item)

        self.status_label.setText(
            f"页面测试：{len(demo_quizzes)} 条示例数据"
        )
        self.empty_label.setText("当前没有测验。")
        self._update_empty_state()
