"""`OpenAILLMClient` — implementación cloud del Protocol `LLMClient` (ADR-0007).

Envuelve `AsyncMonitoredOpenAI` del SDK `llm_observatory`, que es un drop-in de
`openai.AsyncOpenAI` que además dispara (fire-and-forget) un métrico
tokens/coste/latencia/error a una instancia self-hosted de llm-observatory. Se
acepta que el SDK persista prompt y respuesta en la BD del observatory: es infra
propia y la puerta `cloud_safe` (WritingAgent) garantiza que solo contenido ya
autorizado a salir a OpenAI llega a esta ruta.
"""

from __future__ import annotations

from typing import Any, Literal

from kos_core.config import Settings

Task = Literal["planner", "writing"]


class CloudLLMError(Exception):
    """La llamada al LLM cloud falló (error de OpenAI o timeout). El caller
    (factory `FallbackLLMClient`) la captura para reintentar en local."""


def _build_monitored_client(settings: Settings, *, task: Task) -> Any:
    from llm_observatory import AsyncMonitoredOpenAI

    kwargs: dict[str, Any] = {}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return AsyncMonitoredOpenAI(
        api_key=settings.openai_api_key,
        observatory_url=settings.llm_observatory_url or "http://localhost:3001",
        observatory_token=settings.llm_observatory_token or None,
        tags={"app": "kos", "task": task},
        **kwargs,
    )


class OpenAILLMClient:
    def __init__(
        self,
        settings: Settings,
        *,
        task: Task,
        client: Any | None = None,
    ) -> None:
        self._model = settings.openai_llm_model
        self._task = task
        if client is not None:
            self._client = client
        else:
            self._client = _build_monitored_client(settings, task=task)

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system is not None:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        params: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if timeout is not None:
            params["timeout"] = timeout

        try:
            response = await self._client.chat.completions.create(**params)
        except TimeoutError as exc:
            raise CloudLLMError(f"timeout tras {timeout}s") from exc
        except Exception as exc:  # cualquier error del SDK/OpenAI: el caller cae a local
            raise CloudLLMError(str(exc)) from exc

        return response.choices[0].message.content or ""

    async def aclose(self) -> None:
        inner = getattr(self._client, "_client", None)
        if inner is not None and hasattr(inner, "close"):
            await inner.close()
