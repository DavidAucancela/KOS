"""Configuración de Celery: broker/backend en Redis y colas (doc 10 §3)."""

from __future__ import annotations

from celery import Celery

from kos_core.config import get_settings


def create_celery() -> Celery:
    settings = get_settings()
    celery = Celery(
        "kos",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=[
            "kos_workers.tasks.ping",
            "kos_workers.tasks.ingest",
            "kos_workers.tasks.embed",
            "kos_workers.tasks.enrich",
        ],
    )
    celery.conf.update(
        task_default_queue="default",
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
    )
    return celery


app = create_celery()
