"""Disparo inmediato del drain vía Railway (doc 14 §5)."""

from __future__ import annotations

import httpx
import pytest

from kos_api.ops import railway
from kos_core.config import Settings


def _settings(**over: object) -> Settings:
    base: dict[str, object] = {
        "railway_api_token": "tok",
        "railway_cron_service_id": "svc",
        "railway_environment_id": "env",
    }
    base.update(over)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]


def _http(handler: object) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]


async def test_dispara_y_devuelve_el_id_de_despliegue() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer tok"
        payload = request.read().decode()
        assert "serviceInstanceRedeploy" in payload
        return httpx.Response(200, json={"data": {"serviceInstanceRedeploy": "dep-123"}})

    async with _http(handler) as client:
        assert await railway.trigger_cron_run(_settings(), client=client) == "dep-123"


async def test_errores_graphql_no_pasan_por_exito() -> None:
    """GraphQL devuelve 200 con `errors`: mirar solo el código HTTP daría por
    bueno un disparo que no ocurrió."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errors": [{"message": "Not Authorized"}]})

    async with _http(handler) as client:
        with pytest.raises(railway.RailwayTriggerError, match="Not Authorized"):
            await railway.trigger_cron_run(_settings(), client=client)


async def test_sin_credenciales_falla_explicito() -> None:
    with pytest.raises(railway.RailwayNotConfiguredError):
        await railway.trigger_cron_run(_settings(railway_api_token=""))


def test_is_configured_exige_las_tres_piezas() -> None:
    assert railway.is_configured(_settings())
    assert not railway.is_configured(_settings(railway_environment_id=""))
    assert not railway.is_configured(Settings(_env_file=None))
