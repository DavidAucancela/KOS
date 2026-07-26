// Tipos del contrato /v1/graph, derivados del cliente generado desde OpenAPI
// (`pnpm --filter kos-web generate:api` → src/api/schema.d.ts).
// Regla doc 09 §3: los tipos de la API no se escriben a mano.

import type { components } from "../../api/schema";

export type GraphNode = components["schemas"]["GraphNode"];
export type GraphRelation = components["schemas"]["GraphRelation"];
export type GraphNeighbor = components["schemas"]["GraphNeighbor"];
export type NodeWithNeighborhood = components["schemas"]["NodeWithNeighborhood"];
export type GraphQueryResponse = components["schemas"]["GraphQueryResponse"];
export type NodeType = GraphNode["node_type"];
export type RelationType = GraphRelation["relation_type"];

// Los 9 tipos de nodo de la ontología cerrada (doc 02 §3.1). No se puede
// extraer en runtime desde el tipo `NodeType` (se borra al compilar) — si la
// ontología cambia, un tipo nuevo requiere ADR (doc 02 §4 regla 1) y también
// se agrega acá.
export const NODE_TYPES: NodeType[] = [
  "Person",
  "Project",
  "Technology",
  "Concept",
  "Document",
  "Task",
  "Organization",
  "Event",
  "Skill",
];

export const RELATION_TYPES: RelationType[] = [
  "USES",
  "RELATED_TO",
  "AUTHORED_BY",
  "PART_OF",
  "DEPENDS_ON",
  "PREREQUISITE_OF",
  "MENTIONS",
  "KNOWS",
  "CONTRADICTS",
  "SUPERSEDES",
];
