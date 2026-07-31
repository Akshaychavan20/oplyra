"""Shared organization / membership helpers (tenant resolution)."""
from __future__ import annotations

from typing import Optional

from app.models import Membership


def get_user_org_id(user_id: int) -> Optional[int]:
    m = Membership.query.filter_by(user_id=user_id).first()
    return m.organization_id if m else None


def get_user_role(user_id: int, organization_id: Optional[int] = None) -> Optional[str]:
    """Return membership role, or None if user has no membership (deny-by-default)."""
    q = Membership.query.filter_by(user_id=user_id)
    if organization_id:
        q = q.filter_by(organization_id=organization_id)
    m = q.first()
    return m.role if m else None


def user_is_org_admin(user_id: int, organization_id: Optional[int] = None) -> bool:
    role = get_user_role(user_id, organization_id)
    return role == 'admin'
