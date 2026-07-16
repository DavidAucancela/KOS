# apps/api

**API pública de KOS** — FastAPI + Pydantic.

Responsabilidades: superficie HTTP (`/v1/*`), autenticación, orquestación de consultas (planner en Fase 4; pipeline fijo antes). No contiene lógica de dominio: eso vive en `packages/`.

- Contratos y rutas: [docs/06-apis-y-contratos.md](../../docs/06-apis-y-contratos.md)
- Se scaffoldea en el **Sprint 1** ([plan de sprints](../../docs/08-plan-de-sprints.md)).
