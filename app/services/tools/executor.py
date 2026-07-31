"""Tool Executor — validate, execute, retry, timeout, log."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime
from typing import Any, Dict, Optional

from app import db
from app.models import ToolDefinition, ToolLog, ToolRun
from app.services.tools.registry import ToolRegistry
from app.services.tools.types import ToolCallRequest, ToolCallResult


class ToolExecutor:
    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or ToolRegistry()

    def _log(self, run: ToolRun, event: str, message: str = '', level: str = 'info', meta: Optional[dict] = None):
        entry = ToolLog(run_id=run.id, level=level, event=event, message=message)
        entry.meta = meta or {}
        db.session.add(entry)
        db.session.commit()

    def execute(self, request: ToolCallRequest, *, context: Optional[Dict[str, Any]] = None) -> ToolCallResult:
        self.registry.ensure_seeded()
        tool_row = ToolDefinition.query.filter_by(key=request.tool_key).first()
        runtime = self.registry.get_runtime(request.tool_key)

        run = ToolRun(
            tool_key=request.tool_key,
            user_id=request.user_id,
            organization_id=request.organization_id,
            agent_key=request.agent_key,
            agent_run_id=request.agent_run_id,
            status='pending',
        )
        run.input_payload = request.arguments or {}
        db.session.add(run)
        db.session.commit()

        if not tool_row or not tool_row.is_installed:
            run.status = 'failed'
            run.error_message = 'Tool not installed'
            run.completed_at = datetime.utcnow()
            db.session.commit()
            self._log(run, 'failed', 'Tool not installed', level='error')
            return ToolCallResult(False, request.tool_key, error='Tool not installed', run_id=run.id)

        if not tool_row.is_enabled:
            run.status = 'denied'
            run.error_message = 'Tool is disabled'
            run.completed_at = datetime.utcnow()
            db.session.commit()
            self._log(run, 'denied', 'Tool disabled', level='warning')
            return ToolCallResult(False, request.tool_key, error='Tool is disabled', run_id=run.id)

        if not runtime:
            # Try MCP dispatch
            run.status = 'running'
            run.started_at = datetime.utcnow()
            db.session.commit()
            started = time.perf_counter()
            try:
                payload = self.registry.mcp.call_tool(
                    request.tool_key, request.arguments or {}, context=context,
                )
                duration = int((time.perf_counter() - started) * 1000)
                ok = bool(payload.get('success', True))
                run.status = 'completed' if ok else 'failed'
                run.output_payload = payload
                run.duration_ms = duration
                run.completed_at = datetime.utcnow()
                if not ok:
                    run.error_message = str(payload.get('error') or 'MCP call failed')[:500]
                db.session.commit()
                self._log(run, 'completed' if ok else 'failed', run.error_message or 'ok')
                return ToolCallResult(
                    ok, request.tool_key, data=payload.get('data', payload),
                    error=run.error_message, duration_ms=duration, run_id=run.id,
                    mock=bool(payload.get('mock', True)),
                )
            except Exception as exc:
                run.status = 'failed'
                run.error_message = str(exc)[:500]
                run.completed_at = datetime.utcnow()
                db.session.commit()
                return ToolCallResult(False, request.tool_key, error=str(exc), run_id=run.id)

        # Permission check (external module)
        from app.services.tools.permissions import can_execute_tool
        if request.user_id and not can_execute_tool(
            request.user_id, request.tool_key, organization_id=request.organization_id,
        ):
            run.status = 'denied'
            run.error_message = 'Permission denied'
            run.completed_at = datetime.utcnow()
            db.session.commit()
            self._log(run, 'denied', 'Permission denied', level='warning')
            return ToolCallResult(False, request.tool_key, error='Permission denied', run_id=run.id)

        err = runtime.validate(request.arguments or {})
        if err:
            run.status = 'failed'
            run.error_message = err
            run.completed_at = datetime.utcnow()
            db.session.commit()
            self._log(run, 'validation_failed', err, level='error')
            return ToolCallResult(False, request.tool_key, error=err, run_id=run.id)

        run.status = 'running'
        run.started_at = datetime.utcnow()
        db.session.commit()
        self._log(run, 'started', f'Executing {request.tool_key}')

        retries = 0
        last_error = None
        max_retries = max(0, int(request.max_retries))
        timeout = float(request.timeout_seconds or 30)

        ctx = dict(context or {})
        ctx.update({
            'user_id': request.user_id,
            'organization_id': request.organization_id,
            'agent_key': request.agent_key,
        })

        while retries <= max_retries:
            started = time.perf_counter()
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    fut = pool.submit(runtime.execute, request.arguments or {}, context=ctx)
                    payload = fut.result(timeout=timeout)
                duration = int((time.perf_counter() - started) * 1000)
                ok = True
                error = None
                data = payload
                mock = True
                if isinstance(payload, dict):
                    ok = bool(payload.get('success', True))
                    error = payload.get('error')
                    data = payload.get('data', payload)
                    mock = bool(payload.get('mock', True))
                if ok:
                    run.status = 'completed'
                    run.output_payload = payload if isinstance(payload, dict) else {'data': payload}
                    run.duration_ms = duration
                    run.retry_count = retries
                    run.completed_at = datetime.utcnow()
                    db.session.commit()
                    self._log(run, 'completed', f'OK in {duration}ms', meta={'retries': retries})
                    return ToolCallResult(
                        True, request.tool_key, data=data, duration_ms=duration,
                        retries=retries, run_id=run.id, mock=mock,
                    )
                last_error = error or 'Tool reported failure'
            except FuturesTimeout:
                last_error = f'Tool timed out after {timeout}s'
                run.status = 'timeout'
                self._log(run, 'timeout', last_error, level='error')
            except Exception as exc:
                last_error = str(exc)
                self._log(run, 'error', last_error, level='error')

            retries += 1
            if retries <= max_retries:
                self._log(run, 'retry', f'Retry {retries}', level='warning')
                run.retry_count = retries
                db.session.commit()

        run.status = run.status if run.status == 'timeout' else 'failed'
        run.error_message = (last_error or 'Unknown error')[:500]
        run.completed_at = datetime.utcnow()
        run.retry_count = max(0, retries - 1)
        db.session.commit()
        self._log(run, 'failed', run.error_message, level='error')
        return ToolCallResult(
            False, request.tool_key, error=run.error_message,
            retries=run.retry_count, run_id=run.id,
        )
