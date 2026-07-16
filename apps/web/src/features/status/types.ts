// Tipos del contrato GET /health, derivados del cliente generado desde OpenAPI
// (`pnpm --filter kos-web generate:api` → src/api/schema.d.ts).
// Regla doc 09 §3: los tipos de la API no se escriben a mano.

import type { components } from "../../api/schema";

export type ServiceStatus = components["schemas"]["ServiceStatus"];
export type HealthResponse = components["schemas"]["HealthResponse"];
export type ServiceState = ServiceStatus["status"];
