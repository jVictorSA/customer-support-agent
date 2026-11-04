from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "customer_support_agent",
    broker=settings.rabbitmq_url,
    include=["app.worker"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    task_time_limit=settings.celery_task_time_limit,
    task_default_queue="documents.ingest",
    task_routes={"documents.ingest": {"queue": "documents.ingest"}},
    timezone="UTC",
    enable_utc=True,
)
