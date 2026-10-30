"""Celery app cho các job nền: ingest, OpenAlex sync, mining, fingerprint."""

from celery import Celery

from aprkb.core.config import settings

celery_app = Celery("aprkb", broker=settings.redis_url, backend=settings.redis_url)
celery_app.autodiscover_tasks(["aprkb.worker"])

app = celery_app
