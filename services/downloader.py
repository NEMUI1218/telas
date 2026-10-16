"""文件扫描与下载服务。纯逻辑，不依赖 Qt。"""
import os
import re
from services.content_types import get_content_url, has_content_type


BASE_URL = "https://lms2017.teikyo-u.ac.jp"


def sanitize_name(name):
    return re.sub(r'[\\/:*?"<>|]', "_", name)


class DownloadService:
    def __init__(self, api):
        self.api = api

    def scan_tree(self, course_id, content_id, depth=0):
        url = (
            f"{BASE_URL}/learn/api/v1/"
            f"courses/{course_id}/contents/{content_id}/children"
            "?@view=Summary&limit=1000"
        )
        data = self.api.api(url)
        if not data:
            return []
        nodes = []
        for item in data.get("results", []):
            title = item.get("title", "")
            detail = item.get("contentDetail", {}) or {}

            if has_content_type(item, "resource/x-bb-file"):
                file = detail.get("resource/x-bb-file", {}).get("file", {})
                name = file.get("fileName")
                if name:
                    nodes.append({
                        "type": "file", "name": name,
                        "url": file.get("permanentUrl", ""),
                        "link": get_content_url(item, BASE_URL, course_id, content_id),
                    })

            elif has_content_type(item, "resource/x-bb-folder"):
                children = self.scan_tree(course_id, item["id"], depth + 1)
                nodes.append({
                    "type": "lesson",
                    "name": title,
                    # 各层文件夹都只用于展开目录，空文件夹也不提供链接。
                    "url": "",
                    "link": "",
                    "children": children,
                })

            elif has_content_type(item, "resource/x-bb-asmt-test-link"):
                assessment = detail.get("resource/x-bb-asmt-test-link", {}).get("test", {}).get("assessment", {})
                instructions = assessment.get("instructions", {}).get("rawText", "")
                for m in re.finditer(r'<a\s[^>]*?href="(https?://[^"]+/bbcswebdav/[^"]+)"[^>]*>', instructions):
                    file_url = m.group(1)
                    fname = self._extract_filename(instructions, m)
                    if fname and "." in fname:
                        nodes.append({
                            "type": "file", "name": fname,
                            "url": file_url.replace("https://lms2017.teikyo-u.ac.jp", ""),
                            "link": file_url,
                        })

            elif has_content_type(item, "resource/x-bb-document"):
                content_url = get_content_url(item, BASE_URL, course_id, content_id)
                if title:
                    nodes.append({
                        "type": "other",
                        "name": title,
                        "url": "",
                        "link": content_url,
                    })
                body_html = item.get("body", {}).get("rawText", "")
                for m in re.finditer(r'<a\s[^>]*?href="(https?://[^"]+/bbcswebdav/[^"]+)"[^>]*>', body_html):
                    file_url = m.group(1)
                    fname = self._extract_filename(body_html, m)
                    if fname and "." in fname:
                        nodes.append({
                            "type": "file", "name": fname,
                            "url": file_url.replace("https://lms2017.teikyo-u.ac.jp", ""),
                            "link": file_url,
                        })
            elif title:
                nodes.append({
                    "type": "other",
                    "name": title,
                    "url": "",
                    "link": get_content_url(item, BASE_URL, course_id, content_id),
                })
        return nodes

    @staticmethod
    def _extract_filename(html, match):
        import json
        tag = match.group(0)
        fb_match = re.search(r'data-bbfile="([^"]*)"', tag)
        if fb_match:
            try:
                fb = json.loads(fb_match.group(1).replace("&quot;", '"'))
                fname = fb.get("fileName") or fb.get("displayName")
                if fname:
                    return fname
            except Exception:
                pass
        text_match = re.search(r'>([^<]+)</a>', html[match.end():match.end() + 200])
        if text_match:
            return text_match.group(1).strip()
        return None

    def count_files(self, nodes):
        count = 0
        for n in nodes:
            if n["type"] == "file":
                count += 1
            elif n.get("children") is not None:
                count += self.count_files(n.get("children", []))
        return count

    def download_files(self, files, save_path, course_name, progress_cb=None):
        """files: [(name, url), ...]。逐个下载到 save_path/<course_name>/ 下。

        progress_cb(i, size, safe_name) 每下载完一个文件回调一次。
        返回 (成功数, 总数)。
        """
        safe_course = sanitize_name(course_name)
        course_path = os.path.join(save_path, safe_course)
        os.makedirs(course_path, exist_ok=True)
        ok = 0
        total = len(files)
        for i, (name, url) in enumerate(files):
            safe = sanitize_name(name)
            path = os.path.join(course_path, safe)
            size = self.api.download_file(url, path)
            if size:
                ok += 1
            if progress_cb:
                progress_cb(i + 1, size, safe)
        return ok, total
