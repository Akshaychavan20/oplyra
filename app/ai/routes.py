"""
/api/ai/* — Multi-provider AI Gateway HTTP surface.

Keys never leave the server. Frontend only sends provider preference / prompt.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from app import db
from app.models import AIRequestLog, UserAIPreference, TokenBillingLog
from app.services.ai_gateway import AIGateway
from app.services.ai.types import AIRequest, ProviderId
from app.infra.rate_limit_flask import rate_limited

ai_bp = Blueprint('ai', __name__)


def _gateway() -> AIGateway:
    return AIGateway()


def _get_or_create_prefs(user_id: int) -> UserAIPreference:
    prefs = UserAIPreference.query.filter_by(user_id=user_id).first()
    if not prefs:
        prefs = UserAIPreference(user_id=user_id)
        db.session.add(prefs)
        db.session.commit()
    return prefs


@ai_bp.route('/providers', methods=['GET'])
@login_required
def list_providers():
    return jsonify({
        'success': True,
        'providers': _gateway().list_providers(),
        'options': _gateway().ui_provider_options(),
    })


@ai_bp.route('/models', methods=['GET'])
@login_required
def list_models():
    return jsonify({'success': True, 'models': _gateway().list_models()})


@ai_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def ai_settings():
    prefs = _get_or_create_prefs(current_user.id)
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'settings': {
                'preferred_provider': prefs.preferred_provider,
                'preferred_model': prefs.preferred_model,
                'creativity': prefs.creativity,
                'response_length': prefs.response_length,
                'language': prefs.language,
                'streaming_enabled': prefs.streaming_enabled,
            },
            'options': _gateway().ui_provider_options(),
        })

    data = request.get_json() or {}
    if 'preferred_provider' in data:
        prefs.preferred_provider = str(data['preferred_provider'] or 'auto')[:40]
    if 'preferred_model' in data:
        prefs.preferred_model = data['preferred_model'] or None
    if 'creativity' in data:
        try:
            prefs.creativity = max(0.0, min(1.5, float(data['creativity'])))
        except (TypeError, ValueError):
            pass
    if 'response_length' in data and data['response_length'] in ('short', 'medium', 'long'):
        prefs.response_length = data['response_length']
    if 'language' in data:
        prefs.language = str(data['language'] or 'en')[:20]
    if 'streaming_enabled' in data:
        prefs.streaming_enabled = bool(data['streaming_enabled'])
    db.session.commit()
    return jsonify({'success': True, 'message': 'AI preferences saved.'})


@ai_bp.route('/generate', methods=['POST'])
@ai_bp.route('/chat', methods=['POST'])
@login_required
@rate_limited('ai_generate')
def ai_generate():
    data = request.get_json() or {}
    prompt = (data.get('prompt') or data.get('message') or '').strip()
    if not prompt:
        return jsonify({'success': False, 'error': 'Prompt is required.'}), 400

    prefs = _get_or_create_prefs(current_user.id)
    provider = data.get('provider') or prefs.preferred_provider or 'auto'
    model = data.get('model') or prefs.preferred_model
    task_type = data.get('task_type')
    system = data.get('system') or data.get('system_instruction')

    temperature = data.get('temperature')
    if temperature is None:
        temperature = prefs.creativity

    max_tokens = data.get('max_tokens')
    if max_tokens is None and prefs.response_length:
        max_tokens = {'short': 512, 'medium': 2048, 'long': 4096}.get(prefs.response_length)

    try:
        text, tokens = _gateway().generate(
            prompt=prompt,
            system_instruction=system,
            model=model,
            provider=provider,
            task_type=task_type,
            temperature=temperature,
            max_tokens=max_tokens,
            user_id=current_user.id,
            skip_cache=bool(data.get('skip_cache')),
            campaign_id=data.get('campaign_id'),
        )
        return jsonify({
            'success': True,
            'text': text,
            'tokens': tokens,
            'provider': provider,
            'model': model or 'auto',
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 429
    except Exception:
        return jsonify({
            'success': False,
            'error': 'AI generation is temporarily unavailable. Please try again.',
        }), 503


@ai_bp.route('/router', methods=['POST'])
@login_required
def ai_router_preview():
    data = request.get_json() or {}
    prompt = (data.get('prompt') or '').strip()
    task_type = data.get('task_type')
    gateway = _gateway()
    req = AIRequest(
        prompt=prompt or 'general marketing assistance',
        task_type=gateway._coerce_task(task_type),
        provider=ProviderId.AUTO,
    )
    pid, model = gateway.router.select(req)
    classified = gateway.router.classify(prompt, req.task_type)
    return jsonify({
        'success': True,
        'task_type': classified.value,
        'provider': pid.value,
        'model': model,
    })


@ai_bp.route('/history', methods=['GET'])
@login_required
def ai_history():
    limit = min(int(request.args.get('limit', 25)), 100)
    rows = (
        AIRequestLog.query
        .filter_by(user_id=current_user.id)
        .order_by(AIRequestLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return jsonify({
        'success': True,
        'history': [{
            'id': r.id,
            'provider': r.provider,
            'model': r.model_used,
            'tokens': r.total_tokens,
            'cost': float(r.calculated_cost or 0),
            'latency_ms': r.latency_ms,
            'status': r.status,
            'created_at': r.created_at.isoformat() + 'Z' if r.created_at else None,
        } for r in rows],
    })


@ai_bp.route('/usage', methods=['GET'])
@login_required
def ai_usage():
    days = min(int(request.args.get('days', 30)), 90)
    since = datetime.utcnow() - timedelta(days=days)

    logs = AIRequestLog.query.filter(
        AIRequestLog.user_id == current_user.id,
        AIRequestLog.created_at >= since,
    ).all()

    by_provider = {}
    total_tokens = 0
    total_cost = 0.0
    total_latency = 0
    errors = 0
    for row in logs:
        key = row.provider or 'unknown'
        bucket = by_provider.setdefault(key, {'requests': 0, 'tokens': 0, 'cost': 0.0})
        bucket['requests'] += 1
        bucket['tokens'] += row.total_tokens or 0
        bucket['cost'] += float(row.calculated_cost or 0)
        total_tokens += row.total_tokens or 0
        total_cost += float(row.calculated_cost or 0)
        total_latency += row.latency_ms or 0
        if row.status and row.status != 'success':
            errors += 1

    if not logs:
        legacy = TokenBillingLog.query.filter(
            TokenBillingLog.user_id == current_user.id,
            TokenBillingLog.created_at >= since,
        ).all()
        for row in legacy:
            total_tokens += (row.input_tokens or 0) + (row.output_tokens or 0)
            total_cost += float(row.calculated_cost or 0)

    count = max(len(logs), 1)
    return jsonify({
        'success': True,
        'period_days': days,
        'summary': {
            'requests': len(logs),
            'tokens': total_tokens,
            'cost': round(total_cost, 6),
            'avg_latency_ms': int(total_latency / count) if logs else 0,
            'error_rate': round(errors / count, 4) if logs else 0,
            'by_provider': by_provider,
        },
    })
