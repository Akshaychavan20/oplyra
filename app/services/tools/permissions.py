"""Tool permissions — workspace / user / role / admin."""
from __future__ import annotations

from typing import Optional

from app.models import ToolPermission
from app.utils.org import get_user_org_id, get_user_role as _org_role


# Re-export for existing callers
__all__ = [
    'get_user_org_id',
    'get_user_role',
    'can_execute_tool',
    'grant_permission',
]


def get_user_role(user_id: int, organization_id: Optional[int] = None) -> str:
    """Membership role for tool checks; defaults to viewer (deny-leaning) if none."""
    role = _org_role(user_id, organization_id)
    return role or 'viewer'


def can_execute_tool(
    user_id: int,
    tool_key: str,
    *,
    organization_id: Optional[int] = None,
) -> bool:
    """
    Default allow for built-ins unless an explicit deny exists.
    Admins always allowed.
    """
    org_id = organization_id or get_user_org_id(user_id)
    role = get_user_role(user_id, org_id)
    if role == 'admin':
        return True

    # Explicit deny for user
    deny = ToolPermission.query.filter_by(
        tool_key=tool_key, user_id=user_id, effect='deny',
    ).first()
    if deny:
        return False

    # Explicit deny for role
    if org_id:
        role_deny = ToolPermission.query.filter_by(
            tool_key=tool_key, organization_id=org_id, role=role, effect='deny',
        ).first()
        if role_deny:
            return False

    # Explicit allow (optional)
    allow = ToolPermission.query.filter(
        ToolPermission.tool_key == tool_key,
        ToolPermission.effect == 'allow',
    ).filter(
        (ToolPermission.user_id == user_id) |
        (ToolPermission.role == role) |
        (ToolPermission.user_id.is_(None) & ToolPermission.role.is_(None))
    ).first()
    # If no permission rows exist for this tool, default allow
    any_perm = ToolPermission.query.filter_by(tool_key=tool_key).first()
    if not any_perm:
        return True
    return bool(allow)


def grant_permission(
    *,
    tool_key: str,
    effect: str = 'allow',
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    role: Optional[str] = None,
    oauth_scopes: Optional[list] = None,
) -> ToolPermission:
    from app import db
    row = ToolPermission(
        tool_key=tool_key,
        effect=effect,
        user_id=user_id,
        organization_id=organization_id,
        role=role,
    )
    row.oauth_scopes = oauth_scopes or []
    db.session.add(row)
    db.session.commit()
    return row
