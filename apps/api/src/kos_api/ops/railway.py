"""Disparo bajo demanda del servicio cron de Railway (doc 14 §5).

Por qué existe: en el despliegue gestionado el vault vive en el volumen del
servicio cron, y un volumen de Railway se adjunta a un solo servicio. La API no
tiene el filesystem del vault, así que **no puede ingerir aunque quisiera** — lo
único que puede hacer es pedirle a Railway que ejecute ahora ese servicio, que
sí lo tiene. Esa es la diferencia entre esperar al siguiente ciclo (hasta ~12h,
ADR-0009) y sincronizar al instante desde cualquier dispositivo.

Acopla este módulo a Railway a propósito y en un solo sitio: si el despliegue
se muda de plataforma, se reemplaza esto y nada más.
"""

from __future__ import annotations

import httpx

from kos_core.config import Settings

_REDEPLOY_MUTATION = """
mutation serviceInstanceRedeploy($serviceId: String!, $environmentId: String!) {
  serviceInstanceRedeploy(serviceId: $serviceId, environmentId: $environmentId)
}
"""

TIMEOUT_SECONDS = 15.0


class RailwayNotConfiguredError(RuntimeError):
    """Faltan token o ids: el despliegue no es el gestionado, o está a medio cablear."""


class RailwayTriggerError(RuntimeError):
    """Railway rechazó el disparo o no respondió."""


def is_configured(settings: Settings) -> bool:
    return bool(
        settings.railway_api_token
        and settings.railway_cron_service_id
        and settings.railway_environment_id
    )


async def trigger_cron_run(settings: Settings, *, client: httpx.AsyncClient | None = None) -> str:
    """Ejecuta ahora el servicio cron. Devuelve el id del despliegue creado."""
    if not is_configured(settings):
        raise RailwayNotConfiguredError(
            "Falta RAILWAY_API_TOKEN / RAILWAY_CRON_SERVICE_ID / RAILWAY_ENVIRONMENT_ID."
        )
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=TIMEOUT_SECONDS)
    try:
        response = await http.post(
            settings.railway_api_url,
            headers={"Authorization": f"Bearer {settings.railway_api_token}"},
            json={
                "query": _REDEPLOY_MUTATION,
                "variables": {
                    "serviceId": settings.railway_cron_service_id,
                    "environmentId": settings.railway_environment_id,
                },
            },
        )
    except httpx.HTTPError as exc:
        raise RailwayTriggerError(f"no se pudo contactar con Railway: {exc}") from exc
    finally:
        if owns_client:
            await http.aclose()

    if response.status_code >= 400:
        raise RailwayTriggerError(f"Railway respondió {response.status_code}")
    body = response.json()
    # GraphQL devuelve 200 con `errors` cuando la mutación falla: mirar solo el
    # código HTTP daría por bueno un disparo que no ocurrió.
    if body.get("errors"):
        detail = "; ".join(str(error.get("message", error)) for error in body["errors"])
        raise RailwayTriggerError(detail)
    deployment_id = (body.get("data") or {}).get("serviceInstanceRedeploy")
    if not isinstance(deployment_id, str):
        raise RailwayTriggerError("Railway no devolvió un id de despliegue")
    return deployment_id
