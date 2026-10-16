"""账号与会话控制器。

负责：
- 手动登录
- 自动恢复登录
- 切换账号
- 取消切换后恢复原账号
- 退出登录
- 加载课程

不创建窗口，不直接操作任何 QWidget。
所有界面更新通过 Qt 信号通知主窗口。
"""

from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, Signal, Slot


class AccountController(QObject):
    # 登录状态
    login_state = Signal(bool)
    login_busy = Signal(bool)

    # 账号信息：姓名、登录 ID
    account_info = Signal(str, str)

    # 课程数据
    courses_loaded = Signal(object)

    # 一次登录请求的结果：成功与否、错误消息
    login_result = Signal(bool, str)

    # 普通状态消息：翻译键
    message = Signal(str)

    # 后台线程向主线程传递事件
    _worker_event = Signal(int, str, object)

    def __init__(self, ctx, parent=None):
        super().__init__(parent)

        self.ctx = ctx

        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="telas-account",
        )

        self._busy = False
        self._logged_in = False
        self._switching = False

        # 切换账号前暂存的原账号信息
        self._previous_account = None

        # 用于识别已经失效的后台任务
        self._epoch = ctx.account_epoch

        self._worker_event.connect(self._handle_worker_event)

    # ---------------------------------------------------------
    # 基本状态
    # ---------------------------------------------------------

    @property
    def busy(self):
        return self._busy

    @property
    def logged_in(self):
        return self._logged_in

    @property
    def switching(self):
        return self._switching

    def _set_busy(self, busy):
        self._busy = bool(busy)
        self.login_busy.emit(self._busy)

    def _next_epoch(self):
        self.ctx.account_epoch += 1
        self._epoch = self.ctx.account_epoch
        return self._epoch

    def _is_current(self, epoch):
        return epoch == self.ctx.account_epoch

    def _clear_account_data(self):
        self.ctx.courses = {}
        self.ctx.current_course_id = ""
        self.ctx.current_course_name = ""

        self._logged_in = False

        self.login_state.emit(False)
        self.account_info.emit("", "")
        self.courses_loaded.emit({})

    def _saved_credentials(self):
        return (
            self.ctx.settings.get("user", ""),
            self.ctx.settings.get("pwd", ""),
        )

    def _save_credentials(self, user, password):
        self.ctx.settings.set("user", user)
        self.ctx.settings.set("pwd", password)
        self.ctx.settings.save()

    def _delete_credentials(self):
        self.ctx.settings.remove("user")
        self.ctx.settings.remove("pwd")
        self.ctx.settings.save()

    # ---------------------------------------------------------
    # 后台任务
    # ---------------------------------------------------------

    def _submit(self, epoch, operation, *args):
        self._executor.submit(
            self._run_worker,
            epoch,
            operation,
            *args,
        )

    def _emit_worker(self, epoch, event, data=None):
        self._worker_event.emit(epoch, event, data)

    def _run_worker(self, epoch, operation, *args):
        try:
            if operation == "login":
                self._worker_login(epoch, *args)

            elif operation == "auto_login":
                self._worker_auto_login(epoch)

            elif operation == "logout":
                self.ctx.api.logout()

            elif operation == "courses":
                self._worker_courses(epoch)

        except Exception as exc:
            self.ctx.log(
                f"[AccountController] "
                f"{type(exc).__name__}: {exc}"
            )

            if operation in ("login", "auto_login"):
                self._emit_worker(
                    epoch,
                    "login_failed",
                    "login_retry",
                )

    # ---------------------------------------------------------
    # 登录
    # ---------------------------------------------------------

    def login(self, user, password):
        """手动登录。返回是否成功启动登录任务。"""

        if self._busy:
            return False

        user = user.strip()

        if not user or not password:
            self.login_result.emit(
                False,
                self.ctx.tr("credentials_required"),
            )
            return False

        epoch = self._next_epoch()

        self._set_busy(True)

        self._submit(
            epoch,
            "login",
            user,
            password,
        )

        return True

    def _worker_login(self, epoch, user, password):
        """后台执行登录请求。"""

        ok = self.ctx.api.login(user, password)

        if not self._is_current(epoch):
            return

        if not ok:
            self._emit_worker(
                epoch,
                "login_failed",
                "login_retry",
            )
            return

        # 账号信息获取失败不应影响已经成功的登录
        try:
            me = self.ctx.api.get_me()
        except Exception as exc:
            self.ctx.log(str(exc))
            me = None

        self._emit_worker(
            epoch,
            "login_success",
            {
                "user": user,
                "password": password,
                "me": me,
            },
        )

        self._worker_courses(epoch)

    # ---------------------------------------------------------
    # 自动登录
    # ---------------------------------------------------------

    def auto_login(self):
        """启动时尝试恢复会话。"""

        if self._busy:
            return False

        epoch = self._next_epoch()

        self._set_busy(True)
        self.message.emit("session_restoring")

        self._submit(epoch, "auto_login")

        return True

    def _worker_auto_login(self, epoch):
        user, password = self._saved_credentials()

        try:
            session_loaded = self.ctx.api.load_session()
        except Exception as exc:
            self.ctx.log(str(exc))
            session_loaded = False

        if session_loaded:
            try:
                me = self.ctx.api.get_me()
            except Exception as exc:
                self.ctx.log(str(exc))
                me = None

            if me and me.get("id"):
                self._emit_worker(
                    epoch,
                    "session_success",
                    {
                        "user": user,
                        "me": me,
                    },
                )

                self._worker_courses(epoch)
                return

            self._emit_worker(
                epoch,
                "message",
                "session_expired",
            )

        if user and password:
            self._worker_login(
                epoch,
                user,
                password,
            )
        else:
            self._emit_worker(
                epoch,
                "auto_login_empty",
            )

    # ---------------------------------------------------------
    # 课程
    # ---------------------------------------------------------

    def refresh_courses(self):
        """重新加载当前账号的课程。"""

        if not self._logged_in or self._busy:
            return False

        epoch = self._epoch

        self._submit(
            epoch,
            "courses",
        )

        return True

    def _worker_courses(self, epoch):
        if not self._is_current(epoch):
            return

        courses = self.ctx.api.get_courses() or {}

        if not self._is_current(epoch):
            return

        self._emit_worker(
            epoch,
            "courses",
            courses,
        )

    # ---------------------------------------------------------
    # 切换账号
    # ---------------------------------------------------------

    def begin_switch(self):
        """开始切换账号，暂存原账号凭据。

        只负责切换状态，不负责打开弹窗。
        """

        if self._busy:
            return False

        if self._switching:
            return False

        self._previous_account = self._saved_credentials()
        self._switching = True

        self._next_epoch()
        self._clear_account_data()

        # 清除旧会话，但暂时不删除保存的账号密码
        self._submit(
            self._epoch,
            "logout",
        )

        return True

    def cancel_switch(self):
        """取消切换，尝试重新登录原账号。"""

        if not self._switching:
            return False

        if self._busy:
            return False

        previous = self._previous_account

        self._switching = False
        self._previous_account = None

        if not previous:
            self.message.emit("restore_unavailable")
            return False

        user, password = previous

        if not user or not password:
            self.message.emit("restore_unavailable")
            return False

        self.message.emit("restore_account")

        return self.login(user, password)

    # ---------------------------------------------------------
    # 退出登录
    # ---------------------------------------------------------

    def logout(self):
        """执行已确认的退出登录。

        确认弹窗由主窗口负责。
        """

        if self._busy:
            return False

        epoch = self._next_epoch()

        self._switching = False
        self._previous_account = None

        self._clear_account_data()
        self._delete_credentials()

        self._submit(
            epoch,
            "logout",
        )

        self.message.emit("logout_success")

        return True

    # ---------------------------------------------------------
    # 处理后台结果（GUI 主线程）
    # ---------------------------------------------------------

    @Slot(int, str, object)
    def _handle_worker_event(self, epoch, event, data):
        if not self._is_current(epoch):
            return

        if event == "message":
            self.message.emit(data)
            return

        if event == "auto_login_empty":
            self._set_busy(False)
            self.message.emit("enter_credentials")
            return

        if event == "login_failed":
            self._set_busy(False)

            # 切换账号失败时，保留切换状态，
            # 以便用户继续重试或取消并恢复原账号。
            self.login_result.emit(
                False,
                self.ctx.tr(data),
            )

            return

        if event in ("login_success", "session_success"):
            user = data.get("user", "")
            me = data.get("me") or {}

            if event == "login_success":
                self._save_credentials(
                    user,
                    data.get("password", ""),
                )

            name = " ".join(
                str(part)
                for part in (
                    me.get("familyName"),
                    me.get("givenName"),
                )
                if part
            )

            self._logged_in = True
            self._switching = False
            self._previous_account = None

            self.login_state.emit(True)
            self.account_info.emit(name, user)

            self._set_busy(False)

            if event == "session_success":
                self.message.emit("session_ok")
            else:
                self.message.emit("login_ok")

            self.login_result.emit(True, "")

            return

        if event == "courses":
            courses = data or {}

            self.ctx.courses = courses
            self.courses_loaded.emit(courses)

            self.ctx.log(
                self.ctx.tr(
                    "courses_count",
                    len(courses),
                )
            )

    # ---------------------------------------------------------
    # 关闭
    # ---------------------------------------------------------

    def shutdown(self):
        """窗口关闭时停止接收旧任务结果。"""

        self._next_epoch()

        self._executor.shutdown(
            wait=False,
            cancel_futures=True,
        )
