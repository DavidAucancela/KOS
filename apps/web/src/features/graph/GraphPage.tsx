import { useEffect, useMemo, useState } from "react";
import { Route } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { PageContainer, PageHeader } from "@/components/page";
import { GraphCanvas } from "./GraphCanvas";
import { useGraph } from "./useGraph";
import { NODE_TYPE_COLORS, NODE_TYPES, RELATION_TYPES, type NodeType, type RelationType } from "./types";

type ViewMode = "graph" | "table";

// Pantalla de corrección del grafo (doc 06 §2, Sprint 9: vecindario +
// formularios inline; Sprint 10: visualización de fuerzas sobre el mismo
// conjunto de nodos, con la tabla como alternativa para revisar en detalle).
export function GraphPage() {
  const graph = useGraph();
  const [viewMode, setViewMode] = useState<ViewMode>("graph");
  const [typeFilter, setTypeFilter] = useState<NodeType | "">("");
  const [nameDraft, setNameDraft] = useState("");
  const [typeDraft, setTypeDraft] = useState<NodeType | "">("");
  // Modo "resaltar camino" (doc 13 §5.2): el usuario elige dos nodos y se pide
  // `GET /v1/graph/path`. Mientras está activo, clickear un nodo no abre su
  // vecindario — fija un extremo.
  const [pathMode, setPathMode] = useState(false);
  const [pathFrom, setPathFrom] = useState<string | null>(null);

  useEffect(() => {
    void graph.search(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const highlightNodeIds = useMemo(
    () => (graph.path ? new Set(graph.path.nodeIds) : undefined),
    [graph.path],
  );
  const highlightRelationIds = useMemo(
    () => (graph.path ? new Set(graph.path.relationIds) : undefined),
    [graph.path],
  );

  const exitPathMode = () => {
    setPathMode(false);
    setPathFrom(null);
  };

  const handleNodeSelect = (nodeId: string) => {
    if (!pathMode) {
      void graph.selectNode(nodeId);
      return;
    }
    if (pathFrom === null) {
      setPathFrom(nodeId);
      return;
    }
    if (nodeId !== pathFrom) void graph.findPath(pathFrom, nodeId);
    exitPathMode();
  };

  useEffect(() => {
    if (graph.selected) {
      setNameDraft(graph.selected.node.canonical_name);
      setTypeDraft(graph.selected.node.node_type);
    }
  }, [graph.selected]);

  return (
    <PageContainer wide>
      <PageHeader
        title="KOS — Grafo de conocimiento"
        description="Corrección manual (doc 02 §4 regla 5): lo que edites acá queda protegido de la próxima sincronización."
      />

      <section className="flex items-center gap-2">
        <Select
          value={typeFilter}
          onChange={(event) => setTypeFilter(event.target.value as NodeType | "")}
          aria-label="Filtrar por tipo de nodo"
        >
          <option value="">Todos los tipos</option>
          {NODE_TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </Select>
        <Button onClick={() => void graph.search(typeFilter || null)} disabled={graph.nodesLoading}>
          {graph.nodesLoading ? "Buscando…" : "Buscar"}
        </Button>
        <span className="text-muted-foreground text-xs">
          Ordenado por cantidad de relaciones (para priorizar qué revisar).
        </span>
        <div className="ml-auto flex gap-1">
          {viewMode === "graph" && (
            <Button
              size="sm"
              variant={pathMode ? "default" : "outline"}
              onClick={() => (pathMode ? exitPathMode() : setPathMode(true))}
              className="gap-1"
            >
              <Route className="size-3.5" aria-hidden />
              {pathMode ? "Cancelar" : "Resaltar camino"}
            </Button>
          )}
          <Button
            size="sm"
            variant={viewMode === "graph" ? "default" : "outline"}
            onClick={() => setViewMode("graph")}
          >
            Grafo
          </Button>
          <Button
            size="sm"
            variant={viewMode === "table" ? "default" : "outline"}
            onClick={() => setViewMode("table")}
          >
            Tabla
          </Button>
        </div>
      </section>

      {viewMode === "graph" && (pathMode || graph.path || graph.pathError) && (
        <p className="text-muted-foreground flex items-center gap-2 text-xs">
          {pathMode
            ? pathFrom === null
              ? "Elegí el nodo de origen."
              : "Elegí el nodo de destino."
            : graph.pathLoading
              ? "Buscando camino…"
              : graph.pathError
                ? graph.pathError
                : `Camino resaltado: ${graph.path?.nodeIds.length ?? 0} nodos.`}
          {!pathMode && (graph.path || graph.pathError) && (
            <button
              type="button"
              onClick={graph.clearPath}
              className="text-primary hover:underline"
            >
              Limpiar
            </button>
          )}
        </p>
      )}

      {viewMode === "graph" && (
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {NODE_TYPES.map((type) => (
            <span key={type} className="text-muted-foreground flex items-center gap-1.5 text-xs">
              <span
                className="inline-block size-2.5 rounded-full"
                style={{ backgroundColor: NODE_TYPE_COLORS[type] }}
                aria-hidden
              />
              {type}
            </span>
          ))}
        </div>
      )}

      {graph.nodesError && (
        <p className="border-destructive/30 bg-destructive/10 text-destructive rounded-lg border px-4 py-3 text-sm">
          {graph.nodesError}
        </p>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{viewMode === "graph" ? "Grafo" : "Nodos"}</CardTitle>
          </CardHeader>
          <CardContent>
            {viewMode === "graph" ? (
              <GraphCanvas
                nodes={graph.nodes}
                relations={graph.relations}
                selectedId={graph.selected?.node.id ?? null}
                onSelect={handleNodeSelect}
                highlightNodeIds={highlightNodeIds}
                highlightRelationIds={highlightRelationIds}
                endpointIds={pathFrom ? [pathFrom] : undefined}
              />
            ) : (
              <table className="w-full text-sm">
                <thead className="text-muted-foreground text-left text-xs">
                  <tr>
                    <th className="pb-2">Nombre</th>
                    <th className="pb-2">Tipo</th>
                    <th className="pb-2">Confianza</th>
                  </tr>
                </thead>
                <tbody>
                  {graph.nodes.map((node) => (
                    <tr
                      key={node.id}
                      onClick={() => void graph.selectNode(node.id)}
                      className="hover:bg-muted cursor-pointer border-t border-border"
                      aria-selected={graph.selected?.node.id === node.id}
                    >
                      <td className="py-2 pr-2">
                        {node.canonical_name}
                        {node.locked && (
                          <Badge variant="outline" className="ml-2">
                            corregido
                          </Badge>
                        )}
                      </td>
                      <td className="py-2 pr-2">{node.node_type}</td>
                      <td className="py-2">{node.confidence.toFixed(2)}</td>
                    </tr>
                  ))}
                  {graph.nodes.length === 0 && !graph.nodesLoading && (
                    <tr>
                      <td colSpan={3} className="text-muted-foreground py-4 text-center">
                        Sin resultados.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Detalle</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {graph.selectedLoading && <p className="text-muted-foreground text-sm">Cargando…</p>}
            {graph.selectedError && (
              <p className="text-destructive text-sm">{graph.selectedError}</p>
            )}
            {graph.selected && (
              <>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <label className="text-muted-foreground block text-xs" htmlFor="canonical-name">
                      Nombre canónico
                    </label>
                    {graph.selected.node.locked && <Badge variant="outline">corregido</Badge>}
                  </div>
                  <Input
                    id="canonical-name"
                    className="w-full"
                    value={nameDraft}
                    onChange={(event) => setNameDraft(event.target.value)}
                  />
                  <Select
                    className="w-full"
                    value={typeDraft}
                    onChange={(event) => setTypeDraft(event.target.value as NodeType)}
                    aria-label="Tipo de nodo"
                  >
                    {NODE_TYPES.map((type) => (
                      <option key={type} value={type}>
                        {type}
                      </option>
                    ))}
                  </Select>
                  <Button
                    size="sm"
                    disabled={graph.mutating}
                    onClick={() =>
                      void graph.correctNode(graph.selected!.node.id, {
                        canonical_name: nameDraft,
                        node_type: typeDraft || undefined,
                      })
                    }
                  >
                    Corregir nodo
                  </Button>
                </div>

                {graph.mutationError && (
                  <p className="text-destructive text-sm">{graph.mutationError}</p>
                )}

                <div>
                  <h3 className="mb-2 text-xs font-medium tracking-tight">
                    Vecinos ({graph.selected.neighbors.length})
                  </h3>
                  <ul className="space-y-2">
                    {graph.selected.neighbors.map((neighbor) => (
                      <NeighborRow
                        key={neighbor.relation.id}
                        neighbor={neighbor}
                        onCorrect={(relationType) =>
                          void graph.correctRelation(neighbor.relation.id, {
                            relation_type: relationType,
                          })
                        }
                        onReject={() => void graph.rejectRelation(neighbor.relation.id)}
                        busy={graph.mutating}
                      />
                    ))}
                    {graph.selected.neighbors.length === 0 && (
                      <li className="text-muted-foreground text-sm">Sin relaciones activas.</li>
                    )}
                  </ul>
                </div>
              </>
            )}
            {!graph.selected && !graph.selectedLoading && (
              <p className="text-muted-foreground text-sm">
                Elegí un nodo de la lista para ver su vecindario.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </PageContainer>
  );
}

function NeighborRow({
  neighbor,
  onCorrect,
  onReject,
  busy,
}: {
  neighbor: NonNullable<ReturnType<typeof useGraph>["selected"]>["neighbors"][number];
  onCorrect: (relationType: RelationType) => void;
  onReject: () => void;
  busy: boolean;
}) {
  const [relationDraft, setRelationDraft] = useState<RelationType>(neighbor.relation.relation_type);

  return (
    <li className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-2 text-sm">
      <span className="min-w-0 flex-1 truncate">
        {neighbor.direction === "outgoing" ? "→" : "←"} {neighbor.relation.relation_type} —{" "}
        {neighbor.node.canonical_name}
        <span className="text-muted-foreground ml-1 text-xs">({neighbor.node.node_type})</span>
      </span>
      <Select
        className="h-8 text-xs"
        value={relationDraft}
        onChange={(event) => setRelationDraft(event.target.value as RelationType)}
        aria-label="Tipo de relación"
      >
        {RELATION_TYPES.map((type) => (
          <option key={type} value={type}>
            {type}
          </option>
        ))}
      </Select>
      <Button size="sm" variant="outline" disabled={busy} onClick={() => onCorrect(relationDraft)}>
        Corregir
      </Button>
      <Button size="sm" variant="outline" disabled={busy} onClick={onReject}>
        Rechazar
      </Button>
    </li>
  );
}
