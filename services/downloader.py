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
                        "type": "file",
                        "name": name,
                        "url": file.get("permanentUrl", ""),
                        "link": get_content_url(
                            item, BASE_URL, course_id, content_id
                        ),
                    })

            elif has_content_type(item, "resource/x-bb-folder"):
                children = self.scan_tree(course_id, item["id"], depth + 1)
                nodes.append({
                    "type": "lesson" if depth == 0 else "other",
                    "name": title,
                    "url": get_content_url(
                        item, BASE_URL, course_id, content_id
                    ),
                    "link": get_content_url(
                        item, BASE_URL, course_id, content_id
                    ),
                    "children": children,
                })

            elif has_content_type(item, "resource/x-bb-asmt-test-link"):
                assessment = (
                    detail.get("resource/x-bb-asmt-test-link", {})
                    .get("test", {})
                    .get("assessment", {})
                )
                instructions = (
                    assessment.get("instructions", {}).get("rawText", "")
                )
                for match in re.finditer(
                    r'<a\s[^>]*?href="(https?://[^"]+/bbcswebdav/[^"]+)"'
                    r'[^>]*>',
                    instructions,
                ):
                    file_url = match.group(1)
                    filename = self._extract_filename(instructions, match)
                    if filename and "." in filename:
                        nodes.append({
                            "type": "file",
                            "name": filename,
                            "url": file_url.replace(BASE_URL, ""),
                            "link": file_url,
                        })

            elif has_content_type(item, "resource/x-bb-document"):
                content_url = get_content_url(
                    item, BASE_URL, course_id, content_id
                )
                if title:
                    nodes.append({
                        "type": "other",
                        "name": title,
                        "url": "",
                        "link": content_url,
                    })

                body_html = item.get("body", {}).get("rawText", "")
                for match in re.finditer(
                    r'<a\s[^>]*?href="(https?://[^"]+/bbcswebdav/[^"]+)"'
                    r'[^>]*>',
                    body_html,
                ):
                    file_url = match.group(1)
                    filename = self._extract_filename(body_html, match)
                    if filename and "." in filename:
                        nodes.append({
                            "type": "file",
                            "name": filename,
                            "url": file_url.replace(BASE_URL, ""),
                            "link": file_url,
                        })

            elif title:
                nodes.append({
                    "type": "other",
                    "name": title,
                    "url": "",
                    "link": get_content_url(
                        item, BASE_URL, course_id, content_id
                    ),
                })

        return nodes

    @staticmethod
    def _extract_filename(html, match):
        import json

        tag = match.group(0)
        file_match = re.search(r'data-bbfile="([^"]*)"', tag)
        if file_match:
            try:
                file_data = json.loads(
                    file_match.group(1).replace("&quot;", '"')
                )
                filename = (
                    file_data.get("fileName")
                    or file_data.get("displayName")
                )
                if filename:
                    return filename
            except Exception:
                pass

        text_match = re.search(
            r'>([^<]+)</a>',
            html[match.end():match.end() + 200],
        )
        if text_match:
            return text_match.group(1).strip()

        return None

    def count_files(self, nodes):
        count = 0
        for node in nodes:
            if node["type"] == "file":
                count += 1
            elif node.get("children") is not None:
                count += self.count_files(node.get("children", []))
        return count

    def download_files(self, files, save_path, course_name, progress_cb=None):
        """逐个下载到 save_path/<course_name>/ 下。

        files: [(name, url), ...]
        progress_cb(i, size, safe_name) 每下载完一个文件回调一次。
        返回 (成功数, 总数)。
        """
        safe_course = sanitize_name(course_name)
        course_path = os.path.join(save_path, safe_course)
        os.makedirs(course_path, exist_ok=True)

        ok = 0
        total = len(files)
        for index, (name, url) in enumerate(files):
            safe_name = sanitize_name(name)
            path = os.path.join(course_path, safe_name)
            size = self.api.download_file(url, path)
            if size:
                ok += 1
            if progress_cb:
                progress_cb(index + 1, size, safe_name)

        return ok, total
