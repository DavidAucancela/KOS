import { useCallback, useEffect, useState } from "react";

import { errorMessage } from "@/lib/api";
import type { ConversationOut, ConversationPage } from "./types";

export interface UseConversationsResult {
  items: ConversationOut[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  archive: (conversationId: string) => Promise<void>;
}

// Historial de conversaciones (doc 06 §2 addendum 2026-08-21) contra
// GET/DELETE /v1/conversations — mismo patrón fetch-directo que el resto de
// los hooks de features/*.
export function useConversations(): UseConversationsResult {
  const [items, setItems] = useState<ConversationOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/v1/conversations?limit=50");
      if (!response.ok) {
        setError(await errorMessage(response));
        return;
      }
      const page = (await response.json()) as Partial<ConversationPage>;
      setItems(Array.isArray(page.items) ? page.items : []);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setLoading(false);
    }
  }, []);

  const archive = useCallback(async (conversationId: string) => {
    // Optimista: la saca de la lista de inmediato, sin esperar la red.
    setItems((prev) => prev.filter((item) => item.conversation_id !== conversationId));
    try {
      await fetch(`/v1/conversations/${encodeURIComponent(conversationId)}`, {
        method: "DELETE",
      });
    } catch {
      // Si falla, la próxima `refresh()` la vuelve a traer — no se revierte a mano.
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { items, loading, error, refresh, archive };
}
