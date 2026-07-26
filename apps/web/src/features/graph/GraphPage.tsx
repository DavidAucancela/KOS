import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useGraph } from "./useGraph";
import { NODE_TYPES, RELATION_TYPES, type NodeType, type RelationType } from "./types";

// Pantalla mínima de corrección del grafo (doc 06 §2, Sprint 9): tabla de
// nodos + vecindario + formularios inline. La visualización real (canvas)
// es el Sprint 10 — esto es deliberadamente una tabla, no un grafo dibujado.
export function GraphPage() {
  const graph = useGraph();
  const [typeFilter, setTypeFilter] = useState<NodeType | "">("");
  const [nameDraft, setNameDraft] = useState("");
  const [typeDraft, setTypeDraft] = useState<NodeType | "">("");

  useEffect(() => {
    void graph.search(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (graph.selected) {
      setNameDraft(graph.selected.node.canonical_name);
      setTypeDraft(graph.selected.node.node_type);
    }
  }, [graph.selected]);

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-6 px-6 py-10">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">KOS — Grafo de conocimiento</h1>
        <p className="text-muted-foreground text-sm">
          Corrección manual (doc 02 §4 regla 5): lo que edites acá queda protegido de la
          próxima sincronización.
        </p>
      </header>

      <section className="flex items-center gap-2">
        <select
          className="border-border bg-background h-9 rounded-md border px-3 text-sm"
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
        </select>
        <Button onClick={() => void graph.search(typeFilter || null)} disabled={graph.nodesLoading}>
          {graph.nodesLoading ? "Buscando…" : "Buscar"}
        </Button>
        <span className="text-muted-foreground text-xs">
          Ordenado por cantidad de relaciones (para priorizar qué revisar).
        </span>
      </section>

      {graph.nodesError && (
        <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {graph.nodesError}
        </p>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Nodos</CardTitle>
          </CardHeader>
          <CardContent>
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
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Detalle</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {graph.selectedLoading && <p className="text-muted-foreground text-sm">Cargando…</p>}
            {graph.selectedError && (
              <p className="text-sm text-red-400">{graph.selectedError}</p>
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
                  <input
                    id="canonical-name"
                    className="border-border bg-background h-9 w-full rounded-md border px-3 text-sm"
                    value={nameDraft}
                    onChange={(event) => setNameDraft(event.target.value)}
                  />
                  <select
                    className="border-border bg-background h-9 w-full rounded-md border px-3 text-sm"
                    value={typeDraft}
                    onChange={(event) => setTypeDraft(event.target.value as NodeType)}
                    aria-label="Tipo de nodo"
                  >
                    {NODE_TYPES.map((type) => (
                      <option key={type} value={type}>
                        {type}
                      </option>
                    ))}
                  </select>
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
                  <p className="text-sm text-red-400">{graph.mutationError}</p>
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
    </main>
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
      <select
        className="border-border bg-background h-8 rounded-md border px-2 text-xs"
        value={relationDraft}
        onChange={(event) => setRelationDraft(event.target.value as RelationType)}
        aria-label="Tipo de relación"
      >
        {RELATION_TYPES.map((type) => (
          <option key={type} value={type}>
            {type}
          </option>
        ))}
      </select>
      <Button size="sm" variant="outline" disabled={busy} onClick={() => onCorrect(relationDraft)}>
        Corregir
      </Button>
      <Button size="sm" variant="outline" disabled={busy} onClick={onReject}>
        Rechazar
      </Button>
    </li>
  );
}
