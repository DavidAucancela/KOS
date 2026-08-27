import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useMemoryProposals } from "./useMemoryProposals";
import type { MemoryProposal } from "./types";

const STATUS_LABEL: Record<string, string> = {
  approved: "Aprobada",
  rejected: "Rechazada",
};

function ProposalCard({
  item,
  onResolve,
}: {
  item: MemoryProposal;
  onResolve?: (status: "approved" | "rejected", reason?: string) => void;
}) {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const resolved = item.status !== "pending";

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="text-sm">{item.query}</CardTitle>
        {resolved && (
          <Badge variant={item.status === "approved" ? "success" : "outline"}>
            {STATUS_LABEL[item.status] ?? item.status}
          </Badge>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-muted-foreground text-xs">{item.answer}</p>
        {resolved ? (
          item.rejected_reason && (
            <p className="text-muted-foreground text-xs">Motivo: {item.rejected_reason}</p>
          )
        ) : rejecting ? (
          <div className="flex items-center gap-2">
            <Input
              className="h-8 flex-1 text-xs"
              placeholder="¿Por qué? (opcional)"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              aria-label="Motivo del rechazo"
              autoFocus
            />
            <Button
              size="sm"
              variant="outline"
              className="border-destructive/30 text-destructive hover:bg-destructive/10"
              onClick={() => onResolve?.("rejected", reason || undefined)}
            >
              Confirmar
            </Button>
            <Button size="sm" variant="outline" onClick={() => setRejecting(false)}>
              Cancelar
            </Button>
          </div>
        ) : (
          <div className="flex gap-2">
            <Button size="sm" onClick={() => onResolve?.("approved")}>
              Aprobar
            </Button>
            <Button size="sm" variant="outline" onClick={() => setRejecting(true)}>
              Rechazar
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// El Planner puede proponer guardar memoria (agent="memory", operation="store")
// pero nunca la auto-aprueba: `executor.py` fuerza confirm=False siempre, y
// el intento queda acá para revisión humana (mitigación del riesgo
// documentado en docs/deuda-tecnica.md). Mismo patrón de panel que
// RecommendationsPanel (Sprint 25).
export function MemoryProposalsPanel() {
  const { items, loading, error, resolve } = useMemoryProposals();
  const [tab, setTab] = useState<"pending" | "history">("pending");

  const pending = useMemo(() => items.filter((item) => item.status === "pending"), [items]);
  const history = useMemo(() => items.filter((item) => item.status !== "pending"), [items]);
  const visible = tab === "pending" ? pending : history;

  if (loading && items.length === 0) {
    return <p className="text-muted-foreground text-sm">Cargando propuestas de memoria…</p>;
  }
  if (error) {
    return (
      <p className="border-destructive/30 bg-destructive/10 text-destructive rounded-lg border px-4 py-3 text-sm">
        No se pudieron cargar las propuestas de memoria ({error}).
      </p>
    );
  }
  if (items.length === 0) return null;

  return (
    <section className="space-y-3">
      <header className="flex items-center gap-2">
        <h2 className="text-sm font-semibold tracking-tight">Propuestas de memoria</h2>
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
            ? "Sin propuestas de memoria pendientes por ahora."
            : "Todavía no resolviste ninguna propuesta."}
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {visible.map((item) => (
            <ProposalCard
              key={item.proposal_id}
              item={item}
              onResolve={
                tab === "pending"
                  ? (status, reason) => void resolve(item.proposal_id, status, reason)
                  : undefined
              }
            />
          ))}
        </div>
      )}
    </section>
  );
}
