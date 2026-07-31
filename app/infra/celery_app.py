"""Celery application factory — Redis broker, eager mode for tests."""
from __future__ import annotations

import os

from celery import Celery

celery = Celery('oplyra')


def init_celery(app=None):
    broker = os.environ.get('REDIS_URL') or os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0'
    backend = os.environ.get('CELERY_RESULT_BACKEND') or broker
    eager = False
    if app is not None:
        broker = app.config.get('CELERY_BROKER_URL') or broker
        backend = app.config.get('CELERY_RESULT_BACKEND') or backend
        eager = bool(app.config.get('CELERY_TASK_ALWAYS_EAGER') or app.testing)

    celery.conf.update(
        broker_url=broker,
        result_backend=backend,
        task_always_eager=eager,
        task_eager_propagates=True,
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_default_queue='oplyra.default',
        task_routes={
            'app.infra.tasks.index_document': {'queue': 'oplyra.knowledge'},
            'app.infra.tasks.run_agent_job': {'queue': 'oplyra.agents'},
            'app.infra.tasks.run_tool_job': {'queue': 'oplyra.tools'},
            'app.infra.tasks.send_email': {'queue': 'oplyra.mail'},
            'app.infra.tasks.retention_cleanup': {'queue': 'oplyra.maintenance'},
        },
        task_annotations={
            '*': {'max_retries': 3, 'default_retry_delay': 30},
        },
        # Dead-letter style: failed tasks go to dedicated queue after retries
        task_queues=None,
    )

    if app is not None:
        class ContextTask(celery.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)

        celery.Task = ContextTask

    # Import task modules so workers register them
    import app.infra.tasks  # noqa: F401
    return celery
