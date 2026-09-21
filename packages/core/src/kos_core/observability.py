"""Logs, trazas y métricas de KOS (doc 09 §6): API, workers y llamadas a LLM.

Tres primitivas, sin instrumentación automática de terceros (mantiene el core
independiente de frameworks, ADR-0001 en espíritu): un logger stdlib que emite
JSON con `trace_id` inyectado desde un `ContextVar`, un `Tracer` de
OpenTelemetry con exportador de consola por defecto (no hay collector en el
compose todavía; cambiar de exportador es un solo punto de extensión aquí), y
un `CollectorRegistry` propio de `prometheus_client` (no el global: evita
registros duplicados si el módulo se reimporta en tests).
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Iterator, Mapping
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
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

_trace_id_var: ContextVar[str | None] = ContextVar("kos_trace_id", default=None)
_tracer_provider_configured = False

METRICS_REGISTRY = CollectorRegistry()

documents_ingested_total = Counter(
    "kos_documents_ingested_total",
    "Documentos ingeridos correctamente, por conector.",
    ["connector"],
    registry=METRICS_REGISTRY,
)

documents_retired_total = Counter(
    "kos_documents_retired_total",
    "Documentos marcados tombstone (borrados en la fuente), por conector.",
    ["connector"],
    registry=METRICS_REGISTRY,
)

pipeline_duration_seconds = Histogram(
    "kos_pipeline_duration_seconds",
    "Duración del pipeline de parseo (s1-s6), por conector.",
    ["connector"],
    registry=METRICS_REGISTRY,
)

llm_tokens_total = Counter(
    "kos_llm_tokens_total",
    "Tokens de LLM consumidos, por modelo/operación/tipo (prompt|completion).",
    ["model", "operation", "kind"],
    registry=METRICS_REGISTRY,
)

http_request_duration_seconds = Histogram(
    "kos_http_request_duration_seconds",
    "Duración de requests HTTP de la API, por método/ruta/status.",
    ["method", "route", "status"],
    registry=METRICS_REGISTRY,
)


# Métricas de negocio del Planner, los agentes y el Recomendador (doc 09 §6).
# Registry aparte de `METRICS_REGISTRY`: solo la API lo sirve (`GET /metrics`),
# porque son *gauges* que se recalculan desde Postgres en cada scrape
# (`postgres.business_metrics_snapshot`) — un worker que los expusiera en su
# puerto mostraría ceros engañosos. No son contadores en memoria a propósito:
# en Railway la API duerme y el worker sale al drenar (ADR-0009), y un
# contador de proceso se perdería.
BUSINESS_REGISTRY = CollectorRegistry()

business_metrics_up = Gauge(
    "kos_business_metrics_up",
    "1 si el último scrape pudo leer las métricas de negocio de Postgres, 0 si falló.",
    registry=BUSINESS_REGISTRY,
)
plans_gauge = Gauge(
    "kos_plans",
    "Planes generados por el Planner en la ventana (24h|7d).",
    ["window"],
    registry=BUSINESS_REGISTRY,
)
plans_degraded_gauge = Gauge(
    "kos_plans_degraded",
    "Planes degradados en la ventana, por `degraded_reason`.",
    ["window", "reason"],
    registry=BUSINESS_REGISTRY,
)
plan_latency_avg_ms_gauge = Gauge(
    "kos_plan_latency_avg_ms",
    "Latencia promedio de un plan en la ventana (ms).",
    ["window"],
    registry=BUSINESS_REGISTRY,
)
plan_agent_steps_gauge = Gauge(
    "kos_plan_agent_steps",
    "Pasos de plan en la ventana, por agente elegido por el LLM.",
    ["window", "agent"],
    registry=BUSINESS_REGISTRY,
)
plan_agent_latency_avg_ms_gauge = Gauge(
    "kos_plan_agent_latency_avg_ms",
    "Promedio de `cost.ms` por paso en la ventana, por agente (solo pasos con `cost.ms`).",
    ["window", "agent"],
    registry=BUSINESS_REGISTRY,
)
recommendations_gauge = Gauge(
    "kos_recommendations",
    "Recomendaciones existentes, por tipo (gap|contradiction) y estado.",
    ["type", "status"],
    registry=BUSINESS_REGISTRY,
)
recommendations_created_gauge = Gauge(
    "kos_recommendations_created",
    "Recomendaciones creadas en la ventana (7d|30d): el ritmo del criterio de salida de v1.0.",
    ["window"],
    registry=BUSINESS_REGISTRY,
)
recommendation_last_created_gauge = Gauge(
    "kos_recommendation_last_created_timestamp_seconds",
    "Instante (unix) de la recomendación más reciente; 0 si nunca hubo ninguna.",
    registry=BUSINESS_REGISTRY,
)

_BUSINESS_LABELLED_GAUGES = (
    plans_gauge,
    plans_degraded_gauge,
    plan_latency_avg_ms_gauge,
    plan_agent_steps_gauge,
    plan_agent_latency_avg_ms_gauge,
    recommendations_gauge,
    recommendations_created_gauge,
)


def _clear_business_gauges() -> None:
    for gauge in _BUSINESS_LABELLED_GAUGES:
        gauge.clear()
    recommendation_last_created_gauge.set(0)


def mark_business_metrics_unavailable() -> None:
    """Postgres no respondió: vacía los gauges (mejor sin dato que un dato viejo
    que parezca vigente) y baja `kos_business_metrics_up` a 0."""
    _clear_business_gauges()
    business_metrics_up.set(0)


def record_business_snapshot(snapshot: Mapping[str, Any]) -> None:
    """Vuelca la foto de `business_metrics_snapshot` a los gauges. Sin `await`
    dentro: el vaciado y la carga son atómicos respecto de otro scrape."""
    _clear_business_gauges()
    for window, data in snapshot["plans"].items():
        summary = data["summary"]
        plans_gauge.labels(window=window).set(summary["total"])
        plan_latency_avg_ms_gauge.labels(window=window).set(float(summary["avg_ms"]))
        for row in data["degradation"]:
            reason = row["degraded_reason"] or "unknown"
            plans_degraded_gauge.labels(window=window, reason=reason).set(row["count"])
        for row in data["agents"]:
            plan_agent_steps_gauge.labels(window=window, agent=row["agent"]).set(row["count"])
        for row in data["agent_latency"]:
            plan_agent_latency_avg_ms_gauge.labels(window=window, agent=row["agent"]).set(
                float(row["avg_ms"])
            )
    recommendations = snapshot["recommendations"]
    for row in recommendations["by_group"]:
        recommendations_gauge.labels(type=row["type"], status=row["status"]).set(row["count"])
    for window, count in recommendations["created"].items():
        recommendations_created_gauge.labels(window=window).set(count)
    last_created_at = recommendations["last_created_at"]
    if last_created_at is not None:
        recommendation_last_created_gauge.set(last_created_at.timestamp())
    business_metrics_up.set(1)


def bind_trace_id(trace_id: str | None) -> None:
    """Asocia el trace_id de la petición/task actual a los logs subsecuentes."""
    _trace_id_var.set(trace_id)


def current_trace_id() -> str | None:
    return _trace_id_var.get()


# Atributos propios de LogRecord (stdlib): cualquier otra clave en
# `record.__dict__` viene de `logging.info(..., extra={...})` y se propaga tal
# cual al JSON (usado por `kos_mcp.permissions.gate` para auditar invocaciones
# de herramientas con campos propios, no solo un mensaje de texto).
_STANDARD_LOG_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)


class _JsonFormatter(logging.Formatter):
    """Una línea JSON por registro: nivel, logger, mensaje, trace_id, excepción
    y cualquier campo extra pasado vía `extra={...}`."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": current_trace_id(),
        }
        extra = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_LOG_RECORD_ATTRS
        }
        if extra:
            payload.update(extra)
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
