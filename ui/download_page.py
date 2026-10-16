"""文件下载页：扫描、勾选文件树和下载进度。保存选项由设置页管理。"""

import html
import os
import re
import threading

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QTreeWidget,
    QTreeWidgetItem,
    QProgressBar,
    QHeaderView,
)

from utils.theme import colors


class DownloadPage(QWidget):
    _CHECK_STATE_ROLE = Qt.ItemDataRole.UserRole + 3

    def __init__(self, ctx, parent=None):
        super().__init__(parent)

        self.ctx = ctx
        self.course_id = ""
        self._download_files = []
        self._scanning = False
        self._downloading = False

        self._build_ui()

        self.ctx.signals.course_changed.connect(
            self.on_course_changed
        )
        self.ctx.signals.populate_tree.connect(
            self._populate_file_tree
        )
        self.ctx.signals.theme_changed.connect(
            self._refresh_name_links
        )

    def tr(self, key, *args):
        return self.ctx.tr(key, *args)

    # ------------------------------------------------------------- 界面

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # --------------------------------------------------------- 工具栏

        self.toolbar_widget = QWidget()

        action_layout = QHBoxLayout(self.toolbar_widget)
        action_layout.setContentsMargins(9, 0, 9, 0)
        action_layout.setSpacing(8)

        self.select_all_cb = QCheckBox()
        self.select_all_cb.setTristate(True)
        self.select_all_cb.setChecked(False)

        self.select_all_cb.stateChanged.connect(
            self._on_select_all
        )

        action_layout.addWidget(self.select_all_cb)
        action_layout.addStretch()

        self.scan_btn = QPushButton()
        self.scan_btn.setObjectName("secondary")
        self.scan_btn.setFixedSize(110, 34)

        self.scan_btn.clicked.connect(
            self._start_scan
        )

        action_layout.addWidget(self.scan_btn)

        self.download_btn = QPushButton()
        self.download_btn.setFixedSize(110, 34)

        self.download_btn.clicked.connect(
            self._start_download_selected
        )

        action_layout.addWidget(self.download_btn)

        layout.addWidget(self.toolbar_widget)

        # --------------------------------------------------------- 文件树

        self.file_tree = QTreeWidget()
        self.file_tree.setColumnCount(2)
        self.file_tree.setAlternatingRowColors(True)
        self.file_tree.setIndentation(22)

        header = self.file_tree.header()
        header.setStretchLastSection(False)

        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch
        )

        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Fixed
        )

        header.resizeSection(1, 90)

        self.file_tree.itemChanged.connect(
            self._on_tree_item_changed
        )

        self.tree_container = QWidget()

        tree_layout = QHBoxLayout(self.tree_container)
        tree_layout.setContentsMargins(9, 0, 9, 0)
        tree_layout.setSpacing(0)

        tree_layout.addWidget(self.file_tree)

        layout.addWidget(self.tree_container, 1)

        # --------------------------------------------------------- 进度条

        self.download_progress = QProgressBar()
        self.download_progress.setRange(0, 100)
        self.download_progress.setValue(0)
        self.download_progress.setFixedHeight(18)
        self.download_progress.setFormat("%v / %m")
        self.download_progress.setVisible(False)

        layout.addWidget(self.download_progress)

        # --------------------------------------------------------- 初始化

        self.retranslate()

        self._show_empty_message(
            self.tr("empty_state")
        )

        self._update_action_buttons()

    def retranslate(self):
        self.scan_btn.setText(
            self.tr("refresh")
        )

        self.download_btn.setText(
            self.tr("download")
        )

        self.select_all_cb.setText(
            self.tr("select_all")
        )

        header = self.file_tree.headerItem()

        if header:
            header.setText(
                0,
                self.tr("col_name")
            )

            header.setText(
                1,
                self.tr("col_type")
            )

            header.setTextAlignment(
                1,
                Qt.AlignmentFlag.AlignCenter
            )

        # 切换语言时更新空状态提示。
        if self._is_empty_message():
            if not self.course_id:
                message = self.tr("empty_state")
            else:
                message = self.tr("scan_done", 0)

            self._show_empty_message(message)

    # ------------------------------------------------------------- 空状态

    def _is_empty_message(self):
        if self.file_tree.topLevelItemCount() != 1:
            return False

        item = self.file_tree.topLevelItem(0)

        return bool(
            item.data(
                0,
                Qt.ItemDataRole.UserRole + 4
            )
        )

    def _show_empty_message(self, message):
        """
        在文件树内部显示空状态。

        不隐藏工具栏、文件树或表头。
        """

        self.file_tree.blockSignals(True)
        self.file_tree.clear()

        item = QTreeWidgetItem([
            message,
            ""
        ])

        item.setFlags(
            Qt.ItemFlag.ItemIsEnabled
        )

        item.setData(
            0,
            Qt.ItemDataRole.UserRole + 4,
            True
        )

        item.setTextAlignment(
            0,
            Qt.AlignmentFlag.AlignCenter
        )

        self.file_tree.addTopLevelItem(item)

        self.file_tree.blockSignals(False)

        self._reset_select_all()
        self._update_action_buttons()

    def _reset_select_all(self):
        self.select_all_cb.blockSignals(True)

        self.select_all_cb.setCheckState(
            Qt.CheckState.Unchecked
        )

        self.select_all_cb.blockSignals(False)

    def _update_action_buttons(self):
        """
        根据课程、扫描状态和选中文件更新按钮。
        """

        has_course = bool(self.course_id)

        self.scan_btn.setEnabled(
            has_course and not self._scanning
        )

        has_items = self._has_real_items()

        self.select_all_cb.setEnabled(
            has_items and not self._downloading
        )

        has_selection = bool(
            self._get_checked_urls()
        )

        self.download_btn.setEnabled(
            has_selection and not self._downloading
        )

    def _has_real_items(self):
        if self.file_tree.topLevelItemCount() == 0:
            return False

        return not self._is_empty_message()

    # ------------------------------------------------------------- 课程切换

    def on_course_changed(self, course_id, course_name):
        self.course_id = str(course_id or "")

        self._download_files = []

        self.download_progress.setVisible(False)

        self.file_tree.blockSignals(True)
        self.file_tree.clear()
        self.file_tree.blockSignals(False)

        self._reset_select_all()

        if not self.course_id:
            self._show_empty_message(
                self.tr("empty_state")
            )
            return

        self._show_empty_message(
            self.tr("scanning_files")
        )

        self._start_scan()

    def reset(self):
        """
        切换账号时清除上一个账号的课程与文件列表。
        """

        self.course_id = ""
        self._download_files = []

        self._scanning = False
        self._downloading = False

        self.file_tree.blockSignals(True)
        self.file_tree.clear()
        self.file_tree.blockSignals(False)

        self.download_progress.setVisible(False)

        self._reset_select_all()

        self._show_empty_message(
            self.tr("empty_state")
        )

        self._update_action_buttons()

    # ------------------------------------------------------------- 扫描

    def _start_scan(self):
        if not self.course_id:
            self.ctx.log(
                self.tr("select_course_first")
            )
            return

        if self._scanning:
            return

        self._scanning = True

        self._show_empty_message(
            self.tr("scanning_files")
        )

        self._update_action_buttons()

        self.ctx.signals.set_busy.emit(
            self.scan_btn,
            True
        )

        course_id = self.course_id
        epoch = self.ctx.account_epoch

        threading.Thread(
            target=self._scan_thread,
            args=(course_id, epoch),
            daemon=True,
        ).start()

    def _scan_thread(self, course_id, epoch):
        self.ctx.log(
            self.tr("scanning_files")
        )

        try:
            tree = self.ctx.downloader.scan_tree(
                course_id,
                "ROOT"
            )

            if epoch != self.ctx.account_epoch:
                return

            if course_id != self.course_id:
                return

            self.ctx.signals.populate_tree.emit(
                self.file_tree,
                tree
            )

            total = self.ctx.downloader.count_files(
                tree
            )

            self.ctx.log(
                self.tr("scan_done", total)
            )

        except Exception as e:
            self.ctx.log(str(e))

        finally:
            # 与原有全局 busy 信号保持兼容。
            self.ctx.signals.set_busy.emit(
                self.scan_btn,
                False
            )

            self._scanning = False

            # 这里只恢复按钮状态；
            # 文件树更新仍通过 populate_tree 信号进行。
            self._update_action_buttons()

    # ------------------------------------------------------------- 文件树

    def _populate_file_tree(self, tree_widget, nodes):
        if tree_widget is not self.file_tree:
            return

        tree_widget.blockSignals(True)
        tree_widget.clear()

        if nodes:
            self._add_tree_items(
                tree_widget,
                nodes
            )

        tree_widget.blockSignals(False)

        self._reset_select_all()

        if not nodes:
            self._show_empty_message(
                self.tr("scan_done", 0)
            )

        self._update_action_buttons()

    def _add_tree_items(self, parent, nodes):
        for node in nodes:
            name = node.get("name", "")

            item = QTreeWidgetItem()

            self._set_item_check_state(
                item,
                Qt.CheckState.Unchecked
            )

            item.setFlags(
                item.flags()
                & ~Qt.ItemFlag.ItemIsUserCheckable
                & ~Qt.ItemFlag.ItemIsAutoTristate
            )

            item.setText(0, "")

            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                node.get("url", "")
            )

            item.setData(
                0,
                Qt.ItemDataRole.UserRole + 1,
                node.get("type", "other")
            )

            item.setData(
                0,
                Qt.ItemDataRole.UserRole + 2,
                name
            )

            type_key = {
                "lesson": "type_lesson",
                "file": "type_file",
                "other": "type_other",
            }.get(
                node.get("type"),
                "type_other"
            )

            item.setText(
                1,
                self.tr(type_key)
            )

            item.setTextAlignment(
                1,
                Qt.AlignmentFlag.AlignCenter
            )

            if parent is self.file_tree:
                parent.addTopLevelItem(item)
            else:
                parent.addChild(item)

            self._set_name_and_url(
                item,
                name,
                node.get("link", "")
            )

            self._add_tree_items(
                item,
                node.get("children", [])
            )

            if (
                node.get("type") == "other"
                and item.childCount()
            ):
                item.setExpanded(True)

    def _set_name_and_url(self, item, name, url):
        cell = QWidget()

        cell_layout = QHBoxLayout(cell)
        cell_layout.setContentsMargins(0, 0, 0, 0)
        cell_layout.setSpacing(8)

        checkbox = QCheckBox()
        checkbox.setTristate(False)

        checkbox.setCheckState(
            self._item_check_state(item)
        )

        checkbox.stateChanged.connect(
            lambda state, current=item:
            self._on_item_checkbox_changed(
                current,
                state
            )
        )

        cell_layout.addWidget(checkbox)

        name_label = QLabel(name)

        if url:
            name_label.setProperty(
                "name_link_url",
                url
            )

            name_label.setProperty(
                "name_link_title",
                name
            )

            self._render_name_link(
                name_label
            )

            name_label.setTextFormat(
                Qt.TextFormat.RichText
            )

            name_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextBrowserInteraction
            )

            name_label.setOpenExternalLinks(True)
            name_label.setToolTip(url)

        else:
            name_label.setTextFormat(
                Qt.TextFormat.PlainText
            )

        cell_layout.addWidget(name_label)
        cell_layout.addStretch(1)

        self.file_tree.setItemWidget(
            item,
            0,
            cell
        )

    @staticmethod
    def _render_name_link(label):
        font = label.font()
        font.setBold(True)
        label.setFont(font)

        url = html.escape(
            label.property("name_link_url"),
            quote=True
        )

        title = html.escape(
            label.property("name_link_title")
        )

        label.setText(
            f'<a href="{url}" '
            f'style="color:{colors()["text"]}; '
            f'text-decoration:none; '
            f'font-weight:700;">'
            f'<b>{title}</b></a>'
        )

    def _refresh_name_links(self):
        for label in self.file_tree.findChildren(QLabel):
            if label.property("name_link_url"):
                self._render_name_link(label)

    # ------------------------------------------------------------- 勾选

    def _on_item_checkbox_changed(self, item, state):
        check_state = Qt.CheckState(state)

        self.file_tree.blockSignals(True)

        self._set_item_check_state(
            item,
            check_state
        )

        if check_state != Qt.CheckState.PartiallyChecked:

            def set_descendants(parent):
                for index in range(parent.childCount()):
                    child = parent.child(index)

                    self._set_item_check_state(
                        child,
                        check_state
                    )

                    set_descendants(child)

            set_descendants(item)

        self._update_parent_state(item)

        self.file_tree.blockSignals(False)

        self._sync_tree_checkboxes()
        self._update_select_all_state()
        self._update_action_buttons()

    def _sync_tree_checkboxes(self):

        def sync(item):
            cell = self.file_tree.itemWidget(
                item,
                0
            )

            checkbox = (
                cell.findChild(QCheckBox)
                if cell
                else None
            )

            if checkbox:
                checkbox.blockSignals(True)

                checkbox.setCheckState(
                    self._item_check_state(item)
                )

                checkbox.blockSignals(False)

            for index in range(item.childCount()):
                sync(item.child(index))

        for index in range(
            self.file_tree.topLevelItemCount()
        ):
            sync(
                self.file_tree.topLevelItem(index)
            )

    def _on_tree_item_changed(self, item, column):
        if column != 0:
            return

        self.file_tree.blockSignals(True)

        self._update_parent_state(item)

        self.file_tree.blockSignals(False)

        self._sync_tree_checkboxes()
        self._update_select_all_state()
        self._update_action_buttons()

    def _update_parent_state(self, item):
        parent = item.parent()

        if parent is None:
            return

        checked = 0
        partial = 0
        total = parent.childCount()

        for i in range(total):
            state = self._item_check_state(
                parent.child(i)
            )

            if state == Qt.CheckState.Checked:
                checked += 1

            elif state == Qt.CheckState.PartiallyChecked:
                partial += 1

        if checked == total:
            self._set_item_check_state(
                parent,
                Qt.CheckState.Checked
            )

        elif checked == 0 and partial == 0:
            self._set_item_check_state(
                parent,
                Qt.CheckState.Unchecked
            )

        else:
            self._set_item_check_state(
                parent,
                Qt.CheckState.PartiallyChecked
            )

        self._update_parent_state(parent)

    def _item_check_state(self, item):
        value = item.data(
            0,
            self._CHECK_STATE_ROLE
        )

        return Qt.CheckState(
            value if value is not None else 0
        )

    def _set_item_check_state(self, item, state):
        item.setData(
            0,
            self._CHECK_STATE_ROLE,
            int(state.value)
        )

    def _update_select_all_state(self):
        top_count = self.file_tree.topLevelItemCount()

        if not self._has_real_items():
            self._reset_select_all()
            return

        if top_count == 0:
            self._reset_select_all()
            return

        checked = 0
        partial = 0

        for i in range(top_count):
            state = self._item_check_state(
                self.file_tree.topLevelItem(i)
            )

            if state == Qt.CheckState.Checked:
                checked += 1

            elif state == Qt.CheckState.PartiallyChecked:
                partial += 1

        self.select_all_cb.blockSignals(True)

        if checked == top_count:
            self.select_all_cb.setCheckState(
                Qt.CheckState.Checked
            )

        elif checked == 0 and partial == 0:
            self.select_all_cb.setCheckState(
                Qt.CheckState.Unchecked
            )

        else:
            self.select_all_cb.setCheckState(
                Qt.CheckState.PartiallyChecked
            )

        self.select_all_cb.blockSignals(False)

    def _on_select_all(self, state):
        if not self._has_real_items():
            return

        if state == 1:
            self.select_all_cb.blockSignals(True)

            self.select_all_cb.setCheckState(
                Qt.CheckState.Checked
            )

            self.select_all_cb.blockSignals(False)

            state = 2

        self.file_tree.blockSignals(True)

        check_state = (
            Qt.CheckState.Checked
            if state == 2
            else Qt.CheckState.Unchecked
        )

        def set_descendants(item):
            self._set_item_check_state(
                item,
                check_state
            )

            for index in range(item.childCount()):
                set_descendants(
                    item.child(index)
                )

        for i in range(
            self.file_tree.topLevelItemCount()
        ):
            set_descendants(
                self.file_tree.topLevelItem(i)
            )

        self.file_tree.blockSignals(False)

        self._sync_tree_checkboxes()
        self._update_action_buttons()

    # ------------------------------------------------------------- 文件选择

    def _get_checked_urls(self):
        results = []

        if not self._has_real_items():
            return results

        for i in range(
            self.file_tree.topLevelItemCount()
        ):
            self._collect_checked(
                self.file_tree.topLevelItem(i),
                results
            )

        return results

    def _collect_checked(self, item, results):
        if item.childCount() == 0:
            if (
                self._item_check_state(item)
                == Qt.CheckState.Checked
                and item.data(
                    0,
                    Qt.ItemDataRole.UserRole + 1
                ) == "file"
            ):
                url = item.data(
                    0,
                    Qt.ItemDataRole.UserRole
                )

                name = (
                    item.data(
                        0,
                        Qt.ItemDataRole.UserRole + 2
                    )
                    or ""
                )

                if url:
                    results.append(
                        (name, url)
                    )

        else:
            for i in range(item.childCount()):
                self._collect_checked(
                    item.child(i),
                    results
                )

    # ------------------------------------------------------------- 下载

    def _start_download_selected(self):
        if self._downloading:
            return

        files = self._get_checked_urls()

        if not files:
            self.ctx.log(
                self.tr("no_selection")
            )
            return

        default_path = os.path.join(
            os.path.expanduser("~"),
            "Downloads",
            "Blackboard_download"
        )

        save_path = (
            self.ctx.settings.get(
                "save_path",
                default_path
            )
            or ""
        ).strip()

        if not save_path:
            self.ctx.log(
                self.tr("no_path")
            )
            return

        self._download_files = files

        self.download_progress.setRange(
            0,
            len(files)
        )

        self.download_progress.setValue(0)

        self.ctx.signals.set_progress.emit(
            self.download_progress,
            0,
            self.tr("progress_format").format(
                0,
                len(files),
                ""
            )
        )

        self.download_progress.setVisible(True)

        self._downloading = True
        self._update_action_buttons()

        self.ctx.signals.set_busy.emit(
            self.download_btn,
            True
        )

        course_name = (
            self.ctx.current_course_name
            or ""
        )

        if not self.ctx.settings.get(
            "save_term_prefix",
            False
        ):
            short_name = re.sub(
                r"^\s*\d{4}(?:年度)?\s*"
                r"(?:前期|後期|后期)\s*",
                "",
                course_name
            ).strip()

            course_name = (
                short_name or course_name
            )

        threading.Thread(
            target=self._download_thread,
            args=(
                files,
                save_path,
                course_name
            ),
            daemon=True,
        ).start()

    def _download_thread(
        self,
        files,
        save_path,
        course_name
    ):
        total = len(files)

        self.ctx.log(
            self.tr(
                "download_start",
                total
            )
        )

        def progress_cb(i, size, safe_name):
            fmt = self.tr(
                "progress_format"
            ).format(
                i,
                total,
                safe_name
            )

            self.ctx.signals.set_progress.emit(
                self.download_progress,
                i,
                fmt
            )

            self.ctx.log(
                self.tr(
                    "download_progress",
                    i,
                    total,
                    size,
                    safe_name
                )
            )

        try:
            ok, _ = (
                self.ctx.downloader.download_files(
                    files,
                    save_path,
                    course_name,
                    progress_cb=progress_cb
                )
            )

            self.ctx.log(
                self.tr("download_done")
            )

            self.ctx.signals.toast.emit(
                self.tr("download_done")
                + f" ({ok}/{total})",
                (
                    "success"
                    if ok == total
                    else "error"
                )
            )

        except Exception as e:
            self.ctx.log(str(e))

            self.ctx.signals.toast.emit(
                str(e)[:80],
                "error"
            )

        finally:
            self.ctx.signals.set_progress.emit(
                self.download_progress,
                -1,
                ""
            )

            self.ctx.signals.set_busy.emit(
                self.download_btn,
                False
            )

            self._downloading = False
            self._update_action_buttons()
