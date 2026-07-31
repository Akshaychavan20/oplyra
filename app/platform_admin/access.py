"""Admin audit writer + access middleware (host gate, permission map)."""
from __future__ import annotations

import json
from functools import wraps

from flask import request, abort, current_app, redirect, url_for

from app import db
from app.platform_admin.models import AdminAuditLog
from app.platform_admin.session import get_current_admin, current_admin
from app.platform_admin.permissions import ROUTE_PERMISSIONS


def write_admin_audit(
    action: str,
    *,
    resource_type: str | None = None,
    resource_id=None,
    payload: dict | None = None,
) -> None:
    admin = get_current_admin()
    row = AdminAuditLog(
        actor_id=admin.id if admin else None,
        action=action[:80],
        resource_type=(resource_type or '')[:80] or None,
        resource_id=str(resource_id)[:64] if resource_id is not None else None,
        ip_address=(request.remote_addr or '')[:64],
        user_agent=(request.headers.get('User-Agent') or '')[:255],
        payload_json=json.dumps(payload) if payload is not None else None,
    )
    db.session.add(row)
    db.session.commit()


def admin_host_allowed() -> bool:
    """Enforce ADMIN_HOSTS when configured (production subdomain cutover)."""
    hosts = current_app.config.get('ADMIN_HOSTS') or []
    if not hosts:
        return True  # path-mode until subdomain cutover
    host = (request.host or '').split(':')[0].lower()
    allowed = {h.strip().lower() for h in hosts if h and h.strip()}
    return host in allowed


def enforce_admin_request_guards():
    """Blueprint before_request: host + auth + route permission."""
    # Public auth endpoints
    endpoint = request.endpoint or ''
    if endpoint in (
        'platform_admin.login',
        'platform_admin.logout',
        'static',
    ):
        if endpoint == 'platform_admin.login' and not admin_host_allowed():
            abort(403)
        return None

    if not endpoint.startswith('platform_admin.'):
        return None

    if not admin_host_allowed():
        abort(403)

    admin = get_current_admin()
    if not admin:
        return redirect(url_for('platform_admin.login', next=request.path))

    # Feature flags POST needs write
    if endpoint == 'platform_admin.feature_flags' and request.method == 'POST':
        if not admin.has_permission('flags:write') and not admin.has_permission('admin:all'):
            abort(403)
        return None

    required = ROUTE_PERMISSIONS.get(endpoint)
    if required and not admin.has_permission(required):
        abort(403)
    return None


def platform_admin_required(view):
    """Backward-compatible name: requires authenticated internal AdminUser."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not admin_host_allowed():
            abort(403)
        if not get_current_admin():
            return redirect(url_for('platform_admin.login', next=request.path))
        return view(*args, **kwargs)
    return wrapped


def is_platform_admin(user=None) -> bool:
    """True only for an active Internal Admin session — never customer User."""
    return get_current_admin() is not None


# Re-export for templates
__all__ = [
    'write_admin_audit',
    'admin_host_allowed',
    'enforce_admin_request_guards',
    'platform_admin_required',
    'is_platform_admin',
    'current_admin',
]
