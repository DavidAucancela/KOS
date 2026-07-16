from datetime import datetime

from kos_workers.celery_app import app
from kos_workers.tasks.ping import ping


def test_ping_ida_y_vuelta_en_modo_eager() -> None:
    app.conf.task_always_eager = True
    try:
        result = ping.delay("hola kos").get()
    finally:
        app.conf.task_always_eager = False

    assert result["payload"] == "hola kos"
    # worker_time debe ser un instante ISO-8601 válido
    assert datetime.fromisoformat(result["worker_time"]) is not None


def test_la_task_esta_registrada_con_nombre_de_evento() -> None:
    assert "kos.ping" in app.tasks
