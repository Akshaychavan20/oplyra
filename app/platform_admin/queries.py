"""Platform Admin data aggregations — read-only over existing models/services."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app
from sqlalchemy import func

from app import db


def _safe_count(model) -> int:
    try:
        return model.query.count()
    except Exception:
        return 0


def overview_kpis() -> Dict[str, Any]:
    from app.models import (
        User, Organization, Project, Campaign, Content,
        BackgroundJob, AIRequestLog, AgentRun, KnowledgeDocument,
        ToolDefinition, Subscription, Plan, Asset, KnowledgeChunk,
        KnowledgeSearchLog,
    )

    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    total_users = _safe_count(User)
    new_signups = User.query.filter(User.created_at >= week_ago).count()
    active_users = (
        db.session.query(User.id)
        .join(AIRequestLog, AIRequestLog.user_id == User.id)
        .filter(AIRequestLog.created_at >= week_ago)
        .distinct()
        .count()
    )

    # Plan tiers via Organization.plan_tier (no join required) + Subscriptions when present
    free_users = Organization.query.filter(
        (Organization.plan_tier == 'free') | (Organization.plan_tier.is_(None))
    ).count()
    paid_orgs = Organization.query.filter(
        Organization.plan_tier.in_(['pro', 'agency', 'enterprise', 'starter'])
    ).count()

    mrr, arr, paid_subs, trial_subs, cancelled_subs = subscription_revenue()

    ai_today = AIRequestLog.query.filter(AIRequestLog.created_at >= day_ago).count()
    logs_today = (
        AIRequestLog.query.filter(AIRequestLog.created_at >= day_ago).limit(8000).all()
    )
    cost_today = sum(float(r.calculated_cost or 0) for r in logs_today)
    latency_vals = [int(r.latency_ms or 0) for r in logs_today if r.latency_ms]
    avg_latency = int(sum(latency_vals) / len(latency_vals)) if latency_vals else 0

    storage_bytes = 0
    try:
        storage_bytes = db.session.query(func.coalesce(func.sum(Asset.file_size), 0)).scalar() or 0
    except Exception:
        storage_bytes = 0

    queued = BackgroundJob.query.filter_by(status='queued').count()
    running = BackgroundJob.query.filter_by(status='running').count()
    failed = BackgroundJob.query.filter_by(status='failed').count()

    from app.platform_admin.flags import is_user_suspended
    suspended = sum(1 for u in User.query.with_entities(User.id).all() if is_user_suspended(u.id))

    return {
        'total_users': total_users,
        'active_users': active_users,
        'new_signups': new_signups,
        'free_users': free_users,
        'paid_users': paid_orgs,
        'suspended_users': suspended,
        'mrr': mrr,
        'arr': arr,
        'ai_requests_today': ai_today,
        'avg_latency_ms': avg_latency,
        'cost_today': round(cost_today, 4),
        'storage_bytes': int(storage_bytes),
        'storage_human': _human_bytes(storage_bytes),
        'jobs_queued': queued,
        'jobs_running': running,
        'jobs_failed': failed,
        'queue_label': f'{queued} queued · {running} running',
        'total_orgs': _safe_count(Organization),
        'clients': _safe_count(Project),
        'campaigns': _safe_count(Campaign),
        'contents': _safe_count(Content),
        'agent_runs_7d': AgentRun.query.filter(AgentRun.created_at >= week_ago).count(),
        'knowledge_docs': _safe_count(KnowledgeDocument),
        'knowledge_chunks': _safe_count(KnowledgeChunk),
        'search_requests_7d': KnowledgeSearchLog.query.filter(
            KnowledgeSearchLog.created_at >= week_ago
        ).count() if _model_ok(KnowledgeSearchLog) else 0,
        'tools_count': _safe_count(ToolDefinition),
        'paid_subs': paid_subs,
        'trial_subs': trial_subs,
        'cancelled_subs': cancelled_subs,
        'signups_30d': User.query.filter(User.created_at >= month_ago).count(),
        'health': platform_health_snapshot(),
    }


def subscription_revenue() -> Tuple[float, float, int, int, int]:
    from app.models import Subscription, Plan

    mrr = 0.0
    paid = trial = cancelled = 0
    try:
        rows = (
            db.session.query(Subscription, Plan)
            .join(Plan, Subscription.plan_id == Plan.id)
            .all()
        )
        for sub, plan in rows:
            status = (sub.status or '').lower()
            if status in ('canceled', 'cancelled'):
                cancelled += 1
                continue
            if status in ('trialing', 'trial'):
                trial += 1
            if status in ('active', 'past_due', 'trialing', 'trial'):
                paid += 1
                mrr += float(plan.price_monthly or 0)
    except Exception:
        # Fallback: estimate from org plan tiers
        from app.models import Organization
        tier_prices = {'free': 0, 'starter': 19, 'pro': 49, 'agency': 149, 'enterprise': 299}
        for org in Organization.query.all():
            price = tier_prices.get((org.plan_tier or 'free').lower(), 0)
            if price > 0:
                paid += 1
                mrr += price
            else:
                trial += 0
    arr = mrr * 12
    return round(mrr, 2), round(arr, 2), paid, trial, cancelled


def platform_health_snapshot() -> Dict[str, Any]:
    """Reuse the same probes as /health without HTTP round-trip."""
    from app.health.routes import (
        _check_database, _check_redis, _check_vector,
        _check_storage, _check_ai_providers, _check_workers,
    )
    checks = {
        'database': _check_database(),
        'redis': _check_redis(),
        'vector': _check_vector(),
        'storage': _check_storage(),
        'ai_providers': _check_ai_providers(),
        'workers': _check_workers(),
    }
    ok = all(v[0] for v in checks.values())
    return {
        'ok': ok,
        'status': 'healthy' if ok else 'degraded',
        'checks': {k: {'ok': v[0], 'detail': v[1]} for k, v in checks.items()},
        'storage_provider': current_app.config.get('STORAGE_PROVIDER', 'local'),
        'vector_provider': current_app.config.get('KNOWLEDGE_VECTOR_PROVIDER', 'local'),
        'embedding_provider': current_app.config.get('KNOWLEDGE_EMBEDDING_PROVIDER', 'local'),
        'celery_eager': bool(current_app.config.get('CELERY_TASK_ALWAYS_EAGER')),
        'default_ai_provider': current_app.config.get('AI_DEFAULT_PROVIDER', 'auto'),
    }


def ai_analytics_bundle(days: int = 30) -> Dict[str, Any]:
    from app.models import AIRequestLog, AgentRun

    since = datetime.utcnow() - timedelta(days=days)
    logs = (
        AIRequestLog.query.filter(AIRequestLog.created_at >= since)
        .order_by(AIRequestLog.created_at.asc())
        .limit(20000)
        .all()
    )

    daily = defaultdict(lambda: {'requests': 0, 'tokens_in': 0, 'tokens_out': 0, 'cost': 0.0, 'latency': []})
    providers = Counter()
    models = Counter()
    errors = 0
    fallbacks = 0
    total_cost = 0.0
    total_in = total_out = 0
    latencies = []

    for r in logs:
        day = (r.created_at or since).strftime('%Y-%m-%d')
        daily[day]['requests'] += 1
        daily[day]['tokens_in'] += int(r.input_tokens or 0)
        daily[day]['tokens_out'] += int(r.output_tokens or 0)
        cost = float(r.calculated_cost or 0)
        daily[day]['cost'] += cost
        total_cost += cost
        total_in += int(r.input_tokens or 0)
        total_out += int(r.output_tokens or 0)
        if r.latency_ms:
            daily[day]['latency'].append(int(r.latency_ms))
            latencies.append(int(r.latency_ms))
        providers[r.provider or 'unknown'] += 1
        models[r.model_used or 'unknown'] += 1
        status = (r.status or '').lower()
        if status not in ('success', 'ok', 'completed', ''):
            errors += 1
        if int(r.retry_count or 0) > 0:
            fallbacks += 1

    labels = sorted(daily.keys())
    chart_requests = [daily[d]['requests'] for d in labels]
    chart_cost = [round(daily[d]['cost'], 4) for d in labels]
    chart_latency = [
        int(sum(daily[d]['latency']) / len(daily[d]['latency'])) if daily[d]['latency'] else 0
        for d in labels
    ]

    total = len(logs) or 1
    agent_runs = AgentRun.query.filter(AgentRun.created_at >= since).all()
    agent_keys = Counter((r.agent_key or r.mode or 'unknown') for r in agent_runs)
    agent_ok = sum(1 for r in agent_runs if (r.status or '') == 'completed')
    agent_fail = sum(1 for r in agent_runs if (r.status or '') == 'failed')

    return {
        'days': days,
        'total_requests': len(logs),
        'total_cost': round(total_cost, 4),
        'input_tokens': total_in,
        'output_tokens': total_out,
        'avg_latency_ms': int(sum(latencies) / len(latencies)) if latencies else 0,
        'error_rate': round(100.0 * errors / total, 2),
        'fallback_rate': round(100.0 * fallbacks / total, 2),
        'avg_cost': round(total_cost / total, 6),
        'providers': providers.most_common(12),
        'models': models.most_common(12),
        'top_agents': agent_keys.most_common(10),
        'agent_runs': len(agent_runs),
        'agent_success_rate': round(100.0 * agent_ok / (len(agent_runs) or 1), 1),
        'agent_failures': agent_fail,
        'chart': {
            'labels': labels,
            'requests': chart_requests,
            'cost': chart_cost,
            'latency': chart_latency,
        },
        'recent': logs[-100:][::-1] if logs else [],
    }


def list_ai_providers() -> List[Dict[str, Any]]:
    try:
        from app.services.ai.registry import ProviderRegistry
        return ProviderRegistry.instance().list_providers()
    except Exception as exc:
        return [{'id': 'error', 'enabled': False, 'error': str(exc)}]


def agents_dashboard() -> Dict[str, Any]:
    from app.models import AgentRun

    week_ago = datetime.utcnow() - timedelta(days=7)
    runs = AgentRun.query.filter(AgentRun.created_at >= week_ago).order_by(AgentRun.created_at.desc()).limit(200).all()
    all_week = AgentRun.query.filter(AgentRun.created_at >= week_ago).all()
    completed = [r for r in all_week if r.status == 'completed']
    failed = [r for r in all_week if r.status == 'failed']
    durations = []
    for r in completed:
        if r.started_at and r.completed_at:
            durations.append((r.completed_at - r.started_at).total_seconds())
    keys = Counter((r.agent_key or r.mode or '?') for r in all_week)
    agents = []
    try:
        from app.models import AgentDefinition
        agents = AgentDefinition.query.order_by(AgentDefinition.name.asc()).limit(100).all()
    except Exception:
        agents = []
    return {
        'runs_7d': len(all_week),
        'success_rate': round(100.0 * len(completed) / (len(all_week) or 1), 1),
        'failures': len(failed),
        'avg_seconds': round(sum(durations) / len(durations), 2) if durations else 0,
        'top_agents': keys.most_common(10),
        'recent': runs[:40],
        'catalog': agents,
    }


def knowledge_dashboard() -> Dict[str, Any]:
    from app.models import (
        KnowledgeDocument, KnowledgeCollection, KnowledgeChunk,
        KnowledgeEmbedding, KnowledgeSearchLog, CollectionDocument,
    )
    week_ago = datetime.utcnow() - timedelta(days=7)
    docs = KnowledgeDocument.query.order_by(KnowledgeDocument.id.desc()).limit(40).all()
    collections = KnowledgeCollection.query.order_by(KnowledgeCollection.id.desc()).limit(40).all()
    top_collections = []
    for c in collections[:15]:
        try:
            n = CollectionDocument.query.filter_by(collection_id=c.id).count()
        except Exception:
            n = 0
        top_collections.append({'name': c.name, 'docs': n, 'id': c.id})
    top_collections.sort(key=lambda x: x['docs'], reverse=True)
    return {
        'documents': _safe_count(KnowledgeDocument),
        'collections': _safe_count(KnowledgeCollection),
        'chunks': _safe_count(KnowledgeChunk),
        'embeddings': _safe_count(KnowledgeEmbedding),
        'searches_7d': KnowledgeSearchLog.query.filter(KnowledgeSearchLog.created_at >= week_ago).count(),
        'recent_docs': docs,
        'top_collections': top_collections[:10],
        'vector_provider': current_app.config.get('KNOWLEDGE_VECTOR_PROVIDER'),
    }


def tools_dashboard() -> Dict[str, Any]:
    from app.models import ToolDefinition, ToolRun, ToolMarketplaceItem, ToolConnection

    week_ago = datetime.utcnow() - timedelta(days=7)
    tools = ToolDefinition.query.order_by(ToolDefinition.name.asc()).all()
    runs = ToolRun.query.filter(ToolRun.created_at >= week_ago).all() if _model_ok(ToolRun) else []
    failed = sum(1 for r in runs if (getattr(r, 'status', '') or '') == 'failed')
    marketplace = []
    try:
        marketplace = ToolMarketplaceItem.query.limit(40).all()
    except Exception:
        marketplace = []
    oauth = []
    try:
        oauth = ToolConnection.query.order_by(ToolConnection.id.desc()).limit(40).all()
    except Exception:
        oauth = []
    return {
        'installed': len([t for t in tools if t.is_installed]),
        'enabled': len([t for t in tools if t.is_enabled]),
        'executions_7d': len(runs),
        'failures_7d': failed,
        'tools': tools,
        'marketplace': marketplace,
        'oauth': oauth,
        'recent_runs': ToolRun.query.order_by(ToolRun.created_at.desc()).limit(30).all() if _model_ok(ToolRun) else [],
    }


def storage_dashboard() -> Dict[str, Any]:
    from app.models import Asset, Organization

    provider = current_app.config.get('STORAGE_PROVIDER', 'local')
    total = 0
    try:
        total = int(db.session.query(func.coalesce(func.sum(Asset.file_size), 0)).scalar() or 0)
    except Exception:
        total = 0
    by_org = []
    try:
        rows = (
            db.session.query(Asset.organization_id, func.sum(Asset.file_size), func.count(Asset.id))
            .group_by(Asset.organization_id)
            .order_by(func.sum(Asset.file_size).desc())
            .limit(15)
            .all()
        )
        org_names = {o.id: o.name for o in Organization.query.all()}
        for oid, size, count in rows:
            by_org.append({
                'organization_id': oid,
                'name': org_names.get(oid, f'Org {oid}'),
                'bytes': int(size or 0),
                'human': _human_bytes(size or 0),
                'files': int(count or 0),
            })
    except Exception:
        by_org = []
    recent = Asset.query.order_by(Asset.created_at.desc()).limit(30).all() if _model_ok(Asset) else []
    return {
        'provider': provider,
        'providers': ['s3', 'gcs', 'azure', 'local'],
        'total_bytes': total,
        'total_human': _human_bytes(total),
        'by_org': by_org,
        'recent': recent,
        'health': platform_health_snapshot()['checks'].get('storage', {}),
    }


def infra_dashboard() -> Dict[str, Any]:
    from app.models import BackgroundJob

    jobs = BackgroundJob.query.order_by(BackgroundJob.created_at.desc()).limit(50).all()
    by_status = Counter(j.status for j in BackgroundJob.query.with_entities(BackgroundJob.status).all())
    health = platform_health_snapshot()
    return {
        'health': health,
        'jobs': jobs,
        'by_status': dict(by_status),
        'redis_url_set': bool(current_app.config.get('REDIS_URL')),
        'celery_broker': current_app.config.get('CELERY_BROKER_URL', '')[:48] + '…',
        'celery_eager': health['celery_eager'],
    }


def audit_logs_page(q: str = '', page: int = 1, per_page: int = 50) -> Dict[str, Any]:
    from app.models import AuditLog, AnalyticsLog, AIRequestLog, AgentLog, ToolLog

    audit = []
    try:
        query = AuditLog.query.order_by(AuditLog.created_at.desc())
        if q:
            like = f'%{q}%'
            query = query.filter(
                AuditLog.action_type.like(like) | AuditLog.entity_type.like(like)
            )
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        audit = pagination.items
    except Exception:
        pagination = None
        audit = []

    analytics = AnalyticsLog.query.order_by(AnalyticsLog.created_at.desc()).limit(40).all()
    ai_events = AIRequestLog.query.order_by(AIRequestLog.created_at.desc()).limit(40).all()
    agent_events = []
    tool_events = []
    try:
        agent_events = AgentLog.query.order_by(AgentLog.created_at.desc()).limit(40).all()
    except Exception:
        pass
    try:
        tool_events = ToolLog.query.order_by(ToolLog.created_at.desc()).limit(40).all()
    except Exception:
        pass

    return {
        'audit': audit,
        'pagination': pagination,
        'analytics': analytics,
        'ai_events': ai_events,
        'agent_events': agent_events,
        'tool_events': tool_events,
        'q': q,
    }


def billing_dashboard() -> Dict[str, Any]:
    from app.models import Plan, Subscription, Invoice, Payment, Organization

    mrr, arr, paid, trial, cancelled = subscription_revenue()
    plans = Plan.query.order_by(Plan.price_monthly.asc()).all()
    subs = (
        db.session.query(Subscription, Plan, Organization)
        .join(Plan, Subscription.plan_id == Plan.id)
        .join(Organization, Subscription.organization_id == Organization.id)
        .order_by(Subscription.id.desc())
        .limit(100)
        .all()
    ) if _model_ok(Subscription) else []
    invoices = Invoice.query.order_by(Invoice.invoice_date.desc()).limit(50).all() if _model_ok(Invoice) else []
    payments = Payment.query.order_by(Payment.payment_date.desc()).limit(50).all() if _model_ok(Payment) else []

    # Users per plan from org tiers
    tier_counts = Counter((o.plan_tier or 'free').lower() for o in Organization.query.all())

    return {
        'mrr': mrr,
        'arr': arr,
        'paid': paid,
        'trial': trial,
        'cancelled': cancelled,
        'plans': plans,
        'subs': subs,
        'invoices': invoices,
        'payments': payments,
        'tier_counts': dict(tier_counts),
        'growth_label': f'{paid} paid · {trial} trial · {cancelled} cancelled',
    }


def _human_bytes(n) -> str:
    try:
        n = float(n or 0)
    except Exception:
        return '0 B'
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024.0
        i += 1
    return f'{n:.1f} {units[i]}'


def _model_ok(model) -> bool:
    try:
        return model is not None and hasattr(model, 'query')
    except Exception:
        return False
