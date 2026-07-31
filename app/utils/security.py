"""Shared security helpers — redirects, secrets validation, HTML escaping."""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse


# Known-weak / placeholder keys that must never be used in production.
WEAK_SECRET_KEYS = frozenset({
    '',
    'default-dev-secret-key',
    'generate-a-secure-secret-key-here',
    'changeme',
    'secret',
    'SECRET_KEY',
})


def is_weak_secret_key(secret: Optional[str]) -> bool:
    if secret is None:
        return True
    value = str(secret).strip()
    if not value or value in WEAK_SECRET_KEYS:
        return True
    if len(value) < 32:
        return True
    return False


def safe_redirect_target(target: Optional[str], fallback: str = '/') -> str:
    """
    Allow only same-origin relative paths (open-redirect safe).
    Rejects protocol-relative (//evil), absolute URLs, and backslash tricks.
    """
    if not target:
        return fallback
    candidate = str(target).strip()
    if not candidate:
        return fallback
    # Block scheme / host redirects
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        return fallback
    if not candidate.startswith('/') or candidate.startswith('//'):
        return fallback
    if '\\' in candidate or '\n' in candidate or '\r' in candidate:
        return fallback
    return candidate


_SCRIPT_RE = re.compile(
    r'<\s*(script|iframe|object|embed|link|meta|base)[^>]*>.*?<\s*/\s*\1\s*>',
    re.IGNORECASE | re.DOTALL,
)
_SCRIPT_OPEN_RE = re.compile(
    r'<\s*(script|iframe|object|embed|link|meta|base)[^>]*>',
    re.IGNORECASE,
)
_EVENT_ATTR_RE = re.compile(
    r'\s+on[a-z]+\s*=\s*(["\']).*?\1',
    re.IGNORECASE | re.DOTALL,
)
_EVENT_ATTR_UNQUOTED_RE = re.compile(
    r'\s+on[a-z]+\s*=\s*[^\s>]+',
    re.IGNORECASE,
)
_JS_URL_RE = re.compile(
    r'\b(href|src)\s*=\s*(["\'])\s*javascript:[^"\']*\2',
    re.IGNORECASE,
)


def sanitize_html(html: str) -> str:
    """Best-effort HTML sanitizer for markdown/rendered content (no new deps)."""
    if not html:
        return ''
    cleaned = _SCRIPT_RE.sub('', html)
    cleaned = _SCRIPT_OPEN_RE.sub('', cleaned)
    cleaned = _EVENT_ATTR_RE.sub('', cleaned)
    cleaned = _EVENT_ATTR_UNQUOTED_RE.sub('', cleaned)
    cleaned = _JS_URL_RE.sub('', cleaned)
    return cleaned
