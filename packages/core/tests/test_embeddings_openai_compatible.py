"""Cliente de embeddings sobre endpoint OpenAI-compatible (ADR-0008)."""

import httpx
import pytest

from kos_core.config import Settings
from kos_core.llm.factory import make_embedding_client
from kos_core.llm.ollama import OllamaEmbeddingClient
from kos_core.llm.openai_compatible import (
    EmbeddingDimensionError,
    OpenAICompatibleEmbeddingClient,
)

DIM = 1024


def _client(handler: httpx.MockTransport) -> OpenAICompatibleEmbeddingClient:
    settings = Settings(
        _env_file=None,
        kos_embedding_provider="openai_compatible",
        kos_embedding_base_url="https://proveedor.test/v1",
        kos_embedding_api_key="k-secreta",
    )
    return OpenAICompatibleEmbeddingClient(
        settings,
        client=httpx.AsyncClient(
            base_url="https://proveedor.test/v1",
            transport=handler,
            timeout=5.0,
            headers={"Authorization": "Bearer k-secreta"},
        ),
    )


@pytest.mark.asyncio
async def test_embed_devuelve_vectores_en_orden_de_entrada() -> None:
    """El contrato de OpenAI no garantiza el orden de `data`: cada item trae
    `index` y el Protocol exige el orden de entrada."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer k-secreta"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [2.0] * DIM},
                    {"index": 0, "embedding": [1.0] * DIM},
                ]
            },
        )

    client = _client(httpx.MockTransport(handler))
    vectors = await client.embed(["primero", "segundo"])
    assert vectors[0][0] == 1.0
    assert vectors[1][0] == 2.0
    await client.aclose()


@pytest.mark.asyncio
async def test_dimension_distinta_falla_en_vez_de_corromper_el_indice() -> None:
    """ADR-0008: bge-m3 a 1024 es innegociable — el schema es `vector(1024)`."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1] * 1536}]})

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(EmbeddingDimensionError, match="1536"):
        await client.embed(["texto"])
    await client.aclose()


def test_factory_default_es_ollama() -> None:
    assert isinstance(make_embedding_client(Settings(_env_file=None)), OllamaEmbeddingClient)


def test_factory_cae_a_ollama_sin_base_url() -> None:
    """Falta de configuración no debe romper el arranque; se avisa y se sigue."""
    settings = Settings(_env_file=None, kos_embedding_provider="openai_compatible")
    assert isinstance(make_embedding_client(settings), OllamaEmbeddingClient)


def test_factory_usa_endpoint_hospedado_cuando_esta_configurado() -> None:
    settings = Settings(
        _env_file=None,
        kos_embedding_provider="openai_compatible",
        kos_embedding_base_url="https://proveedor.test/v1",
    )
    assert isinstance(make_embedding_client(settings), OpenAICompatibleEmbeddingClient)
