"""文件扫描与下载服务。纯逻辑，不依赖 Qt。"""
import os
import re
from urllib.parse import urljoin
from services.content_types import (
    content_type_diagnostic,
    get_content_url,
    has_content_type,
    is_assessment_content,
    is_content_folder,
    is_content_page,
)


BASE_URL = "https://lms2017.teikyo-u.ac.jp"


def sanitize_name(name):
    return re.sub(r'[\\/:*?"<>|]', "_", name)


class DownloadService:
    def __init__(self, api):
        self.api = api

    def scan_tree(self, course_id, content_id, depth=0):
        nodes, _ = self._scan_tree(course_id, content_id, depth)
        return nodes

    def _scan_tree(self, course_id, content_id, depth=0):
        """扫描节点，并向当前父页面传递是否包含试题/作业。"""
        url = (
            f"{BASE_URL}/learn/api/v1/"
            f"courses/{course_id}/contents/{content_id}/children"
            "?@view=Summary&limit=1000"
        )
        data = self.api.api(url)
        if not data:
            return [], False
        nodes = []
        contains_assessment = False
        for item in data.get("results", []):
            title = item.get("title", "")
            detail = item.get("contentDetail", {}) or {}
            route = "ignored"

            if is_assessment_content(item):
                contains_assessment = True
                route = "assessment_attachments_only"
                # 与试题页使用相同优先级，作业本体不作为普通资料显示。
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

            elif has_content_type(item, "resource/x-bb-file"):
                route = "file"
                file = detail.get("resource/x-bb-file", {}).get("file", {})
                name = file.get("fileName")
                if name:
                    file_node = {
                        "type": "file", "name": name,
                        "url": file.get("permanentUrl", ""),
                        "link": get_content_url(item, BASE_URL, course_id, content_id),
                    }
                    if title and title.strip() != name.strip() and file_node["url"]:
                        route = "material"
                        nodes.append(self._material_node(
                            title, file_node["link"], [file_node]
                        ))
                    else:
                        nodes.append(file_node)

            elif (
                has_content_type(item, "resource/x-bb-folder")
                and is_content_page(item)
            ):
                route = "material"
                # LMS 页面作父项，正文中的实际附件列在其下。
                children, page_has_assessment = self._scan_tree(
                    course_id, item["id"], depth + 1
                )
                contains_assessment = contains_assessment or page_has_assessment
                files = list(self._iter_files(children))
                if page_has_assessment and not files:
                    # 作业本体由试题页呈现；下载页不保留其空的 LMS 外壳。
                    route = "assessment_wrapper_omitted"
                else:
                    nodes.append(self._material_node(
                        title,
                        get_content_url(item, BASE_URL, course_id, content_id),
                        files,
                    ))

            elif is_content_folder(item):
                route = "lesson"
                children, folder_has_assessment = self._scan_tree(
                    course_id, item["id"], depth + 1
                )
                contains_assessment = contains_assessment or folder_has_assessment
                nodes.append({
                    "type": "lesson",
                    "name": title,
                    # 各层文件夹都只用于展开目录，空文件夹也不提供链接。
                    "url": "",
                    "link": "",
                    "children": children,
                })

            elif has_content_type(item, "resource/x-bb-document"):
                route = "material"
                content_url = get_content_url(item, BASE_URL, course_id, content_id)
                body = item.get("body") or {}
                if isinstance(body, dict):
                    body_html = body.get("rawText") or ""
                else:
                    body_html = body if isinstance(body, str) else ""
                downloads = []
                for m in re.finditer(r'<a\s[^>]*?href="(https?://[^"]+/bbcswebdav/[^"]+)"[^>]*>', body_html):
                    file_url = m.group(1)
                    fname = self._extract_filename(body_html, m)
                    if fname and "." in fname:
                        downloads.append({
                            "name": fname,
                            "url": file_url.replace("https://lms2017.teikyo-u.ac.jp", ""),
                        })
                if title or downloads:
                    nodes.append(self._material_node(title, content_url, downloads))
            elif title:
                route = "other"
                nodes.append({
                    "type": "other",
                    "name": title,
                    "url": "",
                    "link": get_content_url(item, BASE_URL, course_id, content_id),
                })
            self.api.log(content_type_diagnostic(
                item, course_id, content_id, "download", route
            ))
        return nodes, contains_assessment

    @staticmethod
    def _material_node(title, link, files):
        attachments = []
        seen_urls = set()
        for file in files:
            name = file.get("name")
            url = file.get("url")
            if not name or not url:
                continue
            # 同一正文可能重复引用附件；同名但 URL 不同的附件仍保留。
            resolved = urljoin(BASE_URL + "/", url)
            if resolved in seen_urls:
                continue
            seen_urls.add(resolved)
            attachments.append({
                "type": "file",
                "name": name,
                "url": url,
                "link": resolved,
            })
        return {
            # 页面可以包含附件，但不是课时目录，也不是附件本体。
            "type": "other",
            "name": title or (attachments[0]["name"] if attachments else ""),
            "url": "",
            "link": link,
            "children": attachments,
        }

    def _iter_files(self, nodes):
        for node in nodes:
            if node.get("type") == "file" and node.get("url"):
                yield node
            else:
                yield from self._iter_files(node.get("children", []))

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
        text_match = re.match(r'([^<]+)</a\s*>', html[match.end():match.end() + 200])
        if text_match:
            return text_match.group(1).strip()
        return None

    def count_files(self, nodes):
        # 一个材料行可能对应多个附件，数量与实际下载任务保持一致。
        return sum(1 for _ in self._iter_files(nodes))

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
