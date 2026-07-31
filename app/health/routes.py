"""Enterprise health, readiness, liveness, and metrics endpoints."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify

health_bp = Blueprint('health', __name__)


def _check_database():
    try:
        from app import db
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        return True, 'ok'
    except Exception as exc:
        return False, type(exc).__name__


def _check_redis():
    try:
        from app.infra.redis_client import get_redis
        client = get_redis()
        client.ping()
        return True, 'ok'
    except Exception as exc:
        return False, type(exc).__name__


def _check_vector():
    try:
        from app.services.knowledge.vector_store import get_vector_store
        store = get_vector_store()
        ok = store.healthcheck() if hasattr(store, 'healthcheck') else True
        return ok, store.provider_id
    except Exception as exc:
        return False, type(exc).__name__


def _check_storage():
    try:
        from app.infra.storage import get_storage
        storage = get_storage()
        return storage.healthcheck(), storage.provider_id
    except Exception as exc:
        return False, type(exc).__name__


def _check_ai_providers():
    try:
        from app.services.ai.registry import ProviderRegistry
        reg = ProviderRegistry.instance()
        enabled = [p for p in reg.list_providers() if p.get('enabled')]
        return len(enabled) > 0, f'{len(enabled)}_enabled'
    except Exception as exc:
        return False, type(exc).__name__


def _check_workers():
    """Best-effort Celery inspect; eager mode counts as healthy in tests."""
    try:
        if current_app.config.get('CELERY_TASK_ALWAYS_EAGER') or current_app.testing:
            return True, 'eager'
        from app.infra.celery_app import celery
        inspector = celery.control.inspect(timeout=1.0)
        ping = inspector.ping() if inspector else None
        if ping:
            return True, f'{len(ping)}_workers'
        return False, 'no_workers'
    except Exception as exc:
        return False, type(exc).__name__


@health_bp.route('/health')
def health():
    """Aggregate health — 200 if core deps up, 503 otherwise."""
    checks = {
        'database': _check_database(),
        'redis': _check_redis(),
        'vector': _check_vector(),
        'storage': _check_storage(),
        'ai_providers': _check_ai_providers(),
        'workers': _check_workers(),
    }
    body = {k: {'ok': v[0], 'detail': v[1]} for k, v in checks.items()}
    # Core: database required; others soft in non-prod
    core_ok = checks['database'][0]
    if current_app.config.get('USE_ALEMBIC_ONLY'):
        # Production: redis + storage + vector must also be healthy
        core_ok = all(checks[k][0] for k in ('database', 'redis', 'storage', 'vector'))
    status = 200 if core_ok else 503
    return jsonify({'status': 'ok' if core_ok else 'degraded', 'checks': body}), status


@health_bp.route('/ready')
def ready():
    """Readiness — can accept traffic (DB + redis)."""
    db_ok, db_detail = _check_database()
    redis_ok, redis_detail = _check_redis()
    ok = db_ok and redis_ok
    return jsonify({
        'status': 'ready' if ok else 'not_ready',
        'database': db_detail,
        'redis': redis_detail,
    }), 200 if ok else 503


@health_bp.route('/live')
def live():
    """Liveness — process is up."""
    return jsonify({'status': 'alive'}), 200


@health_bp.route('/metrics')
def metrics():
    from app.infra.metrics import snapshot
    return jsonify({'success': True, 'metrics': snapshot()})
