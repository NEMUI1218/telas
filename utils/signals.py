"""跨线程 UI 信号总线。所有后台线程通过 SignalBus 安全地把结果发回 GUI 线程。"""
from PySide6.QtCore import QObject, Signal


class SignalBus(QObject):
    # 日志 / 状态栏 / 轻提示
    log = Signal(str)
    status = Signal(str)
    toast = Signal(str, str)  # (text, kind: success|error|info)

    # 通用控件更新
    set_text = Signal(object, str)
    clear_widget = Signal(object)
    set_combo_items = Signal(object, list, int, str)  # (combo, items, select_index, placeholder_key)
    set_progress = Signal(object, int, str)  # (bar, value, format)；value < 0 表示隐藏
    set_busy = Signal(object, bool)  # (widget, busy)

    # 文件树
    populate_tree = Signal(object, list)

    # 登录 / 课程 / 语言
    login_state = Signal(bool)
    login_busy = Signal(bool)
    account_info = Signal(str, str)  # (姓名, 学籍番号)；登录后显示在顶栏，姓名没取到时是空串
    course_changed = Signal(str, str)  # (course_id, course_name)
    language_changed = Signal()
    theme_changed = Signal()  # 主题切换后发出；用 QPainter 画的图标要跟着重画
