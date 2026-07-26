"""Ahorro de recursos: apaga la infra de Docker cuando no se usa y la
enciende bajo demanda (doc 09 §9).

Dos mitades que corren en procesos distintos porque ninguna puede depender
de que la otra siga viva:

- `ensure_stack_up` vive en la API (middleware): antes de servir una
  request que toca Postgres/Neo4j/Redis/MinIO, arranca el compose si está
  caído y registra actividad.
- `watch` es un proceso aparte (vigía) que apaga el compose tras N minutos
  sin actividad; si dependiera del propio API no podría apagarlo cuando el
  API también está inactivo.

Ollama queda fuera a propósito: corre nativo (brew), no en este compose
(docker-compose.yml comentario junto al servicio `ollama`), y Ollama ya
descarga sus modelos de la GPU solo tras su propio `keep_alive`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from kos_core.config import Settings

logger = logging.getLogger("kos.docker_guardian")

REQUIRED_SERVICES = ("postgres", "neo4j", "redis", "minio")


def _activity_path(settings: Settings) -> Path:
    return Path(settings.kos_activity_file)


def touch_activity(settings: Settings) -> None:
    """Marca ahora como el último uso real de la infraestructura."""
    path = _activity_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(time.time()))


def _last_activity(settings: Settings) -> float | None:
    path = _activity_path(settings)
    if not path.exists():
        return None
    try:
        return float(path.read_text().strip())
    except ValueError:
        return None


async def _run(*args: str) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        "docker",
        "compose",
        "-f",
        args[0],
        *args[1:],
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    return proc.returncode or 0, stdout.decode(errors="replace")


async def _running_services(settings: Settings) -> set[str]:
    code, output = await _run(settings.kos_compose_file, "ps", "--status", "running", "--services")
    if code != 0:
        return set()
    return {line.strip() for line in output.splitlines() if line.strip()}


async def is_stack_up(settings: Settings) -> bool:
    running = await _running_services(settings)
    return set(REQUIRED_SERVICES).issubset(running)


async def _wait_healthy(settings: Settings, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if await is_stack_up(settings):
            return True
        await asyncio.sleep(1.0)
    return await is_stack_up(settings)


async def ensure_stack_up(settings: Settings) -> bool:
    """Arranca el compose si hace falta. Devuelve False si no llegó a tiempo."""
    if await is_stack_up(settings):
        touch_activity(settings)
        return True

    logger.info("docker_guardian: infra caída, arrancando docker compose up -d")
    code, output = await _run(settings.kos_compose_file, "up", "-d", *REQUIRED_SERVICES)
    if code != 0:
        logger.error("docker_guardian: fallo al levantar la infra: %s", output)
        return False

    ok = await _wait_healthy(settings, timeout=settings.kos_guardian_start_timeout_seconds)
    if ok:
        touch_activity(settings)
    else:
        logger.error(
            "docker_guardian: la infra no quedó sana tras %ss",
            settings.kos_guardian_start_timeout_seconds,
        )
    return ok


async def stop_if_idle(settings: Settings) -> bool:
    """Apaga el compose si pasó el umbral de inactividad. Devuelve True si apagó."""
    last = _last_activity(settings)
    if last is None:
        return False
    idle_seconds = time.time() - last
    if idle_seconds < settings.kos_idle_stop_minutes * 60:
        return False
    if not await is_stack_up(settings):
        return False

    logger.info(
        "docker_guardian: %.0f min sin actividad (umbral %s min), apagando docker compose",
        idle_seconds / 60,
        settings.kos_idle_stop_minutes,
    )
    code, output = await _run(settings.kos_compose_file, "stop", *REQUIRED_SERVICES)
    if code != 0:
        logger.error("docker_guardian: fallo al apagar la infra: %s", output)
        return False
    return True


async def watch(settings: Settings, interval_seconds: float = 60.0) -> None:
    """Bucle del vigía: revisa inactividad cada `interval_seconds`. No retorna.

    `make dev` siempre lo arranca; si `kos_guardian_enabled` está en False
    (default), sale de inmediato en vez de sondear Docker sin sentido — el
    middleware tampoco registra actividad en ese caso, así que no habría
    nada que vigilar.
    """
    if not settings.kos_guardian_enabled:
        logger.info("docker_guardian: deshabilitado (KOS_GUARDIAN_ENABLED=false), vigía inactivo")
        return

    logger.info(
        "docker_guardian: vigía activo (umbral=%s min, intervalo=%ss)",
        settings.kos_idle_stop_minutes,
        interval_seconds,
    )
    while True:
        await stop_if_idle(settings)
        await asyncio.sleep(interval_seconds)


def _main() -> None:
    import argparse

    from kos_core.config import get_settings

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["watch"])
    parser.add_argument("--interval", type=float, default=60.0, help="segundos entre chequeos")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    settings = get_settings()
    asyncio.run(watch(settings, interval_seconds=args.interval))


if __name__ == "__main__":
    _main()
