import { useState } from "react";
import { Archive, Lock } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { PageContainer, PageHeader } from "@/components/page";
import { cn } from "@/lib/utils";
import { useMemory } from "./useMemory";
import { MEMORY_TYPES, type MemoryItem, type MemoryType } from "./types";

// Pantalla de auditoría de memoria (doc 13 §4, deuda Sprint 12/15). Lista lo
// que el sistema "sabe" (doc 04 §1) con su procedencia y permite corregir
// manualmente un ítem —fijándolo `locked`, análogo a la corrección de nodos del
// grafo de Sprint 9— o archivarlo. Sin edición libre en lote.
export function MemoryPage() {
  const memory = useMemory();
  const [typeDraft, setTypeDraft] = useState<MemoryType | "">("");
  const [queryDraft, setQueryDraft] = useState("");

  return (
    <PageContainer wide>
      <PageHeader
        title="KOS — Memoria"
        description="Lo que el sistema sabe (doc 04 §1). Lo que corrijas acá queda protegido de la próxima consolidación (doc 04 §5)."
      />

      <section className="flex flex-wrap items-center gap-2">
        <Select
          value={typeDraft}
          onChange={(event) => setTypeDraft(event.target.value as MemoryType | "")}
          aria-label="Filtrar por tipo de memoria"
        >
          <option value="">Todos los tipos</option>
          {MEMORY_TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </Select>
        <Input
          value={queryDraft}
          onChange={(event) => setQueryDraft(event.target.value)}
          placeholder="Buscar en el contenido…"
          aria-label="Buscar en la memoria"
          className="h-9 w-64"
        />
        <Button
          onClick={() => memory.applyFilters({ type: typeDraft, q: queryDraft })}
          disabled={memory.loading}
        >
          {memory.loading ? "Buscando…" : "Buscar"}
        </Button>
      </section>

      {memory.error && (
        <p className="border-destructive/30 bg-destructive/10 text-destructive rounded-lg border px-4 py-3 text-sm">
          {memory.error}
        </p>
      )}
      {memory.mutationError && (
        <p className="text-destructive text-sm">{memory.mutationError}</p>
      )}

      <div className="space-y-3">
        {memory.items.map((item) => (
          <MemoryRow
            key={item.memory_id}
            item={item}
            busy={memory.mutating}
            onCorrect={(patch) => void memory.correct(item.memory_id, patch)}
            onArchive={() => void memory.archive(item.memory_id)}
          />
        ))}
        {memory.items.length === 0 && !memory.loading && (
          <p className="text-muted-foreground py-8 text-center text-sm">
            Sin memorias para estos filtros.
          </p>
        )}
      </div>

      {memory.nextCursor && (
        <div className="flex justify-center">
          <Button variant="outline" onClick={memory.loadMore} disabled={memory.loading}>
            {memory.loading ? "Cargando…" : "Cargar más"}
          </Button>
        </div>
      )}
    </PageContainer>
  );
}

function MemoryRow({
  item,
  busy,
  onCorrect,
  onArchive,
}: {
  item: MemoryItem;
  busy: boolean;
  onCorrect: (patch: { content?: string; type?: MemoryType; confidence?: number }) => void;
  onArchive: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [contentDraft, setContentDraft] = useState(item.content);
  const [typeDraft, setTypeDraft] = useState<MemoryType>(item.type);
  const [confidenceDraft, setConfidenceDraft] = useState(String(item.confidence));

  // Heurística simple para decidir si vale ofrecer "Ver más": contenido largo
  // o con varios saltos de línea. Evita medir el DOM.
  const isLong = item.content.length > 220 || item.content.split("\n").length > 3;

  return (
    <Card>
      <CardContent className="space-y-3 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">{item.type}</Badge>
          {item.locked && (
            <Badge variant="outline" className="gap-1">
              <Lock className="size-3" aria-hidden />
              corregida
            </Badge>
          )}
          {item.prune_candidate && <Badge variant="warning">baja confianza</Badge>}
          {item.archived_at && <Badge variant="destructive">archivada</Badge>}
          <span className="text-muted-foreground ml-auto text-xs">
            confianza {item.confidence.toFixed(2)} · saliencia {item.salience.toFixed(2)} ·{" "}
            {item.sources.length} fuente{item.sources.length === 1 ? "" : "s"}
          </span>
        </div>

        {editing ? (
          <div className="space-y-2">
            <Textarea
              value={contentDraft}
              onChange={(event) => setContentDraft(event.target.value)}
              rows={3}
              aria-label="Contenido de la memoria"
            />
            <div className="flex flex-wrap items-center gap-2">
              <Select
                value={typeDraft}
                onChange={(event) => setTypeDraft(event.target.value as MemoryType)}
                aria-label="Tipo de memoria"
              >
                {MEMORY_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </Select>
              <Input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={confidenceDraft}
                onChange={(event) => setConfidenceDraft(event.target.value)}
                aria-label="Confianza"
                className="h-9 w-24"
              />
              <Button
                size="sm"
                disabled={busy}
                onClick={() => {
                  const parsed = Number(confidenceDraft);
                  onCorrect({
                    content: contentDraft,
                    type: typeDraft,
                    confidence: Number.isFinite(parsed) ? parsed : undefined,
                  });
                  setEditing(false);
                }}
              >
                Guardar corrección
              </Button>
              <Button size="sm" variant="outline" onClick={() => setEditing(false)}>
                Cancelar
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-1">
            <p
              className={cn(
                "text-sm leading-relaxed whitespace-pre-wrap",
                isLong && !expanded && "line-clamp-3",
              )}
            >
              {item.content}
            </p>
            {isLong && (
              <button
                type="button"
                onClick={() => setExpanded((prev) => !prev)}
                className="text-primary text-xs hover:underline"
              >
                {expanded ? "Ver menos" : "Ver más"}
              </button>
            )}
          </div>
        )}

        {!editing && (
          <div className="flex gap-2">
            <Button size="sm" variant="outline" disabled={busy} onClick={() => setEditing(true)}>
              Corregir
            </Button>
            {!item.archived_at && (
              <Button
                size="sm"
                variant="outline"
                disabled={busy}
                onClick={onArchive}
                className="gap-1"
              >
                <Archive className="size-3.5" aria-hidden />
                Archivar
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
