"""Password-reset domain helpers — token hashing, issuance, lookup, audit."""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple

from flask import current_app, request

from app import db
from app.models import AuthSecurityLog, PasswordResetToken, User

RESET_TOKEN_TTL_MINUTES = 30
GENERIC_FORGOT_MESSAGE = (
    "If an account exists for this email address, we've sent password reset instructions."
)
SUCCESS_RESET_MESSAGE = 'Password updated successfully.'


def hash_reset_token(raw_token: str) -> str:
    """SHA-256 hex digest of the URL-safe token (never store plaintext)."""
    return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()


def _client_ip() -> Optional[str]:
    try:
        forwarded = request.headers.get('X-Forwarded-For', '')
        if forwarded:
            return forwarded.split(',')[0].strip()[:45] or None
        return (request.remote_addr or None)
    except RuntimeError:
        return None


def _user_agent() -> Optional[str]:
    try:
        ua = request.headers.get('User-Agent') or ''
        return ua[:512] or None
    except RuntimeError:
        return None


def log_auth_security(
    event_type: str,
    *,
    user_id: Optional[int] = None,
    details: Optional[dict] = None,
) -> None:
    """Persist a security audit row. Never include passwords or raw tokens."""
    try:
        payload = details or {}
        # Defense-in-depth: strip sensitive keys if callers pass them by mistake
        for key in ('password', 'token', 'reset_link', 'confirm_password'):
            payload.pop(key, None)
        row = AuthSecurityLog(
            event_type=event_type,
            user_id=user_id,
            ip_address=_client_ip(),
            user_agent=_user_agent(),
            details=json.dumps(payload) if payload else None,
        )
        db.session.add(row)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(
            'Failed to write auth security log event=%s err=%s',
            event_type,
            type(exc).__name__,
        )


def invalidate_user_reset_tokens(user_id: int) -> int:
    """Mark all unused tokens for a user as used (multi-request safe)."""
    now = datetime.utcnow()
    rows = PasswordResetToken.query.filter_by(user_id=user_id, used=False).all()
    for row in rows:
        row.used = True
        row.used_at = now
    return len(rows)


def issue_reset_token(user: User) -> Tuple[str, PasswordResetToken]:
    """
    Invalidate prior tokens, create a new hashed token (30 min TTL).
    Returns (raw_token, row). Raw token must only be emailed — never logged.
    """
    invalidate_user_reset_tokens(user.id)

    raw = secrets.token_urlsafe(32)
    row = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_reset_token(raw),
        expires_at=datetime.utcnow() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
        used=False,
        ip_address=_client_ip(),
        user_agent=_user_agent(),
    )
    db.session.add(row)
    db.session.commit()
    return raw, row


def find_valid_reset_token(raw_token: str) -> Optional[PasswordResetToken]:
    """Lookup by hash; returns row only if unused and unexpired."""
    if not raw_token:
        return None
    token_hash = hash_reset_token(raw_token)
    row = PasswordResetToken.query.filter_by(token_hash=token_hash).first()
    if not row:
        return None
    if row.used:
        return None
    if row.is_expired:
        return None
    return row


def classify_token(raw_token: str) -> Tuple[str, Optional[PasswordResetToken]]:
    """
    Returns (status, row) where status is one of:
    valid | missing | used | expired
    """
    if not raw_token:
        return 'missing', None
    token_hash = hash_reset_token(raw_token)
    row = PasswordResetToken.query.filter_by(token_hash=token_hash).first()
    if not row:
        return 'missing', None
    if row.used:
        return 'used', row
    if row.is_expired:
        return 'expired', row
    return 'valid', row


def consume_reset_token(row: PasswordResetToken) -> None:
    """Mark this token used and invalidate any other unused tokens for the user."""
    row.mark_used()
    others = PasswordResetToken.query.filter(
        PasswordResetToken.user_id == row.user_id,
        PasswordResetToken.id != row.id,
        PasswordResetToken.used.is_(False),
    ).all()
    now = datetime.utcnow()
    for other in others:
        other.used = True
        other.used_at = now
