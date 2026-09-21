import io
import json
import logging

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from prometheus_client import generate_latest

from kos_core import observability


def test_json_formatter_incluye_trace_id() -> None:
    observability.bind_trace_id("abc-123")
    try:
        buffer = io.StringIO()
        handler = logging.StreamHandler(buffer)
        handler.setFormatter(observability._JsonFormatter())
        logger = logging.getLogger("kos_core.test_observability")
        logger.handlers = [handler]
        logger.setLevel("INFO")
        logger.propagate = False

        logger.info("hola %s", "mundo")

        payload = json.loads(buffer.getvalue())
        assert payload["message"] == "hola mundo"
        assert payload["trace_id"] == "abc-123"
        assert payload["level"] == "INFO"
    finally:
        observability.bind_trace_id(None)


def test_json_formatter_incluye_campos_extra() -> None:
    """Sprint 16: `kos_mcp.permissions.gate` audita invocaciones con campos
    propios (tool_name, confirm), no solo un mensaje de texto."""
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(observability._JsonFormatter())
    logger = logging.getLogger("kos_core.test_observability_extra")
    logger.handlers = [handler]
    logger.setLevel("INFO")
    logger.propagate = False

    logger.info("mcp_tool_invocation", extra={"tool_name": "memory.store", "confirm": False})

    payload = json.loads(buffer.getvalue())
    assert payload["tool_name"] == "memory.store"
    assert payload["confirm"] is False
    assert payload["message"] == "mcp_tool_invocation"


def test_traced_span_propaga_trace_id_como_atributo() -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")

    observability.bind_trace_id("xyz-789")
    try:
        with observability.traced_span(tracer, "etapa", foo="bar"):
            pass
    finally:
        observability.bind_trace_id(None)

    (span,) = exporter.get_finished_spans()
    assert span.name == "etapa"
    assert span.attributes is not None
    assert span.attributes["kos.trace_id"] == "xyz-789"
    assert span.attributes["foo"] == "bar"


def test_metricas_incrementan_en_el_registro_propio() -> None:
    """Doc 09 §6, Sprint 5: counters/histogramas reales, no el REGISTRY global."""
    observability.documents_ingested_total.labels(connector="test-connector").inc()
    observability.llm_tokens_total.labels(
        model="test-model", operation="generate", kind="prompt"
    ).inc(42)

    exposed = generate_latest(observability.METRICS_REGISTRY).decode()
    assert 'kos_documents_ingested_total{connector="test-connector"} 1.0' in exposed
    assert (
        'kos_llm_tokens_total{kind="prompt",model="test-model",operation="generate"} 42.0'
        in exposed
    )


def test_snapshot_de_negocio_sin_pasadas_ni_recomendaciones_no_falla() -> None:
    """Base recién creada: `last_run_at`/`last_created_at` llegan como `None` (el
    `max()` de cero filas es NULL, no una excepción) y no hay series de pasadas."""
    empty_window = {"summary": {"total": 0, "degraded": 0, "avg_ms": 0.0}, "degradation": []}
    observability.record_business_snapshot(
        {
            "plans": {
                "24h": {**empty_window, "agents": [], "agent_latency": []},
            },
            "recommender": {"runs": {"7d": [], "30d": []}, "last_run_at": None},
            "recommendations": {
                "by_group": [],
                "created": {"7d": 0, "30d": 0},
                "last_created_at": None,
            },
        }
    )

    exposed = generate_latest(observability.BUSINESS_REGISTRY).decode()
    assert "kos_business_metrics_up 1.0" in exposed
    assert "kos_recommender_last_run_timestamp_seconds 0.0" in exposed
    assert "kos_recommendation_last_created_timestamp_seconds 0.0" in exposed
    assert "kos_recommender_runs{" not in exposed
