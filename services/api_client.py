"""Blackboard REST API 客户端。

只负责 HTTP 通讯与会话管理，不包含任何 UI 逻辑。只发 GET 请求读取数据，不修改服务器上的任何东西。
bb_config.json / bb_session.json 都在每个用户自己的数据目录里，见 utils/paths.py。
"""
import json
import os
import requests
from bs4 import BeautifulSoup

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
                "name": c.name, "value": c.value,
                "domain": c.domain, "path": c.path,
            })
        data = {"cookies": cookies, "xsrf": self.xsrf}
        try:
            with open(data_path(SESSION_FILE), "w", encoding="utf-8") as f:
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
                    c["name"], c["value"],
                    domain=c.get("domain", ""), path=c.get("path", "/"),
                )
            self.xsrf = data.get("xsrf", "")
            return bool(self.xsrf)
        except Exception:
            return False

    def logout(self):
        """丢掉当前登录：内存里的 cookie 和 token，以及磁盘上的会话文件。

        只清本机的东西，不请求服务器；服务器那边的会话到期后自己失效。
        """
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
            "html.parser"
        )

        data = {}
        for x in soup.find_all("input"):
            name = x.get("name")
            if name:
                data[name] = x.get("value", "")

        data.update({
            "user_id": user,
            "password": pwd,
            "login": "サインイン"
        })

        self.log("提交登录...")

        login_response = self.session.post(
            LOGIN_URL,
            data=data,
            allow_redirects=True
        )

        self.log(f"[登录诊断] 提交后 HTTP 状态码: {login_response.status_code}")
        self.log(f"[登录诊断] 提交后最终路径: {login_response.url.split('?')[0]}")

        page_response = self.session.get(
            BASE_URL + "/ultra",
            allow_redirects=True
        )

        self.log(f"[登录诊断] 访问课程页面 HTTP 状态码: {page_response.status_code}")
        self.log(f"[登录诊断] 课程页面最终路径: {page_response.url.split('?')[0]}")

        # 检查是否仍然显示登录表单
        page = BeautifulSoup(page_response.text, "html.parser")
        has_password_input = page.find("input", {"type": "password"}) is not None
  
        if has_password_input:
            self.log("登录失败：访问课程页面后仍检测到密码输入框。")
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
                    xsrf = cookie.value.split("xsrf:", 1)[1].split(",", 1)[0]
                    break

        if not xsrf:
            self.log("登录状态未确认：没有找到 XSRF 信息。")
            return False

        self.xsrf = xsrf
        self.log("已找到 XSRF 信息，继续验证 API 认证状态。")

        # 用真实的用户信息接口验证认证状态
        try:
            response = self.session.get(
                BASE_URL + "/learn/api/v1/users/me",
                headers={"Accept": "application/json"},
                timeout=20
            )

            self.log(f"[登录诊断] 用户信息 API HTTP 状态码: {response.status_code}")

            if response.status_code != 200:
                self.log("登录验证失败：用户信息 API 未通过认证。")
                return False

            result = response.json()
            if not isinstance(result, dict) or not result:
                self.log("登录验证失败：用户信息 API 没有返回有效的用户数据。")
                return False

        except Exception as e:
            self.log(f"登录验证失败：请求用户信息 API 时发生异常（{type(e).__name__}）。")
            return False

        self.log("登录成功：用户信息 API 验证通过。")
        self.save_session()
        return True

    # ------------------------------------------------------------------ 请求
    def api(self, url):
        from urllib.parse import urlparse

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
            self.log(f"[API] Content-Type: {r.headers.get('Content-Type', '')}")

            if r.status_code == 200:
                try:
                    data = r.json()

                    if isinstance(data, dict):
                        self.log(f"[API] JSON 顶层字段: {list(data.keys())}")

                        if isinstance(data.get("results"), list):
                            self.log(f"[API] results 数量: {len(data['results'])}")
                    else:
                        self.log(f"[API] JSON 类型: {type(data).__name__}")

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
        return self.api(f"{BASE_URL}/learn/api/v1/users/me")

    def get_courses(self):
        me = self.get_me()
        if not me:
            return {}
        user_id = me.get("id", "")
        self.log(f"用户ID: {user_id}")
        data = self.api(
            f"{BASE_URL}/learn/api/v1/users/{user_id}/memberships"
            "?expand=course.effectiveAvailability,course.permissions,courseRole"
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
                courses[name] = {"id": cid, "role": role}
        return courses

    def download_file(self, url, path):
        """下载到 path，返回字节数。不是 200 或内容为空时不写文件、返回 0（计为失败），
        免得把登录页或错误页当成文件存下来。"""
        r = self.session.get(BASE_URL + url, headers={"Accept": "*/*"})
        if r.status_code != 200 or not r.content:
            return 0
        with open(path, "wb") as f:
            f.write(r.content)
        return len(r.content)
