import { useCallback, useEffect, useState } from "react";

import { errorMessage } from "@/lib/api";
import type { MemoryProposal } from "./types";

export interface UseMemoryProposalsResult {
  items: MemoryProposal[];
  loading: boolean;
  error: string | null;
  resolve: (id: string, status: "approved" | "rejected", reason?: string) => Promise<void>;
}

// Mismo patrón que useRecommendations: un solo fetch sin filtrar por status,
// pendientes/historial se derivan client-side — volumen bajo (un `store`
// pendiente por consulta del Planner que decide guardar algo, no por request).
export function useMemoryProposals(): UseMemoryProposalsResult {
  const [items, setItems] = useState<MemoryProposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch("/v1/memory/proposals?limit=100");
      if (!response.ok) {
        setError(await errorMessage(response));
        return;
      }
      const body = (await response.json()) as { items?: MemoryProposal[] };
      setItems(Array.isArray(body.items) ? body.items : []);
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchAll();
  }, [fetchAll]);

  const resolve = useCallback(
    async (id: string, status: "approved" | "rejected", reason?: string) => {
      const response = await fetch(`/v1/memory/proposals/${encodeURIComponent(id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status, reason }),
      });
      if (!response.ok) {
        setError(await errorMessage(response));
        return;
      }
      const updated = (await response.json()) as MemoryProposal;
      setItems((current) =>
        current.map((item) => (item.proposal_id === id ? updated : item)),
      );
    },
    [],
  );

  return { items, loading, error, resolve };
}
