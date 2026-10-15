"""测验识别页面。"""

import threading

from PySide6.QtCore import Qt, QObject, Signal
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


class QuizScanSignals(QObject):
    """用于将后台扫描结果安全地传回 UI 线程。"""

    finished = Signal(str, int, int, object, str)


class QuizPage(QWidget):
    def __init__(self, ctx: AppContext):
        super().__init__()

        self.ctx = ctx

        self.course_id = str(
            getattr(ctx, "current_course_id", "") or ""
        )

        self._scan_generation = 0
        self._loading = False
        self._has_loaded = False
        self._last_loaded_course_id = ""

        self._scan_signals = QuizScanSignals()
        self._scan_signals.finished.connect(
            self._on_scan_finished
        )

        self._build_ui()

        # 课程切换后，自动扫描新课程。
        self.ctx.signals.course_changed.connect(
            self.on_course_changed
        )

    # -------------------------------------------------------------- 界面
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 标题和刷新按钮
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.title_label = QLabel()
        self.title_label.setObjectName("page_title")

        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        self.refresh_btn = QPushButton()
        self.refresh_btn.setObjectName("secondary")
        self.refresh_btn.setFixedHeight(34)
        self.refresh_btn.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(self.refresh_btn)

        layout.addLayout(header_layout)

        # 测验列表
        self.quiz_list = QListWidget()
        self.quiz_list.setAlternatingRowColors(True)
        layout.addWidget(self.quiz_list, 1)

        # 状态提示
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.status_label.setObjectName("empty_state")
        layout.addWidget(self.status_label)

        self.retranslate()
        self._show_status("请先选择一门课程。")

    def tr(self, key, *args):
        return self.ctx.tr(key, *args)

    def retranslate(self):
        self.title_label.setText(self.tr("tab_quiz"))
        self.refresh_btn.setText("↻ 刷新")

    # -------------------------------------------------------------- 页面显示
    def showEvent(self, event):
        super().showEvent(event)

        # 首次进入页面或课程发生变化时自动读取。
        current_course_id = str(
            getattr(self.ctx, "current_course_id", "") or ""
        )

        if current_course_id:
            if (
                not self._has_loaded
                or current_course_id != self._last_loaded_course_id
            ):
                self.course_id = current_course_id
                self.refresh()
        else:
            self.course_id = ""
            self._show_status("请先选择一门课程。")

    # -------------------------------------------------------------- 课程切换
    def on_course_changed(self, course_id, course_name):
        self.course_id = str(course_id or "")

        # 课程切换后，立即清除旧课程的测验。
        self.quiz_list.clear()
        self._has_loaded = False
        self._last_loaded_course_id = ""

        if not self.course_id:
            self._show_status("请先选择一门课程。")
            return

        self.refresh()

    # -------------------------------------------------------------- 刷新
    def refresh(self):
        """重新读取当前课程的测验列表。"""

        course_id = str(
            getattr(self.ctx, "current_course_id", "")
            or self.course_id
            or ""
        )

        if not course_id:
            self.course_id = ""
            self.quiz_list.clear()
            self._show_status("请先选择一门课程。")
            self.ctx.log("[测验识别] 尚未选择课程。")
            return

        self.course_id = course_id

        # 每次开始扫描都增加编号。
        # 较早的扫描即使晚返回，也不会覆盖最新结果。
        self._scan_generation += 1
        generation = self._scan_generation

        account_epoch = self.ctx.account_epoch

        self._loading = True
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("正在刷新…")
        self._show_status("正在读取测验列表，请稍候…")

        self.ctx.log(
            f"[测验识别] 正在刷新课程："
            f"{self.ctx.current_course_name or course_id}"
        )

        threading.Thread(
            target=self._scan_thread,
            args=(
                course_id,
                generation,
                account_epoch,
            ),
            daemon=True,
        ).start()

    def _scan_thread(
        self,
        course_id,
        generation,
        account_epoch,
    ):
        quizzes = None
        error = ""

        try:
            quizzes = self.ctx.api.get_course_quizzes(
                course_id
            )

            if quizzes is None:
                error = "读取测验失败，请检查登录状态和 API 日志。"

        except Exception as e:
            error = (
                f"读取测验时发生异常：{type(e).__name__}"
            )
            self.ctx.log(
                f"[测验识别] 异常：{type(e).__name__}: {e}"
            )

        self._scan_signals.finished.emit(
            course_id,
            generation,
            account_epoch,
            quizzes,
            error,
        )

    # -------------------------------------------------------------- 显示结果
    def _on_scan_finished(
        self,
        course_id,
        generation,
        account_epoch,
        quizzes,
        error,
    ):
        # 忽略旧扫描结果。
        if generation != self._scan_generation:
            return

        # 忽略旧账号的数据。
        if account_epoch != self.ctx.account_epoch:
            return

        # 忽略已经切换课程的旧结果。
        current_course_id = str(
            getattr(self.ctx, "current_course_id", "")
            or self.course_id
            or ""
        )

        if str(course_id) != current_course_id:
            return

        self._loading = False
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("↻ 刷新")

        self.quiz_list.clear()

        if error or quizzes is None:
            self._has_loaded = False
            self._show_status(error or "读取测验失败。")
            self.ctx.log(
                f"[测验识别] {error or '读取测验失败。'}"
            )
            return

        self._has_loaded = True
        self._last_loaded_course_id = str(course_id)

        for quiz in quizzes:
            title = quiz.get("title") or "未命名测验"
            quiz_id = quiz.get("id", "")

            item = QListWidgetItem(title)
            item.setData(
                Qt.ItemDataRole.UserRole,
                quiz_id,
            )

            self.quiz_list.addItem(item)

        count = self.quiz_list.count()

        if count == 0:
            self._show_status("当前课程没有找到测验。")
        else:
            self._show_status(
                f"共找到 {count} 个测验。"
            )

        self.ctx.log(
            f"[测验识别] 列表更新完成，共 {count} 个测验。"
        )

    # -------------------------------------------------------------- 状态
    def _show_status(self, text):
        self.status_label.setText(text)

        # 有测验时隐藏状态文字，让列表占据主要空间。
        self.status_label.setVisible(
            self.quiz_list.count() == 0
        )

    def reset(self):
        """切换账号时清除旧账号的测验数据。"""

        self._scan_generation += 1
        self._loading = False
        self._has_loaded = False
        self._last_loaded_course_id = ""
        self.course_id = ""

        self.quiz_list.clear()
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("↻ 刷新")

        self._show_status("请先选择一门课程。")
