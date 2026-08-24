// Tipos del contrato GET /v1/plans/{id}, derivados del cliente generado desde
// OpenAPI (`pnpm --filter kos-web generate:api` → src/api/schema.d.ts).
// Regla doc 09 §3: los tipos de la API no se escriben a mano.

import type { components } from "../../api/schema";

export type PlanOut = components["schemas"]["PlanOut"];
export type PlanStep = components["schemas"]["PlanStep"];
export type PlanSummary = components["schemas"]["PlanSummary"];
export type PlanPage = components["schemas"]["PlanPage"];
