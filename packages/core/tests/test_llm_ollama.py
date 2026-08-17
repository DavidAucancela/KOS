import json
from typing import Any

import httpx

from kos_core.config import Settings
from kos_core.llm.base import EmbeddingClient, LLMClient
from kos_core.llm.ollama import OllamaEmbeddingClient, OllamaLLMClient


def _client_con_respuesta(
    respuesta: dict[str, Any], capturadas: list[httpx.Request]
) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        capturadas.append(request)
        return httpx.Response(200, json=respuesta)

    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://localhost:11434"
    )


async def test_embed_envia_modelo_y_textos() -> None:
    requests: list[httpx.Request] = []
    settings = Settings(_env_file=None)
    client = OllamaEmbeddingClient(
        settings, client=_client_con_respuesta({"embeddings": [[0.1, 0.2]]}, requests)
    )
    result = await client.embed(["hola"])
    assert result == [[0.1, 0.2]]

    [request] = requests
    assert request.url.path == "/api/embed"
    body = json.loads(request.content)
    assert body == {"model": "bge-m3", "input": ["hola"]}


async def test_generate_envia_system_y_opciones() -> None:
    requests: list[httpx.Request] = []
    settings = Settings(_env_file=None)
    client = OllamaLLMClient(
        settings, client=_client_con_respuesta({"response": "hola humano"}, requests)
    )
    result = await client.generate("saluda", system="eres KOS", max_tokens=32)
    assert result == "hola humano"

    body = json.loads(requests[0].content)
    assert body["model"] == settings.ollama_llm_model
    assert body["system"] == "eres KOS"
    assert body["stream"] is False
    assert body["options"] == {"temperature": 0.2, "num_predict": 32}


async def test_generate_pasa_timeout_a_la_llamada_http(monkeypatch: Any) -> None:
    """Auditoría de cierre v0.5 (2026-08-16): `timeout` (ej. de
    `Constraints.timeout_s`) debe llegar al `post()` real, no quedar
    desacoplado del `_DEFAULT_TIMEOUT` fijo del cliente."""
    settings = Settings(_env_file=None)
    captured: dict[str, Any] = {}

    class _FakeHttpClient:
        async def post(self, url: str, **kwargs: Any) -> httpx.Response:
            captured.update(kwargs)
            response = httpx.Response(200, json={"response": "ok"})
            response.request = httpx.Request("POST", "http://localhost:11434" + url)
            return response

    client = OllamaLLMClient(settings, client=_FakeHttpClient())  # type: ignore[arg-type]
    await client.generate("hola", timeout=5.0)

    assert captured["timeout"] == 5.0


async def test_generate_sin_timeout_no_lo_manda_explicito() -> None:
    """Sin `timeout`, no se pasa `timeout=None` (que en httpx significa 'sin
    límite') — se omite el kwarg para que el cliente use su default real."""
    settings = Settings(_env_file=None)
    captured: dict[str, Any] = {}

    class _FakeHttpClient:
        async def post(self, url: str, **kwargs: Any) -> httpx.Response:
            captured.update(kwargs)
            response = httpx.Response(200, json={"response": "ok"})
            response.request = httpx.Request("POST", "http://localhost:11434" + url)
            return response

    client = OllamaLLMClient(settings, client=_FakeHttpClient())  # type: ignore[arg-type]
    await client.generate("hola")

    assert "timeout" not in captured


def test_implementaciones_cumplen_los_protocolos() -> None:
    settings = Settings(_env_file=None)
    assert isinstance(OllamaEmbeddingClient(settings), EmbeddingClient)
    assert isinstance(OllamaLLMClient(settings), LLMClient)
