// Tipos del contrato POST /v1/query y de historial de conversaciones, derivados
// del cliente generado desde OpenAPI (`pnpm --filter kos-web generate:api` →
// src/api/schema.d.ts). Regla doc 09 §3: los tipos de la API no se escriben a
// mano — antes de la migración server-side de historial (2026-08-21) esta era
// la única excepción del proyecto; ya no hace falta.

import type { components } from "../../api/schema";

export type QueryRequest = components["schemas"]["QueryRequest"];
export type QueryResponse = components["schemas"]["QueryResponse"];
export type Evidence = components["schemas"]["EvidenceRef"];
export type PlanStep = components["schemas"]["PlanStep"];

export type ConversationOut = components["schemas"]["ConversationOut"];
export type ConversationPage = components["schemas"]["ConversationPage"];
export type ConversationDetail = components["schemas"]["ConversationDetail"];
export type MessageOut = components["schemas"]["MessageOut"];

// Lectura del documento original para el visor de citas.
export type DocumentDetail = components["schemas"]["DocumentDetail"];
export type DocumentChunk = components["schemas"]["ChunkOut"];
export type ChunkPage = components["schemas"]["ChunkPage"];
