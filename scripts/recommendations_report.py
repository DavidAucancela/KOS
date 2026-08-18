"""Regenera `docs/eval/recomendaciones.md` desde `GET /v1/recommendations` real
(Sprint 26, doc 11 §10, doc 08 Sprint 26).

Registro manual de la ventana de uso real que arranca al cerrar la
construcción de v1.0: no es infraestructura de medición nueva (doc 11 §10 lo
dice explícito), solo un snapshot legible de lo que ya existe en Postgres —
mismo espíritu que `scripts/run_eval.py` para búsqueda, pero sobre datos
reales generados por el propio Recomendador en vez de un set de preguntas
fijo.

Criterio de "útil" (doc 11 §10): `accepted`, o `pending` sin `dismissed`
dentro de los 7 días de creada. `dismissed` nunca cuenta como útil,
sin importar cuánto tiempo pasó.

Requisitos: `make up`, API corriendo (`make dev-api` o equivalente).

Uso: `uv run python scripts/recommendations_report.py`
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "docs" / "eval" / "recomendaciones.md"
API_URL = "http://localhost:8000/v1/recommendations"
USEFUL_WINDOW_DAYS = 7


@dataclass
class Recommendation:
    recommendation_id: str
    type: str
    title: str
    status: str
    created_at: datetime
    resolved_at: datetime | None


def _parse(item: dict[str, object]) -> Recommendation:
    return Recommendation(
        recommendation_id=str(item["recommendation_id"]),
        type=str(item["type"]),
        title=str(item["title"]),
        status=str(item["status"]),
        created_at=datetime.fromisoformat(str(item["created_at"])),
        resolved_at=(
            datetime.fromisoformat(str(item["resolved_at"])) if item.get("resolved_at") else None
        ),
    )


def _fetch_all() -> list[Recommendation]:
    items: list[Recommendation] = []
    cursor: str | None = None
    with httpx.Client(timeout=10.0) as client:
        while True:
            params = {"limit": 100} | ({"cursor": cursor} if cursor else {})
            response = client.get(API_URL, params=params)
            response.raise_for_status()
            body = response.json()
            items.extend(_parse(item) for item in body["items"])
            cursor = body["next_cursor"]
            if cursor is None:
                break
    return items


def _is_useful(rec: Recommendation, *, now: datetime) -> bool | None:
    """`True`/`False`/`None` (todavía sin resolver, dentro de la ventana de
    7 días — no cuenta ni a favor ni en contra hasta que venza)."""
    if rec.status == "accepted":
        return True
    if rec.status == "dismissed":
        return False
    if rec.status == "pending":
        age_days = (now - rec.created_at).total_seconds() / 86400.0
        return True if age_days >= USEFUL_WINDOW_DAYS else None
    return None  # expired/superseded: fuera del criterio, no cuenta


def _render(recs: list[Recommendation], *, now: datetime) -> str:
    verdicts = [(rec, _is_useful(rec, now=now)) for rec in recs]
    decided = [v for _, v in verdicts if v is not None]
    useful_count = sum(1 for v in decided if v)
    lines = [
        "# Registro de recomendaciones reales — ventana de uso (v1.0)",
        "",
        f"**Generado por:** `scripts/recommendations_report.py` · **{now:%Y-%m-%d %H:%M} UTC**",
        "",
        "Criterio de éxito de v1.0 (doc 07, doc 11 §10): ≥1 recomendación útil por semana durante "
        "un mes de uso real. Útil = `accepted`, o `pending` sin `dismissed` dentro de los 7 días "
        "de creada. Este archivo se regenera corriendo el script — no editar a mano.",
        "",
        f"**Total: {len(recs)} recomendaciones · {useful_count}/{len(decided)} decididas son "
        "útiles** (el resto sigue `pending` dentro de la ventana de 7 días, sin veredicto todavía)",
        "",
        "| Creada | Tipo | Título | Estado | Resuelta | Útil |",
        "|---|---|---|---|---|---|",
    ]
    for rec, verdict in sorted(verdicts, key=lambda pair: pair[0].created_at, reverse=True):
        useful_label = "✅" if verdict is True else "❌" if verdict is False else "⏳"
        resolved = f"{rec.resolved_at:%Y-%m-%d}" if rec.resolved_at else "—"
        lines.append(
            f"| {rec.created_at:%Y-%m-%d} | {rec.type} | {rec.title} | {rec.status} "
            f"| {resolved} | {useful_label} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    recs = _fetch_all()
    now = datetime.now(UTC)
    OUTPUT_PATH.write_text(_render(recs, now=now), encoding="utf-8")
    print(f"{len(recs)} recomendaciones — escrito en {OUTPUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
