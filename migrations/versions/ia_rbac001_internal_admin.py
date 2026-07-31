"""Internal Admin RBAC schema — separate staff identity from customer users.

Revision ID: ia_rbac001
Revises: drift001ksl
Create Date: 2026-07-21
"""
from alembic import op
import sqlalchemy as sa


revision = 'ia_rbac001'
down_revision = 'drift001ksl'
branch_labels = None
depends_on = None


def _tables() -> set:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return set(insp.get_table_names())


def upgrade():
    existing = _tables()

    if 'admin_roles' not in existing:
        op.create_table(
            'admin_roles',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('slug', sa.String(64), nullable=False),
            sa.Column('name', sa.String(120), nullable=False),
            sa.Column('description', sa.String(255), nullable=True),
            sa.Column('is_system', sa.Boolean(), nullable=False, server_default=sa.text('1')),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.UniqueConstraint('slug'),
        )
        op.create_index('ix_admin_roles_slug', 'admin_roles', ['slug'])

    if 'admin_permissions' not in existing:
        op.create_table(
            'admin_permissions',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('code', sa.String(80), nullable=False),
            sa.Column('description', sa.String(255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.UniqueConstraint('code'),
        )
        op.create_index('ix_admin_permissions_code', 'admin_permissions', ['code'])

    if 'admin_role_permissions' not in existing:
        op.create_table(
            'admin_role_permissions',
            sa.Column('role_id', sa.Integer(), sa.ForeignKey('admin_roles.id', ondelete='CASCADE'), primary_key=True),
            sa.Column('permission_id', sa.Integer(), sa.ForeignKey('admin_permissions.id', ondelete='CASCADE'), primary_key=True),
        )

    if 'admin_users' not in existing:
        op.create_table(
            'admin_users',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('email', sa.String(120), nullable=False),
            sa.Column('full_name', sa.String(120), nullable=True),
            sa.Column('password_hash', sa.String(255), nullable=False),
            sa.Column('role_id', sa.Integer(), sa.ForeignKey('admin_roles.id', ondelete='RESTRICT'), nullable=False),
            sa.Column('status', sa.String(32), nullable=False, server_default='active'),
            sa.Column('linked_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('mfa_enabled', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('mfa_secret', sa.String(64), nullable=True),
            sa.Column('email_verified_at', sa.DateTime(), nullable=True),
            sa.Column('failed_login_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('locked_until', sa.DateTime(), nullable=True),
            sa.Column('last_login_at', sa.DateTime(), nullable=True),
            sa.Column('last_login_ip', sa.String(64), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.UniqueConstraint('email'),
        )
        op.create_index('ix_admin_users_email', 'admin_users', ['email'])
        op.create_index('ix_admin_users_role_id', 'admin_users', ['role_id'])
        op.create_index('ix_admin_users_status', 'admin_users', ['status'])

    if 'admin_sessions' not in existing:
        op.create_table(
            'admin_sessions',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('admin_user_id', sa.Integer(), sa.ForeignKey('admin_users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('token_hash', sa.String(64), nullable=False),
            sa.Column('ip_address', sa.String(64), nullable=True),
            sa.Column('user_agent', sa.String(255), nullable=True),
            sa.Column('remember', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('revoked_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.UniqueConstraint('token_hash'),
        )
        op.create_index('ix_admin_sessions_admin_user_id', 'admin_sessions', ['admin_user_id'])
        op.create_index('ix_admin_sessions_token_hash', 'admin_sessions', ['token_hash'])
        op.create_index('ix_admin_sessions_expires_at', 'admin_sessions', ['expires_at'])

    if 'admin_audit_logs' not in existing:
        op.create_table(
            'admin_audit_logs',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('actor_id', sa.Integer(), sa.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('action', sa.String(80), nullable=False),
            sa.Column('resource_type', sa.String(80), nullable=True),
            sa.Column('resource_id', sa.String(64), nullable=True),
            sa.Column('ip_address', sa.String(64), nullable=True),
            sa.Column('user_agent', sa.String(255), nullable=True),
            sa.Column('payload_json', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
        )
        op.create_index('ix_admin_audit_logs_actor_id', 'admin_audit_logs', ['actor_id'])
        op.create_index('ix_admin_audit_logs_action', 'admin_audit_logs', ['action'])
        op.create_index('ix_admin_audit_logs_created_at', 'admin_audit_logs', ['created_at'])

    if 'admin_login_events' not in existing:
        op.create_table(
            'admin_login_events',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('email', sa.String(120), nullable=False),
            sa.Column('admin_user_id', sa.Integer(), sa.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('success', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('reason', sa.String(120), nullable=True),
            sa.Column('ip_address', sa.String(64), nullable=True),
            sa.Column('user_agent', sa.String(255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
        )
        op.create_index('ix_admin_login_events_email', 'admin_login_events', ['email'])
        op.create_index('ix_admin_login_events_created_at', 'admin_login_events', ['created_at'])

    if 'admin_feature_flags' not in existing:
        op.create_table(
            'admin_feature_flags',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('key', sa.String(80), nullable=False),
            sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('description', sa.String(255), nullable=True),
            sa.Column('audience_json', sa.Text(), nullable=True),
            sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.UniqueConstraint('key'),
        )
        op.create_index('ix_admin_feature_flags_key', 'admin_feature_flags', ['key'])


def downgrade():
    for table in (
        'admin_feature_flags',
        'admin_login_events',
        'admin_audit_logs',
        'admin_sessions',
        'admin_users',
        'admin_role_permissions',
        'admin_permissions',
        'admin_roles',
    ):
        if table in _tables():
            op.drop_table(table)
