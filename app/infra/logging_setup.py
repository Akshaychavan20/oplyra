"""Structured JSON logging with request / correlation / tenant context."""
from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_request_id: ContextVar[str] = ContextVar('request_id', default='')
_correlation_id: ContextVar[str] = ContextVar('correlation_id', default='')
_workspace_id: ContextVar[str] = ContextVar('workspace_id', default='')
_user_id: ContextVar[str] = ContextVar('user_id', default='')
_agent_id: ContextVar[str] = ContextVar('agent_id', default='')
_tool_id: ContextVar[str] = ContextVar('tool_id', default='')


def get_request_id() -> str:
    return _request_id.get() or ''


def set_log_context(
    *,
    request_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    workspace_id: Optional[Any] = None,
    user_id: Optional[Any] = None,
    agent_id: Optional[str] = None,
    tool_id: Optional[str] = None,
):
    if request_id is not None:
        _request_id.set(str(request_id))
    if correlation_id is not None:
        _correlation_id.set(str(correlation_id))
    if workspace_id is not None:
        _workspace_id.set(str(workspace_id) if workspace_id != '' else '')
    if user_id is not None:
        _user_id.set(str(user_id) if user_id != '' else '')
    if agent_id is not None:
        _agent_id.set(str(agent_id))
    if tool_id is not None:
        _tool_id.set(str(tool_id))


def clear_log_context():
    _request_id.set('')
    _correlation_id.set('')
    _workspace_id.set('')
    _user_id.set('')
    _agent_id.set('')
    _tool_id.set('')


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            'ts': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'request_id': _request_id.get() or getattr(record, 'request_id', ''),
            'correlation_id': _correlation_id.get() or getattr(record, 'correlation_id', ''),
            'workspace_id': _workspace_id.get() or getattr(record, 'workspace_id', ''),
            'user_id': _user_id.get() or getattr(record, 'user_id', ''),
            'agent_id': _agent_id.get() or getattr(record, 'agent_id', ''),
            'tool_id': _tool_id.get() or getattr(record, 'tool_id', ''),
        }
        if hasattr(record, 'duration_ms'):
            payload['duration_ms'] = record.duration_ms
        if hasattr(record, 'error_code'):
            payload['error_code'] = record.error_code
        if record.exc_info:
            payload['exc_info'] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_structured_logging(app):
    """Attach JSON handler for production / when STRUCTURING_LOGGING enabled."""
    enabled = app.config.get('STRUCTURED_LOGGING', False) or (
        not app.debug and not app.testing
    )
    if not enabled:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    handler.setLevel(logging.INFO)

    root = logging.getLogger()
    # Avoid duplicate handlers on reload
    for h in list(root.handlers):
        if isinstance(h, logging.StreamHandler) and isinstance(getattr(h, 'formatter', None), JsonLogFormatter):
            return
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    app.logger.handlers = [handler]
    app.logger.setLevel(logging.INFO)
    app.logger.propagate = False


def init_request_logging(app):
    """Flask before/after hooks for request IDs and duration."""
    from flask import g, request

    @app.before_request
    def _bind_request_context():
        rid = request.headers.get('X-Request-ID') or uuid.uuid4().hex
        cid = request.headers.get('X-Correlation-ID') or rid
        g.request_id = rid
        g.request_started = time.time()
        set_log_context(request_id=rid, correlation_id=cid)
        try:
            from flask_login import current_user
            if current_user.is_authenticated:
                set_log_context(user_id=current_user.id)
                from app.utils.org import get_user_org_id
                org = get_user_org_id(current_user.id)
                if org:
                    set_log_context(workspace_id=org)
        except Exception:
            pass

    @app.after_request
    def _emit_request_log(response):
        try:
            started = getattr(g, 'request_started', None)
            duration = int((time.time() - started) * 1000) if started else None
            response.headers['X-Request-ID'] = getattr(g, 'request_id', '')
            if duration is not None and request.path.startswith('/api/'):
                app.logger.info(
                    'http_request',
                    extra={
                        'duration_ms': duration,
                        'error_code': str(response.status_code) if response.status_code >= 400 else '',
                    },
                )
                # metrics counter
                try:
                    from app.infra.metrics import incr
                    incr('http.requests')
                    if response.status_code >= 400:
                        incr('http.errors')
                except Exception:
                    pass
        finally:
            clear_log_context()
        return response
