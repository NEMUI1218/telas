"""Shared Blackboard course-content type detection."""

import json
from urllib.parse import urlencode, urljoin


def has_content_type(item, resource_type):
    """Use the explicit handler ID before falling back to content details."""
    handler = item.get("contentHandler", "")
    if isinstance(handler, dict):
        handler = handler.get("id", "")
    if isinstance(handler, str) and handler.strip():
        return handler.strip() == resource_type
    detail = item.get("contentDetail") or {}
    return isinstance(detail, dict) and resource_type in detail


def is_assessment_content(item):
    """Recognize native assessments and explicit links to course assessments."""
    for resource_type in (
        "resource/x-bb-asmt-test-link",
        "resource/x-bb-asmt-survey-link",
        "resource/x-bb-assignment",
    ):
        if has_content_type(item, resource_type):
            return True

    link_type = "resource/x-bb-courselink"
    if not has_content_type(item, link_type):
        return False

    handler = item.get("contentHandler")
    detail = item.get("contentDetail") or {}
    link_detail = detail.get(link_type) if isinstance(detail, dict) else None
    for source in (handler, link_detail):
        if not isinstance(source, dict):
            continue
        target_type = source.get("targetType")
        if isinstance(target_type, str) and target_type.strip():
            return target_type.strip() == "CourseAssessment"
    return False


def is_content_page(item):
    """Identify documents and folders explicitly marked as Ultra pages."""
    if has_content_type(item, "resource/x-bb-document"):
        return True
    if not has_content_type(item, "resource/x-bb-folder"):
        return False

    handler = item.get("contentHandler")
    detail = item.get("contentDetail") or {}
    folder_detail = (
        detail.get("resource/x-bb-folder")
        if isinstance(detail, dict) else None
    )
    for source in (handler, folder_detail):
        if not isinstance(source, dict):
            continue
        flag = source.get("isBbPage")
        if isinstance(flag, bool):
            return flag
        if isinstance(flag, str):
            normalized = flag.strip().lower()
            if normalized in ("true", "false"):
                return normalized == "true"
    # Missing page metadata does not turn an ordinary folder into a page.
    return False


def is_content_folder(item):
    """Recognize a content directory while excluding document page wrappers."""
    return (
        has_content_type(item, "resource/x-bb-folder")
        and not is_content_page(item)
    )


def content_type_diagnostic(item, course_id, parent_id, source, route):
    """Describe routing identity without logging content bodies or responses."""
    item = item if isinstance(item, dict) else {}
    handler = item.get("contentHandler")
    handler_id = handler.get("id") if isinstance(handler, dict) else handler
    handler_id = handler_id.strip() if isinstance(handler_id, str) else ""
    detail = item.get("contentDetail")
    detail = detail if isinstance(detail, dict) else {}
    identity_keys = (
        "isBbPage", "targetType", "targetId", "assessmentId", "gradeColumnId",
    )

    def scalar(value):
        return value if value is None or isinstance(value, (str, bool, int, float)) else None

    def identity_fields(value):
        if not isinstance(value, dict):
            return {}
        return {
            key: value[key]
            for key in identity_keys
            if key in value
            and (value[key] is None or isinstance(value[key], (str, bool, int, float)))
        }

    record = {
        "source": scalar(source),
        "course_id": scalar(course_id),
        "parent_id": scalar(parent_id),
        "content_id": scalar(item.get("id")),
        "title": scalar(item.get("title")),
        "handler_id": handler_id,
        "detail_keys": sorted(key for key in detail if isinstance(key, str)),
        "route": scalar(route),
        "handler_fields": identity_fields(handler),
        "detail_fields": {
            key: identity_fields(value)
            for key, value in detail.items()
            if isinstance(key, str)
            and key.startswith("resource/")
            and identity_fields(value)
        },
    }
    return "[CONTENT_TYPE] " + json.dumps(record, ensure_ascii=False, separators=(",", ":"))


def get_content_url(item, base_url, course_id=None, parent_id=None):
    """Return a user-facing URL exposed by a Blackboard content item."""
    # Blackboard's alternate link is the UI route. Prefer it over `url`,
    # which may point back to the REST API representation of this item.
    links = item.get("links", []) or []
    if isinstance(links, dict):
        links = [links]
    for link in links:
        if not isinstance(link, dict):
            continue
        if link.get("type") == "text/html" or link.get("rel") == "alternate":
            href = link.get("href")
            if isinstance(href, str) and href.strip():
                return urljoin(base_url.rstrip("/") + "/", href.strip())

    candidates = [
        item.get("launchUrl"),
        item.get("htmlUrl"),
        item.get("permanentUrl"),
        item.get("url"),
    ]

    detail = item.get("contentDetail") or {}
    if isinstance(detail, dict):
        for value in detail.values():
            if isinstance(value, dict):
                candidates.extend((value.get("url"), value.get("permanentUrl")))
                nested_file = value.get("file")
                if isinstance(nested_file, dict):
                    candidates.extend(
                        (nested_file.get("url"), nested_file.get("permanentUrl"))
                    )

    for url in candidates:
        if isinstance(url, str) and url.strip():
            resolved = urljoin(base_url.rstrip("/") + "/", url.strip())
            if "/learn/api/" not in resolved:
                return resolved

    item_id = item.get("id")
    if course_id and item_id:
        params = {
            "redirectType": "nautilus",
            "courseId": course_id,
            "contentId": item_id,
        }
        resolved_parent = item.get("parentId") or parent_id
        if resolved_parent:
            params["parentId"] = resolved_parent
        return f"{base_url.rstrip('/')}/ultra/redirect?{urlencode(params)}"
    return ""
