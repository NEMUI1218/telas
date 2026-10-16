            elif state == Qt.CheckState.PartiallyChecked:
                partial += 1
        if checked == total:
            self._set_item_check_state(parent, Qt.CheckState.Checked)
        elif checked == 0 and partial == 0:
            self._set_item_check_state(parent, Qt.CheckState.Unchecked)
        else:
            self._set_item_check_state(parent, Qt.CheckState.PartiallyChecked)
        self._update_parent_state(parent)

    def _item_check_state(self, item):
        value = item.data(0, self._CHECK_STATE_ROLE)
        return Qt.CheckState(value if value is not None else 0)

    def _set_item_check_state(self, item, state):
        item.setData(0, self._CHECK_STATE_ROLE, int(state.value))

    def _update_select_all_state(self):
        top_count = self.file_tree.topLevelItemCount()
        if top_count == 0:
            return
        checked = 0
        for i in range(top_count):
            if self._item_check_state(self.file_tree.topLevelItem(i)) == Qt.CheckState.Checked:
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
        def set_descendants(item):
            self._set_item_check_state(item, check_state)
            for index in range(item.childCount()):
                set_descendants(item.child(index))

        for i in range(self.file_tree.topLevelItemCount()):
            set_descendants(self.file_tree.topLevelItem(i))
        self.file_tree.blockSignals(False)
        self._sync_tree_checkboxes()

    def _get_checked_urls(self):
        results = []
        for i in range(self.file_tree.topLevelItemCount()):
            self._collect_checked(self.file_tree.topLevelItem(i), results)
        return results

    def _collect_checked(self, item, results):
        if item.childCount() == 0:
            if (
                self._item_check_state(item) == Qt.CheckState.Checked
                and item.data(0, Qt.ItemDataRole.UserRole + 1) == "file"
            ):
                url = item.data(0, Qt.ItemDataRole.UserRole)
                name = item.data(0, Qt.ItemDataRole.UserRole + 2) or ""
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
        default_path = os.path.join(
            os.path.expanduser("~"), "Downloads", "Blackboard_download"
        )
        save_path = (self.ctx.settings.get("save_path", default_path) or "").strip()
        if not save_path:
            self.ctx.log(self.tr("no_path"))
            return
        self._download_files = files
        self.download_progress.setRange(0, len(files))
        self.download_progress.setValue(0)
        self.ctx.signals.set_progress.emit(self.download_progress, 0, self.tr("progress_format").format(0, len(files), ""))
        self.download_progress.setVisible(True)
        self.ctx.signals.set_busy.emit(self.download_btn, True)
        course_name = self.ctx.current_course_name or ""
        if not self.ctx.settings.get("save_term_prefix", False):
            # 与课程选框一致，只移除开头的学期标记，保留名称中的其他年份。
            short_name = re.sub(
                r"^\s*\d{4}(?:年度)?\s*(?:前期|後期|后期)\s*",
                "",
                course_name,
            ).strip()
            course_name = short_name or course_name
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
