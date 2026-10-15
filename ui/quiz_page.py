"""测验识别页面。"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
)

from utils.app_context import AppContext


class QuizPage(QWidget):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.title_label = QLabel()
        layout.addWidget(self.title_label)

        self.scan_btn = QPushButton()
        layout.addWidget(self.scan_btn)

        self.quiz_list = QListWidget()
        layout.addWidget(self.quiz_list)

        self.empty_label = QLabel()
        layout.addWidget(self.empty_label)

        self.retranslate()

    def retranslate(self):
        self.title_label.setText(self.ctx.tr("tab_quiz"))
        self.scan_btn.setText("扫描测验")
        self.empty_label.setText("选择课程后，点击扫描测验")
