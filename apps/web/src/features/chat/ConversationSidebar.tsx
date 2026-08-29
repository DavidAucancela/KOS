import { useMemo, useState } from "react";
import {
  Archive,
  MessagesSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { ConversationOut } from "./types";

const GROUP_ORDER = ["Hoy", "Ayer", "Últimos 7 días", "Anteriores"] as const;
type GroupLabel = (typeof GROUP_ORDER)[number];

function groupLabel(updatedAt: string): GroupLabel {
  const then = new Date(updatedAt);
  const now = new Date();
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const daysAgo = Math.round((startOfDay(now) - startOfDay(then)) / 86_400_000);
  if (daysAgo <= 0) return "Hoy";
  if (daysAgo === 1) return "Ayer";
  if (daysAgo <= 7) return "Últimos 7 días";
  return "Anteriores";
}

function groupConversations(
  items: ConversationOut[],
): { label: GroupLabel; items: ConversationOut[] }[] {
  const buckets = new Map<GroupLabel, ConversationOut[]>();
  for (const item of items) {
    const label = groupLabel(item.updated_at);
    const bucket = buckets.get(label);
    if (bucket) bucket.push(item);
    else buckets.set(label, [item]);
  }
  return GROUP_ORDER.filter((label) => buckets.has(label)).map((label) => ({
    label,
    items: buckets.get(label)!,
  }));
}

function ConversationRow({
  conversation,
  active,
  onSelect,
  onArchive,
}: {
  conversation: ConversationOut;
  active: boolean;
  onSelect: () => void;
  onArchive: () => void;
}) {
  return (
    <div
      className={cn(
        "group relative flex items-center gap-1 rounded-md border-l-2 pl-2 pr-1",
        active ? "border-primary bg-muted/50" : "border-transparent hover:bg-muted/30",
      )}
    >
      <button
        type="button"
        onClick={onSelect}
        className="min-w-0 flex-1 truncate py-2 text-left text-sm transition-colors"
        aria-current={active}
      >
        {conversation.title ?? "Sin título"}
      </button>
      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          onArchive();
        }}
        className="text-muted-foreground hover:text-destructive shrink-0 rounded p-1 opacity-0 transition-opacity group-hover:opacity-100"
        aria-label="Archivar conversación"
        title="Archivar conversación"
      >
        <Archive className="size-3.5" aria-hidden />
      </button>
    </div>
  );
}

export function ConversationSidebar({
  conversations,
  activeId,
  collapsed,
  onToggle,
  onSelect,
  onNew,
  onArchive,
}: {
  conversations: ConversationOut[];
  activeId: string | null;
  collapsed: boolean;
  onToggle: () => void;
  onSelect: (conversationId: string) => void;
  onNew: () => void;
  onArchive: (conversationId: string) => void;
}) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter((item) => (item.title ?? "sin título").toLowerCase().includes(q));
  }, [conversations, query]);

  const groups = useMemo(() => groupConversations(filtered), [filtered]);

  if (collapsed) {
    return (
      <aside className="flex w-8 shrink-0 flex-col items-center border-r border-border py-3">
        <button
          type="button"
          onClick={onToggle}
          title="Mostrar conversaciones"
          aria-label="Mostrar conversaciones"
          aria-expanded={false}
          className="text-muted-foreground hover:bg-muted flex size-6 items-center justify-center rounded-md"
        >
          <PanelLeftOpen className="size-4" aria-hidden />
        </button>
      </aside>
    );
  }

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-border">
      <div className="flex flex-col gap-2 border-b border-border p-3">
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="flex-1 justify-start gap-2"
            onClick={onNew}
          >
            <Plus className="size-4" aria-hidden />
            Nueva conversación
          </Button>
          <button
            type="button"
            onClick={onToggle}
            title="Ocultar conversaciones"
            aria-label="Ocultar conversaciones"
            aria-expanded={true}
            className="text-muted-foreground hover:bg-muted hover:text-foreground shrink-0 rounded-md p-1.5"
          >
            <PanelLeftClose className="size-4" aria-hidden />
          </button>
        </div>
        <div className="relative">
          <Search
            className="text-muted-foreground pointer-events-none absolute top-1/2 left-2 size-3.5 -translate-y-1/2"
            aria-hidden
          />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Buscar conversación…"
            aria-label="Buscar conversación"
            className="h-8 pl-7 text-xs"
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
        {conversations.length === 0 && (
          <div className="text-muted-foreground flex flex-col items-center gap-2 px-2 py-8 text-center text-xs">
            <MessagesSquare className="size-6" aria-hidden />
            Sin conversaciones todavía. Hacé una pregunta para empezar.
          </div>
        )}
        {conversations.length > 0 && filtered.length === 0 && (
          <p className="text-muted-foreground px-2 py-4 text-center text-xs">Sin resultados.</p>
        )}
        {groups.map((group) => (
          <div key={group.label} className="mb-3">
            <p className="text-muted-foreground px-2 pb-1 text-xs font-medium uppercase tracking-wide">
              {group.label}
            </p>
            <div className="space-y-0.5">
              {group.items.map((conversation) => (
                <ConversationRow
                  key={conversation.conversation_id}
                  conversation={conversation}
                  active={conversation.conversation_id === activeId}
                  onSelect={() => onSelect(conversation.conversation_id)}
                  onArchive={() => onArchive(conversation.conversation_id)}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}
