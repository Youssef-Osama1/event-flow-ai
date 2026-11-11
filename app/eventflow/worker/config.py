from celery import Celery

from eventflow.config import get_settings

settings = get_settings()

celery_app = Celery(
    "eventflow",
    broker=settings.redis_url,
    include=["eventflow.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_ignore_result=True,
    broker_connection_retry_on_startup=True,
    timezone="UTC",
)
