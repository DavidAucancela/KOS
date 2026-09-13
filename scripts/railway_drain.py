"""Atajo local para el drain del despliegue gestionado (doc 14 §4).

La lógica vive en `kos_workers.drain` — ahí es importable y testeable, y ahí la
invoca el servicio cron de Railway (`python -m kos_workers.drain`). Este script
existe para poder dispararlo a mano desde la Mac contra las bases gestionadas,
que es el camino de urgencia alternativo a `POST /v1/ops/sync-now`.
"""

from __future__ import annotations

import sys

from kos_workers.drain import main

if __name__ == "__main__":
    sys.exit(main())
