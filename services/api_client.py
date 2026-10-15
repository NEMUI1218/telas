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
        soup = BeautifulSoup(self.session.get(BASE_URL).text, "html.parser")
        data = {}
        for x in soup.find_all("input"):
            name = x.get("name")
            if name:
                data[name] = x.get("value", "")
        data.update({"user_id": user, "password": pwd, "login": "サインイン"})
        self.log("提交登录...")
        self.session.post(LOGIN_URL, data=data, allow_redirects=True)
        self.session.get(BASE_URL + "/ultra", allow_redirects=True)

        all_cookies = self.session.cookies.get_dict()
        if "BbRouter" in all_cookies:
            bb = all_cookies["BbRouter"]
            if "xsrf:" in bb:
                self.xsrf = bb.split("xsrf:")[1].split(",")[0]
            self.log("登录成功!")
            self.save_session()
            return True
        for cookie in self.session.cookies:
            if "xsrf:" in cookie.value:
                self.xsrf = cookie.value.split("xsrf:")[1].split(",")[0]
                self.log("登录成功!")
                self.save_session()
                return True
        self.log("登录失败！")
        return False

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
