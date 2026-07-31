"""Background jobs — wrap existing services (no architecture rewrite)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app.infra.celery_app import celery
from app.infra.metrics import incr

logger = logging.getLogger(__name__)


def _update_job(job_id, **fields):
    if not job_id:
        return
    from app import db
    from app.models import BackgroundJob
    job = BackgroundJob.query.get(job_id)
    if not job:
        return
    for k, v in fields.items():
        setattr(job, k, v)
    db.session.commit()


@celery.task(bind=True, name='app.infra.tasks.index_document', autoretry_for=(Exception,), retry_backoff=True)
def index_document(self, document_id: int, job_id: int = None):
    """Re-index / embed a knowledge document asynchronously."""
    from app.models import KnowledgeDocument
    from app.services.knowledge.pipeline import IngestPipeline
    incr('jobs.embeddings')
    _update_job(job_id, status='running', started_at=datetime.utcnow(),
                celery_task_id=getattr(self.request, 'id', None), progress=10)
    try:
        document = KnowledgeDocument.query.get(document_id)
        if not document:
            raise ValueError(f'document {document_id} not found')
        IngestPipeline().reindex_document(document)
        _update_job(job_id, status='completed', progress=100, completed_at=datetime.utcnow())
        return {'document_id': document_id, 'status': 'completed'}
    except Exception as exc:
        _update_job(job_id, status='failed', error_message=str(exc)[:500],
                    completed_at=datetime.utcnow())
        raise


@celery.task(bind=True, name='app.infra.tasks.run_agent_job', autoretry_for=(Exception,), retry_backoff=True)
def run_agent_job(self, user_id: int, goal: str, job_id: int = None, **kwargs):
    from app.services.agents.manager import AgentManager
    incr('jobs.enqueued')
    incr('ai.requests')
    _update_job(job_id, status='running', started_at=datetime.utcnow(), celery_task_id=self.request.id)
    try:
        run = AgentManager().run(user_id=user_id, goal=goal, **kwargs)
        _update_job(job_id, status='completed', progress=100, completed_at=datetime.utcnow(),
                    result_json=__import__('json').dumps({'run_id': run.id, 'status': run.status}))
        return {'run_id': run.id, 'status': run.status}
    except Exception as exc:
        _update_job(job_id, status='failed', error_message=str(exc)[:500],
                    completed_at=datetime.utcnow())
        raise


@celery.task(bind=True, name='app.infra.tasks.run_tool_job', autoretry_for=(Exception,), retry_backoff=True)
def run_tool_job(self, tool_key: str, arguments: dict, user_id: int, job_id: int = None, **kwargs):
    from app.services.tools.service import ToolPlatformService
    incr('jobs.enqueued')
    incr('tool.runs')
    _update_job(job_id, status='running', started_at=datetime.utcnow(), celery_task_id=self.request.id)
    try:
        result = ToolPlatformService().run_tool(
            tool_key=tool_key, arguments=arguments or {}, user_id=user_id, **kwargs,
        )
        _update_job(job_id, status='completed' if result.get('success') else 'failed',
                    progress=100, completed_at=datetime.utcnow(),
                    result_json=__import__('json').dumps(result)[:8000])
        return result
    except Exception as exc:
        _update_job(job_id, status='failed', error_message=str(exc)[:500],
                    completed_at=datetime.utcnow())
        raise


@celery.task(bind=True, name='app.infra.tasks.send_email', autoretry_for=(Exception,), retry_backoff=True)
def send_email(self, to, subject, text_body, html_body=None, job_id=None):
    """Deliver transactional email asynchronously (password reset, etc.)."""
    from app.services.mail import send_email_sync
    incr('jobs.email')
    if job_id:
        _update_job(job_id, status='running', started_at=datetime.utcnow(),
                    celery_task_id=getattr(self.request, 'id', None))
    ok = send_email_sync(
        to=to,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )
    if job_id:
        _update_job(
            job_id,
            status='completed' if ok else 'failed',
            progress=100,
            completed_at=datetime.utcnow(),
            error_message=None if ok else 'SMTP send failed',
        )
    if not ok:
        logger.info('Email task finished without SMTP delivery (mail may be unconfigured)')
    return {'to': to, 'subject': subject, 'sent': ok}


@celery.task(bind=True, name='app.infra.tasks.retention_cleanup')
def retention_cleanup(self, days: int = 90, job_id: int = None):
    """Archive/delete old logs beyond retention window."""
    from app import db
    from app.models import AIRequestLog, ToolLog, AgentLog, KnowledgeSearchLog
    cutoff = datetime.utcnow() - timedelta(days=days)
    _update_job(job_id, status='running', started_at=datetime.utcnow())
    deleted = 0
    for model in (ToolLog, AgentLog, KnowledgeSearchLog):
        try:
            q = model.query.filter(model.created_at < cutoff)
            count = q.count()
            q.delete(synchronize_session=False)
            deleted += count
        except Exception as exc:
            logger.warning('Retention skip %s: %s', model.__name__, type(exc).__name__)
    try:
        q = AIRequestLog.query.filter(AIRequestLog.created_at < cutoff)
        deleted += q.count()
        q.delete(synchronize_session=False)
    except Exception:
        pass
    db.session.commit()
    _update_job(job_id, status='completed', progress=100, completed_at=datetime.utcnow(),
                result_json=__import__('json').dumps({'deleted': deleted}))
    incr('jobs.retention')
    return {'deleted': deleted}


def enqueue_job(task_name: str, *, user_id=None, organization_id=None, payload=None, **task_kwargs):
    """Create BackgroundJob row and dispatch Celery task. Returns job dict."""
    import json
    from app import db
    from app.models import BackgroundJob
    from app.infra import tasks as task_module

    job = BackgroundJob(
        task_name=task_name,
        user_id=user_id,
        organization_id=organization_id,
        status='queued',
        payload_json=json.dumps(payload or {}),
    )
    db.session.add(job)
    db.session.commit()

    task_fn = getattr(task_module, task_name, None)
    if task_fn is None:
        job.status = 'failed'
        job.error_message = f'Unknown task {task_name}'
        db.session.commit()
        return job.to_dict()

    async_result = task_fn.delay(job_id=job.id, **task_kwargs)
    job.celery_task_id = async_result.id
    db.session.commit()
    incr('jobs.enqueued')
    return job.to_dict()
