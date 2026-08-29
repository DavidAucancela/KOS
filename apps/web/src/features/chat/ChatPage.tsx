import { Fragment, useState, type ReactNode } from "react";
import { AlertTriangle, ListTree, Quote, Send, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { collapsedByDefault, setUiPref } from "@/lib/uiPrefs";
import { CitationViewer, type CitationTarget } from "./CitationViewer";
import { ConversationSidebar } from "./ConversationSidebar";
import type { Evidence } from "./types";
import { useChat, type ChatTurn } from "./useChat";
import { useConversations } from "./useConversations";

const CITATION_MARKER = /\[(\d+)\]/g;

// Convierte los marcadores [n] del answer en botones clicables que abren la
// cita n-ésima (1-indexada); el texto restante se mantiene literal.
function renderAnswer(
  answer: string,
  evidence: Evidence[],
  onCite: (index: number) => void,
): ReactNode[] {
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  CITATION_MARKER.lastIndex = 0;

  while ((match = CITATION_MARKER.exec(answer)) !== null) {
    const [marker, digits] = match;
    const citationNumber = Number(digits);
    if (match.index > lastIndex) {
      nodes.push(<Fragment key={`t${lastIndex}`}>{answer.slice(lastIndex, match.index)}</Fragment>);
    }
    if (citationNumber >= 1 && citationNumber <= evidence.length) {
      nodes.push(
        <button
          key={`c${match.index}`}
          type="button"
          onClick={() => onCite(citationNumber - 1)}
          className="bg-primary/15 text-primary hover:bg-primary/25 mx-0.5 inline-flex size-4 items-center justify-center rounded-full text-[10px] font-bold"
          aria-label={`Abrir cita ${citationNumber}`}
        >
          {marker}
        </button>,
      );
    } else {
      nodes.push(<Fragment key={`t${match.index}`}>{marker}</Fragment>);
    }
    lastIndex = match.index + marker.length;
  }
  if (lastIndex < answer.length) {
    nodes.push(<Fragment key={`t${lastIndex}`}>{answer.slice(lastIndex)}</Fragment>);
  }
  return nodes;
}

function CitationCard({
  index,
  evidence,
  onOpen,
}: {
  index: number;
  evidence: Evidence;
  onOpen: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="w-full rounded-lg border border-border bg-card px-3 py-2 text-left hover:border-primary/50"
    >
      <div className="flex items-center gap-2 text-xs">
        <span className="bg-primary/15 text-primary flex size-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold">
          {index + 1}
        </span>
        <span className="font-medium">{evidence.title ?? evidence.source_id ?? "Documento"}</span>
        {evidence.doc_type === "template" && (
          <Badge variant="outline" className="border-primary/40 text-primary">
            Plantilla
          </Badge>
        )}
        {typeof evidence.score === "number" && (
          <span className="text-muted-foreground ml-auto">{evidence.score.toFixed(3)}</span>
        )}
      </div>
      {evidence.quote && (
        <p className="text-muted-foreground mt-1 line-clamp-2 text-xs">{evidence.quote}</p>
      )}
    </button>
  );
}

// Umbrales alineados con los variants ya definidos en Badge (success/warning/destructive).
function confidenceTone(value: number): "success" | "warning" | "destructive" {
  if (value >= 0.7) return "success";
  if (value >= 0.4) return "warning";
  return "destructive";
}

const CONFIDENCE_BAR_CLASS = {
  success: "bg-success",
  warning: "bg-warning",
  destructive: "bg-destructive",
} as const;

const CONFIDENCE_TEXT_CLASS = {
  success: "text-success",
  warning: "text-warning",
  destructive: "text-destructive",
} as const;

function ConfidenceMeter({ value }: { value: number }) {
  const tone = confidenceTone(value);
  return (
    <div
      className="flex items-center gap-2"
      title="Confianza: qué tan bien encajó la mejor evidencia recuperada, no si el modelo alucinó."
    >
      <div className="bg-muted h-1.5 w-14 overflow-hidden rounded-full">
        <div
          className={cn("h-full", CONFIDENCE_BAR_CLASS[tone])}
          style={{ width: `${Math.round(value * 100)}%` }}
        />
      </div>
      <span className={cn("text-xs font-semibold", CONFIDENCE_TEXT_CLASS[tone])}>
        {(value * 100).toFixed(0)}%
      </span>
    </div>
  );
}

function AssistantTurn({
  turn,
  onCite,
  onViewPlan,
}: {
  turn: ChatTurn;
  onCite: (evidence: Evidence) => void;
  onViewPlan: (planId: string) => void;
}) {
  if (turn.pending) {
    return (
      <div className="border-border rounded-lg border">
        <div className="border-border bg-card flex items-center gap-2 border-b px-3 py-2">
          <Sparkles className="text-primary size-3.5" aria-hidden />
          <span className="text-muted-foreground text-xs font-semibold tracking-wide">
            RESPUESTA
          </span>
        </div>
        <p className="text-muted-foreground px-3 py-3 text-sm">Pensando…</p>
      </div>
    );
  }
  if (turn.error) {
    return (
      <p className="border-destructive/30 bg-destructive/10 text-destructive rounded-lg border px-3 py-2 text-sm">
        {turn.error}
      </p>
    );
  }
  if (!turn.response) return null;

  const { answer, evidence, confidence, degraded, plan_id } = turn.response;
  return (
    <div className="border-border overflow-hidden rounded-lg border">
      <div className="border-border bg-card flex items-center gap-2 border-b px-3 py-2">
        <Sparkles className="text-primary size-3.5" aria-hidden />
        <span className="text-muted-foreground text-xs font-semibold tracking-wide">
          RESPUESTA
        </span>
        <div className="ml-auto">
          <ConfidenceMeter value={confidence} />
        </div>
      </div>
      {degraded && (
        <p className="border-warning/30 bg-warning/10 text-warning flex items-center gap-2 border-b px-3 py-2 text-xs">
          <AlertTriangle className="size-4" aria-hidden />
          Respuesta degradada: síntesis limitada por falta del modelo local.
        </p>
      )}
      <div className="px-3 py-3 text-sm leading-relaxed whitespace-pre-wrap">
        {renderAnswer(answer, evidence, (i) => onCite(evidence[i]))}
      </div>
      {confidence < 0.4 && (
        <p className="border-warning/30 bg-warning/10 text-warning flex items-center gap-2 border-t px-3 py-2 text-xs">
          <AlertTriangle className="size-4" aria-hidden />
          Confianza baja: revisa la evidencia antes de confiar en esta respuesta.
        </p>
      )}
      {plan_id && (
        <div className="border-border border-t px-3 py-2">
          <button
            type="button"
            onClick={() => onViewPlan(plan_id)}
            className="text-muted-foreground hover:text-primary flex items-center gap-1 text-xs"
          >
            <ListTree className="size-3" aria-hidden />
            Ver plan
          </button>
        </div>
      )}
    </div>
  );
}

function EvidencePanel({
  evidence,
  onOpen,
}: {
  evidence: Evidence[];
  onOpen: (evidence: Evidence) => void;
}) {
  return (
    <div className="border-border flex h-full min-h-0 flex-col border-l">
      <div className="border-border flex h-11 shrink-0 items-center gap-2 border-b px-4">
        <Quote className="text-muted-foreground size-3.5" aria-hidden />
        <span className="text-muted-foreground text-xs font-semibold tracking-wide">
          EVIDENCIA
        </span>
        <span className="bg-muted text-muted-foreground ml-auto rounded-full px-2 py-0.5 text-xs">
          {evidence.length}
        </span>
      </div>
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
        {evidence.map((item, index) => (
          <CitationCard
            key={item.chunk_id ?? `${item.doc_id}-${index}`}
            index={index}
            evidence={item}
            onOpen={() => onOpen(item)}
          />
        ))}
      </div>
    </div>
  );
}

export function ChatPage({ onViewPlan }: { onViewPlan: (planId: string) => void }) {
  const { turns, busy, conversationId, ask, loadConversation, newConversation } = useChat();
  const { items: conversations, refresh: refreshConversations, archive } = useConversations();
  const [draft, setDraft] = useState("");
  const [citation, setCitation] = useState<CitationTarget | null>(null);
  // Colapso del sidebar de conversaciones (doc 13 §3): default responsivo
  // (colapsado bajo `lg`), la elección explícita del usuario gana y persiste.
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() =>
    collapsedByDefault("chatSidebarCollapsed"),
  );

  const toggleSidebar = () => {
    setSidebarCollapsed((prev) => {
      const next = !prev;
      setUiPref("chatSidebarCollapsed", next);
      return next;
    });
  };

  const openCitation = (evidence: Evidence) => {
    // Sin doc_id no hay nada que abrir (evidencia mínima real, doc 06 §2).
    if (!evidence.doc_id) return;
    setCitation({ docId: evidence.doc_id, chunkId: evidence.chunk_id ?? null });
  };

  const submit = () => {
    const text = draft;
    setDraft("");
    void ask(text).then(() => refreshConversations());
  };

  // Evidencia siempre visible en el panel derecho: la de la última respuesta
  // con turno completo, salvo que haya una cita abierta (esa gana el panel).
  const lastEvidence = [...turns].reverse().find((turn) => turn.response?.evidence.length)
    ?.response?.evidence;

  return (
    <div className="flex h-full min-h-0 flex-1">
      <ConversationSidebar
        conversations={conversations}
        activeId={conversationId}
        collapsed={sidebarCollapsed}
        onToggle={toggleSidebar}
        onSelect={(id) => void loadConversation(id)}
        onNew={newConversation}
        onArchive={(id) => {
          void archive(id);
          if (id === conversationId) newConversation();
        }}
      />

      <main className="flex min-h-0 w-full flex-1 flex-col">
        <div className="border-border flex h-11 shrink-0 items-center border-b px-6">
          <h1 className="text-sm font-semibold">KOS — Preguntar al conocimiento</h1>
        </div>

        <div className="mx-auto min-h-0 w-full max-w-3xl flex-1 space-y-6 overflow-y-auto px-6 py-6">
          {turns.length === 0 && (
            <p className="text-muted-foreground text-sm">
              Haz una pregunta sobre tus notas; la respuesta vendrá con citas clicables.
            </p>
          )}
          {turns.map((turn) => (
            <div key={turn.id} className="space-y-2">
              <p className="ml-auto w-fit max-w-[85%] rounded-lg bg-muted px-3 py-2 text-sm">
                {turn.question}
              </p>
              <AssistantTurn turn={turn} onCite={openCitation} onViewPlan={onViewPlan} />
            </div>
          ))}
        </div>

        <form
          className="border-border mx-auto flex w-full max-w-3xl items-end gap-2 border-t px-6 py-3"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <Textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
            placeholder="¿Qué quieres saber?"
            rows={1}
            aria-label="Pregunta"
          />
          <Button type="submit" size="icon" disabled={busy || !draft.trim()} aria-label="Enviar">
            <Send className="size-4" aria-hidden />
          </Button>
        </form>
      </main>

      {(citation ?? lastEvidence) && (
        <div className="hidden w-96 shrink-0 lg:block">
          {citation ? (
            <CitationViewer target={citation} onClose={() => setCitation(null)} />
          ) : (
            <EvidencePanel evidence={lastEvidence!} onOpen={openCitation} />
          )}
        </div>
      )}
    </div>
  );
}
