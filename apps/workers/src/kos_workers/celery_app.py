"""Configuración de Celery: broker/backend en Redis y colas (doc 10 §3)."""

from __future__ import annotations

import contextlib
import uuid

from celery import Celery
from celery.signals import task_postrun, task_prerun, worker_process_init
from opentelemetry.trace import Span
from prometheus_client import start_http_server

from kos_core.config import get_settings
from kos_core.observability import (
    METRICS_REGISTRY,
    bind_trace_id,
    configure_logging,
    configure_tracing,
    get_tracer,
)

_tracer = get_tracer("kos-workers")
_spans: dict[str, Span] = {}


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
            "kos_workers.tasks.graph_sync",
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


@worker_process_init.connect
def _init_observability(**_kwargs: object) -> None:
    settings = get_settings()
    configure_logging(level=settings.kos_log_level)
    configure_tracing("kos-workers")
    # Celery no tiene servidor HTTP propio: Prometheus scrapea este puerto
    # directo del proceso worker (doc 09 §6). Con pool prefork y concurrency>1,
    # cada proceso hijo dispara este signal; solo el primero gana el puerto.
    with contextlib.suppress(OSError):  # otro proceso hijo del mismo worker ya lo expone
        start_http_server(settings.kos_worker_metrics_port, registry=METRICS_REGISTRY)


@task_prerun.connect
def _start_task_span(task_id: str, task: object, **_kwargs: object) -> None:
    trace_id = str(uuid.uuid4())
    bind_trace_id(trace_id)
    span = _tracer.start_span(getattr(task, "name", "kos.task"))
    span.set_attribute("kos.trace_id", trace_id)
    span.set_attribute("kos.task_id", task_id)
    _spans[task_id] = span


@task_postrun.connect
def _end_task_span(task_id: str, **_kwargs: object) -> None:
    span = _spans.pop(task_id, None)
    if span is not None:
        span.end()
    bind_trace_id(None)
