"""Shared Blackboard course-content type detection."""

from urllib.parse import urlencode, urljoin


def has_content_type(item, resource_type):
    """Match the handler recognition used by course-content scanning."""
    detail = item.get("contentDetail") or {}
    handler = item.get("contentHandler", "")
    return resource_type in detail or handler == resource_type


def get_content_url(item, base_url, course_id=None, parent_id=None):
    """Return a user-facing URL exposed by a Blackboard content item."""
    candidates = [
        item.get("url"),
        item.get("launchUrl"),
        item.get("htmlUrl"),
        item.get("permanentUrl"),
    ]

    for link in item.get("links", []) or []:
        if not isinstance(link, dict):
            continue
        if link.get("type") == "text/html" or link.get("rel") == "alternate":
            candidates.append(link.get("href"))

    detail = item.get("contentDetail") or {}
    if isinstance(detail, dict):
        for value in detail.values():
            if isinstance(value, dict):
                candidates.extend((value.get("url"), value.get("permanentUrl")))
                nested_file = value.get("file")
                if isinstance(nested_file, dict):
                    candidates.extend((
                        nested_file.get("url"),
                        nested_file.get("permanentUrl"),
                    ))

    for url in candidates:
        if isinstance(url, str) and url.strip():
            return urljoin(base_url.rstrip("/") + "/", url.strip())

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
