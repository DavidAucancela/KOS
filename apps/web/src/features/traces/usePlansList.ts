import { useCallback, useEffect, useState } from "react";

import { errorMessage } from "@/lib/api";
import type { PlanSummary } from "./types";

export interface UsePlansListResult {
  items: PlanSummary[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

// "Planes recientes" (doc 06 §2 addendum 2026-08-21) contra GET /v1/plans —
// da un camino a Trazas que no depende de pegar un plan_id ni de venir desde
// el chat.
export function usePlansList(): UsePlansListResult {
  const [items, setItems] = useState<PlanSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/v1/plans?limit=20");
      if (!response.ok) {
        setError(await errorMessage(response));
        return;
      }
      const page = (await response.json()) as { items?: PlanSummary[] };
      setItems(Array.isArray(page.items) ? page.items : []);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { items, loading, error, refresh };
}
