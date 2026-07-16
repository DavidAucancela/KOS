"""Tarea de prueba de ida y vuelta del Sprint 1 (doc 08)."""

from __future__ import annotations

from datetime import UTC, datetime

from kos_workers.celery_app import app


@app.task(name="kos.ping")
def ping(payload: str = "pong") -> dict[str, str]:
    """Devuelve el payload y la hora del worker: demuestra broker y backend."""
    return {"payload": payload, "worker_time": datetime.now(UTC).isoformat()}
