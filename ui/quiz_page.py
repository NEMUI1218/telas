                ])
                self._center_result_columns(lesson_item)
                lesson_item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    {"path": [lesson_name]},
                )
                self.quiz_tree.addTopLevelItem(lesson_item)
                lessons[lesson_name] = lesson_item
            return lessons[lesson_name]

        # 只把课程目录下的第一层文件夹作为课时显示。
        # 更深层的“授業用資料について”等资料文件夹继续由文件下载页展示。
        for folder in folder_list:
            path = folder.get("path", [])
            if len(path) == 1:
                ensure_lesson(path)

        for quiz in quiz_list:
            parent = ensure_lesson(quiz.get("path", []))
            quiz_item = QTreeWidgetItem([
                quiz.get("title") or self.ctx.tr("unnamed_quiz"),
                self._format_attempts(quiz),
                self._format_points(quiz),
                self.ctx.tr("quiz_type"),
            ])
            self._center_result_columns(quiz_item)
            quiz_item.setData(0, Qt.ItemDataRole.UserRole, quiz.get("id", ""))
            if parent is None:
                self.quiz_tree.addTopLevelItem(quiz_item)
            else:
                parent.addChild(quiz_item)
            # QTreeWidget 只有在条目已加入树后才能设置单元格控件。
            # 清空底层文字，避免它与 QLabel 重叠绘制造成重影。
            quiz_item.setText(0, "")
            self._set_name_and_url(
                quiz_item,
                quiz.get("title") or self.ctx.tr("unnamed_quiz"),
                quiz.get("url", ""),
            )

        for lesson_name, lesson_item in lessons.items():
            has_quiz = any(
                quiz.get("path") and quiz["path"][0] == lesson_name
                for quiz in quiz_list
            )
            if not has_quiz:
                lesson_item.addChild(
                    QTreeWidgetItem([
                        self.ctx.tr("no_quiz_for_lesson"),
                        "",
                        "",
                        "",
                    ])
                )
            lesson_item.setExpanded(True)

        if quiz_list:
            self.status_label.setText(
                self.ctx.tr("quiz_scan_done", len(quiz_list))
            )
        else:
            self.status_label.setText(self.ctx.tr("quiz_scan_empty"))

    def _format_attempts(self, quiz):
        if not quiz.get("attempts_known"):
            return "—"
        count = quiz.get("attempt_count", 0)
        allowed = quiz.get("attempts_allowed")
        if not quiz.get("attempts_allowed_known"):
            return "—"
        if allowed in (None, 0, -1, "0", "-1"):
            return self.ctx.tr("quiz_attempts_unlimited")
        return self.ctx.tr("quiz_attempts_format", count, allowed)

    @staticmethod
    def _center_result_columns(item):
        for column in (1, 2, 3):
            item.setTextAlignment(column, Qt.AlignmentFlag.AlignCenter)

    def _format_points(self, quiz):
        possible = quiz.get("points_possible")
        if possible is None:
            return "-/-" if quiz.get("gradebook_known") else "—"
        possible = self._format_number(possible)
        earned = quiz.get("points_earned")
        if earned is not None:
            return f"{self._format_number(earned)}/{possible}"
        if quiz.get("attempts_known") and not quiz.get("attempt_count", 0):
            return f"-/{possible}"
        return "—"

    @staticmethod
    def _format_number(value):
        try:
            number = float(value)
            return str(int(number)) if number.is_integer() else str(number)
        except (TypeError, ValueError):
            return str(value)

    def _set_name_and_url(self, item, title, url):
        link_label = QLabel()
        if url:
            link_label.setTextFormat(Qt.TextFormat.RichText)
            link_label.setProperty("name_link_url", url)
            link_label.setProperty("name_link_title", title)
            self._render_name_link(link_label)
            link_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextBrowserInteraction
            )
            link_label.setOpenExternalLinks(True)
            link_label.setToolTip(url)
        else:
            link_label.setTextFormat(Qt.TextFormat.PlainText)
            link_label.setText(title)
        self.quiz_tree.setItemWidget(item, 0, link_label)

    @staticmethod
    def _render_name_link(label):
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        safe_url = html.escape(label.property("name_link_url"), quote=True)
        safe_title = html.escape(label.property("name_link_title"))
        text_color = colors()["text"]
        label.setText(
            f'<a href="{safe_url}" style="color:{text_color}; '
            f'text-decoration:none; font-weight:700;"><b>{safe_title}</b></a>'
