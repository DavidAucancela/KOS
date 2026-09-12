"""Autenticación por claves nombradas y rate limit (ADR-0010)."""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from kos_api.auth import RateLimiter
from kos_api.main import create_app
from kos_core.config import Settings, get_settings


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    def _settings() -> Settings:
        return Settings(_env_file=None, kos_api_keys="web:clave-web,mac:clave-mac")

    get_settings.cache_clear()
    monkeypatch.setattr("kos_api.middleware.get_settings", _settings)
    with TestClient(create_app()) as test_client:
        yield test_client


def _basic(name: str, secret: str) -> dict[str, str]:
    token = base64.b64encode(f"{name}:{secret}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_health_no_pide_credencial(client: TestClient) -> None:
    """Railway sondea /health sin credencial (ADR-0010)."""
    assert client.get("/health").status_code == 200


def test_sin_credencial_devuelve_401_con_reto_basic(client: TestClient) -> None:
    """El reto Basic es lo que hace que el navegador pida usuario y clave."""
    response = client.get("/v1/sources")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == 'Basic realm="KOS"'
    assert response.headers["content-type"].startswith("application/problem+json")


def test_metrics_tambien_pide_credencial(client: TestClient) -> None:
    assert client.get("/metrics").status_code == 401


def test_basic_valido_autentica(client: TestClient) -> None:
    assert client.get("/v1/sources", headers=_basic("web", "clave-web")).status_code == 200


def test_basic_con_clave_de_otro_cliente_falla(client: TestClient) -> None:
    """Cada clave vale solo para su nombre: revocar una no afecta a las otras."""
    assert client.get("/v1/sources", headers=_basic("web", "clave-mac")).status_code == 401


def test_x_api_key_autentica_a_clientes_sin_navegador(client: TestClient) -> None:
    response = client.get("/v1/sources", headers={"X-API-Key": "clave-mac"})
    assert response.status_code == 200


def test_x_api_key_invalida_falla(client: TestClient) -> None:
    assert client.get("/v1/sources", headers={"X-API-Key": "no"}).status_code == 401


def test_sin_claves_configuradas_solo_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """Modo local de doc 09: sin KOS_API_KEYS no se atiende a nadie de fuera."""
    monkeypatch.setattr(
        "kos_api.middleware.get_settings", lambda: Settings(_env_file=None, kos_api_keys="")
    )
    with TestClient(create_app()) as local_client:
        # El TestClient se presenta como host local.
        assert local_client.get("/v1/sources").status_code == 200


def test_rate_limit_por_ventana() -> None:
    limiter = RateLimiter()
    assert limiter.allow("1.2.3.4", "llm", 2)
    assert limiter.allow("1.2.3.4", "llm", 2)
    assert not limiter.allow("1.2.3.4", "llm", 2)
    # Otro bucket y otro cliente llevan su propia cuenta.
    assert limiter.allow("1.2.3.4", "general", 2)
    assert limiter.allow("5.6.7.8", "llm", 2)


def test_rate_limit_desactivado_con_limite_cero() -> None:
    limiter = RateLimiter()
    assert all(limiter.allow("1.2.3.4", "general", 0) for _ in range(100))
