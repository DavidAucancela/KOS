import { useEffect, useState } from "react";
import { FileText, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { DocumentChunk, DocumentDetail } from "./types";

export interface CitationTarget {
  docId: string;
  chunkId: string | null;
}

interface ViewerState {
  loading: boolean;
  error: string | null;
  detail: DocumentDetail | null;
  chunks: DocumentChunk[];
}

const EMPTY: ViewerState = { loading: true, error: null, detail: null, chunks: [] };

// Carga GET /v1/documents/{id} + sus chunks y resalta el chunk citado.
async function loadDocument(docId: string): Promise<Pick<ViewerState, "detail" | "chunks">> {
  const [detailRes, chunksRes] = await Promise.all([
    fetch(`/v1/documents/${docId}`),
    fetch(`/v1/documents/${docId}/chunks`),
  ]);
  if (!detailRes.ok) throw new Error(`HTTP ${detailRes.status}`);
  const detail = (await detailRes.json()) as DocumentDetail;
  const chunks = chunksRes.ok
    ? ((await chunksRes.json()) as { items: DocumentChunk[] }).items
    : [];
  return { detail, chunks };
}

export function CitationViewer({
  target,
  onClose,
}: {
  target: CitationTarget;
  onClose: () => void;
}) {
  const [state, setState] = useState<ViewerState>(EMPTY);

  useEffect(() => {
    let cancelled = false;
    setState(EMPTY);
    loadDocument(target.docId)
      .then(({ detail, chunks }) => {
        if (!cancelled) setState({ loading: false, error: null, detail, chunks });
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          const error = cause instanceof Error ? cause.message : String(cause);
          setState({ loading: false, error, detail: null, chunks: [] });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [target.docId]);

  return (
    <aside className="flex h-full w-full flex-col border-l border-border bg-card">
      <header className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <FileText className="text-muted-foreground size-4 shrink-0" aria-hidden />
          <span className="truncate text-sm font-medium">
            {state.detail?.title ?? state.detail?.source_id ?? "Documento"}
          </span>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Cerrar visor de citas">
          <X className="size-4" aria-hidden />
        </Button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
        {state.loading && <p className="text-muted-foreground text-sm">Cargando documento…</p>}
        {state.error && (
          <p className="text-sm text-red-400">No se pudo abrir el documento ({state.error}).</p>
        )}
        {state.detail && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              {state.detail.connector && <Badge variant="outline">{state.detail.connector}</Badge>}
              {state.detail.source_id && (
                <span className="text-muted-foreground truncate">{state.detail.source_id}</span>
              )}
            </div>
            {state.chunks.map((chunk) => {
              const cited = chunk.chunk_id === target.chunkId;
              return (
                <p
                  key={chunk.chunk_id}
                  data-cited={cited}
                  className={
                    cited
                      ? "rounded-md border border-primary/40 bg-primary/10 px-3 py-2 text-sm whitespace-pre-wrap"
                      : "text-muted-foreground px-3 py-2 text-sm whitespace-pre-wrap"
                  }
                >
                  {chunk.text}
                </p>
              );
            })}
          </div>
        )}
      </div>
    </aside>
  );
}
