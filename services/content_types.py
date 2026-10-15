"""Shared Blackboard course-content type detection."""


def has_content_type(item, resource_type):
    """Match the handler recognition used by course-content scanning."""
    detail = item.get("contentDetail") or {}
    handler = item.get("contentHandler", "")
    return resource_type in detail or handler == resource_type
