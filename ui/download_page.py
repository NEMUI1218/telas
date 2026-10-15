"""文件下载页：保存路径 + 扫描 + 勾选文件树 + 下载进度。"""
import html
import os
import threading

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QTreeWidget, QTreeWidgetItem, QFileDialog,
    QProgressBar, QStackedWidget, QHeaderView,
)


class DownloadPage(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.course_id = ""
        self._download_files = []
        self._build_ui()
        self.ctx.signals.course_changed.connect(self.on_course_changed)
        self.ctx.signals.populate_tree.connect(self._populate_file_tree)

    def tr(self, key, *args):
        return self.ctx.tr(key, *args)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ---- 内容栈：空态 / 实际操作区 ----
        self.content_stack = QStackedWidget()

        # 页 0：空态提示
        empty_page = QWidget()
        empty_layout = QVBoxLayout(empty_page)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label = QLabel()
        self.empty_label.setObjectName("empty_state")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.empty_label)
        self.content_stack.addWidget(empty_page)

        # 页 1：实际操作
        active_page = QWidget()
        active_layout = QVBoxLayout(active_page)
        active_layout.setContentsMargins(0, 0, 0, 0)
        active_layout.setSpacing(10)

        # 保存路径：一行，标签在左
        path_layout = QHBoxLayout()
        path_layout.setSpacing(8)
        self.save_label = QLabel()
        self.save_label.setObjectName("field_label")
        path_layout.addWidget(self.save_label)

        self.save_path_input = QLineEdit()
        default_path = self.ctx.settings.get("save_path") or os.path.join(
            os.path.expanduser("~"), "Downloads", "Blackboard_download")
        self.save_path_input.setText(default_path)
        self.save_path_input.setFixedHeight(32)
        self.save_path_input.setPlaceholderText("")
        self.save_path_input.editingFinished.connect(self._save_path_setting)
        path_layout.addWidget(self.save_path_input, 1)

        browse_btn = QPushButton()
        self.browse_btn = browse_btn
        browse_btn.setObjectName("secondary")
        browse_btn.setFixedHeight(32)
        browse_btn.clicked.connect(self._browse_path)
        path_layout.addWidget(browse_btn)
        active_layout.addLayout(path_layout)

        # 工具行：左边全选，右边扫描（次要）和下载（主要）
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        self.select_all_cb = QCheckBox()
        self.select_all_cb.setTristate(True)
        self.select_all_cb.setChecked(False)
        self.select_all_cb.stateChanged.connect(self._on_select_all)
        action_layout.addWidget(self.select_all_cb)
        action_layout.addStretch()

        scan_btn = QPushButton()
        self.scan_btn = scan_btn
        scan_btn.setObjectName("secondary")
        scan_btn.setFixedSize(110, 34)
        scan_btn.clicked.connect(self._start_scan)
        action_layout.addWidget(scan_btn)

        download_btn = QPushButton()
        self.download_btn = download_btn
        download_btn.setFixedSize(110, 34)
        download_btn.clicked.connect(self._start_download_selected)
        action_layout.addWidget(download_btn)
        active_layout.addLayout(action_layout)

        # 文件树
        self.file_tree = QTreeWidget()
        self.file_tree.setColumnCount(3)
        self.file_tree.setAlternatingRowColors(True)
        self.file_tree.setIndentation(22)
        header = self.file_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(2, 90)
        self.file_tree.itemChanged.connect(self._on_tree_item_changed)
        active_layout.addWidget(self.file_tree, 1)

        # 进度条：只在下载时出现，贴着文件树下方
        self.download_progress = QProgressBar()
        self.download_progress.setRange(0, 100)
        self.download_progress.setValue(0)
        self.download_progress.setFixedHeight(18)
        self.download_progress.setFormat("%v / %m")
        self.download_progress.setVisible(False)
        active_layout.addWidget(self.download_progress)

        self.content_stack.addWidget(active_page)
        self.content_stack.setCurrentIndex(0)
        layout.addWidget(self.content_stack, 1)

        self.retranslate()

    def retranslate(self):
        self.save_label.setText(self.tr("save_group"))
        self.browse_btn.setText(self.tr("browse"))
        self.scan_btn.setText(self.tr("refresh"))
        self.download_btn.setText(self.tr("download"))
        self.select_all_cb.setText(self.tr("select_all"))
        self.empty_label.setText(self.tr("empty_state"))
        header = self.file_tree.headerItem()
        if header:
            header.setText(0, self.tr("col_name"))
            header.setText(1, self.tr("col_url"))
            header.setText(2, self.tr("col_type"))

    def _save_path_setting(self):
        self.ctx.settings.set("save_path", self.save_path_input.text().strip())
        self.ctx.settings.save()

    def _browse_path(self):
        path = QFileDialog.getExistingDirectory(self, self.tr("browse_title"))
        if path:
            self.save_path_input.setText(path)
            self._save_path_setting()

    # ------------------------------------------------------------- 课程切换
    def on_course_changed(self, course_id, course_name):
        self.course_id = course_id
        self._start_scan()

    def reset(self):
        """切换账号：丢掉上一个账号的课程和文件树，回到空状态。"""
        self.course_id = ""
        self._download_files = []
        self.file_tree.blockSignals(True)
        self.file_tree.clear()
        self.file_tree.blockSignals(False)
        self.download_progress.setVisible(False)
        self.content_stack.setCurrentIndex(0)

    def _start_scan(self):
        if not self.course_id:
            self.ctx.log(self.tr("select_course_first"))
            return
        self._save_path_setting()
        self.ctx.signals.set_busy.emit(self.scan_btn, True)
        threading.Thread(target=self._scan_thread, daemon=True).start()

    def _scan_thread(self):
        self.ctx.log(self.tr("scanning_files"))
        epoch = self.ctx.account_epoch
        try:
            tree = self.ctx.downloader.scan_tree(self.course_id, "ROOT")
            if epoch != self.ctx.account_epoch:
                return  # 扫描期间切换了账号，结果作废
            self.ctx.signals.populate_tree.emit(self.file_tree, tree)
            total = self.ctx.downloader.count_files(tree)
            self.ctx.log(self.tr("scan_done", total))
        except Exception as e:
            self.ctx.log(str(e))
        finally:
            self.ctx.signals.set_busy.emit(self.scan_btn, False)

    # ------------------------------------------------------------- 文件树
    def _populate_file_tree(self, tree_widget, nodes):
        tree_widget.blockSignals(True)
        tree_widget.clear()
        self._add_tree_items(tree_widget, nodes)
        tree_widget.blockSignals(False)
        self.select_all_cb.blockSignals(True)
        self.select_all_cb.setCheckState(Qt.CheckState.Unchecked)
        self.select_all_cb.blockSignals(False)
        # 有内容时切到操作页
        if nodes:
            self.content_stack.setCurrentIndex(1)

    def _add_tree_items(self, parent, nodes):
        for node in nodes:
            item = QTreeWidgetItem()
            item.setCheckState(0, Qt.CheckState.Unchecked)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsAutoTristate)
            item.setText(0, node.get("name", ""))
            item.setData(0, Qt.ItemDataRole.UserRole, node.get("url", ""))
            item.setData(0, Qt.ItemDataRole.UserRole + 1, node.get("type", "other"))
            type_key = {
                "lesson": "type_lesson",
                "file": "type_file",
                "other": "type_other",
            }.get(node.get("type"), "type_other")
            item.setText(2, self.tr(type_key))
            if parent is self.file_tree:
                parent.addTopLevelItem(item)
            else:
                parent.addChild(item)
            self._set_url_cell(item, node.get("link", ""))
            self._add_tree_items(item, node.get("children", []))

    def _set_url_cell(self, item, url):
        if not url:
            return
        safe_url = html.escape(url, quote=True)
        link_label = QLabel(
            f'<a href="{safe_url}">{html.escape(self.tr("open"))}</a>'
        )
        link_label.setTextFormat(Qt.TextFormat.RichText)
        link_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        link_label.setOpenExternalLinks(True)
        link_label.setToolTip(url)
        self.file_tree.setItemWidget(item, 1, link_label)

    def _on_tree_item_changed(self, item, column):
        if column != 0:
            return
        self.file_tree.blockSignals(True)
        self._update_parent_state(item)
        self.file_tree.blockSignals(False)
        self._update_select_all_state()

    def _update_parent_state(self, item):
        parent = item.parent()
        if parent is None:
            return
        checked = 0
        total = parent.childCount()
        for i in range(total):
            if parent.child(i).checkState(0) == Qt.CheckState.Checked:
                checked += 1
        if checked == 0:
            parent.setCheckState(0, Qt.CheckState.Unchecked)
        elif checked == total:
            parent.setCheckState(0, Qt.CheckState.Checked)
        else:
            parent.setCheckState(0, Qt.PartiallyChecked)
        self._update_parent_state(parent)

    def _update_select_all_state(self):
        top_count = self.file_tree.topLevelItemCount()
        if top_count == 0:
            return
        checked = 0
        for i in range(top_count):
            if self.file_tree.topLevelItem(i).checkState(0) == Qt.CheckState.Checked:
                checked += 1
        self.select_all_cb.blockSignals(True)
        if checked == 0:
            self.select_all_cb.setCheckState(Qt.CheckState.Unchecked)
        elif checked == top_count:
            self.select_all_cb.setCheckState(Qt.CheckState.Checked)
        else:
            self.select_all_cb.setCheckState(Qt.PartiallyChecked)
        self.select_all_cb.blockSignals(False)

    def _on_select_all(self, state):
        # 用户点击不应停在「部分选中」：未选 -> 点击 -> 直接全选
        if state == 1:
            self.select_all_cb.blockSignals(True)
            self.select_all_cb.setCheckState(Qt.CheckState.Checked)
            self.select_all_cb.blockSignals(False)
            state = 2
        self.file_tree.blockSignals(True)
        check_state = Qt.CheckState.Checked if state == 2 else Qt.CheckState.Unchecked
        for i in range(self.file_tree.topLevelItemCount()):
            self.file_tree.topLevelItem(i).setCheckState(0, check_state)
        self.file_tree.blockSignals(False)

    def _get_checked_urls(self):
        results = []
        for i in range(self.file_tree.topLevelItemCount()):
            self._collect_checked(self.file_tree.topLevelItem(i), results)
        return results

    def _collect_checked(self, item, results):
        if item.childCount() == 0:
            if (
                item.checkState(0) == Qt.CheckState.Checked
                and item.data(0, Qt.ItemDataRole.UserRole + 1) == "file"
            ):
                url = item.data(0, Qt.ItemDataRole.UserRole)
                name = item.text(0)
                if url:
                    results.append((name, url))
        else:
            for i in range(item.childCount()):
                self._collect_checked(item.child(i), results)

    # ------------------------------------------------------------- 下载
    def _start_download_selected(self):
        files = self._get_checked_urls()
        if not files:
            self.ctx.log(self.tr("no_selection"))
            return
        save_path = self.save_path_input.text().strip()
        if not save_path:
            self.ctx.log(self.tr("no_path"))
            return
        self._save_path_setting()
        self._download_files = files
        self.download_progress.setRange(0, len(files))
        self.download_progress.setValue(0)
        self.ctx.signals.set_progress.emit(self.download_progress, 0, self.tr("progress_format").format(0, len(files), ""))
        self.download_progress.setVisible(True)
        self.ctx.signals.set_busy.emit(self.download_btn, True)
        course_name = self.ctx.current_course_name or ""
        threading.Thread(
            target=self._download_thread,
            args=(files, save_path, course_name),
            daemon=True,
        ).start()

    def _download_thread(self, files, save_path, course_name):
        total = len(files)
        self.ctx.log(self.tr("download_start", total))

        def progress_cb(i, size, safe_name):
            fmt = self.tr("progress_format").format(i, total, safe_name)
            self.ctx.signals.set_progress.emit(self.download_progress, i, fmt)
            self.ctx.log(self.tr("download_progress", i, total, size, safe_name))

        try:
            ok, _ = self.ctx.downloader.download_files(
                files, save_path, course_name, progress_cb=progress_cb)
            self.ctx.log(self.tr("download_done"))
            self.ctx.signals.toast.emit(
                self.tr("download_done") + f" ({ok}/{total})",
                "success" if ok == total else "error",
            )
        except Exception as e:
            self.ctx.log(str(e))
            self.ctx.signals.toast.emit(str(e)[:80], "error")
        finally:
            self.ctx.signals.set_progress.emit(self.download_progress, -1, "")
            self.ctx.signals.set_busy.emit(self.download_btn, False)
