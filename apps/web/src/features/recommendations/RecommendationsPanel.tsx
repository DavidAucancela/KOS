import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { Recommendation } from "./types";
import { useRecommendations } from "./useRecommendations";

const TYPE_LABEL: Record<string, string> = {
  gap: "Laguna",
  contradiction: "Contradicción",
  related_relation: "Relación",
  roadmap: "Roadmap",
  reorganization: "Reorganización",
};

const STATUS_LABEL: Record<string, string> = {
  accepted: "Aceptada",
  dismissed: "Descartada",
};

function RecommendationCard({
  item,
  onResolve,
}: {
  item: Recommendation;
  onResolve?: (status: "accepted" | "dismissed", reason?: string) => void;
}) {
  const [dismissing, setDismissing] = useState(false);
  const [reason, setReason] = useState("");
  const resolved = item.status !== "pending";

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="flex items-center gap-2 text-sm">{item.title}</CardTitle>
        <div className="flex items-center gap-1">
          {resolved && (
            <Badge variant={item.status === "accepted" ? "success" : "outline"}>
              {STATUS_LABEL[item.status] ?? item.status}
            </Badge>
          )}
          <Badge variant="outline">{TYPE_LABEL[item.type] ?? item.type}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {item.description && (
          <p className="text-muted-foreground text-xs">{item.description}</p>
        )}
        {resolved ? (
          item.dismissed_reason && (
            <p className="text-muted-foreground text-xs">Motivo: {item.dismissed_reason}</p>
          )
        ) : dismissing ? (
          <div className="flex items-center gap-2">
            <Input
              className="h-8 flex-1 text-xs"
              placeholder="¿Por qué? (opcional)"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              aria-label="Motivo del descarte"
              autoFocus
            />
            <Button
              size="sm"
              variant="outline"
              className="border-destructive/30 text-destructive hover:bg-destructive/10"
              onClick={() => onResolve?.("dismissed", reason || undefined)}
            >
              Confirmar
            </Button>
            <Button size="sm" variant="outline" onClick={() => setDismissing(false)}>
              Cancelar
            </Button>
          </div>
        ) : (
          <div className="flex gap-2">
            <Button size="sm" onClick={() => onResolve?.("accepted")}>
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

// Superficie mínima de recomendaciones (doc 11 §7, Sprint 25 + mejoras de
// interfaz posteriores): lista de pendientes con aceptar/descartar, más un
// historial de solo lectura de las ya resueltas — embebida en un panel
// existente, sin pantalla propia nueva (doc 11 §7).
export function RecommendationsPanel() {
  const { items, loading, error, resolve } = useRecommendations();
  const [tab, setTab] = useState<"pending" | "history">("pending");

  const pending = useMemo(() => items.filter((item) => item.status === "pending"), [items]);
  const history = useMemo(() => items.filter((item) => item.status !== "pending"), [items]);
  const visible = tab === "pending" ? pending : history;

  if (loading && items.length === 0) {
    return <p className="text-muted-foreground text-sm">Cargando recomendaciones…</p>;
  }
  if (error) {
    return (
      <p className="border-destructive/30 bg-destructive/10 text-destructive rounded-lg border px-4 py-3 text-sm">
        No se pudieron cargar las recomendaciones ({error}).
      </p>
    );
  }
  if (items.length === 0) return null;

  return (
    <section className="space-y-3">
      <header className="flex items-center gap-2">
        <h2 className="text-sm font-semibold tracking-tight">Recomendaciones</h2>
        {pending.length > 0 && <Badge>{pending.length}</Badge>}
        <div className="ml-auto flex gap-1">
          <Button
            size="sm"
            variant={tab === "pending" ? "default" : "outline"}
            onClick={() => setTab("pending")}
          >
            Pendientes
          </Button>
          <Button
            size="sm"
            variant={tab === "history" ? "default" : "outline"}
            onClick={() => setTab("history")}
          >
            Historial
          </Button>
        </div>
      </header>

      {visible.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          {tab === "pending"
            ? "Sin recomendaciones pendientes por ahora."
            : "Todavía no resolviste ninguna recomendación."}
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {visible.map((item) => (
            <RecommendationCard
              key={item.recommendation_id}
              item={item}
              onResolve={
                tab === "pending"
                  ? (status, reason) => void resolve(item.recommendation_id, status, reason)
                  : undefined
              }
            />
          ))}
        </div>
      )}
    </section>
  );
}
