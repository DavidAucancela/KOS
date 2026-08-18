# Retro — Sprint 26: cierre de construcción + inicio de la ventana de uso real

**Estado:** ✅ Cerrado 2026-08-18. Quinto y último sprint de construcción de v1.0 — Recomendador
(Fase 5). **v1.0 no cierra en este sprint** — el criterio de salida exige un mes de uso real, que
arranca hoy.

## Motivación

Sprints 22-25 dejaron el Recomendador construido de punta a punta: el evento `graph.updated`
dejó de ser huérfano (Sprint 22), dos tipos reales de recomendación generándose (lagunas Sprint
23, contradicciones Sprint 24), y el feedback loop completo (Sprint 25). Este sprint no agrega
funcionalidad nueva — cierra la fase de construcción, deja el mecanismo de medición manual listo,
y revisa la deuda acumulada de cara a planificar v1.1.

## Qué se construye

- **`scripts/recommendations_report.py`** (nuevo): snapshot de `GET /v1/recommendations` real que
  regenera `docs/eval/recomendaciones.md` — mismo patrón que `scripts/run_eval.py` para búsqueda,
  pero sobre datos generados por uso real en vez de un set de preguntas fijo. Calcula el veredicto
  de "útil" por recomendación según doc 11 §10 (`accepted` → útil; `dismissed` → no útil, sin
  importar cuánto tiempo pasó; `pending` → útil recién a los 7 días sin descartar, `⏳` mientras
  tanto). **No es infraestructura de medición nueva** (doc 11 §10 lo pide explícito) — es un
  script de lectura, el registro real vive en Postgres, esto solo lo hace legible.
- **`docs/eval/recomendaciones.md`** (nuevo): el registro en sí, regenerado por el script — arranca
  en 0 recomendaciones (estado real del vault a hoy).

## Revisión de deuda acumulada (Sprints 22-25)

De los ítems que `docs/deuda-tecnica.md` acumuló durante la construcción de v1.0, ninguno bloquea
el criterio de salida (≥1 recomendación útil/semana durante un mes) — todos son ajuste fino o
alcance explícitamente diferido:

| Ítem | Bloquea el criterio de salida? |
|---|---|
| Sin nodo "usuario"/`KNOWS` real (lagunas usan `confidence` como proxy) | No — el proxy ya genera recomendaciones reales |
| `gaps_by_prerequisite`/`recent_seed_chunks` no acotan por el disparo real | No — rendimiento, no funcionalidad, aceptable al volumen de un vault de un solo usuario |
| Veredicto de contradicción conservador con `llama3.2` | **Riesgo real de ritmo**: si el modelo local rara vez confirma una contradicción, ese tipo puede aportar pocas o ninguna recomendación útil durante el mes de medición — lagunas es el tipo que más probablemente sostenga el ritmo de ≥1/semana |
| Banda de similitud de contradicción sin tuning | No — mismo riesgo de arriba, no uno nuevo |
| `RecommendationsPanel` solo muestra `pending`, sin badge de conteo en el nav | No — afecta visibilidad/UX, no la generación ni el registro (el script mide contra Postgres directo, no contra lo que se ve en la UI) |

**Implicación para la ventana de medición:** dado que contradicciones puede no aportar mucho
volumen (deuda ya documentada), el ritmo real de "≥1 útil/semana" depende sobre todo de lagunas.
Si el vault tiene pocos `PREREQUISITE_OF` débilmente evidenciados nuevos por semana, el criterio
puede no cumplirse por falta de candidatos, no por falla del mecanismo — distinción importante a
tener en cuenta al evaluar el mes.

## Ventana de medición

**Arranca:** 2026-08-18. **Criterio de salida se evalúa:** a partir de 2026-09-18 (un mes de
calendario), corriendo `uv run python scripts/recommendations_report.py` (con `make up` y la API
corriendo) y revisando `docs/eval/recomendaciones.md`. El sprint 26 no puede cerrar v1.0 —
solo puede iniciar el reloj.

## Lecciones para planificar v1.1

- **La redefinición operable (Sprint 23/24) fue más valiosa que el diseño original.** Tanto
  `KNOWS`/`Person` como el nodo `Claim` estaban en el diseño de doc 02/11 desde antes de
  implementar, y ninguno de los dos se necesitó — el sistema encontró proxies (`confidence` del
  nodo, banda de similitud de chunks) que funcionan con lo que ya existe. Al planificar v1.1
  (SDK/API pública/empaquetado), vale la pena revisar qué piezas de doc 07 asumen infraestructura
  que en la práctica nunca hizo falta.
- **Verificar en vivo encontró bugs que ningún mock iba a encontrar** (el hallazgo del dedup de
  Sprint 25, el bug de robustez cross-test del `RecommendationsPanel`) — patrón ya repetido desde
  v0.2. v1.1 (SDK de conectores) es exactamente el tipo de superficie donde un conector de
  terceros real, no solo tests unitarios del SDK, va a revelar los huecos reales del contrato.
- **El patrón de "un solo commit por sprint, PR stackeado sobre el anterior sin mergear"**
  (Sprints 22-26) funcionó bien para mantener el ritmo sin esperar revisión/merge entre sprints,
  pero acumula una cadena de PRs dependientes (#7→#8→#9→#10→este) que en algún momento hay que
  mergear en orden. Antes de arrancar v1.1, conviene revisar y mergear la cadena pendiente.

## Verificación

`scripts/recommendations_report.py` corrido contra infra real (API real en un puerto separado del
proyecto no relacionado que ocupa el 8000 en la máquina, Postgres real): con la tabla vacía generó
el registro inicial correcto; insertando dos recomendaciones reales sintéticas (una `accepted`,
una `pending` con `created_at` forzado a hace 10 días) confirmó ambos veredictos de "útil" antes de
limpiar los datos de prueba. Sin tests automatizados nuevos — es un script de reporte de una sola
función, verificado en vivo, mismo criterio que otros scripts de `scripts/` (`run_eval.py`,
`demo_sprintNN.py`) que tampoco tienen suite propia.

Durante la verificación se encontró y corrigió un problema de entorno no relacionado con el código
de este sprint: `uv sync` corrido sin `UV_PROJECT_ENVIRONMENT` creó un `.venv` local roto dentro
del repo (la trampa de iCloud ya documentada en la memoria del entorno) — se removió y se confirmó
que el entorno real (`~/.venvs/kos`) seguía intacto, `pytest` volvió a 367 tests verdes.

## Qué se recorta (deuda visible)

Ninguna nueva — este sprint no agrega funcionalidad, solo cierra construcción y revisa lo
acumulado (ver tabla arriba).

## Qué se aprendió

- Cerrar una fase de construcción sin poder declarar el criterio de éxito cumplido en el mismo
  sprint es una situación distinta a cualquier cierre anterior de v0.1-v0.5 — todas esas versiones
  cerraban con una demo verificable en el momento. v1.0 es la primera que depende de tiempo de
  calendario real, no de trabajo completado, y el plan ya lo anticipaba (doc 08) desde que se
  escribió el sprint.
- Revisar la deuda acumulada contra el criterio de salida específico (no solo "¿está resuelta o
  no?") reveló un riesgo que ninguna retro individual había señalado: dos tipos de recomendación
  con ritmos de generación muy distintos (lagunas determinística vs. contradicciones con veredicto
  LLM conservador) pueden hacer que el criterio dependa de uno solo de los dos, no de ambos por
  igual.
