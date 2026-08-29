import { useCallback, useEffect, useState } from "react";

import { errorMessage } from "@/lib/api";
import type { MemoryItem, MemoryType } from "./types";

export interface MemoryFilters {
  type: MemoryType | "";
  q: string;
}

export interface UseMemoryResult {
  items: MemoryItem[];
  nextCursor: string | null;
  loading: boolean;
  error: string | null;
  filters: MemoryFilters;
  applyFilters: (next: MemoryFilters) => void;
  loadMore: () => void;

  mutating: boolean;
  mutationError: string | null;
  correct: (
    id: string,
    patch: { content?: string; type?: MemoryType; confidence?: number },
  ) => Promise<void>;
  archive: (id: string) => Promise<void>;
}

const PAGE_SIZE = 20;

// Auditoría de memoria (doc 13 §4, doc 04 §5) contra /v1/memory (proxy de Vite
// → apps/api): listado con filtros + paginación por cursor, corrección manual
// (`PATCH`, fija `locked`) y archivado (`DELETE`). Sin endpoints nuevos — mismo
// molde que useGraph.
export function useMemory(): UseMemoryResult {
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<MemoryFilters>({ type: "", q: "" });

  const [mutating, setMutating] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);

  const fetchPage = useCallback(
    async (active: MemoryFilters, cursor: string | null) => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
        if (active.type) params.set("type", active.type);
        if (active.q.trim()) params.set("q", active.q.trim());
        if (cursor) params.set("cursor", cursor);
        const response = await fetch(`/v1/memory?${params.toString()}`);
        if (!response.ok) {
          setError(await errorMessage(response));
          return;
        }
        const body = (await response.json()) as {
          items?: MemoryItem[] | null;
          next_cursor?: string | null;
        };
        setItems((current) =>
          cursor ? [...current, ...(body.items ?? [])] : (body.items ?? []),
        );
        setNextCursor(body.next_cursor ?? null);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : String(cause));
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    void fetchPage({ type: "", q: "" }, null);
  }, [fetchPage]);

  const applyFilters = useCallback(
    (next: MemoryFilters) => {
      setFilters(next);
      void fetchPage(next, null);
    },
    [fetchPage],
  );

  const loadMore = useCallback(() => {
    if (nextCursor) void fetchPage(filters, nextCursor);
  }, [fetchPage, filters, nextCursor]);

  const correct = useCallback(
    async (id: string, patch: { content?: string; type?: MemoryType; confidence?: number }) => {
      setMutating(true);
      setMutationError(null);
      try {
        const response = await fetch(`/v1/memory/${encodeURIComponent(id)}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(patch),
        });
        if (!response.ok) {
          setMutationError(await errorMessage(response));
          return;
        }
        const updated = (await response.json()) as MemoryItem;
        setItems((current) =>
          current.map((item) => (item.memory_id === id ? updated : item)),
        );
      } catch (cause) {
        setMutationError(cause instanceof Error ? cause.message : String(cause));
      } finally {
        setMutating(false);
      }
    },
    [],
  );

  const archive = useCallback(async (id: string) => {
    setMutating(true);
    setMutationError(null);
    try {
      const response = await fetch(`/v1/memory/${encodeURIComponent(id)}`, { method: "DELETE" });
      if (!response.ok && response.status !== 204) {
        setMutationError(await errorMessage(response));
        return;
      }
      setItems((current) => current.filter((item) => item.memory_id !== id));
    } catch (cause) {
      setMutationError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setMutating(false);
    }
  }, []);

  return {
    items,
    nextCursor,
    loading,
    error,
    filters,
    applyFilters,
    loadMore,
    mutating,
    mutationError,
    correct,
    archive,
  };
}
