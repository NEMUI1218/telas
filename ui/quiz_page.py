"""测验页面的 UI 预览。使用示例数据，不请求测验 API。"""

from PySide6.QtCore import Qt
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

from utils.app_context import AppContext


class QuizPage(QWidget):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self._has_loaded = False

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
        # 顶部课程选择变化后，只展示当前选中的课程。
        self.refresh_quizzes()

    def refresh_quizzes(self):
        """用示例数据展示课程分组和测验列表的布局。"""
        self._has_loaded = True
        self.quiz_tree.clear()

        course_id = str(self.ctx.current_course_id or "")
        course_name = self.ctx.current_course_name or ""
        if not course_id:
            self.status_label.setText("请先从主界面选择课程。")
            return

        course_item = QTreeWidgetItem([course_name, "课程"])
        course_item.setData(0, Qt.ItemDataRole.UserRole, course_id)
        self.quiz_tree.addTopLevelItem(course_item)

        # 仅用示例内容预览选中课程下的子菜单布局。
        for number in (1, 2):
            test_item = QTreeWidgetItem([
                f"测试作业示例 {number}",
                "测试",
            ])
            test_item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                {"preview": True},
            )
            course_item.addChild(test_item)

        course_item.setExpanded(True)

        self.quiz_tree.expandAll()
        self.status_label.setText(
            f"界面预览：当前课程“{course_name}”；"
            "测试名称为示例数据，未调用测验 API。"
        )
