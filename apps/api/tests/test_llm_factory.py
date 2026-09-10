"""Unit de la selección de proveedor LLM por tarea (ADR-0007)."""

from __future__ import annotations

from typing import Any

import pytest

from kos_api.llm.factory import FallbackLLMClient, make_llm_client, make_writing_clients
from kos_core.config import Settings
from kos_core.llm.ollama import OllamaLLMClient


@pytest.fixture(autouse=True)
def _stub_monitored_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Evita construir `AsyncMonitoredOpenAI` real (necesitaría el SDK + red)."""
    monkeypatch.setattr(
        "kos_api.llm.openai_client._build_monitored_client",
        lambda settings, *, task: object(),
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
