# Retro — Sprint 0: "El entorno existe"

**Cerrado:** 2026-07-13 · **Fase:** 0 (v0.1 — Fundaciones)

## Qué se demostró

- `make up` levanta la infraestructura completa (Postgres+pgvector, Neo4j, Redis, MinIO); Ollama corre nativo en macOS (perfil `ollama-docker` disponible para otros entornos).
- Los 11 documentos de arquitectura (00–10) y los ADRs 0001–0006 existen y son navegables desde `docs/README.md`.
- CI en verde: validación de enlaces internos de los docs en cada PR.
- Docs **00, 01, 02 y 05 aprobados** (🟢) el 2026-07-13 — habilitan el Sprint 1 y la Fase 1.

## Qué se recortó (deuda visible)

- Docs 03, 04, 06, 07, 08, 09 y 10 siguen en 🟡 Borrador; se aprueban un sprint por delante del código que habilitan (06 y 09 deberían pasar a revisión durante el Sprint 1).
- Los jobs de lint/test de la CI son un placeholder hasta que exista código (se activan en el Sprint 1).
- Sin verificación automática de las reglas de dependencia entre paquetes (import-linter) — pendiente de que existan los paquetes.

## Qué se aprendió

- En macOS con Apple Silicon, Ollama en Docker no accede a la GPU: se decidió usar el Ollama nativo del host y dejar el servicio del compose bajo un perfil opcional.
- Escribir los docs antes que el código obligó a resolver por adelantado decisiones que habrían bloqueado el scaffold (dueño único del esquema de BD, regla de dependencias entre paquetes, contratos en `packages/core`).
