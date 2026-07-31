"""Enterprise permissions / workspace isolation helpers."""
from __future__ import annotations

from typing import Optional

from app.models import KnowledgeDocument, KnowledgePermission, Membership


def get_user_org_id(user_id: int) -> Optional[int]:
    m = Membership.query.filter_by(user_id=user_id).first()
    return m.organization_id if m else None


def get_user_role(user_id: int, organization_id: Optional[int] = None) -> str:
    q = Membership.query.filter_by(user_id=user_id)
    if organization_id:
        q = q.filter_by(organization_id=organization_id)
    m = q.first()
    return (m.role if m else 'editor') or 'editor'


def can_read_document(user_id: int, document: KnowledgeDocument) -> bool:
    if document.status == 'deleted':
        return False
    if document.visibility == 'private' and document.user_id != user_id:
        # Check explicit permission
        perm = KnowledgePermission.query.filter_by(
            document_id=document.id,
            user_id=user_id,
        ).first()
        return bool(perm)
    org_id = get_user_org_id(user_id)
    if document.organization_id and org_id and document.organization_id != org_id:
        return False
    return True


def can_write_document(user_id: int, document: KnowledgeDocument) -> bool:
    if not can_read_document(user_id, document):
        return False
    if document.user_id == user_id:
        return True
    role = get_user_role(user_id, document.organization_id)
    if role in ('admin', 'manager', 'editor'):
        return True
    perm = KnowledgePermission.query.filter_by(
        document_id=document.id,
        user_id=user_id,
    ).first()
    return bool(perm and perm.permission in ('write', 'admin'))


def can_admin_collection(user_id: int, organization_id: Optional[int]) -> bool:
    role = get_user_role(user_id, organization_id)
    return role in ('admin', 'manager')
