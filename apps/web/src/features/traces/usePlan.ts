import { useCallback, useState } from "react";

import { errorMessage } from "@/lib/api";
import type { PlanOut } from "./types";

export interface UsePlanResult {
  plan: PlanOut | null;
  loading: boolean;
  error: string | null;
  fetchPlan: (planId: string) => Promise<void>;
}

// Auditoría de un plan ejecutado (doc 06 línea 59, Sprint 19) contra
// /v1/plans/{id} (proxy de Vite → apps/api) — mismo patrón que `useGraph`.
export function usePlan(): UsePlanResult {
  const [plan, setPlan] = useState<PlanOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPlan = useCallback(async (planId: string) => {
    const trimmed = planId.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/v1/plans/${encodeURIComponent(trimmed)}`);
      if (!response.ok) {
        setPlan(null);
        setError(await errorMessage(response));
        return;
      }
      setPlan((await response.json()) as PlanOut);
    } catch (cause) {
      setPlan(null);
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setLoading(false);
    }
  }, []);

  return { plan, loading, error, fetchPlan };
}
