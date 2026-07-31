"""Seed roles, permissions, and bootstrap super admin."""
from __future__ import annotations

from flask import current_app

from app import db
from app.platform_admin.models import AdminRole, AdminPermission, AdminUser, AdminFeatureFlag
from app.platform_admin.permissions import PERMISSIONS, ROLE_MATRIX, ROLE_META
from app.platform_admin import flags as flagstore


def seed_rbac(commit: bool = True) -> dict:
    """Idempotent: ensure permission catalog + roles + matrix exist."""
    created_perms = 0
    for code, desc in PERMISSIONS.items():
        row = AdminPermission.query.filter_by(code=code).first()
        if not row:
            db.session.add(AdminPermission(code=code, description=desc))
            created_perms += 1
    db.session.flush()

    created_roles = 0
    for slug, codes in ROLE_MATRIX.items():
        name, desc = ROLE_META.get(slug, (slug.replace('_', ' ').title(), ''))
        role = AdminRole.query.filter_by(slug=slug).first()
        if not role:
            role = AdminRole(slug=slug, name=name, description=desc, is_system=True)
            db.session.add(role)
            db.session.flush()
            created_roles += 1
        else:
            role.name = name
            role.description = desc

        wanted = set(codes)
        # Resolve permission objects
        perms = AdminPermission.query.filter(AdminPermission.code.in_(wanted)).all()
        role.permissions = perms

    # Sync default feature flags into DB mirror
    for key, enabled in flagstore.get_flags().items():
        row = AdminFeatureFlag.query.filter_by(key=key).first()
        if not row:
            db.session.add(AdminFeatureFlag(key=key, enabled=bool(enabled)))

    if commit:
        db.session.commit()
    return {'permissions_created': created_perms, 'roles_created': created_roles}


def bootstrap_super_admin(commit: bool = True) -> AdminUser | None:
    """Create first super_admin from env if no admin users exist."""
    if AdminUser.query.count() > 0:
        return None

    email = (current_app.config.get('INTERNAL_ADMIN_BOOTSTRAP_EMAIL') or '').strip().lower()
    password = current_app.config.get('INTERNAL_ADMIN_BOOTSTRAP_PASSWORD') or ''

    # Fallback: first PLATFORM_ADMIN_EMAILS entry + bootstrap password / default in DEBUG
    if not email:
        emails = current_app.config.get('PLATFORM_ADMIN_EMAILS') or []
        if emails:
            email = emails[0]

    if not email:
        return None

    if not password:
        if current_app.config.get('DEBUG') or current_app.config.get('TESTING'):
            password = 'AdminBootstrap1!'
        else:
            current_app.logger.warning(
                'INTERNAL_ADMIN_BOOTSTRAP_PASSWORD not set; skipping admin bootstrap'
            )
            return None

    seed_rbac(commit=False)
    role = AdminRole.query.filter_by(slug='super_admin').first()
    if not role:
        return None

    admin = AdminUser(
        email=email,
        full_name='Bootstrap Super Admin',
        role_id=role.id,
        status=AdminUser.STATUS_ACTIVE,
    )
    admin.set_password(password)
    from datetime import datetime
    admin.email_verified_at = datetime.utcnow()
    db.session.add(admin)
    if commit:
        db.session.commit()
    current_app.logger.info('Bootstrapped internal super_admin: %s', email)
    return admin


def sync_bootstrap_admin_password(commit: bool = True) -> bool:
    """Keep bootstrap admin password aligned with env when explicitly allowed.

    Bootstrap only *creates* the first AdminUser once. Changing
    INTERNAL_ADMIN_BOOTSTRAP_PASSWORD in .env does not update the stored hash,
    which produces 'Invalid email or password' at check_password.

    Syncs when DEBUG/TESTING, or INTERNAL_ADMIN_BOOTSTRAP_RESET_PASSWORD=1.
    Uses the same Flask-Bcrypt path as login (AdminUser.set_password).
    """
    email = (current_app.config.get('INTERNAL_ADMIN_BOOTSTRAP_EMAIL') or '').strip().lower()
    if not email:
        emails = current_app.config.get('PLATFORM_ADMIN_EMAILS') or []
        email = emails[0] if emails else ''
    password = current_app.config.get('INTERNAL_ADMIN_BOOTSTRAP_PASSWORD') or ''
    if not email or not password:
        return False

    reset_flag = str(current_app.config.get('INTERNAL_ADMIN_BOOTSTRAP_RESET_PASSWORD') or '').lower() in (
        '1', 'true', 'yes',
    )
    if not (reset_flag or current_app.config.get('DEBUG') or current_app.config.get('TESTING')):
        return False

    admin = AdminUser.query.filter_by(email=email).first()
    if not admin:
        return False

    # Already matches — still clear lockout from failed attempts against a stale password
    if admin.check_password(password):
        if admin.failed_login_count or admin.locked_until:
            admin.failed_login_count = 0
            admin.locked_until = None
            if commit:
                db.session.commit()
            return True
        return False

    admin.set_password(password)
    admin.failed_login_count = 0
    admin.locked_until = None
    admin.status = AdminUser.STATUS_ACTIVE
    if commit:
        db.session.commit()
    current_app.logger.info(
        'Synced INTERNAL_ADMIN_BOOTSTRAP_PASSWORD for %s (stale hash / lockout cleared)',
        email,
    )
    return True


def ensure_internal_admin_ready() -> None:
    """Called from app factory — seed + optional bootstrap."""
    try:
        seed_rbac(commit=True)
        bootstrap_super_admin(commit=True)
        sync_bootstrap_admin_password(commit=True)
    except Exception as exc:
        # Tables may not exist yet during first migrate
        current_app.logger.debug('Internal admin seed skipped: %s', exc)
        db.session.rollback()
