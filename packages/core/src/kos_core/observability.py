"""Logs estructurados + trazas OTel en API, workers y llamadas a LLM (doc 09 §6).

Dos primitivas, sin instrumentación automática de terceros (mantiene el core
independiente de frameworks, ADR-0001 en espíritu): un logger stdlib que emite
JSON con `trace_id` inyectado desde un `ContextVar`, y un `Tracer` de
OpenTelemetry con exportador de consola por defecto (no hay collector en el
compose todavía; cambiar de exportador es un solo punto de extensión aquí).
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
)
from opentelemetry.trace import Tracer

_trace_id_var: ContextVar[str | None] = ContextVar("kos_trace_id", default=None)
_tracer_provider_configured = False


def bind_trace_id(trace_id: str | None) -> None:
    """Asocia el trace_id de la petición/task actual a los logs subsecuentes."""
    _trace_id_var.set(trace_id)


def current_trace_id() -> str | None:
    return _trace_id_var.get()


class _JsonFormatter(logging.Formatter):
    """Una línea JSON por registro: nivel, logger, mensaje, trace_id, excepción."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": current_trace_id(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(*, level: str = "INFO") -> None:
    """Reemplaza los handlers del logger raíz por uno solo que emite JSON a stdout."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root.handlers = [handler]


def configure_tracing(service_name: str, *, exporter: SpanExporter | None = None) -> None:
    """Registra el TracerProvider del servicio. Idempotente (seguro llamarlo más de una vez)."""
    global _tracer_provider_configured
    if _tracer_provider_configured:
        return
    # Exportador síncrono (sin hilo de fondo): no hay collector OTLP en el compose
    # todavía, y un BatchSpanProcessor puede intentar exportar tras cerrar stdout
    # al final de los tests. Cambiar a BatchSpanProcessor + OTLP es el punto de
    # extensión cuando haya un collector real (doc 09 §6).
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    provider.add_span_processor(SimpleSpanProcessor(exporter or ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    _tracer_provider_configured = True


def get_tracer(name: str) -> Tracer:
    return trace.get_tracer(name)


@contextmanager
def traced_span(tracer: Tracer, name: str, **attributes: Any) -> Iterator[trace.Span]:
    """Span con trace_id de contexto como atributo, para correlacionar con los logs."""
    with tracer.start_as_current_span(name) as span:
        trace_id = current_trace_id()
        if trace_id:
            span.set_attribute("kos.trace_id", trace_id)
        for key, value in attributes.items():
            span.set_attribute(key, value)
        yield span
