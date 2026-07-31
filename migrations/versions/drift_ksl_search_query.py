"""Align knowledge_search_logs.query -> search_query (additive rename).

Revision ID: drift001ksl
Revises: p2infra001
Create Date: 2026-07-20

Safe for existing production DBs created via db.create_all():
- Never drops tables
- Renames legacy `query` column to `search_query` (preserves data)
- No-op if `search_query` already exists
- Adds `search_query` only if neither column exists
"""
from alembic import op
import sqlalchemy as sa


revision = 'drift001ksl'
down_revision = 'p2infra001'
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return set()
    return {c['name'] for c in insp.get_columns(table_name)}


def upgrade():
    cols = _column_names('knowledge_search_logs')
    if not cols:
        # Table missing entirely — create to match models (empty prod edge case)
        op.create_table(
            'knowledge_search_logs',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('organization_id', sa.Integer(), nullable=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('search_query', sa.String(length=500), nullable=False),
            sa.Column('search_type', sa.String(length=30), nullable=True),
            sa.Column('collection_ids_json', sa.Text(), nullable=True),
            sa.Column('top_k', sa.Integer(), nullable=True),
            sa.Column('result_count', sa.Integer(), nullable=True),
            sa.Column('latency_ms', sa.Integer(), nullable=True),
            sa.Column('project_id', sa.Integer(), nullable=True),
            sa.Column('campaign_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_knowledge_search_logs_organization_id', 'knowledge_search_logs', ['organization_id'])
        op.create_index('ix_knowledge_search_logs_user_id', 'knowledge_search_logs', ['user_id'])
        op.create_index('ix_knowledge_search_logs_created_at', 'knowledge_search_logs', ['created_at'])
        return

    if 'search_query' in cols:
        return

    if 'query' in cols:
        # MySQL CHANGE preserves row data; dialect-portable via ALTER COLUMN rename
        op.alter_column(
            'knowledge_search_logs',
            'query',
            new_column_name='search_query',
            existing_type=sa.String(length=500),
            existing_nullable=False,
        )
        return

    # Neither column present — add required column safely
    op.add_column(
        'knowledge_search_logs',
        sa.Column('search_query', sa.String(length=500), nullable=False, server_default=''),
    )
    op.alter_column('knowledge_search_logs', 'search_query', server_default=None)


def downgrade():
    cols = _column_names('knowledge_search_logs')
    if 'search_query' in cols and 'query' not in cols:
        op.alter_column(
            'knowledge_search_logs',
            'search_query',
            new_column_name='query',
            existing_type=sa.String(length=500),
            existing_nullable=False,
        )
