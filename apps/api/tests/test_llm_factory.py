"""Unit de la selección de proveedor LLM por tarea (ADR-0007)."""

from __future__ import annotations

from typing import Any

import pytest

from kos_api.llm.factory import (
    ChainLLMClient,
    FallbackLLMClient,
    make_llm_client,
    make_writing_clients,
)
from kos_core.config import Settings
from kos_core.llm.ollama import OllamaLLMClient


@pytest.fixture(autouse=True)
def _stub_monitored_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Evita construir `AsyncMonitoredOpenAI` real (necesitaría el SDK + red)."""
    monkeypatch.setattr(
        "kos_api.llm.openai_client._build_monitored_client",
        lambda settings, *, task, **kwargs: object(),
    )


def _settings(**over: Any) -> Settings:
    return Settings(_env_file=None, **over)


def test_provider_ollama_devuelve_ollama() -> None:
    client = make_llm_client(_settings(kos_planner_llm_provider="ollama"), task="planner")
    assert isinstance(client, OllamaLLMClient)


def test_provider_openai_sin_key_cae_a_ollama(caplog: pytest.LogCaptureFixture) -> None:
    client = make_llm_client(
        _settings(kos_planner_llm_provider="openai", openai_api_key=""), task="planner"
    )
    assert isinstance(client, OllamaLLMClient)
    assert "openai_api_key vacío" in caplog.text


def test_provider_openai_con_key_envuelve_en_fallback() -> None:
    client = make_llm_client(
        _settings(kos_planner_llm_provider="openai", openai_api_key="sk-x"), task="planner"
    )
    assert isinstance(client, FallbackLLMClient)


def test_provider_desconocido_cae_a_ollama() -> None:
    client = make_llm_client(_settings(kos_writing_llm_provider="anthropic"), task="writing")
    assert isinstance(client, OllamaLLMClient)


async def test_fallback_reintenta_local_si_el_primario_falla() -> None:
    class _Boom:
        async def generate(self, *a: Any, **k: Any) -> str:
            raise RuntimeError("cloud caído")

        async def aclose(self) -> None:
            return None

    class _Local:
        async def generate(self, *a: Any, **k: Any) -> str:
            return "local ok"

        async def aclose(self) -> None:
            return None

    client = FallbackLLMClient(_Boom(), _Local())
    assert await client.generate("x") == "local ok"


def test_make_writing_clients_sin_cloud() -> None:
    local, cloud = make_writing_clients(_settings(kos_writing_llm_provider="ollama"))
    assert isinstance(local, OllamaLLMClient)
    assert cloud is None


def test_make_writing_clients_con_cloud() -> None:
    local, cloud = make_writing_clients(
        _settings(kos_writing_llm_provider="openai", openai_api_key="sk-x")
    )
    assert isinstance(local, OllamaLLMClient)
    assert isinstance(cloud, FallbackLLMClient)


# --- Cadena de proveedores cloud (ADR-0008) --------------------------------


def test_cadena_construye_un_cliente_por_proveedor() -> None:
    client = make_llm_client(
        _settings(
            kos_llm_provider_chain="openai,openrouter",
            openai_api_key="sk-x",
            openrouter_api_key="or-x",
        ),
        task="planner",
    )
    assert isinstance(client, ChainLLMClient)
    assert len(client._clients) == 2


def test_cadena_omite_proveedores_sin_key(caplog: pytest.LogCaptureFixture) -> None:
    client = make_llm_client(
        _settings(
            kos_llm_provider_chain="openai,openrouter",
            openai_api_key="sk-x",
            openrouter_api_key="",
        ),
        task="planner",
    )
    # Con un solo proveedor usable no hace falta envolver en cadena.
    assert not isinstance(client, ChainLLMClient)
    assert "sin API key" in caplog.text


def test_cadena_sin_proveedores_usables_cae_a_ollama(caplog: pytest.LogCaptureFixture) -> None:
    client = make_llm_client(
        _settings(kos_llm_provider_chain="openai", openai_api_key=""), task="planner"
    )
    assert isinstance(client, OllamaLLMClient)
    assert "ningún proveedor usable" in caplog.text


def test_cadena_gana_sobre_la_seleccion_por_tarea() -> None:
    """ADR-0008: en el despliegue gestionado la cadena manda sobre ADR-0007."""
    client = make_llm_client(
        _settings(
            kos_planner_llm_provider="ollama",
            kos_llm_provider_chain="openai",
            openai_api_key="sk-x",
        ),
        task="planner",
    )
    assert not isinstance(client, OllamaLLMClient)


async def test_cadena_agotada_propaga_el_error() -> None:
    """Sin Ollama detrás, un fallo de todos los proveedores debe verse (ADR-0008)."""

    class _Boom:
        def __init__(self, name: str) -> None:
            self.name = name

        async def generate(self, *a: Any, **k: Any) -> str:
            raise RuntimeError(f"{self.name} caído")

        async def aclose(self) -> None:
            return None

    chain = ChainLLMClient([_Boom("primero"), _Boom("segundo")])
    with pytest.raises(RuntimeError, match="segundo caído"):
        await chain.generate("x")


def test_writing_con_cadena_usa_la_cadena_en_la_ranura_cloud() -> None:
    local, cloud = make_writing_clients(
        _settings(
            kos_llm_provider_chain="openai,openrouter",
            openai_api_key="sk-x",
            openrouter_api_key="or-x",
        )
    )
    assert isinstance(local, OllamaLLMClient)
    assert isinstance(cloud, ChainLLMClient)
