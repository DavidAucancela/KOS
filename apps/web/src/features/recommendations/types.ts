// Tipos del contrato GET/PATCH /v1/recommendations, derivados del cliente
// generado desde OpenAPI (`pnpm --filter kos-web generate:api` →
// src/api/schema.d.ts). Regla doc 09 §3: los tipos de la API no se escriben
// a mano.

import type { components } from "../../api/schema";

export type Recommendation = components["schemas"]["Recommendation"];
export type RecommendationPage = components["schemas"]["RecommendationPage"];
