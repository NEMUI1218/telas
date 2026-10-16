"""主题：两套配色 + 一份样式表模板。

所有颜色都从 PALETTES 取，样式表模板里不写死颜色。控件需要特殊外观时，
给它一个 objectName 或动态属性，然后在 _QSS 里写规则；不要在控件上 setStyleSheet。

样式表里用到的小图标（复选框的勾、下拉箭头）没有随程序分发的图片文件，
而是启动时画到临时目录里，这样 PyInstaller 的 spec 不需要加 datas。
"""
import os
import tempfile
from string import Template

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPalette, QPen

PALETTES = {
    "dark": {
        "bg": "#111318",            # 窗口底色
        "sidebar": "#0c0e12",
        "surface": "#181b22",       # 卡片
        "input": "#1f232c",         # 输入框、下拉框
        "well": "#12141a",          # 卡片里的大块文本区
        "hover": "#262b36",
        "row_alt": "#1c2028",
        "border": "#2a2f3a",
        "border_strong": "#3b4252",
        "text": "#e7e9ee",
        "muted": "#a0a7b4",
        "faint": "#6f7785",
        "accent": "#2f6feb",        # 主按钮底色，白字对比度 4.6
        "accent_hover": "#4a82f0",
        "accent_pressed": "#2559c4",
        "accent_text": "#7eaaff",   # 深色底上的强调色文字、焦点框
        "accent_soft": "#1b2a4a",
        "on_accent": "#ffffff",
        "progress_chunk": "#27467f",
        "success": "#4cc38a",
        "success_soft": "#15291f",
        "danger": "#f0616d",
        "danger_soft": "#2c171b",
        "danger_border": "#7a2f37",
        "toast_success": "#1f8f55",
        "toast_error": "#d1343f",
        "toast_info": "#4b5568",
    },
    "light": {
        "bg": "#f3f4f7",
        "sidebar": "#ffffff",
        "surface": "#ffffff",
        "input": "#ffffff",
        "well": "#f8f9fb",
        "hover": "#eceef3",
        "row_alt": "#f8f9fb",
        "border": "#dfe2e8",
        "border_strong": "#c7ccd6",
        "text": "#1b1f27",
        "muted": "#596170",
        "faint": "#8a92a0",
        "accent": "#2563eb",
        "accent_hover": "#1d4fd8",
        "accent_pressed": "#1a43b8",
        "accent_text": "#2563eb",
        "accent_soft": "#e6eeff",
        "on_accent": "#ffffff",
        "progress_chunk": "#bcd2ff",
        "success": "#1a7f45",
        "success_soft": "#e3f5ea",
        "danger": "#d1343f",
        "danger_soft": "#fde8ea",
        "danger_border": "#eeaab0",
        "toast_success": "#1f8f55",
        "toast_error": "#d1343f",
        "toast_info": "#4b5568",
    },
}

_QSS = Template("""
* {
    font-family: "Segoe UI", "Yu Gothic UI", "Microsoft YaHei UI", sans-serif;
    font-size: 13px;
}
QMainWindow, QDialog, QMessageBox {
    background-color: $bg;
}
QWidget {
    color: $text;
}
QLabel {
    background: transparent;
}
QToolTip {
    background-color: $input;
    color: $text;
    border: 1px solid $border_strong;
    padding: 4px 8px;
}

/* ---------------------------------------------------------------- 侧栏 */
QWidget#sidebar {
    background-color: $sidebar;
    border-right: 1px solid $border;
}
QLabel#app_title {
    font-size: 15px;
    font-weight: 700;
    padding: 2px 10px 10px 10px;
}
QPushButton#nav_btn {
    background-color: transparent;
    color: $muted;
    border: none;
    border-radius: 8px;
    padding: 0 12px;
    font-weight: 600;
    text-align: left;
}
QPushButton#nav_btn:hover {
    background-color: $hover;
    color: $text;
}
QPushButton#nav_btn:checked {
    background-color: $accent_soft;
    color: $accent_text;
}

/* ---------------------------------------------------------------- 文字 */
QLabel#field_label {
    color: $muted;
}
QLabel#hint {
    color: $faint;
    font-size: 12px;
}
QLabel#empty_state {
    color: $faint;
    font-size: 15px;
    padding: 40px;
}
QLabel#status_text {
    color: $muted;
    font-size: 12px;
}
QLabel#status_badge {
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 600;
}
QLabel#status_badge[state="on"] {
    color: $success;
    background-color: $success_soft;
}
QLabel#status_badge[state="off"] {
    color: $muted;
    background-color: $hover;
}
QLabel#toast {
    color: #ffffff;
    border-radius: 8px;
    padding: 10px 16px;
    font-weight: 600;
}
QLabel#toast[kind="success"] { background-color: $toast_success; }
QLabel#toast[kind="error"]   { background-color: $toast_error; }
QLabel#toast[kind="info"]    { background-color: $toast_info; }

/* ---------------------------------------------------------------- 卡片 */
QGroupBox {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 10px;
    margin-top: 0px;
    padding: 38px 12px 12px 12px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    top: 12px;
    color: $muted;
}
QFrame#log_panel {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 10px;
}

/* ---------------------------------------------------------------- 输入 */
QLineEdit, QComboBox {
    background-color: $input;
    color: $text;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 4px 10px;
    selection-background-color: $accent;
    selection-color: $on_accent;
}
QLineEdit:hover, QComboBox:hover {
    border-color: $border_strong;
}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
    border-color: $accent_text;
}
QComboBox::drop-down {
    border: none;
    width: 28px;
}
QComboBox::down-arrow {
    image: url($icons/chevron.png);
    width: 12px;
    height: 12px;
}
QComboBox QAbstractItemView {
    background-color: $input;
    color: $text;
    border: 1px solid $border_strong;
    selection-background-color: $accent_soft;
    selection-color: $text;
    outline: none;
    padding: 4px;
}
QTextEdit {
    background-color: $well;
    color: $text;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 8px;
    selection-background-color: $accent;
    selection-color: $on_accent;
}
QTextEdit#answer_input, QTextEdit#log_area {
    font-family: "Cascadia Mono", "Consolas", "Yu Gothic UI", "Microsoft YaHei UI", monospace;
}
QTextEdit#log_area {
    font-size: 12px;
}

/* ---------------------------------------------------------------- 按钮 */
QPushButton {
    background-color: $accent;
    color: $on_accent;
    border: 1px solid $accent;
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: $accent_hover;
    border-color: $accent_hover;
}
QPushButton:pressed {
    background-color: $accent_pressed;
    border-color: $accent_pressed;
}
QPushButton:disabled {
    background-color: $hover;
    color: $faint;
    border-color: $border;
}
QPushButton#secondary, QMessageBox QPushButton {
    background-color: $input;
    color: $text;
    border: 1px solid $border_strong;
}
QPushButton#secondary:hover, QMessageBox QPushButton:hover {
    background-color: $hover;
}
QPushButton#secondary:pressed, QMessageBox QPushButton:pressed {
    background-color: $border;
}
QPushButton#secondary:disabled {
    background-color: $hover;
    color: $faint;
    border-color: $border;
}
/* 对话框里只有默认按钮用强调色：按回车会触发的就是它 */
QMessageBox QPushButton {
    min-width: 72px;
}
QMessageBox QPushButton:default {
    background-color: $accent;
    color: $on_accent;
    border-color: $accent;
}
QMessageBox QPushButton:default:hover {
    background-color: $accent_hover;
}
QPushButton#danger {
    background-color: transparent;
    color: $danger;
    border: 1px solid $danger_border;
}
QPushButton#danger:hover {
    background-color: $danger_soft;
}
QPushButton#danger:pressed {
    background-color: $danger_soft;
    border-color: $danger;
}
QPushButton#danger:disabled {
    color: $faint;
    border-color: $border;
}
QPushButton#ghost {
    background-color: transparent;
    color: $muted;
    border: 1px solid transparent;
    padding: 4px 10px;
}
QPushButton#ghost:hover {
    background-color: $hover;
    color: $text;
}
QPushButton#ghost:pressed {
    background-color: $border;
}

/* ---------------------------------------------------------------- 文件树 */
QTreeWidget {
    background-color: $surface;
    alternate-background-color: $row_alt;
    color: $text;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 4px;
    outline: none;
}
QTreeWidget::item {
    padding: 5px 2px;
}
QTreeWidget::item:hover {
    background-color: $hover;
}
QTreeWidget::item:selected {
    background-color: $accent_soft;
    color: $text;
}
QHeaderView::section {
    background-color: $surface;
    color: $muted;
    border: none;
    border-bottom: 1px solid $border;
    padding: 6px 8px;
    font-weight: 600;
}
QCheckBox {
    spacing: 8px;
}
QCheckBox::indicator, QTreeWidget::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid $border_strong;
    border-radius: 9px;
    background-color: $input;
}
QCheckBox::indicator:hover, QTreeWidget::indicator:hover {
    border-color: $accent_text;
}
QCheckBox::indicator:checked, QTreeWidget::indicator:checked {
    background-color: $accent;
    border-color: $accent;
    image: url($icons/check.png);
}
QCheckBox::indicator:indeterminate, QTreeWidget::indicator:indeterminate {
    background-color: $accent;
    border-color: $accent;
    image: url($icons/dash.png);
}

/* ---------------------------------------------------------------- 其他 */
QProgressBar {
    background-color: $hover;
    color: $text;
    border: none;
    border-radius: 9px;
    text-align: center;
    font-size: 12px;
}
QProgressBar::chunk {
    background-color: $progress_chunk;
    border-radius: 9px;
}
QSplitter::handle {
    background-color: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background-color: $border_strong;
    border-radius: 3px;
    min-height: 30px;
    min-width: 30px;
}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background-color: $faint;
}
QScrollBar::add-line, QScrollBar::sub-line {
    width: 0px;
    height: 0px;
}
QScrollBar::add-page, QScrollBar::sub-page {
    background: transparent;
}
""")

_current = "dark"


def current_theme():
    return _current


def colors(theme=None):
    """返回某个主题的配色字典；不传参数时返回当前主题的。"""
    return PALETTES.get(theme or _current, PALETTES["dark"])


# ---------------------------------------------------------------------- 图标
def _draw_strokes(path, color, strokes, width=1.8):
    """把若干折线画成 16×16 的透明底 PNG，同时生成 @2x 版本。坐标按 16 单位写。"""
    base, ext = os.path.splitext(path)
    for scale, suffix in ((1, ""), (2, "@2x")):
        img = QImage(16 * scale, 16 * scale, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(scale, scale)
        pen = QPen(QColor(color))
        pen.setWidthF(width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        for line in strokes:
            painter.drawPolyline([QPointF(x, y) for x, y in line])
        painter.end()
        img.save(base + suffix + ext)


def _ensure_icons(theme):
    """生成样式表引用的图标，返回所在目录（正斜杠路径，供 QSS 的 url() 使用）。"""
    c = PALETTES[theme]
    folder = os.path.join(tempfile.gettempdir(), "BlackboardTool_theme", theme)
    os.makedirs(folder, exist_ok=True)
    _draw_strokes(os.path.join(folder, "check.png"), c["on_accent"],
                  [[(3.5, 8.5), (6.5, 11.5), (12.5, 4.5)]], width=2.0)
    _draw_strokes(os.path.join(folder, "dash.png"), c["on_accent"],
                  [[(4, 8), (12, 8)]], width=2.0)
    _draw_strokes(os.path.join(folder, "chevron.png"), c["muted"],
                  [[(3.5, 6), (8, 10.5), (12.5, 6)]])
    return folder.replace("\\", "/")


def _palette(c):
    """Fusion 风格下没被样式表覆盖到的部分（对话框、树的展开箭头等）用调色板上色。"""
    pal = QPalette()
    role = QPalette.ColorRole
    for r, key in (
        (role.Window, "bg"), (role.WindowText, "text"),
        (role.Base, "input"), (role.AlternateBase, "row_alt"),
        (role.Text, "text"), (role.Button, "input"), (role.ButtonText, "text"),
        (role.ToolTipBase, "input"), (role.ToolTipText, "text"),
        (role.Highlight, "accent"), (role.HighlightedText, "on_accent"),
        (role.PlaceholderText, "faint"), (role.Link, "accent_text"),
    ):
        pal.setColor(r, QColor(c[key]))
    disabled = QPalette.ColorGroup.Disabled
    for r in (role.Text, role.ButtonText, role.WindowText):
        pal.setColor(disabled, r, QColor(c["faint"]))
    return pal


def apply_theme(app, theme="dark"):
    """应用深色、浅色或系统主题。"""
    global _current
    if theme == "system":
        try:
            scheme = app.styleHints().colorScheme()
            theme = "light" if scheme == Qt.ColorScheme.Light else "dark"
        except (AttributeError, RuntimeError):
            theme = "dark"
    if theme not in PALETTES:
        theme = "dark"
    _current = theme
    if app is None:
        return
    c = PALETTES[theme]
    # 统一用 Fusion 做底：系统默认风格和样式表混用时，复选框等控件会画不全
    if app.style().objectName().lower() != "fusion":
        app.setStyle("Fusion")
    app.setPalette(_palette(c))
    app.setStyleSheet(_QSS.substitute(c, icons=_ensure_icons(theme)))
