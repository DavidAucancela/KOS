import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Recommendation } from "./types";
import { useRecommendations } from "./useRecommendations";

const TYPE_LABEL: Record<string, string> = {
  gap: "Laguna",
  contradiction: "Contradicción",
  related_relation: "Relación",
  roadmap: "Roadmap",
  reorganization: "Reorganización",
};

function RecommendationCard({
  item,
  onResolve,
}: {
  item: Recommendation;
  onResolve: (status: "accepted" | "dismissed", reason?: string) => void;
}) {
  const [dismissing, setDismissing] = useState(false);
  const [reason, setReason] = useState("");

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="flex items-center gap-2 text-sm">{item.title}</CardTitle>
        <Badge variant="outline">{TYPE_LABEL[item.type] ?? item.type}</Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        {item.description && (
          <p className="text-muted-foreground text-xs">{item.description}</p>
        )}
        {dismissing ? (
          <div className="flex items-center gap-2">
            <input
              className="border-border bg-background h-8 flex-1 rounded-md border px-2 text-xs"
              placeholder="¿Por qué? (opcional)"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              aria-label="Motivo del descarte"
              autoFocus
            />
            <Button
              size="sm"
              variant="outline"
              className="border-red-500/30 text-red-400 hover:bg-red-500/10"
              onClick={() => onResolve("dismissed", reason || undefined)}
            >
              Confirmar
            </Button>
            <Button size="sm" variant="outline" onClick={() => setDismissing(false)}>
              Cancelar
            </Button>
          </div>
        ) : (
          <div className="flex gap-2">
            <Button size="sm" onClick={() => onResolve("accepted")}>
              Aceptar
            </Button>
            <Button size="sm" variant="outline" onClick={() => setDismissing(true)}>
              Descartar
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// Superficie mínima de recomendaciones (doc 11 §7, Sprint 25): lista de
// pendientes con aceptar/descartar, embebida en un panel existente — sin
// pantalla propia nueva, el criterio de éxito de v1.0 no la exige.
export function RecommendationsPanel() {
  const { items, loading, error, resolve } = useRecommendations();

  if (loading && items.length === 0) return null;
  if (error) {
    return (
      <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
        No se pudieron cargar las recomendaciones ({error}).
      </p>
    );
  }
  if (items.length === 0) return null;

  return (
    <section className="space-y-3">
      <header className="flex items-center gap-2">
        <h2 className="text-sm font-semibold tracking-tight">Recomendaciones</h2>
        <Badge>{items.length}</Badge>
      </header>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {items.map((item) => (
          <RecommendationCard
            key={item.recommendation_id}
            item={item}
            onResolve={(status, reason) => void resolve(item.recommendation_id, status, reason)}
          />
        ))}
      </div>
    </section>
  );
}
