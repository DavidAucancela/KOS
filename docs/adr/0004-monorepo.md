# ADR-0004 — Monorepo para todo el sistema

**Estado:** Aceptado
**Fecha:** 2026-07-11

## Contexto

KOS tiene backend Python (API, workers, conectores, agentes), frontend TypeScript y contratos compartidos que evolucionan juntos. Es un proyecto de una persona con ambición de plataforma: la fricción de coordinar repos separados no aporta nada todavía.

## Decisión

Un único monorepo con fronteras internas explícitas: `apps/` (deployables), `packages/` (librerías), `infra/`, `docs/`. Los contratos viven en `packages/core` y son la única dependencia compartida. Tooling: **uv workspaces** para Python y **pnpm** para JS; se añadirá Turborepo/Nx solo cuando el tiempo de build lo justifique.

## Alternativas consideradas

- **Repos separados (api, web, connectors…)** — versionar contratos entre repos, PRs coordinadas y CI multiplicada; para un equipo de 1–3 personas es puro coste. Descartada.
- **Turborepo/Nx desde el día uno** — añade maquinaria de orquestación de builds antes de tener builds lentos. Aplazada, no descartada.

## Consecuencias

- Positivas: un cambio de contrato + sus consumidores en una sola PR atómica; una sola CI; refactors transversales baratos.
- Negativas: hay que vigilar las fronteras internas (import-linter en CI) para que el monorepo no degenere en una bola de barro.
- La estructura por dominios hace trivial extraer un paquete a repo propio si algún día se abre el SDK.
