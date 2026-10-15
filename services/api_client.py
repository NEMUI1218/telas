"""Blackboard REST API 客户端。

只负责 HTTP 通讯与会话管理，不包含任何 UI 逻辑。
只发 GET 请求读取数据，不修改服务器上的任何东西。
bb_config.json / bb_session.json 都在每个用户自己的数据目录里，
见 utils/paths.py。
"""

import json
import os
import requests

from bs4 import BeautifulSoup
from urllib.parse import quote, urlparse

from utils.paths import data_path


BASE_URL = "https://lms2017.teikyo-u.ac.jp"
LOGIN_URL = BASE_URL + "/webapps/login/"
SESSION_FILE = "bb_session.json"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


class BlackboardAPI:
    def __init__(self, log_cb=None):
        self.log_fn = log_cb
        self.session = requests.Session()
        self.xsrf = ""
        self.session.headers.update({"User-Agent": UA})

    def log(self, *args):
        if self.log_fn:
            self.log_fn(" ".join(map(str, args)))

    # ------------------------------------------------------------------ 会话
    def save_session(self):
        cookies = []

        for c in self.session.cookies:
            cookies.append({
                "name": c.name,
                "value": c.value,
                "domain": c.domain,
                "path": c.path,
            })

        data = {
            "cookies": cookies,
            "xsrf": self.xsrf,
        }

        try:
            with open(
                data_path(SESSION_FILE),
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass

    def load_session(self):
        path = data_path(SESSION_FILE)

        if not os.path.exists(path):
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for c in data.get("cookies", []):
                self.session.cookies.set(
                    c["name"],
                    c["value"],
                    domain=c.get("domain", ""),
                    path=c.get("path", "/"),
                )

            self.xsrf = data.get("xsrf", "")
            return bool(self.xsrf)

        except Exception:
            return False

    def logout(self):
        """清除本机登录状态，不主动修改服务器上的数据。"""
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UA})
        self.xsrf = ""

        try:
            os.remove(data_path(SESSION_FILE))
        except OSError:
            pass

    # ------------------------------------------------------------------ 登录
    def login(self, user, pwd):
        self.log("打开登录页面...")
        self.session.get(BASE_URL, allow_redirects=True)

        soup = BeautifulSoup(
            self.session.get(BASE_URL).text,
            "html.parser",
        )

        data = {}

        for x in soup.find_all("input"):
            name = x.get("name")

            if name:
                data[name] = x.get("value", "")

        data.update({
            "user_id": user,
            "password": pwd,
            "login": "サインイン",
        })

        self.log("提交登录...")

        login_response = self.session.post(
            LOGIN_URL,
            data=data,
            allow_redirects=True,
        )

        self.log(
            f"[登录诊断] 提交后 HTTP 状态码: "
            f"{login_response.status_code}"
        )
        self.log(
            f"[登录诊断] 提交后最终路径: "
            f"{login_response.url.split('?')[0]}"
        )

        page_response = self.session.get(
            BASE_URL + "/ultra",
            allow_redirects=True,
        )

        self.log(
            f"[登录诊断] 访问课程页面 HTTP 状态码: "
            f"{page_response.status_code}"
        )
        self.log(
            f"[登录诊断] 课程页面最终路径: "
            f"{page_response.url.split('?')[0]}"
        )

        page = BeautifulSoup(
            page_response.text,
            "html.parser",
        )

        has_password_input = (
            page.find("input", {"type": "password"}) is not None
        )

        if has_password_input:
            self.log(
                "登录失败：访问课程页面后仍检测到密码输入框。"
            )
            return False

        # 提取 XSRF 信息
        all_cookies = self.session.cookies.get_dict()
        xsrf = None

        bb = all_cookies.get("BbRouter", "")

        if "xsrf:" in bb:
            xsrf = bb.split("xsrf:", 1)[1].split(",", 1)[0]

        if not xsrf:
            for cookie in self.session.cookies:
                if "xsrf:" in cookie.value:
                    xsrf = (
                        cookie.value
                        .split("xsrf:", 1)[1]
                        .split(",", 1)[0]
                    )
                    break

        if not xsrf:
            self.log("登录状态未确认：没有找到 XSRF 信息。")
            return False

        self.xsrf = xsrf
        self.log("已找到 XSRF 信息，继续验证 API 认证状态。")

        # 验证 API 认证状态
        try:
            response = self.session.get(
                BASE_URL + "/learn/api/v1/users/me",
                headers={"Accept": "application/json"},
                timeout=20,
            )

            self.log(
                f"[登录诊断] 用户信息 API HTTP 状态码: "
                f"{response.status_code}"
            )

            if response.status_code != 200:
                self.log("登录验证失败：用户信息 API 未通过认证。")
                return False

            result = response.json()

            if not isinstance(result, dict) or not result:
                self.log(
                    "登录验证失败：用户信息 API "
                    "没有返回有效的用户数据。"
                )
                return False

        except Exception as e:
            self.log(
                f"登录验证失败：请求用户信息 API 时发生异常"
                f"（{type(e).__name__}）。"
            )
            return False

        self.log("登录成功：用户信息 API 验证通过。")
        self.save_session()

        return True

    # ------------------------------------------------------------------ 请求
    def api(self, url):
        try:
            r = self.session.get(
                url,
                headers={"Accept": "application/json"},
                timeout=20,
            )

            path = urlparse(url).path

            self.log(f"[API] 请求路径: {path}")
            self.log(f"[API] HTTP 状态码: {r.status_code}")
            self.log(f"[API] 最终响应地址: {urlparse(r.url).path}")
            self.log(
                f"[API] Content-Type: "
                f"{r.headers.get('Content-Type', '')}"
            )

            if r.status_code == 200:
                try:
                    data = r.json()

                    if isinstance(data, dict):
                        self.log(
                            f"[API] JSON 顶层字段: {list(data.keys())}"
                        )

                        if isinstance(data.get("results"), list):
                            self.log(
                                f"[API] results 数量: "
                                f"{len(data['results'])}"
                            )
                    else:
                        self.log(
                            f"[API] JSON 类型: "
                            f"{type(data).__name__}"
                        )

                    return data

                except ValueError:
                    self.log("[API] 响应不是有效的 JSON")
                    return None

            self.log(f"[API] 请求失败，HTTP {r.status_code}")
            return None

        except requests.RequestException as e:
            self.log(f"[API] 请求异常: {type(e).__name__}")
            return None

    # ------------------------------------------------------------------ 数据
    def get_me(self):
        return self.api(
            f"{BASE_URL}/learn/api/v1/users/me"
        )

    def get_courses(self):
        me = self.get_me()

        if not me:
            return {}

        user_id = me.get("id", "")
        self.log(f"用户ID: {user_id}")

        data = self.api(
            f"{BASE_URL}/learn/api/v1/users/{user_id}/memberships"
            "?expand=course.effectiveAvailability,"
            "course.permissions,courseRole"
            "&includeCount=true&limit=10000"
        )

        if not data:
            return {}

        courses = {}

        for item in data.get("results", []):
            course = item.get("course", {})

            cid = course.get("id", "")
            name = course.get("name", "")
            role = item.get("courseRole", "")

            if cid and name:
                courses[name] = {
                    "id": cid,
                    "role": role,
                }

        return courses

    # -------------------------------------------------------------- 测验识别
    def get_course_quizzes(self, course_id):
        """读取指定课程中的测验，返回测验列表。

        返回格式：
        [
            {"id": "测验内容ID", "title": "测验名称"},
            ...
        ]

        如果读取失败，返回 None。
        如果读取成功但没有测验，返回空列表。
        """

        if not course_id:
            self.log("[测验识别] 没有指定课程 ID。")
            return None

        course_id = str(course_id)
        encoded_course_id = quote(course_id, safe="")

        quizzes = []
        quiz_ids = set()
        visited_folders = set()

        # 防止递归过程无限循环。
        def get_children(content_id):
            encoded_content_id = quote(
                str(content_id),
                safe="",
            )

            url = (
                f"{BASE_URL}/learn/api/v1/courses/"
                f"{encoded_course_id}/contents/"
                f"{encoded_content_id}/children"
                "?@view=Summary"
                "&expand=assignedGroups,selfEnrollmentGroups.group,"
                "gradebookCategory"
                "&includeInActivityTracking=true"
                "&limit=10000"
            )

            data = self.api(url)

            if not isinstance(data, dict):
                return None

            results = data.get("results")

            if not isinstance(results, list):
                self.log(
                    "[测验识别] 课程内容接口没有返回有效的 results。"
                )
                return None

            return results

        def is_folder(item):
            """根据 Blackboard 返回的内容类型判断是否为文件夹。"""

            handler = str(item.get("contentHandler") or "").lower()

            if item.get("hasChildren") is True:
                return True

            if "folder" in handler:
                return True

            # 兼容部分返回中没有 contentHandler，
            # 但明确提供了子内容标记的情况。
            if item.get("hasChildren") in (1, "true", "True"):
                return True

            return False

        def walk(content_id="ROOT"):
            content_id = str(content_id)

            if content_id in visited_folders:
                return True

            visited_folders.add(content_id)

            items = get_children(content_id)

            if items is None:
                return False

            for item in items:
                if not isinstance(item, dict):
                    continue

                item_id = item.get("id")

                if not item_id:
                    continue

                item_id = str(item_id)
                handler = item.get("contentHandler", "")

                # 识别 Blackboard 测验链接。
                if handler == "resource/x-bb-asmt-test-link":
                    if item_id not in quiz_ids:
                        quiz_ids.add(item_id)

                        title = (
                            item.get("title")
                            or "未命名测验"
                        )

                        detail = item.get("contentDetail") or {}
                        test = (
                            detail
                            .get("resource/x-bb-asmt-test-link", {})
                            .get("test", {})
                        )
                        assessment = test.get("assessment", {})

                        quizzes.append({
                            "id": item_id,
                            "title": title,
                            "assessment_id": (
                                assessment.get("id")
                                or assessment.get("assessmentId")
                                or test.get("assessmentId")
                                or ""
                            ),
                            "instructions": (
                                assessment
                                .get("instructions", {})
                                .get("rawText", "")
                            ),
                        })

                        self.log(f"[测验识别] 找到测验：{title}")

                # 只对可能是文件夹的内容继续递归。
                if is_folder(item):
                    if not walk(item_id):
                        return False

            return True

        self.log(
            f"[测验识别] 开始扫描课程，课程 ID: {course_id}"
        )

        success = walk("ROOT")

        if not success:
            self.log(
                "[测验识别] 扫描未能完整完成，"
                "请检查 API 日志。"
            )
            return None

        self.log(
            f"[测验识别] 扫描完成，共找到 {len(quizzes)} 个测验。"
        )

        return quizzes

    def _quiz_api(self, path):
        """通过当前会话读取测验 API，并兼容 Blackboard 公共 API 路径。"""
        data = self.api(f"{BASE_URL}/learn/api/v1{path}")

        if data is not None:
            return data

        return self.api(f"{BASE_URL}/learn/api/public/v1{path}")

    def get_quiz_questions(self, course_id, assessment_id):
        """读取测验题目；失败返回 None，成功但无题目返回空列表。"""
        if not course_id or not assessment_id:
            self.log("[测验详情] 缺少课程 ID 或测验 assessment ID。")
            return None

        course_id = quote(str(course_id), safe="")
        assessment_id = quote(str(assessment_id), safe="")
        questions = []
        offset = 0
        limit = 100

        while True:
            path = (
                f"/courses/{course_id}/assessments/{assessment_id}/questions"
                f"?offset={offset}&limit={limit}"
            )
            data = self._quiz_api(path)

            if not isinstance(data, dict):
                return None

            results = data.get("results")

            if not isinstance(results, list):
                self.log("[测验详情] 题目接口未返回有效的 results。")
                return None

            questions.extend(
                question for question in results
                if isinstance(question, dict)
            )

            if len(results) < limit:
                break

            offset += len(results)

        self.log(f"[测验详情] 已读取 {len(questions)} 道题目。")
        return questions

    def get_quiz_question(self, course_id, assessment_id, question_id):
        """读取单道题目的完整信息；失败返回 None。"""
        if not course_id or not assessment_id or not question_id:
            self.log("[测验详情] 缺少课程、测验或题目 ID。")
            return None

        course_id = quote(str(course_id), safe="")
        assessment_id = quote(str(assessment_id), safe="")
        question_id = quote(str(question_id), safe="")
        path = (
            f"/courses/{course_id}/assessments/{assessment_id}/questions/"
            f"{question_id}"
        )
        data = self._quiz_api(path)

        if isinstance(data, dict):
            return data

        return None

    # ------------------------------------------------------------------ 下载
    def download_file(self, url, path):
        """下载文件。

        不是 HTTP 200 或内容为空时不写文件，返回 0。
        """
        r = self.session.get(
            BASE_URL + url,
            headers={"Accept": "*/*"},
        )

        if r.status_code != 200 or not r.content:
            return 0

        with open(path, "wb") as f:
            f.write(r.content)

        return len(r.content)
