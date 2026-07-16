import { Fragment, useState, type ReactNode } from "react";
import { AlertTriangle, Quote, Send } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { CitationViewer, type CitationTarget } from "./CitationViewer";
import type { Evidence } from "./types";
import { useChat, type ChatTurn } from "./useChat";

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
          className="mx-0.5 inline-flex items-center rounded bg-primary/15 px-1 text-xs font-medium text-primary hover:bg-primary/25"
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
        <Badge variant="outline">[{index + 1}]</Badge>
        <span className="font-medium">{evidence.title ?? evidence.source_id ?? "Documento"}</span>
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

function AssistantTurn({
  turn,
  onCite,
}: {
  turn: ChatTurn;
  onCite: (evidence: Evidence) => void;
}) {
  if (turn.pending) {
    return <p className="text-muted-foreground text-sm">Pensando…</p>;
  }
  if (turn.error) {
    return (
      <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
        {turn.error}
      </p>
    );
  }
  if (!turn.response) return null;

  const { answer, evidence, confidence, degraded } = turn.response;
  return (
    <div className="space-y-3">
      {degraded && (
        <p className="flex items-center gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-400">
          <AlertTriangle className="size-4" aria-hidden />
          Respuesta degradada: síntesis limitada por falta del modelo local.
        </p>
      )}
      <div className="text-sm leading-relaxed whitespace-pre-wrap">
        {renderAnswer(answer, evidence, (i) => onCite(evidence[i]))}
      </div>
      {evidence.length > 0 && (
        <div className="space-y-2">
          <p className="text-muted-foreground flex items-center gap-1 text-xs font-medium">
            <Quote className="size-3" aria-hidden />
            Citas
          </p>
          {evidence.map((item, index) => (
            <CitationCard
              key={item.chunk_id ?? `${item.doc_id}-${index}`}
              index={index}
              evidence={item}
              onOpen={() => onCite(item)}
            />
          ))}
        </div>
      )}
      <p className="text-muted-foreground text-xs">Confianza: {(confidence * 100).toFixed(0)}%</p>
    </div>
  );
}

export function ChatPage() {
  const { turns, busy, ask } = useChat();
  const [draft, setDraft] = useState("");
  const [citation, setCitation] = useState<CitationTarget | null>(null);

  const openCitation = (evidence: Evidence) =>
    setCitation({ docId: evidence.doc_id, chunkId: evidence.chunk_id });

  const submit = () => {
    void ask(draft);
    setDraft("");
  };

  return (
    <div className="flex h-full min-h-0 flex-1">
      <main className="mx-auto flex min-h-0 w-full max-w-3xl flex-1 flex-col gap-4 px-6 py-8">
        <h1 className="text-xl font-semibold tracking-tight">KOS — Preguntar al conocimiento</h1>

        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto">
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
              <AssistantTurn turn={turn} onCite={openCitation} />
            </div>
          ))}
        </div>

        <form
          className="flex items-end gap-2"
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

      {citation && (
        <div className="hidden w-96 shrink-0 lg:block">
          <CitationViewer target={citation} onClose={() => setCitation(null)} />
        </div>
      )}
    </div>
  );
}
