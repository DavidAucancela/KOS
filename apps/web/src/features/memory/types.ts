// Tipos del contrato /v1/memory, derivados del cliente generado desde OpenAPI
// (`pnpm --filter kos-web generate:api` → src/api/schema.d.ts).
// Regla doc 09 §3: los tipos de la API no se escriben a mano.

import type { components } from "../../api/schema";

export type MemoryItem = components["schemas"]["MemoryOut"];
export type MemoryPage = components["schemas"]["MemoryPage"];
export type MemoryType = MemoryItem["type"];

// Los 5 tipos de memoria del contrato (doc 04 §2). No se puede extraer en
// runtime desde el tipo `MemoryType` (se borra al compilar); si el contrato
// cambia, se agrega acá.
export const MEMORY_TYPES: MemoryType[] = [
  "episodic",
  "semantic",
  "procedural",
  "temporal",
  "preference",
];
