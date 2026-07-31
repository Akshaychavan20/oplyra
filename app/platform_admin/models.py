"""Internal Administration identity & RBAC models.

Completely separate from customer ``User`` / org ``Membership`` roles.
"""
from __future__ import annotations

from datetime import datetime

from app import db, bcrypt


class AdminRole(db.Model):
    __tablename__ = 'admin_roles'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    is_system = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    permissions = db.relationship(
        'AdminPermission',
        secondary='admin_role_permissions',
        lazy='joined',
        backref=db.backref('roles', lazy='dynamic'),
    )
    users = db.relationship('AdminUser', back_populates='role', lazy='dynamic')

    def __repr__(self):
        return f'<AdminRole {self.slug}>'


class AdminPermission(db.Model):
    __tablename__ = 'admin_permissions'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<AdminPermission {self.code}>'


class AdminRolePermission(db.Model):
    __tablename__ = 'admin_role_permissions'

    role_id = db.Column(
        db.Integer, db.ForeignKey('admin_roles.id', ondelete='CASCADE'), primary_key=True
    )
    permission_id = db.Column(
        db.Integer, db.ForeignKey('admin_permissions.id', ondelete='CASCADE'), primary_key=True
    )


class AdminUser(db.Model):
    """Internal staff account — never a customer ``User``."""
    __tablename__ = 'admin_users'

    STATUS_ACTIVE = 'active'
    STATUS_SUSPENDED = 'suspended'
    STATUS_INVITED = 'invited'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role_id = db.Column(
        db.Integer, db.ForeignKey('admin_roles.id', ondelete='RESTRICT'), nullable=False, index=True
    )
    status = db.Column(db.String(32), default=STATUS_ACTIVE, nullable=False, index=True)

    # Optional link for support context only — does NOT grant admin via customer login
    linked_user_id = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )

    mfa_enabled = db.Column(db.Boolean, default=False, nullable=False)
    mfa_secret = db.Column(db.String(64), nullable=True)
    email_verified_at = db.Column(db.DateTime, nullable=True)

    failed_login_count = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    last_login_ip = db.Column(db.String(64), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    role = db.relationship('AdminRole', back_populates='users')
    sessions = db.relationship(
        'AdminSession', back_populates='admin_user', lazy='dynamic', cascade='all, delete-orphan'
    )

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)

    @property
    def is_active_admin(self) -> bool:
        return self.status == self.STATUS_ACTIVE

    def permission_codes(self) -> set:
        if not self.role:
            return set()
        return {p.code for p in (self.role.permissions or [])}

    def has_permission(self, code: str) -> bool:
        if not self.is_active_admin:
            return False
        codes = self.permission_codes()
        if '*' in codes or 'admin:all' in codes:
            return True
        return code in codes

    def __repr__(self):
        return f'<AdminUser {self.email}>'


class AdminSession(db.Model):
    __tablename__ = 'admin_sessions'

    id = db.Column(db.Integer, primary_key=True)
    admin_user_id = db.Column(
        db.Integer, db.ForeignKey('admin_users.id', ondelete='CASCADE'), nullable=False, index=True
    )
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    remember = db.Column(db.Boolean, default=False, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    admin_user = db.relationship('AdminUser', back_populates='sessions')

    @property
    def is_valid(self) -> bool:
        if self.revoked_at is not None:
            return False
        return self.expires_at > datetime.utcnow()


class AdminAuditLog(db.Model):
    """Append-only internal staff audit trail (not org-scoped AuditLog)."""
    __tablename__ = 'admin_audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(
        db.Integer, db.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True, index=True
    )
    action = db.Column(db.String(80), nullable=False, index=True)
    resource_type = db.Column(db.String(80), nullable=True, index=True)
    resource_id = db.Column(db.String(64), nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    payload_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    actor = db.relationship('AdminUser', foreign_keys=[actor_id])


class AdminLoginEvent(db.Model):
    __tablename__ = 'admin_login_events'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    admin_user_id = db.Column(
        db.Integer, db.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True
    )
    success = db.Column(db.Boolean, nullable=False, default=False)
    reason = db.Column(db.String(120), nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)


class AdminFeatureFlag(db.Model):
    __tablename__ = 'admin_feature_flags'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False, index=True)
    enabled = db.Column(db.Boolean, default=False, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    audience_json = db.Column(db.Text, nullable=True)
    updated_by_id = db.Column(
        db.Integer, db.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True
    )
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
