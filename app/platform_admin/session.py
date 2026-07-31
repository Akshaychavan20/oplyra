"""Internal admin session management — isolated from Flask-Login customer sessions."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import session, request, g, current_app, redirect, url_for, abort
from werkzeug.local import LocalProxy

from app import db
from app.platform_admin.models import AdminUser, AdminSession, AdminLoginEvent

SESSION_ADMIN_ID = '_ia_id'
SESSION_ADMIN_TOKEN = '_ia_sid'


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def get_current_admin() -> AdminUser | None:
    if hasattr(g, '_current_admin'):
        return g._current_admin

    admin_id = session.get(SESSION_ADMIN_ID)
    token = session.get(SESSION_ADMIN_TOKEN)
    if not admin_id or not token:
        g._current_admin = None
        return None

    row = AdminSession.query.filter_by(
        admin_user_id=admin_id,
        token_hash=_hash_token(token),
    ).first()
    if not row or not row.is_valid:
        clear_admin_session()
        g._current_admin = None
        return None

    admin = AdminUser.query.get(admin_id)
    if not admin or not admin.is_active_admin:
        clear_admin_session()
        g._current_admin = None
        return None

    g._current_admin = admin
    g._admin_session = row
    return admin


current_admin = LocalProxy(get_current_admin)


def clear_admin_session() -> None:
    session.pop(SESSION_ADMIN_ID, None)
    session.pop(SESSION_ADMIN_TOKEN, None)
    if hasattr(g, '_current_admin'):
        g._current_admin = None


def create_admin_session(admin: AdminUser, *, remember: bool = False) -> str:
    raw = secrets.token_urlsafe(32)
    hours = current_app.config.get('ADMIN_SESSION_HOURS', 8)
    if remember:
        hours = current_app.config.get('ADMIN_REMEMBER_HOURS', 24 * 14)
    row = AdminSession(
        admin_user_id=admin.id,
        token_hash=_hash_token(raw),
        ip_address=(request.remote_addr or '')[:64],
        user_agent=(request.headers.get('User-Agent') or '')[:255],
        remember=remember,
        expires_at=datetime.utcnow() + timedelta(hours=hours),
    )
    db.session.add(row)
    admin.last_login_at = datetime.utcnow()
    admin.last_login_ip = (request.remote_addr or '')[:64]
    admin.failed_login_count = 0
    admin.locked_until = None
    db.session.commit()

    session[SESSION_ADMIN_ID] = admin.id
    session[SESSION_ADMIN_TOKEN] = raw
    session.permanent = bool(remember)
    g._current_admin = admin
    return raw


def revoke_current_admin_session() -> None:
    admin_id = session.get(SESSION_ADMIN_ID)
    token = session.get(SESSION_ADMIN_TOKEN)
    if admin_id and token:
        row = AdminSession.query.filter_by(
            admin_user_id=admin_id,
            token_hash=_hash_token(token),
        ).first()
        if row and row.revoked_at is None:
            row.revoked_at = datetime.utcnow()
            db.session.commit()
    clear_admin_session()


def record_login_event(
    email: str,
    *,
    success: bool,
    reason: str | None = None,
    admin_user_id: int | None = None,
) -> None:
    ev = AdminLoginEvent(
        email=(email or '')[:120].lower(),
        admin_user_id=admin_user_id,
        success=success,
        reason=(reason or '')[:120] or None,
        ip_address=(request.remote_addr or '')[:64],
        user_agent=(request.headers.get('User-Agent') or '')[:255],
    )
    db.session.add(ev)
    db.session.commit()


def attempt_admin_login(email: str, password: str, *, remember: bool = False) -> tuple[bool, str]:
    """Returns (ok, error_message). On success creates session."""
    email_n = (email or '').strip().lower()
    if not email_n or not password:
        record_login_event(email_n, success=False, reason='missing_credentials')
        return False, 'Email and password are required.'

    max_fails = int(current_app.config.get('ADMIN_MAX_FAILED_LOGINS', 5))
    lock_minutes = int(current_app.config.get('ADMIN_LOCKOUT_MINUTES', 15))

    admin = AdminUser.query.filter_by(email=email_n).first()
    if not admin:
        record_login_event(email_n, success=False, reason='unknown_user')
        return False, 'Invalid email or password.'

    if admin.locked_until and admin.locked_until > datetime.utcnow():
        record_login_event(email_n, success=False, reason='locked', admin_user_id=admin.id)
        return False, 'Account temporarily locked. Try again later.'

    if not admin.is_active_admin:
        record_login_event(email_n, success=False, reason='inactive', admin_user_id=admin.id)
        return False, 'This admin account is not active.'

    if not admin.check_password(password):
        admin.failed_login_count = (admin.failed_login_count or 0) + 1
        if admin.failed_login_count >= max_fails:
            admin.locked_until = datetime.utcnow() + timedelta(minutes=lock_minutes)
        db.session.commit()
        record_login_event(email_n, success=False, reason='bad_password', admin_user_id=admin.id)
        return False, 'Invalid email or password.'

    # MFA hook (Phase 1): if mfa_enabled, require second step — for now allow if disabled
    if admin.mfa_enabled and admin.mfa_secret:
        # Store pending MFA challenge — Phase 1 completes TOTP verification
        session['_ia_mfa_pending'] = admin.id
        record_login_event(email_n, success=False, reason='mfa_required', admin_user_id=admin.id)
        return False, 'MFA_REQUIRED'

    create_admin_session(admin, remember=remember)
    record_login_event(email_n, success=True, reason='ok', admin_user_id=admin.id)
    return True, ''


def admin_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not get_current_admin():
            return redirect(url_for('platform_admin.login', next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_permission_required(*codes: str):
    """Require ALL listed permission codes (AND)."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            admin = get_current_admin()
            if not admin:
                return redirect(url_for('platform_admin.login', next=request.path))
            for code in codes:
                if not admin.has_permission(code):
                    abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator
