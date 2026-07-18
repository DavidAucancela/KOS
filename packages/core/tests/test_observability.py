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
