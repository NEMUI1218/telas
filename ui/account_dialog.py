"""登录账号 / 切换账号弹窗。"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFormLayout,
)


class AccountDialog(QDialog):
    """用于登录或切换 Blackboard 账号的弹窗。"""

    def __init__(
        self,
        parent=None,
        title="登录账号",
        username="",
        password="",
    ):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(340)

        self.setWindowFlag(
            Qt.WindowType.WindowContextHelpButtonHint,
            False,
        )

        self._build_ui(username, password)

    def _build_ui(self, username, password):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(18)

        # 标题
        self.title_label = QLabel(self.windowTitle())

        font = self.title_label.font()
        font.setPointSize(15)
        font.setBold(True)
        self.title_label.setFont(font)

        root.addWidget(self.title_label)

        # 输入区域
        form = QFormLayout()
        form.setSpacing(12)

        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("请输入用户名")
        self.user_input.setText(username)
        self.user_input.setMinimumHeight(34)

        self.pwd_input = QLineEdit()
        self.pwd_input.setPlaceholderText("请输入密码")
        self.pwd_input.setEchoMode(
            QLineEdit.EchoMode.Password
        )
        self.pwd_input.setText(password)
        self.pwd_input.setMinimumHeight(34)

        form.addRow("用户名", self.user_input)
        form.addRow("密码", self.pwd_input)

        root.addLayout(form)

        # 提示信息
        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        self.message_label.hide()

        root.addWidget(self.message_label)

        # 底部按钮
        buttons = QHBoxLayout()
        buttons.setSpacing(10)

        buttons.addStretch()

        self.login_btn = QPushButton("登录")
        self.login_btn.setMinimumWidth(82)
        self.login_btn.setMinimumHeight(32)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setMinimumWidth(82)
        self.cancel_btn.setMinimumHeight(32)

        buttons.addWidget(self.login_btn)
        buttons.addWidget(self.cancel_btn)

        root.addLayout(buttons)

        # 信号
        self.login_btn.clicked.connect(self._submit)
        self.cancel_btn.clicked.connect(self.reject)

        self.pwd_input.returnPressed.connect(
            self._submit
        )

        self.user_input.returnPressed.connect(
            self.pwd_input.setFocus
        )

        # 默认焦点
        if username:
            self.pwd_input.setFocus()
        else:
            self.user_input.setFocus()

    def _submit(self):
        """检查输入内容，然后关闭弹窗并返回账号信息。"""

        username = self.get_user()
        password = self.get_pwd()

        if not username or not password:
            self.show_message("请输入用户名和密码。")
            return

        self.accept()

    def get_user(self):
        return self.user_input.text().strip()

    def get_pwd(self):
        return self.pwd_input.text()

    def show_message(self, message):
        self.message_label.setText(message)
        self.message_label.show()

    def set_login_busy(self, busy):
        """预留给后续异步登录使用。"""

        self.user_input.setEnabled(not busy)
        self.pwd_input.setEnabled(not busy)
        self.login_btn.setEnabled(not busy)

        self.login_btn.setText(
            "登录中..." if busy else "登录"
        )
