// Tipos del contrato GET/PATCH /v1/memory/proposals, derivados del cliente
// generado desde OpenAPI (`pnpm --filter kos-web generate:api` →
// src/api/schema.d.ts). Regla doc 09 §3: los tipos de la API no se escriben
// a mano.

import type { components } from "../../api/schema";

export type MemoryProposal = components["schemas"]["MemoryProposal"];
export type MemoryProposalPage = components["schemas"]["MemoryProposalPage"];
