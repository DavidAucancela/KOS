// Tipos del contrato /v1/graph, derivados del cliente generado desde OpenAPI
// (`pnpm --filter kos-web generate:api` → src/api/schema.d.ts).
// Regla doc 09 §3: los tipos de la API no se escriben a mano.

import type { components } from "../../api/schema";

export type GraphNode = components["schemas"]["GraphNode"];
export type GraphRelation = components["schemas"]["GraphRelation"];
export type GraphNeighbor = components["schemas"]["GraphNeighbor"];
export type NodeWithNeighborhood = components["schemas"]["NodeWithNeighborhood"];
export type GraphQueryResponse = components["schemas"]["GraphQueryResponse"];
export type GraphPathOut = components["schemas"]["GraphPathOut"];
export type NodeType = GraphNode["node_type"];
export type RelationType = GraphRelation["relation_type"];

// Colores por tipo de nodo (Sprint 10, visualización): mismo orden que
// NODE_TYPES para que el color sea estable si la ontología crece.
export const NODE_TYPE_COLORS: Record<NodeType, string> = {
  Person: "#f472b6",
  Project: "#60a5fa",
  Technology: "#34d399",
  Concept: "#a78bfa",
  Document: "#fbbf24",
  Task: "#fb923c",
  Organization: "#22d3ee",
  Event: "#f87171",
  Skill: "#a3e635",
};

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
