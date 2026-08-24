import { useCallback, useEffect, useState } from "react";

import { errorMessage } from "@/lib/api";
import type { PlanMetricsOut, SinceRange } from "./types";

export interface UseMetricsResult {
  metrics: PlanMetricsOut | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

// Métricas agregadas del Planner (doc 06 §2 addendum 2026-08-21) contra
// GET /v1/plans/metrics. `bucket` se elige según el rango para no pedir 720
// puntos por hora en la vista de 30 días.
export function useMetrics(sinceHours: SinceRange): UseMetricsResult {
  const [metrics, setMetrics] = useState<PlanMetricsOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const bucket = sinceHours > 24 ? "day" : "hour";
      const response = await fetch(
        `/v1/plans/metrics?since_hours=${sinceHours}&bucket=${bucket}`,
      );
      if (!response.ok) {
        setError(await errorMessage(response));
        return;
      }
      setMetrics((await response.json()) as PlanMetricsOut);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setLoading(false);
    }
  }, [sinceHours]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { metrics, loading, error, refresh };
}
