"""Unit de `OpenAILLMClient` (ADR-0007): SDK fake, sin red ni OpenAI real."""

from __future__ import annotations

from typing import Any

import pytest

from kos_api.llm.openai_client import CloudLLMError, OpenAILLMClient
from kos_core.config import Settings


class _FakeMessage:
    def __init__(self, content: str | None) -> None:
        self.message = type("_M", (), {"content": content})()


class _FakeCompletions:
    def __init__(self, *, content: str | None = "ok", error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.last_params: dict[str, Any] | None = None

    async def create(self, **params: Any) -> Any:
        self.last_params = params
        if self.error is not None:
            raise self.error
        return type("_R", (), {"choices": [_FakeMessage(self.content)]})()


class _FakeMonitored:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.chat = type("_C", (), {"completions": completions})()


def _settings() -> Settings:
    return Settings(_env_file=None, openai_llm_model="gpt-4o-mini")


async def test_generate_mapea_system_y_prompt_a_messages() -> None:
    comp = _FakeCompletions(content="Respuesta [1].")
    client = OpenAILLMClient(_settings(), task="writing", client=_FakeMonitored(comp))

    out = await client.generate("pregunta", system="reglas", timeout=12.0, max_tokens=99)

    assert out == "Respuesta [1]."
    assert comp.last_params is not None
    assert comp.last_params["messages"] == [
        {"role": "system", "content": "reglas"},
        {"role": "user", "content": "pregunta"},
    ]
    assert comp.last_params["model"] == "gpt-4o-mini"
    assert comp.last_params["timeout"] == 12.0
    assert comp.last_params["max_tokens"] == 99


async def test_generate_content_none_devuelve_cadena_vacia() -> None:
    client = OpenAILLMClient(
        _settings(), task="planner", client=_FakeMonitored(_FakeCompletions(content=None))
    )
    assert await client.generate("x") == ""


async def test_error_del_sdk_se_reenvela_como_cloud_llm_error() -> None:
    comp = _FakeCompletions(error=RuntimeError("429 rate limit"))
    client = OpenAILLMClient(_settings(), task="writing", client=_FakeMonitored(comp))

    with pytest.raises(CloudLLMError):
        await client.generate("x")


async def test_respuesta_sin_choices_es_cloud_llm_error() -> None:
    """Un proveedor OpenAI-compatible puede devolver `choices: []` (content
    filter). Antes salía un IndexError, que se escapaba del contrato que
    `FallbackLLMClient` espera para caer a local."""

    class _SinChoices(_FakeCompletions):
        async def create(self, **params: Any) -> Any:
            self.last_params = params
            return type("_R", (), {"choices": []})()

    client = OpenAILLMClient(_settings(), task="writing", client=_FakeMonitored(_SinChoices()))

    with pytest.raises(CloudLLMError, match="sin choices"):
        await client.generate("x")


async def test_el_error_reenvuelto_conserva_el_tipo_original() -> None:
    """En el log, un fallo permanente (key revocada) tiene que distinguirse de
    uno transitorio; `str(exc)` a secas aplana ambos."""
    comp = _FakeCompletions(error=PermissionError("401 invalid api key"))
    client = OpenAILLMClient(_settings(), task="planner", client=_FakeMonitored(comp))

    with pytest.raises(CloudLLMError, match="PermissionError: 401 invalid api key"):
        await client.generate("x")
