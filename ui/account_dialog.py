"""账号登录弹窗。

只负责界面和用户输入，不执行网络请求。
登录结果由 AccountController 处理。
"""

from PySide6.QtCore import Qt, Signal
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
    """登录账号 / 切换账号弹窗。"""

    # 点击登录时发出账号和密码，不直接关闭弹窗
    login_requested = Signal(str, str)

    def __init__(
        self,
        ctx,
        parent=None,
        username="",
        password="",
    ):
        super().__init__(parent)

        self.ctx = ctx
        self._busy = False

        self.setModal(True)
        self.setMinimumWidth(340)

        self.setWindowFlag(
            Qt.WindowType.WindowContextHelpButtonHint,
            False,
        )

        self._build_ui(username, password)
        self.retranslate()

        # 语言变化时更新弹窗文字
        self.ctx.signals.language_changed.connect(
            self.retranslate
        )

    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------

    def _build_ui(self, username, password):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(18)

        # 标题
        self.title_label = QLabel()

        font = self.title_label.font()
        font.setPointSize(15)
        font.setBold(True)

        self.title_label.setFont(font)
        root.addWidget(self.title_label)

        # 账号密码
        form = QFormLayout()
        form.setSpacing(12)

        self.user_label = QLabel()
        self.pwd_label = QLabel()

        self.user_input = QLineEdit()
        self.user_input.setText(username)
        self.user_input.setMinimumHeight(34)

        self.pwd_input = QLineEdit()
        self.pwd_input.setText(password)
        self.pwd_input.setMinimumHeight(34)

        self.pwd_input.setEchoMode(
            QLineEdit.EchoMode.Password
        )

        form.addRow(
            self.user_label,
            self.user_input,
        )

        form.addRow(
            self.pwd_label,
            self.pwd_input,
        )

        root.addLayout(form)

        # 错误信息
        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.message_label.setObjectName(
            "account_error"
        )
        self.message_label.hide()

        root.addWidget(self.message_label)

        # 按钮
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch()

        self.login_btn = QPushButton()
        self.login_btn.setMinimumWidth(82)
        self.login_btn.setMinimumHeight(32)

        self.cancel_btn = QPushButton()
        self.cancel_btn.setMinimumWidth(82)
        self.cancel_btn.setMinimumHeight(32)

        buttons.addWidget(self.login_btn)
        buttons.addWidget(self.cancel_btn)

        root.addLayout(buttons)

        # 信号
        self.login_btn.clicked.connect(
            self._submit
        )

        self.cancel_btn.clicked.connect(
            self.reject
        )

        self.pwd_input.returnPressed.connect(
            self._submit
        )

        self.user_input.returnPressed.connect(
            self.pwd_input.setFocus
        )

        if username:
            self.pwd_input.setFocus()
        else:
            self.user_input.setFocus()

    # ---------------------------------------------------------
    # 输入
    # ---------------------------------------------------------

    def get_user(self):
        return self.user_input.text().strip()

    def get_pwd(self):
        return self.pwd_input.text()

    def _submit(self):
        """发送登录请求，不立即关闭弹窗。"""

        if self._busy:
            return

        user = self.get_user()
        password = self.get_pwd()

        if not user or not password:
            self.show_message(
                self.ctx.tr("credentials_required")
            )
            return

        self.clear_message()

        self.login_requested.emit(
            user,
            password,
        )

    # ---------------------------------------------------------
    # 登录状态
    # ---------------------------------------------------------

    def set_login_busy(self, busy):
        """登录过程中禁用输入和登录按钮。"""

        self._busy = bool(busy)

        self.user_input.setEnabled(not busy)
        self.pwd_input.setEnabled(not busy)
        self.login_btn.setEnabled(not busy)

        # 登录期间允许取消按钮保持可见，
        # 但禁止取消正在进行的请求。
        self.cancel_btn.setEnabled(not busy)

        self.login_btn.setText(
            self.ctx.tr(
                "login_busy"
                if busy
                else "login_btn"
            )
        )

    def show_message(self, message):
        """显示错误或提示信息。"""

        self.message_label.setText(message)
        self.message_label.show()

    def clear_message(self):
        self.message_label.clear()
        self.message_label.hide()

    def login_succeeded(self):
        """登录成功，由主窗口调用。"""

        self.set_login_busy(False)
        self.accept()

    def login_failed(self, message=""):
        """登录失败时保持弹窗打开。"""

        self.set_login_busy(False)

        self.show_message(
            message or self.ctx.tr("login_retry")
        )

        self.pwd_input.setFocus()
        self.pwd_input.selectAll()

    # ---------------------------------------------------------
    # 国际化
    # ---------------------------------------------------------

    def retranslate(self):
        """根据当前语言更新全部界面文字。"""

        tr = self.ctx.tr

        self.setWindowTitle(
            tr("login_account")
        )

        self.title_label.setText(
            tr("login_account")
        )

        self.user_label.setText(
            tr("username")
        )

        self.pwd_label.setText(
            tr("password")
        )

        self.user_input.setPlaceholderText(
            tr("username").rstrip(":：")
        )

        self.pwd_input.setPlaceholderText(
            tr("password").rstrip(":：")
        )

        self.login_btn.setText(
            tr(
                "login_busy"
                if self._busy
                else "login_btn"
            )
        )

        self.cancel_btn.setText(
            tr("cancel")
        )
