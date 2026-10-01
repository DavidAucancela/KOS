"""Chequea la salud de producción (Railway) contra `GET /metrics` y avisa por
Discord si algo se sale de umbral (Sprint de monitoreo, doc 09 §6, doc
14 — Prometheus/Grafana no se despliegan en Railway, así que este script hace
de "alerta" sin necesitar infraestructura ahí).

Reglas evaluadas, todas sobre métricas de negocio que ya existen en
`BUSINESS_REGISTRY` (`packages/core/src/kos_core/observability.py`):

- `/metrics` inalcanzable (red, timeout, status 4xx/5xx) → Railway caído o despertando.
- `kos_business_metrics_up == 0` → Postgres inalcanzable desde `/metrics`.
- El Recomendador no corre hace más de `RECOMMENDER_STALE_DAYS` días (o nunca).
- Alguna pasada del Recomendador falló en la ventana de 7 días.
- No hay recomendaciones nuevas hace más de `NO_RECOMMENDATIONS_STALE_DAYS` días.

Solo lectura contra `/metrics` — nunca escribe nada. Pensado para correr desde
`.github/workflows/monitor-production.yml` (cron), con las credenciales como
GitHub Secrets (nunca pasan por Claude, mismo criterio que la fase D de doc 14).

Uso:

    export KOS_MONITOR_API_URL='https://<host-de-railway>'
    export KOS_MONITOR_API_KEY='<una clave de KOS_API_KEYS>'
    export DISCORD_WEBHOOK_URL='https://discord.com/api/webhooks/...'
    uv run python scripts/check_production_health.py check
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass

import httpx
from prometheus_client.parser import text_string_to_metric_families

RECOMMENDER_STALE_DAYS = 3
NO_RECOMMENDATIONS_STALE_DAYS = 14
_SECONDS_PER_DAY = 86400.0


@dataclass
class Alert:
    rule: str
    detail: str


def _fetch_metrics(base_url: str, api_key: str) -> str:
    """Puede lanzar `httpx.HTTPError` (red, timeout, status 4xx/5xx) — a propósito:
    que `/metrics` sea inalcanzable es en sí mismo una condición a alertar (ver
    `main`), no un error fatal del script."""
    url = f"{base_url.rstrip('/')}/metrics"
    response = httpx.get(url, headers={"X-API-Key": api_key}, timeout=10.0)
    response.raise_for_status()
    return response.text


def _sample_value(
    text: str, metric_name: str, labels: dict[str, str] | None = None
) -> float | None:
    """Primer valor de `metric_name` cuyas etiquetas incluyen `labels` (subconjunto).
    `None` si la métrica no aparece — con `kos_business_metrics_up == 0` el resto
    de gauges de negocio vienen vacíos (doc 09 §6), así que la ausencia no es un
    error del script sino una condición a reportar aparte."""
    labels = labels or {}
    for family in text_string_to_metric_families(text):
        if family.name != metric_name:
            continue
        for sample in family.samples:
            if all(sample.labels.get(key) == value for key, value in labels.items()):
                return sample.value
    return None


def evaluate(text: str, *, now_seconds: float) -> list[Alert]:
    alerts: list[Alert] = []

    business_up = _sample_value(text, "kos_business_metrics_up")
    if business_up != 1.0:
        alerts.append(
            Alert(
                "kos_business_metrics_up",
                f"valor={business_up!r} — /metrics no pudo leer Postgres",
            )
        )
        # El resto de gauges de negocio no dicen nada confiable si esta está en 0.
        return alerts

    last_run = _sample_value(text, "kos_recommender_last_run_timestamp_seconds")
    if last_run is None or last_run == 0.0:
        alerts.append(
            Alert("kos_recommender_last_run_timestamp_seconds", "el Recomendador nunca corrió")
        )
    else:
        stale_days = (now_seconds - last_run) / _SECONDS_PER_DAY
        if stale_days > RECOMMENDER_STALE_DAYS:
            alerts.append(
                Alert(
                    "kos_recommender_last_run_timestamp_seconds",
                    f"última pasada hace {stale_days:.1f} días (umbral {RECOMMENDER_STALE_DAYS})",
                )
            )

    # `None` = la serie {status="error"} no existe porque no hubo ninguna pasada
    # fallida en la ventana (el gauge solo emite combinaciones que ocurrieron de
    # verdad, observability.py:200-203) — ausencia equivale a cero, no a un dato
    # faltante.
    errors_7d = _sample_value(text, "kos_recommender_runs", {"window": "7d", "status": "error"})
    if (errors_7d or 0.0) > 0:
        alerts.append(
            Alert(
                "kos_recommender_runs",
                f"{errors_7d:.0f} pasada(s) con error en los últimos 7 días",
            )
        )

    last_created = _sample_value(text, "kos_recommendation_last_created_timestamp_seconds")
    if last_created is None or last_created == 0.0:
        alerts.append(
            Alert(
                "kos_recommendation_last_created_timestamp_seconds",
                "nunca se creó una recomendación",
            )
        )
    else:
        stale_days = (now_seconds - last_created) / _SECONDS_PER_DAY
        if stale_days > NO_RECOMMENDATIONS_STALE_DAYS:
            alerts.append(
                Alert(
                    "kos_recommendation_last_created_timestamp_seconds",
                    f"sin recomendaciones nuevas hace {stale_days:.1f} días "
                    f"(umbral {NO_RECOMMENDATIONS_STALE_DAYS})",
                )
            )

    return alerts


def _notify_discord(webhook_url: str, alerts: list[Alert]) -> None:
    lines = ["**KOS — alertas de producción**", ""]
    lines.extend(f"- `{alert.rule}`: {alert.detail}" for alert in alerts)
    try:
        response = httpx.post(webhook_url, json={"content": "\n".join(lines)}, timeout=10.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise SystemExit(f"no se pudo notificar a Discord ({exc})") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=["check"])
    parser.parse_args(argv)

    base_url = os.environ.get("KOS_MONITOR_API_URL", "")
    api_key = os.environ.get("KOS_MONITOR_API_KEY", "")
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not base_url or not api_key or not webhook_url:
        print(
            "Faltan KOS_MONITOR_API_URL / KOS_MONITOR_API_KEY / DISCORD_WEBHOOK_URL "
            "(ver el encabezado de este script).",
            file=sys.stderr,
        )
        return 2

    try:
        text = _fetch_metrics(base_url, api_key)
    except httpx.HTTPError as exc:
        alert = Alert("metrics_unreachable", f"no se pudo consultar /metrics en producción: {exc}")
        print(f"✗ {alert.rule}: {alert.detail}", file=sys.stderr)
        _notify_discord(webhook_url, [alert])
        return 1

    alerts = evaluate(text, now_seconds=time.time())

    if not alerts:
        print("✓ todo dentro de umbral")
        return 0

    for alert in alerts:
        print(f"✗ {alert.rule}: {alert.detail}")
    _notify_discord(webhook_url, alerts)
    print(f"\n{len(alerts)} alerta(s) enviada(s) a Discord.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
