"""Harden password_reset_tokens + add auth_security_logs.

Revision ID: pwdreset001
Revises: ia_rbac001
Create Date: 2026-07-27

- Store only SHA-256 token hashes (drop plaintext ``token``)
- Add used_at, ip_address, user_agent
- Add auth_security_logs for password-reset audit events
- Invalidate any pre-existing reset tokens (cannot re-hash safely without raw)
"""
from alembic import op
import sqlalchemy as sa


revision = 'pwdreset001'
down_revision = 'ia_rbac001'
branch_labels = None
depends_on = None


def _tables() -> set:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return set(insp.get_table_names())


def _columns(table: str) -> set:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if table not in set(insp.get_table_names()):
        return set()
    return {c['name'] for c in insp.get_columns(table)}


def upgrade():
    tables = _tables()
    cols = _columns('password_reset_tokens')

    if 'password_reset_tokens' in tables:
        # Wipe existing tokens — plaintext cannot be migrated to hash without raw values
        op.execute(sa.text('DELETE FROM password_reset_tokens'))

        if 'token_hash' not in cols:
            with op.batch_alter_table('password_reset_tokens') as batch:
                batch.add_column(sa.Column('token_hash', sa.String(length=64), nullable=True))
        if 'used_at' not in cols:
            with op.batch_alter_table('password_reset_tokens') as batch:
                batch.add_column(sa.Column('used_at', sa.DateTime(), nullable=True))
        if 'ip_address' not in cols:
            with op.batch_alter_table('password_reset_tokens') as batch:
                batch.add_column(sa.Column('ip_address', sa.String(length=45), nullable=True))
        if 'user_agent' not in cols:
            with op.batch_alter_table('password_reset_tokens') as batch:
                batch.add_column(sa.Column('user_agent', sa.String(length=512), nullable=True))

        cols = _columns('password_reset_tokens')
        if 'token' in cols:
            with op.batch_alter_table('password_reset_tokens') as batch:
                try:
                    batch.drop_index('ix_password_reset_tokens_token')
                except Exception:
                    pass
                try:
                    batch.drop_constraint('token', type_='unique')
                except Exception:
                    pass
                batch.drop_column('token')

        # Enforce NOT NULL + unique on token_hash for new rows
        with op.batch_alter_table('password_reset_tokens') as batch:
            batch.alter_column(
                'token_hash',
                existing_type=sa.String(length=64),
                nullable=False,
            )
        try:
            op.create_index(
                'ix_password_reset_tokens_token_hash',
                'password_reset_tokens',
                ['token_hash'],
                unique=True,
            )
        except Exception:
            pass

    if 'auth_security_logs' not in tables:
        op.create_table(
            'auth_security_logs',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('event_type', sa.String(length=80), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('ip_address', sa.String(length=45), nullable=True),
            sa.Column('user_agent', sa.String(length=512), nullable=True),
            sa.Column('details', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_auth_security_logs_event_type', 'auth_security_logs', ['event_type'])
        op.create_index('ix_auth_security_logs_user_id', 'auth_security_logs', ['user_id'])
        op.create_index('ix_auth_security_logs_created_at', 'auth_security_logs', ['created_at'])


def downgrade():
    tables = _tables()
    if 'auth_security_logs' in tables:
        op.drop_table('auth_security_logs')

    cols = _columns('password_reset_tokens')
    if 'password_reset_tokens' in tables:
        if 'token' not in cols:
            with op.batch_alter_table('password_reset_tokens') as batch:
                batch.add_column(sa.Column('token', sa.String(length=100), nullable=True))
        for col in ('user_agent', 'ip_address', 'used_at', 'token_hash'):
            if col in _columns('password_reset_tokens'):
                with op.batch_alter_table('password_reset_tokens') as batch:
                    batch.drop_column(col)
