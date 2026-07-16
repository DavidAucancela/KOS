// Tipos del contrato POST /v1/query y de la lectura de documentos citados.
// TEMPORAL: se migrarán al cliente generado desde OpenAPI (src/api/schema.d.ts,
// `pnpm --filter kos-web generate:api`). No añadir aquí tipos de la API a mano
// una vez exista el generado.

export type QueryMode = "hybrid" | "lexical" | "vector";

export interface QueryRequest {
  query: string;
  limit?: number;
  mode?: QueryMode;
}

export interface Evidence {
  doc_id: string;
  chunk_id: string | null;
  quote: string | null;
  title: string | null;
  source_id: string | null;
  connector: string | null;
  score: number | null;
}

export interface PlanStep {
  id: string;
  agent: string;
  task: string;
  depends_on: string[];
  evidence_count?: number;
}

export interface QueryResponse {
  query: string;
  answer: string;
  evidence: Evidence[];
  confidence: number;
  plan: PlanStep[];
  degraded: boolean;
  trace_id: string;
}

// Lectura del documento original para el visor de citas.
export interface DocumentDetail {
  doc_id: string;
  title: string | null;
  source_id: string | null;
  connector: string | null;
  summary: string | null;
}

export interface DocumentChunk {
  chunk_id: string;
  doc_id: string;
  text: string;
  position: number;
  metadata: Record<string, unknown>;
}

export interface ChunkPage {
  items: DocumentChunk[];
  next_cursor: number | null;
}
