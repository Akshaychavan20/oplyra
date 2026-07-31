"""Phase 2: background_jobs table + enterprise scale indexes.

Revision ID: p2infra001
Revises: 7758b3e937e3
Create Date: 2026-07-20

Additive only — safe for zero-downtime (CREATE INDEX concurrently not used
for MySQL/SQLite portability; apply during low traffic if tables are huge).
"""
from alembic import op
import sqlalchemy as sa


revision = 'p2infra001'
down_revision = '7758b3e937e3'
branch_labels = None
depends_on = None


def upgrade():
    # Background job tracking
    op.create_table(
        'background_jobs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('task_name', sa.String(length=120), nullable=False),
        sa.Column('celery_task_id', sa.String(length=120), nullable=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='queued'),
        sa.Column('progress', sa.Integer(), server_default='0'),
        sa.Column('payload_json', sa.Text(), nullable=True),
        sa.Column('result_json', sa.Text(), nullable=True),
        sa.Column('error_message', sa.String(length=500), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_background_jobs_task_name', 'background_jobs', ['task_name'])
    op.create_index('ix_background_jobs_celery_task_id', 'background_jobs', ['celery_task_id'])
    op.create_index('ix_background_jobs_user_id', 'background_jobs', ['user_id'])
    op.create_index('ix_background_jobs_organization_id', 'background_jobs', ['organization_id'])
    op.create_index('ix_background_jobs_status', 'background_jobs', ['status'])
    op.create_index('ix_background_jobs_created_at', 'background_jobs', ['created_at'])

    # Hot-path indexes on classic SaaS tables (IF NOT EXISTS via try/except for idempotency)
    _safe_index('ix_projects_user_id', 'projects', ['user_id'])
    _safe_index('ix_projects_is_archived', 'projects', ['is_archived'])
    _safe_index('ix_campaigns_organization_id', 'campaigns', ['organization_id'])
    _safe_index('ix_campaigns_project_id', 'campaigns', ['project_id'])
    _safe_index('ix_campaigns_status', 'campaigns', ['status'])
    _safe_index('ix_contents_organization_id', 'contents', ['organization_id'])
    _safe_index('ix_contents_project_id', 'contents', ['project_id'])
    _safe_index('ix_contents_campaign_id', 'contents', ['campaign_id'])
    _safe_index('ix_contents_status', 'contents', ['status'])
    _safe_index('ix_memberships_user_id', 'memberships', ['user_id'])
    _safe_index('ix_audit_logs_organization_id', 'audit_logs', ['organization_id'])
    _safe_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])
    _safe_index('ix_analytics_logs_user_id', 'analytics_logs', ['user_id'])
    _safe_index('ix_analytics_logs_created_at', 'analytics_logs', ['created_at'])
    # Composite tenant + time for log tables
    _safe_index('ix_tool_runs_org_created', 'tool_runs', ['organization_id', 'created_at'])
    _safe_index('ix_agent_runs_org_created', 'agent_runs', ['organization_id', 'created_at'])
    _safe_index('ix_ai_request_logs_org_created', 'ai_request_logs', ['organization_id', 'created_at'])


def _safe_index(name, table, columns):
    try:
        op.create_index(name, table, columns)
    except Exception:
        # Index may already exist on some environments
        pass


def downgrade():
    for name in (
        'ix_ai_request_logs_org_created',
        'ix_agent_runs_org_created',
        'ix_tool_runs_org_created',
        'ix_analytics_logs_created_at',
        'ix_analytics_logs_user_id',
        'ix_audit_logs_created_at',
        'ix_audit_logs_organization_id',
        'ix_memberships_user_id',
        'ix_contents_status',
        'ix_contents_campaign_id',
        'ix_contents_project_id',
        'ix_contents_organization_id',
        'ix_campaigns_status',
        'ix_campaigns_project_id',
        'ix_campaigns_organization_id',
        'ix_projects_is_archived',
        'ix_projects_user_id',
    ):
        try:
            op.drop_index(name)
        except Exception:
            pass
    op.drop_table('background_jobs')
