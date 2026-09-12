"""Drain programado del despliegue gestionado (doc 14 §4, ADR-0009).

En Railway el worker no es un proceso vivo: un servicio Celery conectado al
broker nunca deja de emitir tráfico saliente y por tanto nunca duerme, lo que
por sí solo se comería el techo de coste. En su lugar, Railway ejecuta este
script según un crontab (dos veces al día) y **espera que termine**.

Lo que hace, en orden:

1. `git pull` del clon del vault que vive en el volumen de este servicio.
2. Encola `kos.sync_all_sources` — lo que en local hace Celery beat.
3. Encola la consolidación de memoria si toca (≥ KOS_MEMORY_CONSOLIDATION_HOURS).
4. Levanta un worker Celery embebido y lo para en cuanto la cola queda vacía.
5. Empuja al repo las notas que la ingesta haya creado.
6. Registra la ejecución en `cron_runs`, que es lo que `/v1/ops/status` lee.

Reglas de oro: **siempre termina** (timeout duro; si el proceso no sale, Railway
salta todas las ejecuciones siguientes y la ingesta muere en silencio) y
**nunca deja conexiones abiertas**.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from celery.signals import task_postrun

from kos_core.config import Settings, get_settings
from kos_core.storage import postgres as postgres_storage
from kos_core.storage import redis as redis_storage

logger = logging.getLogger("kos.drain")

DEFAULT_TIMEOUT_SECONDS = 30 * 60
"""30 min (ADR-0009). Con 12 h entre ciclos nunca choca con la ejecución
siguiente, y lo que no dé tiempo a procesar espera en Redis al próximo drain."""

IDLE_CHECKS_TO_STOP = 3
"""Comprobaciones consecutivas con la cola vacía antes de parar. Más de una
porque una tarea encadenada tarda un instante en aparecer en la cola después de
que termine la anterior — parar a la primera cortaría la cadena a la mitad."""

POLL_SECONDS = 2.0
FORCE_EXIT_GRACE_SECONDS = 30.0
"""Margen tras pedirle al worker que pare antes de salir a lo bruto. Parar un
worker Celery desde otro hilo no está garantizado por la API de Celery, y un
proceso que no termina es el peor fallo de esta topología: Railway saltaría
todas las ejecuciones siguientes. El estado vive en Postgres y Redis, así que
salir de golpe no pierde nada."""
QUEUE_NAME = "default"
UNACKED_KEY = "unacked"
"""Hash donde el broker Redis de Celery guarda lo entregado y aún sin confirmar:
sin mirarlo, una tarea en curso parecería cola vacía."""

_processed = 0
_processed_lock = threading.Lock()


@task_postrun.connect
def _count_processed(**_kwargs: object) -> None:
    """Cuenta tareas ejecutadas. Funciona porque el worker corre con pool
    `solo`: la tarea se ejecuta en este mismo proceso y la señal llega aquí."""
    global _processed
    with _processed_lock:
        _processed += 1


def _run_git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=check,
    )
    return result.stdout.strip()


def vault_pull(vault_path: Path) -> str | None:
    """Trae los cambios del repo del vault. Devuelve un aviso si no pudo."""
    if not (vault_path / ".git").is_dir():
        return f"{vault_path} no es un repo git: se ingiere lo que haya en el volumen"
    try:
        _run_git(vault_path, "pull", "--ff-only")
    except subprocess.CalledProcessError as exc:
        # Un pull fallido no debe abortar el drain: se ingiere el estado local
        # y se deja constancia.
        return f"git pull falló: {exc.stderr.strip() or exc}"
    return None


def vault_push(vault_path: Path, *, message: str) -> str | None:
    """Publica las notas creadas por la ingesta. Devuelve un aviso si no pudo."""
    if not (vault_path / ".git").is_dir():
        return None
    if not _run_git(vault_path, "status", "--porcelain"):
        return None
    try:
        _run_git(vault_path, "add", "-A")
        _run_git(vault_path, "commit", "-m", message)
        _run_git(vault_path, "push")
    except subprocess.CalledProcessError as exc:
        return f"git push falló: {exc.stderr.strip() or exc}"
    return None


def queue_is_empty(settings: Settings) -> bool:
    """True si no queda nada pendiente ni en curso en el broker."""
    client = redis_storage.create_sync_client(settings)
    try:
        pending = client.llen(QUEUE_NAME)
        unacked = client.hlen(UNACKED_KEY)
    finally:
        client.close()
    return bool(pending == 0 and unacked == 0)


async def _memory_consolidation_due(engine: object, settings: Settings) -> bool:
    """¿Toca consolidar memoria? (ADR-0009: va dentro del drain, no en un
    servicio aparte). El estado vive en Postgres, no en el filesystem, que aquí
    es efímero."""
    last = await postgres_storage.last_cron_run(engine, job="memory_consolidate")  # type: ignore[arg-type]
    if last is None:
        return True
    reference = last["finished_at"] or last["started_at"]
    return datetime.now(UTC) - reference >= timedelta(hours=settings.kos_memory_consolidation_hours)


def _watchdog(
    worker: object,
    settings: Settings,
    timeout: float,
    stopped: threading.Event,
    on_stuck: Callable[[], None] | None,
) -> None:
    """Para el worker cuando la cola se vacía, o cuando vence el timeout.

    Si tras `FORCE_EXIT_GRACE_SECONDS` el worker sigue vivo, llama a `on_stuck`:
    la regla de ADR-0009 es que este proceso **siempre** termina.
    """
    deadline = time.monotonic() + timeout
    idle_checks = 0
    while True:
        time.sleep(POLL_SECONDS)
        if time.monotonic() > deadline:
            logger.warning("timeout de %.0fs alcanzado: se corta el drain", timeout)
            break
        try:
            empty = queue_is_empty(settings)
        except Exception as exc:  # el broker caído no debe dejar el proceso vivo
            logger.warning("no se pudo consultar el broker (%s); se para el drain", exc)
            break
        idle_checks = idle_checks + 1 if empty else 0
        if idle_checks >= IDLE_CHECKS_TO_STOP:
            logger.info("cola vacía: se para el worker")
            break
    worker.stop()  # type: ignore[attr-defined]
    if stopped.wait(FORCE_EXIT_GRACE_SECONDS):
        return
    logger.error(
        "el worker no paró en %.0fs tras pedírselo: se fuerza la salida",
        FORCE_EXIT_GRACE_SECONDS,
    )
    if on_stuck is not None:
        on_stuck()


def drain(
    settings: Settings, *, timeout: float, on_stuck: Callable[[], None] | None = None
) -> tuple[int, bool]:
    """Levanta el worker embebido y lo para al vaciarse la cola.

    Devuelve `(tareas_procesadas, truncado_por_timeout)`. El pool `solo` no es
    casual: ejecuta las tareas en este mismo proceso, que es lo que permite
    contarlas con la señal `task_postrun` sin depender de `inspect` (que con
    este pool no responde mientras una tarea corre).
    """
    from kos_workers.celery_app import app

    started = time.monotonic()
    worker = app.Worker(
        pool="solo",
        concurrency=1,
        without_gossip=True,
        without_mingle=True,
        without_heartbeat=True,
        quiet=True,
    )
    stopped = threading.Event()
    watchdog = threading.Thread(
        target=_watchdog, args=(worker, settings, timeout, stopped, on_stuck), daemon=True
    )
    watchdog.start()
    try:
        worker.start()  # bloquea hasta que el watchdog lo para
    finally:
        stopped.set()
    truncated = time.monotonic() - started >= timeout
    with _processed_lock:
        return _processed, truncated


async def _record_start(settings: Settings, job: str) -> tuple[object, uuid.UUID]:
    engine = postgres_storage.create_engine(settings)
    run_id = await postgres_storage.start_cron_run(engine, job=job)
    return engine, run_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Drain programado de KOS (doc 14 §4)")
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("KOS_DRAIN_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)),
        help="segundos antes de cortar el drain (default: 1800)",
    )
    parser.add_argument(
        "--vault-path",
        default=os.environ.get("VAULT_PATH", ""),
        help="clon del vault en el volumen; vacío = no se toca git",
    )
    parser.add_argument(
        "--skip-sync",
        action="store_true",
        help="no encolar sync_all_sources (para drenar solo lo que ya había)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()

    from kos_workers.celery_app import app

    engine, run_id = asyncio.run(_record_start(settings, "drain"))
    notes: list[str] = []
    status = "ok"
    processed = 0
    memory_run_id: uuid.UUID | None = None
    try:
        if args.vault_path:
            warning = vault_pull(Path(args.vault_path))
            if warning:
                notes.append(warning)
                logger.warning(warning)

        if not args.skip_sync:
            app.send_task("kos.sync_all_sources", queue=QUEUE_NAME)
        if asyncio.run(_memory_consolidation_due(engine, settings)):
            app.send_task("kos.memory_consolidate", queue=QUEUE_NAME)
            # Se deja marca en cron_runs en el mismo momento de encolarla: sin
            # esto, `_memory_consolidation_due` volvería a dar True en todos los
            # ciclos siguientes y la consolidación correría dos veces al día en
            # vez de una.
            memory_run_id = asyncio.run(
                postgres_storage.start_cron_run(engine, job="memory_consolidate")  # type: ignore[arg-type]
            )
            notes.append("consolidación de memoria encolada")

        def _abandon() -> None:
            """El worker no paró: se deja constancia y se sale de golpe."""
            asyncio.run(
                postgres_storage.finish_cron_run(
                    engine,  # type: ignore[arg-type]
                    run_id,
                    status="stuck",
                    tasks_drained=_processed,
                    detail="el worker no paró tras el timeout; salida forzada",
                )
            )
            os._exit(0)

        processed, truncated = drain(settings, timeout=args.timeout, on_stuck=_abandon)
        if truncated:
            status = "truncated"
            notes.append("timeout: lo pendiente queda en Redis para el próximo ciclo")

        if args.vault_path:
            warning = vault_push(
                Path(args.vault_path),
                message=f"kos: notas creadas por la ingesta ({datetime.now(UTC).date()})",
            )
            if warning:
                notes.append(warning)
                logger.warning(warning)
    except Exception as exc:  # el fallo tiene que quedar registrado, no perderse
        status = "error"
        notes.append(str(exc))
        logger.exception("el drain falló")
    finally:
        if memory_run_id is not None:
            # La tarea puede seguir en cola si venció el timeout; la marca dice
            # "encolada en este ciclo", que es lo que decide el siguiente.
            asyncio.run(
                postgres_storage.finish_cron_run(
                    engine,  # type: ignore[arg-type]
                    memory_run_id,
                    status=status,
                )
            )
        asyncio.run(
            postgres_storage.finish_cron_run(
                engine,  # type: ignore[arg-type]
                run_id,
                status=status,
                tasks_drained=processed,
                detail="; ".join(notes) or None,
            )
        )
        asyncio.run(engine.dispose())  # type: ignore[attr-defined]

    logger.info("drain %s: %d tareas", status, processed)
    # Sale 0 incluso en `truncated`: es una ejecución acotada a propósito, no un
    # fallo, y un exit distinto de 0 haría que Railway marque el deploy caído.
    return 1 if status == "error" else 0


if __name__ == "__main__":  # `python -m kos_workers.drain` (comando del cron)
    sys.exit(main())
