"""Oplyra Internal Administration Platform — module routes.

Authorization: AdminUser session + RBAC (not customer Flask-Login).
"""
from __future__ import annotations

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request, abort,
)
from flask import current_app

from app import db
from app.platform_admin.access import (
    platform_admin_required,
    is_platform_admin,
    enforce_admin_request_guards,
    write_admin_audit,
)
from app.platform_admin.session import get_current_admin, admin_permission_required
from app.platform_admin import queries as q
from app.platform_admin import flags as flagstore
from app.platform_admin.models import AdminUser
from app.models import User, Organization, Membership, Project, AIRequestLog, AnalyticsLog

platform_admin_bp = Blueprint('platform_admin', __name__, url_prefix='/admin')


@platform_admin_bp.before_request
def _admin_guards():
    return enforce_admin_request_guards()


@platform_admin_bp.context_processor
def inject_admin_context():
    admin = get_current_admin()
    return dict(
        is_platform_admin=bool(admin),
        current_admin=admin,
        admin_can=lambda code: bool(admin and admin.has_permission(code)),
    )


# ── Overview ────────────────────────────────────────────────────────────────

@platform_admin_bp.route('/')
@platform_admin_required
def overview():
    stats = q.overview_kpis()
    return render_template('platform_admin/overview.html', stats=stats, section='overview')


# ── Users ───────────────────────────────────────────────────────────────────

@platform_admin_bp.route('/users')
@platform_admin_required
def users():
    search = (request.args.get('q') or '').strip()
    status = (request.args.get('status') or 'all').strip().lower()
    page = request.args.get('page', 1, type=int)

    query = User.query
    if search:
        like = f'%{search}%'
        query = query.filter(
            (User.username.like(like)) | (User.email.like(like))
        )
    query = query.order_by(User.created_at.desc())
    pagination = query.paginate(page=page, per_page=25, error_out=False)

    rows = []
    for u in pagination.items:
        suspended = flagstore.is_user_suspended(u.id)
        if status == 'suspended' and not suspended:
            continue
        if status == 'active' and suspended:
            continue
        org = None
        mem = Membership.query.filter_by(user_id=u.id).first()
        if mem:
            org = Organization.query.get(mem.organization_id)
        usage = AIRequestLog.query.filter_by(user_id=u.id).count()
        rows.append({
            'user': u,
            'suspended': suspended,
            'org': org,
            'usage': usage,
            'clients': Project.query.filter_by(user_id=u.id).count(),
        })

    return render_template(
        'platform_admin/users.html',
        rows=rows,
        pagination=pagination,
        search=search,
        status=status,
        section='users',
    )


@platform_admin_bp.route('/users/<int:user_id>')
@platform_admin_required
def user_detail(user_id):
    user = User.query.get_or_404(user_id)
    mem = Membership.query.filter_by(user_id=user.id).first()
    org = Organization.query.get(mem.organization_id) if mem else None
    recent_ai = (
        AIRequestLog.query.filter_by(user_id=user.id)
        .order_by(AIRequestLog.created_at.desc())
        .limit(30)
        .all()
    )
    recent_activity = (
        AnalyticsLog.query.filter_by(user_id=user.id)
        .order_by(AnalyticsLog.created_at.desc())
        .limit(40)
        .all()
    )
    clients = Project.query.filter_by(user_id=user.id).order_by(Project.updated_at.desc()).limit(20).all()
    return render_template(
        'platform_admin/user_detail.html',
        user=user,
        org=org,
        membership=mem,
        suspended=flagstore.is_user_suspended(user.id),
        recent_ai=recent_ai,
        recent_activity=recent_activity,
        clients=clients,
        section='users',
    )


@platform_admin_bp.route('/users/<int:user_id>/suspend', methods=['POST'])
@platform_admin_required
def user_suspend(user_id):
    user = User.query.get_or_404(user_id)
    flagstore.suspend_user(user.id)
    write_admin_audit(
        'users.suspend',
        resource_type='user',
        resource_id=user.id,
        payload={'email': user.email},
    )
    flash(f'User {user.email} suspended.', 'success')
    return redirect(url_for('platform_admin.user_detail', user_id=user_id))


@platform_admin_bp.route('/users/<int:user_id>/activate', methods=['POST'])
@platform_admin_required
def user_activate(user_id):
    user = User.query.get_or_404(user_id)
    flagstore.activate_user(user.id)
    write_admin_audit(
        'users.activate',
        resource_type='user',
        resource_id=user.id,
        payload={'email': user.email},
    )
    flash(f'User {user.email} activated.', 'success')
    return redirect(url_for('platform_admin.user_detail', user_id=user_id))


@platform_admin_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@platform_admin_required
def user_reset_password(user_id):
    """Create a one-time hashed reset token — never display or set a raw password."""
    from app.services.password_reset import issue_reset_token
    from app.services.mail import queue_password_reset_email

    user = User.query.get_or_404(user_id)
    raw_token, _row = issue_reset_token(user)
    # Admin-issued tokens still use the standard 30-minute TTL from issue_reset_token
    reset_url = url_for('auth.reset_password', token=raw_token, _external=True)
    try:
        queue_password_reset_email(to=user.email, reset_link=reset_url, expires_minutes=30)
    except Exception:
        pass
    write_admin_audit(
        'users.reset_password',
        resource_type='user',
        resource_id=user.id,
        payload={'email': user.email},
    )
    # Do not embed the raw reset URL in the flash (leak risk) — confirm issuance only
    flash(
        f'Password reset link created for {user.email} (valid 30 minutes). '
        'A reset email was queued; share the link out-of-band only if email delivery is unavailable.',
        'info',
    )
    return redirect(url_for('platform_admin.user_detail', user_id=user_id))


# ── Subscriptions & Billing ─────────────────────────────────────────────────

@platform_admin_bp.route('/subscriptions')
@platform_admin_required
def subscriptions():
    data = q.billing_dashboard()
    return render_template('platform_admin/subscriptions.html', data=data, section='subscriptions')


@platform_admin_bp.route('/billing')
@platform_admin_required
def billing():
    data = q.billing_dashboard()
    return render_template('platform_admin/billing.html', data=data, section='billing')


@platform_admin_bp.route('/organizations')
@platform_admin_required
def organizations():
    orgs = Organization.query.order_by(Organization.created_at.desc()).limit(200).all()
    return render_template('platform_admin/organizations.html', orgs=orgs, section='users')


# ── AI ──────────────────────────────────────────────────────────────────────

@platform_admin_bp.route('/ai-analytics')
@platform_admin_required
def ai_analytics():
    days = request.args.get('days', 30, type=int)
    days = 7 if days not in (7, 30, 90) else days
    data = q.ai_analytics_bundle(days=days)
    return render_template(
        'platform_admin/ai_analytics.html',
        data=data,
        section='ai-analytics',
    )


@platform_admin_bp.route('/ai-providers')
@platform_admin_required
def ai_providers():
    providers = q.list_ai_providers()
    health = q.platform_health_snapshot()
    return render_template(
        'platform_admin/ai_providers.html',
        providers=providers,
        health=health,
        default_provider=health.get('default_ai_provider'),
        section='ai-providers',
    )


@platform_admin_bp.route('/agents')
@platform_admin_required
def agents():
    data = q.agents_dashboard()
    return render_template('platform_admin/agents.html', data=data, section='agents')


@platform_admin_bp.route('/knowledge')
@platform_admin_required
def knowledge():
    data = q.knowledge_dashboard()
    return render_template('platform_admin/knowledge.html', data=data, section='knowledge')


@platform_admin_bp.route('/tools')
@platform_admin_required
def tools():
    data = q.tools_dashboard()
    return render_template('platform_admin/tools.html', data=data, section='tools')


# ── Infra ───────────────────────────────────────────────────────────────────

@platform_admin_bp.route('/storage')
@platform_admin_required
def storage():
    data = q.storage_dashboard()
    return render_template('platform_admin/storage.html', data=data, section='storage')


@platform_admin_bp.route('/infrastructure')
@platform_admin_required
def infrastructure():
    data = q.infra_dashboard()
    return render_template('platform_admin/infrastructure.html', data=data, section='infrastructure')


@platform_admin_bp.route('/monitoring')
@platform_admin_required
def monitoring():
    health = q.platform_health_snapshot()
    from app.infra.metrics import snapshot
    metrics = snapshot()
    return render_template(
        'platform_admin/monitoring.html',
        health=health,
        metrics=metrics,
        section='monitoring',
    )


@platform_admin_bp.route('/health')
@platform_admin_required
def health_page():
    return redirect(url_for('platform_admin.monitoring'))


@platform_admin_bp.route('/audit')
@platform_admin_required
def audit():
    page = request.args.get('page', 1, type=int)
    search = (request.args.get('q') or '').strip()
    data = q.audit_logs_page(q=search, page=page)
    return render_template('platform_admin/audit.html', data=data, section='audit')


@platform_admin_bp.route('/feature-flags', methods=['GET', 'POST'])
@platform_admin_required
def feature_flags():
    if request.method == 'POST':
        key = (request.form.get('key') or '').strip()
        enabled = request.form.get('enabled') == '1'
        if key:
            flagstore.set_flag(key, enabled)
            write_admin_audit(
                'flags.set',
                resource_type='feature_flag',
                resource_id=key,
                payload={'enabled': enabled},
            )
            flash(f'Flag “{key}” set to {"on" if enabled else "off"}.', 'success')
        return redirect(url_for('platform_admin.feature_flags'))
    flags = flagstore.get_flags()
    return render_template(
        'platform_admin/feature_flags.html',
        flags=flags,
        section='feature-flags',
    )


@platform_admin_bp.route('/settings')
@platform_admin_required
def settings():
    cfg = {
        'default_ai_provider': current_app.config.get('AI_DEFAULT_PROVIDER'),
        'gemini_model': current_app.config.get('GEMINI_MODEL'),
        'storage_provider': current_app.config.get('STORAGE_PROVIDER'),
        'vector_provider': current_app.config.get('KNOWLEDGE_VECTOR_PROVIDER'),
        'embedding_provider': current_app.config.get('KNOWLEDGE_EMBEDDING_PROVIDER'),
        'redis_url': 'configured' if current_app.config.get('REDIS_URL') else 'missing',
        'celery_eager': current_app.config.get('CELERY_TASK_ALWAYS_EAGER'),
        'structured_logging': current_app.config.get('STRUCTURED_LOGGING'),
        'platform_admins': AdminUser.query.count(),
        'admin_hosts': current_app.config.get('ADMIN_HOSTS') or [],
    }
    providers_enabled = {
        'gemini': current_app.config.get('AI_ENABLE_GEMINI'),
        'openai': current_app.config.get('AI_ENABLE_OPENAI'),
        'anthropic': current_app.config.get('AI_ENABLE_ANTHROPIC'),
        'deepseek': current_app.config.get('AI_ENABLE_DEEPSEEK'),
    }
    return render_template(
        'platform_admin/settings.html',
        cfg=cfg,
        providers_enabled=providers_enabled,
        section='settings',
    )


# Legacy stub redirect for old bookmarks
@platform_admin_bp.route('/section/<slug>')
@platform_admin_required
def section_stub(slug):
    mapping = {
        'subscriptions': 'platform_admin.subscriptions',
        'billing': 'platform_admin.billing',
        'ai-providers': 'platform_admin.ai_providers',
        'ai-models': 'platform_admin.ai_providers',
        'token-usage': 'platform_admin.ai_analytics',
        'provider-costs': 'platform_admin.ai_analytics',
        'agents': 'platform_admin.agents',
        'knowledge': 'platform_admin.knowledge',
        'tools': 'platform_admin.tools',
        'mcp': 'platform_admin.tools',
        'storage': 'platform_admin.storage',
        'queues': 'platform_admin.infrastructure',
        'workers': 'platform_admin.infrastructure',
        'redis': 'platform_admin.infrastructure',
        'vector': 'platform_admin.infrastructure',
        'logs': 'platform_admin.audit',
        'monitoring': 'platform_admin.monitoring',
        'analytics': 'platform_admin.ai_analytics',
        'audit': 'platform_admin.audit',
        'feature-flags': 'platform_admin.feature_flags',
        'system': 'platform_admin.settings',
    }
    endpoint = mapping.get(slug)
    if endpoint:
        return redirect(url_for(endpoint))
    abort(404)


# Register auth routes on the same blueprint
from app.platform_admin import auth_routes  # noqa: E402, F401
