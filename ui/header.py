            str(p).strip() for p in (name, login_id)
            if p and str(p).strip()
        ]
        self.account_label.set_full_text(" · ".join(parts))
        self._update_responsive_layout()

    def reset(self):
        self.set_login_status(False)
        self.account_label.set_full_text("")
        self.courses = {}
        self.prefix_cb.blockSignals(True)
        self.course_cb.blockSignals(True)
        self.prefix_cb.clear()
        self.course_cb.clear()
        self.prefix_cb.blockSignals(False)
        self.course_cb.blockSignals(False)
        self.prefix_cb.addItem(self.tr("all_terms"), "")
        self.course_cb.addItem(self.tr("placeholder_course"), None)
        self.course_selected.emit("", "")

    def set_courses(self, courses):
        self.courses_loaded.emit(courses or {})

    @staticmethod
    def _term_prefix(course_name):
        match = re.match(
            r"^\s*(\d{4}(?:年度)?\s*(?:前期|後期|后期))", str(course_name)
        )
        if match:
            return re.sub(r"\s+", "", match.group(1))
        return None

    @classmethod
    def _display_course_name(cls, course_name):
        if cls._term_prefix(course_name) is None:
            return course_name
        return re.sub(
            r"^\s*\d{4}(?:年度)?\s*(?:前期|後期|后期)\s*", "", course_name
        ).strip()

    def _populate_courses(self, courses):
        self.courses = courses or {}
        names = list(self.courses.keys())
        terms = {
            term for name in names
            if (term := self._term_prefix(name)) is not None
        }
        terms = sorted(
            terms,
            key=lambda term: (
                int(re.search(r"\d{4}", term).group()),
                2 if ("後期" in term or "后期" in term) else 1,
            ),
            reverse=True,
        )
        self.prefix_cb.blockSignals(True)
        self.prefix_cb.clear()
        self.prefix_cb.addItem(self.tr("all_terms"), "")
        for term in terms:
            self.prefix_cb.addItem(term, term)
        if any(self._term_prefix(name) is None for name in names):
            self.prefix_cb.addItem(self.tr("other_term"), "__other__")
        self.prefix_cb.setCurrentIndex(1 if terms else 0)
        self.prefix_cb.blockSignals(False)
        self._rebuild_course_options()

    def _rebuild_course_options(self):
        term = self.prefix_cb.currentData() or ""
        if term == "__other__":
            names = [
                name for name in self.courses
                if self._term_prefix(name) is None
            ]
        elif term:
            names = [
                name for name in self.courses
                if self._term_prefix(name) == term
            ]
        else:
            names = list(self.courses)
        old_name = (
            self.course_cb.currentData()
            if self.course_cb.currentIndex() > 0 else ""
        )
        self.course_cb.blockSignals(True)
        self.course_cb.clear()
        self.course_cb.addItem(self.tr("placeholder_course"))
        for name in names:
            self.course_cb.addItem(self._display_course_name(name), name)
        if old_name in names:
            self.course_cb.setCurrentIndex(names.index(old_name) + 1)
        else:
            self.course_cb.setCurrentIndex(0)
        self.course_cb.blockSignals(False)
        if old_name and old_name not in names:
            self.course_selected.emit("", "")

    def _on_prefix_changed(self, _index):
        self._rebuild_course_options()

    def _on_course_index_changed(self, *_):
        idx = self.course_cb.currentIndex()
        if idx <= 0:
            self.course_selected.emit("", "")
            return
        name = self.course_cb.currentData()
        if name in self.courses:
            course = self.courses[name]
            course_id = course.get("id", "") if isinstance(course, dict) else course
            self.course_selected.emit(str(course_id), str(name))

    def retranslate(self):
        self.course_label.setText(self.tr("course_name"))
        self.prefix_label.setText(self.tr("prefix_filter"))
        self.login_action.setText(self.tr("login_account"))
        self.switch_action.setText(self.tr("switch_account"))
        self.logout_action.setText(self.tr("logout"))
        if self.prefix_cb.count():
            self.prefix_cb.setItemText(0, self.tr("all_terms"))
            for index in range(1, self.prefix_cb.count()):
                if self.prefix_cb.itemData(index) == "__other__":
                    self.prefix_cb.setItemText(index, self.tr("other_term"))
        if self.course_cb.count():
            self.course_cb.setItemText(0, self.tr("placeholder_course"))
        self._update_badge_text()
        self._update_selector_widths()
