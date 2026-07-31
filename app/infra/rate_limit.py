"""Production rate limiting — Redis token window with memory fallback."""
from __future__ import annotations

import time
from typing import Optional, Tuple

from app.infra.redis_client import get_redis


# Default quotas (requests per window_seconds)
DEFAULT_LIMITS = {
    'auth': (20, 60),           # 20 / minute
    'ai_generate': (60, 60),    # 60 / minute
    'knowledge_search': (120, 60),
    'upload': (30, 60),
    'tool_run': (90, 60),
    'admin': (30, 60),
    'admin_auth': (10, 60),  # Internal Admin login — stricter
    'api': (300, 60),
    # Password reset — 5 requests / hour (email identity and IP identity separately)
    'password_reset_email': (5, 3600),
    'password_reset_ip': (5, 3600),
    'password_reset_attempt': (20, 3600),  # reset form submissions / IP
}


class RateLimitExceeded(Exception):
    def __init__(self, scope: str, retry_after: int = 60):
        self.scope = scope
        self.retry_after = retry_after
        super().__init__(f'Rate limit exceeded for {scope}')


def check_rate_limit(
    scope: str,
    *,
    identity: str,
    organization_id: Optional[int] = None,
    limit: Optional[int] = None,
    window_seconds: Optional[int] = None,
) -> Tuple[bool, int, int]:
    """
    Returns (allowed, remaining, retry_after_seconds).
    Workspace-aware key: oplyra:rl:{scope}:{org}:{identity}
    """
    default_limit, default_window = DEFAULT_LIMITS.get(scope, (100, 60))
    max_requests = limit if limit is not None else default_limit
    window = window_seconds if window_seconds is not None else default_window

    # Org-specific overrides via config
    try:
        from flask import current_app
        overrides = current_app.config.get('RATE_LIMIT_OVERRIDES') or {}
        if scope in overrides:
            max_requests, window = overrides[scope]
        if organization_id and current_app.config.get('ORG_RATE_LIMIT_MULTIPLIER'):
            max_requests = int(max_requests * float(current_app.config['ORG_RATE_LIMIT_MULTIPLIER']))
    except RuntimeError:
        pass

    org_part = organization_id if organization_id is not None else 'global'
    key = f'oplyra:rl:{scope}:{org_part}:{identity}'
    client = get_redis()
    try:
        count = client.incr(key)
        if count == 1:
            client.expire(key, window)
        if count > max_requests:
            return False, 0, window
        return True, max(0, max_requests - count), 0
    except Exception:
        # Fail-open for availability (AI credits still enforced in gateway)
        return True, max_requests, 0


def enforce_rate_limit(scope: str, *, identity: str, organization_id: Optional[int] = None):
    allowed, remaining, retry_after = check_rate_limit(
        scope, identity=identity, organization_id=organization_id,
    )
    if not allowed:
        raise RateLimitExceeded(scope, retry_after=retry_after or 60)
    return remaining
