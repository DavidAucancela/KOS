"""Corre el set de evaluación (docs/eval/preguntas.md) contra POST /v1/query.

Sprint 5/post-Sprint-5: reemplaza el script desechable que se usó una vez y se
borró. Parsea la tabla de preguntas, llama a la API en vivo, compara
`evidence[].source_id` contra el archivo esperado (normalizado a NFC) y
regenera `docs/eval/resultados.md` con el detalle y el % final.

Requisitos: `make up`, API y worker corriendo (`make dev` o equivalente), y el
vault real ya sincronizado con embeddings.

Uso: `uv run python scripts/run_eval.py`
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
PREGUNTAS_PATH = REPO_ROOT / "docs" / "eval" / "preguntas.md"
RESULTADOS_PATH = REPO_ROOT / "docs" / "eval" / "resultados.md"
API_URL = "http://localhost:8000/v1/query"
CRITERIO_PCT = 90.0


@dataclass
class Pregunta:
    numero: int
    texto: str
    esperado: str
    hecho_clave: str


@dataclass
class Resultado:
    pregunta: Pregunta
    citados: list[str]
    acierto: bool
    error: str | None = None


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value or "")


def parse_preguntas(path: Path) -> list[Pregunta]:
    """Parsea la tabla markdown `| # | Pregunta | Archivo esperado | Hecho clave |`."""
    preguntas: list[Pregunta] = []
    row_re = re.compile(r"^\|\s*(\d+)\s*\|(.+)\|(.+)\|(.+)\|\s*$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = row_re.match(line.strip())
        if not match:
            continue
        numero, texto, esperado, hecho = match.groups()
        preguntas.append(
            Pregunta(
                numero=int(numero),
                texto=texto.strip(),
                esperado=esperado.strip(),
                hecho_clave=hecho.strip(),
            )
        )
    return preguntas


def run_query(client: httpx.Client, pregunta: Pregunta) -> Resultado:
    try:
        response = client.post(API_URL, json={"query": pregunta.texto}, timeout=90.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return Resultado(pregunta=pregunta, citados=[], acierto=False, error=str(exc))

    data = response.json()
    citados = [_nfc(ev.get("source_id", "")) for ev in data.get("evidence", [])]
    acierto = _nfc(pregunta.esperado) in citados
    return Resultado(pregunta=pregunta, citados=citados, acierto=acierto)


def render_resultados(resultados: list[Resultado]) -> str:
    aciertos = sum(1 for r in resultados if r.acierto)
    total = len(resultados)
    pct = 100 * aciertos / total if total else 0.0

    lines = [
        "# Resultados del set de evaluación",
        "",
        f"**Generado por:** `scripts/run_eval.py` · **Preguntas:** {total}",
        "",
        f"**Resultado: {aciertos}/{total} = {pct:.1f}%** "
        f"(criterio de cierre de v0.2: >{CRITERIO_PCT:.0f}%, ≥1 cita correcta)",
        "",
        "| # | Pregunta | Esperado | Citado(s) | Acierto |",
        "|---|---|---|---|---|",
    ]
    for r in resultados:
        citados = ", ".join(r.citados[:3]) or "(sin evidencia)"
        marca = "✅" if r.acierto else ("⚠️ error" if r.error else "❌")
        lines.append(
            f"| {r.pregunta.numero} | {r.pregunta.texto} | {r.pregunta.esperado} "
            f"| {citados} | {marca} |"
        )

    fallidas = [r for r in resultados if not r.acierto]
    if fallidas:
        lines += ["", "## Fallidas", ""]
        for r in fallidas:
            detalle = r.error or f"citó {r.citados[:3]!r}"
            lines.append(f"- **#{r.pregunta.numero}** ({r.pregunta.esperado}): {detalle}")

    return "\n".join(lines) + "\n"


def main() -> None:
    preguntas = parse_preguntas(PREGUNTAS_PATH)
    if not preguntas:
        raise SystemExit(f"No se encontraron preguntas en {PREGUNTAS_PATH}")

    resultados: list[Resultado] = []
    with httpx.Client() as client:
        for pregunta in preguntas:
            resultado = run_query(client, pregunta)
            marca = "OK" if resultado.acierto else "MISS"
            print(f"{pregunta.numero:>2} {marca:<4} {pregunta.esperado} -> {resultado.citados[:3]}")
            resultados.append(resultado)

    aciertos = sum(1 for r in resultados if r.acierto)
    print(f"\n{aciertos}/{len(resultados)} = {100 * aciertos / len(resultados):.1f}%")

    RESULTADOS_PATH.write_text(render_resultados(resultados), encoding="utf-8")
    print(f"✓ {RESULTADOS_PATH.relative_to(REPO_ROOT)} actualizado")


if __name__ == "__main__":
    main()
