import { useEffect, useState } from "react";
import { AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageContainer, PageHeader } from "@/components/page";
import { DEGRADED_REASON_LABEL } from "@/lib/degradedReasons";
import { cn } from "@/lib/utils";
import type { PlanStep } from "./types";
import { usePlan } from "./usePlan";
import { usePlansList } from "./usePlansList";

function StepCard({ step, muted }: { step: PlanStep; muted?: boolean }) {
  return (
    <div
      className={cn(
        "rounded-md border px-3 py-2 text-sm",
        muted ? "border-border/60 bg-muted/20" : "border-border",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline">{step.id}</Badge>
        <span className="font-medium">{step.agent}</span>
        <span className="text-muted-foreground">{step.task}</span>
        {step.depends_on && step.depends_on.length > 0 && (
          <span className="text-muted-foreground text-xs">
            depende de: {step.depends_on.join(", ")}
          </span>
        )}
      </div>
      <div className="text-muted-foreground mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs">
        <span>evidencia: {step.evidence_count ?? "—"}</span>
        <span>
          confianza: {typeof step.confidence === "number" ? step.confidence.toFixed(2) : "—"}
        </span>
        <span>
          costo:{" "}
          {step.cost
            ? `${step.cost.ms.toFixed(0)} ms${step.cost.tokens ? ` · ${step.cost.tokens} tokens` : ""}`
            : "—"}
        </span>
      </div>
    </div>
  );
}

function RecentPlans({ onSelect }: { onSelect: (planId: string) => void }) {
  const { items, loading, error } = usePlansList();
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-md border border-border">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-sm font-medium"
      >
        {open ? (
          <ChevronDown className="size-4" aria-hidden />
        ) : (
          <ChevronRight className="size-4" aria-hidden />
        )}
        Planes recientes
      </button>
      {open && (
        <div className="space-y-1 border-t border-border p-2">
          {loading && <p className="text-muted-foreground px-2 py-1 text-xs">Cargando…</p>}
          {error && <p className="text-destructive px-2 py-1 text-xs">{error}</p>}
          {!loading && items.length === 0 && (
            <p className="text-muted-foreground px-2 py-1 text-xs">Todavía no hay planes.</p>
          )}
          {items.map((item) => (
            <button
              key={item.plan_id}
              type="button"
              onClick={() => onSelect(item.plan_id)}
              className="hover:bg-muted flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs"
            >
              <span className="min-w-0 flex-1 truncate">{item.query}</span>
              {item.degraded && (
                <Badge variant="outline" className="border-warning/40 text-warning shrink-0">
                  degradado
                </Badge>
              )}
              <span className="text-muted-foreground shrink-0">
                {new Date(item.created_at).toLocaleString()}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// Pantalla mínima de inspección de planes (doc 03 §3 regla 3, doc 06 línea
// 59, Sprint 19): pegar un plan_id (o llegar con uno preseleccionado desde el
// chat) muestra los pasos ejecutados, su costo/confianza y el motivo de
// degradación si lo hubo.
export function TracesPage({ initialPlanId }: { initialPlanId: string | null }) {
  const { plan, loading, error, fetchPlan } = usePlan();
  const [draft, setDraft] = useState(initialPlanId ?? "");

  useEffect(() => {
    if (initialPlanId) {
      setDraft(initialPlanId);
      void fetchPlan(initialPlanId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialPlanId]);

  return (
    <PageContainer>
      <PageHeader
        title="KOS — Trazas de planes"
        description="Un plan es la unidad de depuración (doc 03 §3): qué pasos corrió, cuánto tardó cada uno, y por qué se degradó si se degradó."
      />

      <form
        className="flex items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (!draft.trim()) return;
          void fetchPlan(draft);
        }}
      >
        <Input
          className="flex-1"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="plan_id"
          aria-label="plan_id"
        />
        <Button type="submit" disabled={loading || !draft.trim()}>
          {loading ? "Buscando…" : "Buscar"}
        </Button>
      </form>

      <RecentPlans
        onSelect={(planId) => {
          setDraft(planId);
          void fetchPlan(planId);
        }}
      />

      {error && (
        <p className="border-destructive/30 bg-destructive/10 text-destructive rounded-lg border px-4 py-3 text-sm">
          {error}
        </p>
      )}

      {plan && (
        <div className="space-y-4">
          {plan.degraded && (
            <p className="border-warning/30 bg-warning/10 text-warning flex items-center gap-2 rounded-md border px-3 py-2 text-xs">
              <AlertTriangle className="size-4" aria-hidden />
              Plan degradado
              {plan.degraded_reason && (
                <>: {DEGRADED_REASON_LABEL[plan.degraded_reason] ?? plan.degraded_reason}</>
              )}
            </p>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">{plan.query}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-xs text-muted-foreground">
              <p>trace_id: {plan.trace_id}</p>
              <p>tiempo total: {plan.elapsed_ms.toFixed(0)} ms</p>
            </CardContent>
          </Card>

          <div className="space-y-2">
            {plan.steps.map((step) => (
              <StepCard key={step.id} step={step} />
            ))}
          </div>

          {plan.post.length > 0 && (
            <div className="space-y-2">
              <p className="text-muted-foreground flex items-center gap-2 text-xs font-medium">
                Post-ejecución
                <Badge variant="outline" className="text-muted-foreground">
                  fire-and-forget
                </Badge>
              </p>
              {plan.post.map((step) => (
                <StepCard key={step.id} step={step} muted />
              ))}
            </div>
          )}
        </div>
      )}

      {!plan && !loading && !error && (
        <p className="text-muted-foreground text-sm">
          Pegá un plan_id (o abrí uno desde una respuesta del chat) para ver su traza.
        </p>
      )}
    </PageContainer>
  );
}
