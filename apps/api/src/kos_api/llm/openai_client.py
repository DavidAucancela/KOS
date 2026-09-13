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


def _build_monitored_client(
    settings: Settings,
    *,
    task: Task,
    api_key: str | None = None,
    base_url: str | None = None,
    provider: str = "openai",
) -> Any:
    from llm_observatory import AsyncMonitoredOpenAI

    kwargs: dict[str, Any] = {}
    resolved_base_url = base_url or settings.openai_base_url
    if resolved_base_url:
        kwargs["base_url"] = resolved_base_url
    return AsyncMonitoredOpenAI(
        api_key=api_key or settings.openai_api_key,
        observatory_url=settings.llm_observatory_url or "http://localhost:3001",
        observatory_token=settings.llm_observatory_token or None,
        tags={"app": "kos", "task": task, "provider": provider},
        **kwargs,
    )


class OpenAILLMClient:
    """Cliente para OpenAI y para cualquier proveedor con su mismo wire format.

    `model`/`base_url`/`api_key` permiten apuntar el mismo cliente a OpenRouter,
    Groq o similares sin código nuevo (ADR-0008, doc 15 §2.1). El coste de esos
    proveedores se audita como `cost_confidence="unknown"`: no están en
    `OPENAI_PRICING`. `provider` solo etiqueta la métrica.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        task: Task,
        client: Any | None = None,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        provider: str = "openai",
    ) -> None:
        self._model = model or settings.openai_llm_model
        self._task = task
        self._provider = provider
        if client is not None:
            self._client = client
        else:
            self._client = _build_monitored_client(
                settings, task=task, api_key=api_key, base_url=base_url, provider=provider
            )

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
            # Dentro del try a propósito: un proveedor OpenAI-compatible puede
            # devolver `choices: []` (content filter), y un IndexError acá se
            # escaparía del contrato `CloudLLMError` que espera el caller.
            choices = getattr(response, "choices", None) or []
            if not choices:
                raise CloudLLMError("el proveedor devolvió una respuesta sin choices")
            content = choices[0].message.content
        except CloudLLMError:
            raise
        except TimeoutError as exc:
            raise CloudLLMError(f"timeout tras {timeout}s") from exc
        except Exception as exc:  # cualquier error del SDK/OpenAI: el caller cae a local
            # El tipo va en el mensaje: `CloudLLMError(str(exc))` a secas aplana
            # un 401 permanente y un corte de red transitorio al mismo log.
            raise CloudLLMError(f"{type(exc).__name__}: {exc}") from exc

        return content or ""

    async def aclose(self) -> None:
        inner = getattr(self._client, "_client", None)
        if inner is not None and hasattr(inner, "close"):
            await inner.close()
