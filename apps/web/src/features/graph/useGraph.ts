import { useCallback, useState } from "react";

import type {
  GraphNode,
  GraphRelation,
  NodeType,
  NodeWithNeighborhood,
  RelationType,
} from "./types";

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // el body no era JSON (o no traía `detail`) — se usa el status.
  }
  return `HTTP ${response.status}`;
}

export interface UseGraphResult {
  nodes: GraphNode[];
  relations: GraphRelation[];
  nodesLoading: boolean;
  nodesError: string | null;
  search: (nodeType: NodeType | null) => Promise<void>;

  selected: NodeWithNeighborhood | null;
  selectedLoading: boolean;
  selectedError: string | null;
  selectNode: (nodeId: string) => Promise<void>;

  mutating: boolean;
  mutationError: string | null;
  correctNode: (
    nodeId: string,
    patch: { canonical_name?: string; node_type?: NodeType },
  ) => Promise<void>;
  correctRelation: (
    relationId: string,
    patch: { relation_type?: RelationType },
  ) => Promise<void>;
  rejectRelation: (relationId: string) => Promise<void>;
}

// Pantalla de corrección del grafo (doc 06 §2, Sprint 9) contra /v1/graph/*
// (proxy de Vite → apps/api): tabla de búsqueda + vecindario + formularios de
// corrección, más la visualización (Sprint 10) sobre el mismo `nodes`/
// `relations` — el template `subgraph` trae ambos en una sola llamada.
export function useGraph(): UseGraphResult {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [relations, setRelations] = useState<GraphRelation[]>([]);
  const [nodesLoading, setNodesLoading] = useState(false);
  const [nodesError, setNodesError] = useState<string | null>(null);

  const [selected, setSelected] = useState<NodeWithNeighborhood | null>(null);
  const [selectedLoading, setSelectedLoading] = useState(false);
  const [selectedError, setSelectedError] = useState<string | null>(null);

  const [mutating, setMutating] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);

  const search = useCallback(async (nodeType: NodeType | null) => {
    setNodesLoading(true);
    setNodesError(null);
    try {
      const response = await fetch("/v1/graph/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          template: "subgraph",
          node_type: nodeType,
          limit: 20,
        }),
      });
      if (!response.ok) {
        setNodesError(await errorMessage(response));
        return;
      }
      const body = (await response.json()) as {
        nodes?: GraphNode[] | null;
        relations?: GraphRelation[] | null;
      };
      setNodes(body.nodes ?? []);
      setRelations(body.relations ?? []);
    } catch (cause) {
      setNodesError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setNodesLoading(false);
    }
  }, []);

  const selectNode = useCallback(async (nodeId: string) => {
    setSelectedLoading(true);
    setSelectedError(null);
    try {
      const response = await fetch(`/v1/graph/nodes/${encodeURIComponent(nodeId)}`);
      if (!response.ok) {
        setSelected(null);
        setSelectedError(await errorMessage(response));
        return;
      }
      setSelected((await response.json()) as NodeWithNeighborhood);
    } catch (cause) {
      setSelected(null);
      setSelectedError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setSelectedLoading(false);
    }
  }, []);

  const correctNode = useCallback(
    async (nodeId: string, patch: { canonical_name?: string; node_type?: NodeType }) => {
      setMutating(true);
      setMutationError(null);
      try {
        const response = await fetch(`/v1/graph/nodes/${encodeURIComponent(nodeId)}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(patch),
        });
        if (!response.ok) {
          setMutationError(await errorMessage(response));
          return;
        }
        await selectNode(nodeId);
      } catch (cause) {
        setMutationError(cause instanceof Error ? cause.message : String(cause));
      } finally {
        setMutating(false);
      }
    },
    [selectNode],
  );

  const correctRelation = useCallback(
    async (relationId: string, patch: { relation_type?: RelationType }) => {
      if (selected === null) return;
      setMutating(true);
      setMutationError(null);
      try {
        const response = await fetch(`/v1/graph/relations/${encodeURIComponent(relationId)}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(patch),
        });
        if (!response.ok) {
          setMutationError(await errorMessage(response));
          return;
        }
        await selectNode(selected.node.id);
      } catch (cause) {
        setMutationError(cause instanceof Error ? cause.message : String(cause));
      } finally {
        setMutating(false);
      }
    },
    [selected, selectNode],
  );

  const rejectRelation = useCallback(
    async (relationId: string) => {
      if (selected === null) return;
      setMutating(true);
      setMutationError(null);
      try {
        const response = await fetch(`/v1/graph/relations/${encodeURIComponent(relationId)}`, {
          method: "DELETE",
        });
        if (!response.ok && response.status !== 204) {
          setMutationError(await errorMessage(response));
          return;
        }
        await selectNode(selected.node.id);
      } catch (cause) {
        setMutationError(cause instanceof Error ? cause.message : String(cause));
      } finally {
        setMutating(false);
      }
    },
    [selected, selectNode],
  );

  return {
    nodes,
    relations,
    nodesLoading,
    nodesError,
    search,
    selected,
    selectedLoading,
    selectedError,
    selectNode,
    mutating,
    mutationError,
    correctNode,
    correctRelation,
    rejectRelation,
  };
}
