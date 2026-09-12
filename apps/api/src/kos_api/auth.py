"""Autenticación por claves nombradas y rate limit en memoria (ADR-0010).

Dos formas de presentar la **misma** credencial contra `KOS_API_KEYS`:

- **HTTP Basic** (`usuario` = nombre de la clave) — es lo que usa el navegador.
  Como la API sirve también el HTML de `apps/web`, un `401` con
  `WWW-Authenticate: Basic` hace que el navegador pida credenciales y las
  reenvíe en todas las peticiones del mismo origen, incluidas las `fetch` de la
  SPA: sin sesión, sin token en `localStorage` y sin CSRF.
- **`X-API-Key`** — para la Mac, el conector y el CLI, que no tienen navegador.

Con `KOS_API_KEYS` vacío (modo local de doc 09) no hay credenciales que validar
y solo se aceptan conexiones desde la propia máquina.

El contador del rate limit vive en memoria del proceso a propósito: hay una sola
réplica y el servicio duerme; llevarlo a Redis añadiría tráfico saliente
periódico que impediría dormir a la API (doc 14 §2.2), que es de donde sale el
ahorro del despliegue.
"""

from __future__ import annotations

import base64
import hmac
import logging
import time
from collections import deque

from fastapi import Request

from kos_core.config import Settings

logger = logging.getLogger(__name__)

# Sondeos de plataforma: Railway y el monitoreo los necesitan sin credencial.
PUBLIC_PATHS = frozenset({"/health"})
# Rutas cuyo coste no es CPU sino llamadas a un LLM de pago: límite aparte.
LLM_PATH_PREFIXES = ("/v1/query",)
# Loopback + el host que usa el TestClient de Starlette, que no atraviesa red.
_LOCAL_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})
_WINDOW_SECONDS = 60.0
# Cota de memoria del contador: sin esto, IPs falsificadas lo harían crecer sin fin.
_MAX_TRACKED_CLIENTS = 2048


class RateLimiter:
    """Ventana deslizante por (cliente, bucket), en memoria. Un minuto por
    defecto; `window` permite ventanas más largas (el disparo manual del cron
    se cuenta por hora, porque cada uno arranca un contenedor)."""

    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = {}

    def allow(
        self, client: str, bucket: str, limit: int, *, window: float = _WINDOW_SECONDS
    ) -> bool:
        if limit <= 0:
            return True
        now = time.monotonic()
        key = (client, bucket)
        hits = self._hits.get(key)
        if hits is None:
            if len(self._hits) >= _MAX_TRACKED_CLIENTS:
                self._evict()
            hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] > window:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True

    def _evict(self) -> None:
        """Descarta las ventanas ya vencidas; si ninguna lo está, empieza de cero.

        Perder el contador relaja el límite un minuto, que es preferible a
        crecer sin límite en el proceso.
        """
        now = time.monotonic()
        stale = [
            key for key, hits in self._hits.items() if not hits or now - hits[-1] > _WINDOW_SECONDS
        ]
        for key in stale:
            del self._hits[key]
        if not stale:
            self._hits.clear()


def client_ip(request: Request) -> str:
    """IP del cliente detrás del proxy de Railway (`X-Forwarded-For`)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "desconocido"


def is_local(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in _LOCAL_HOSTS


def _credentials(request: Request) -> tuple[str | None, str | None]:
    """`(nombre, clave)` de la petición: Basic, o `X-API-Key` sin nombre."""
    header = request.headers.get("authorization", "")
    scheme, _, payload = header.partition(" ")
    if scheme.lower() == "basic" and payload:
        try:
            decoded = base64.b64decode(payload).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None, None
        name, separator, secret = decoded.partition(":")
        if separator:
            return name, secret
        return None, None
    api_key = request.headers.get("x-api-key")
    if api_key:
        return None, api_key
    return None, None


def authenticate(request: Request, settings: Settings) -> str | None:
    """Nombre del cliente autenticado, o None si la credencial no vale.

    La clave se compara con `compare_digest` para no filtrar por tiempo qué
    prefijo era correcto.
    """
    keys = settings.api_keys
    name, secret = _credentials(request)
    if secret is None:
        return None
    if name is not None:
        expected = keys.get(name)
        if expected and hmac.compare_digest(expected, secret):
            return name
        return None
    # `X-API-Key` no dice qué cliente es: vale cualquier clave configurada.
    for key_name, expected in keys.items():
        if hmac.compare_digest(expected, secret):
            return key_name
    return None
