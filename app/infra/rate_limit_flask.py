"""Flask helpers for rate limiting JSON APIs."""
from __future__ import annotations

from functools import wraps

from flask import jsonify, request
from flask_login import current_user

from app.infra.rate_limit import RateLimitExceeded, enforce_rate_limit
from app.utils.org import get_user_org_id


def rate_limited(scope: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                if current_user.is_authenticated:
                    identity = f'user:{current_user.id}'
                    org_id = get_user_org_id(current_user.id)
                else:
                    identity = f'ip:{request.remote_addr or "unknown"}'
                    org_id = None
                remaining = enforce_rate_limit(scope, identity=identity, organization_id=org_id)
            except RateLimitExceeded as exc:
                resp = jsonify({
                    'success': False,
                    'error': str(exc),
                    'error_code': 'RATE_LIMITED',
                })
                resp.status_code = 429
                resp.headers['Retry-After'] = str(exc.retry_after)
                return resp
            result = fn(*args, **kwargs)
            return result
        return wrapper
    return decorator
