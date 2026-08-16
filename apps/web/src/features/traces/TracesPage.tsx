import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { usePlan } from "./usePlan";

const DEGRADED_REASON_LABEL: Record<string, string> = {
  llm_generation: "El LLM no generó un plan válido tras reintentar",
  step_failure: "Un paso individual falló y degradó a evidencia parcial",
  budget_timeout: "Se cortó por presupuesto de tiempo (timeout_s)",
  budget_max_steps: "El plan generado excedía el máximo de pasos permitido",
};

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
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-6 px-6 py-10">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">KOS — Trazas de planes</h1>
        <p className="text-muted-foreground text-sm">
          Un plan es la unidad de depuración (doc 03 §3): qué pasos corrió, cuánto tardó cada
          uno, y por qué se degradó si se degradó.
        </p>
      </header>

      <form
        className="flex items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          void fetchPlan(draft);
        }}
      >
        <input
          className="border-border bg-background h-9 flex-1 rounded-md border px-3 text-sm"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="plan_id"
          aria-label="plan_id"
        />
        <Button type="submit" disabled={loading || !draft.trim()}>
          {loading ? "Buscando…" : "Buscar"}
        </Button>
      </form>

      {error && (
        <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </p>
      )}

      {plan && (
        <div className="space-y-4">
          {plan.degraded && (
            <p className="flex items-center gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-400">
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
              <div
                key={step.id}
                className="rounded-md border border-border px-3 py-2 text-sm"
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
                    confianza:{" "}
                    {typeof step.confidence === "number" ? step.confidence.toFixed(2) : "—"}
                  </span>
                  <span>costo: {step.cost ? `${step.cost.ms.toFixed(0)} ms` : "—"}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {!plan && !loading && !error && (
        <p className="text-muted-foreground text-sm">
          Pegá un plan_id (o abrí uno desde una respuesta del chat) para ver su traza.
        </p>
      )}
    </main>
  );
}
