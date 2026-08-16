import { useState } from "react";
import { Activity, ListTree, MessagesSquare, Network } from "lucide-react";

import { cn } from "@/lib/utils";
import { ChatPage } from "./features/chat/ChatPage";
import { GraphPage } from "./features/graph/GraphPage";
import { StatusPage } from "./features/status/StatusPage";
import { TracesPage } from "./features/traces/TracesPage";

// Shell de la app: semilla del layout IDE del doc 10 §4. Chat, Grafo, Trazas
// (Sprint 19) y Estado.
type View = "chat" | "graph" | "traces" | "status";

const NAV: { id: View; label: string; icon: typeof Activity }[] = [
  { id: "chat", label: "Chat", icon: MessagesSquare },
  { id: "graph", label: "Grafo", icon: Network },
  { id: "traces", label: "Trazas", icon: ListTree },
  { id: "status", label: "Estado", icon: Activity },
];

export default function App() {
  const [view, setView] = useState<View>("chat");
  // Sprint 19: "ver plan" en el chat navega acá con un plan_id preseleccionado.
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);

  return (
    <div className="flex h-screen">
      <nav className="flex w-14 shrink-0 flex-col items-center gap-1 border-r border-border py-3">
        {NAV.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setView(id)}
            title={label}
            aria-label={label}
            aria-current={view === id}
            className={cn(
              "flex size-10 items-center justify-center rounded-md",
              view === id ? "bg-muted text-primary" : "text-muted-foreground hover:bg-muted",
            )}
          >
            <Icon className="size-5" aria-hidden />
          </button>
        ))}
      </nav>

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {view === "chat" && (
          <ChatPage
            onViewPlan={(planId) => {
              setSelectedPlanId(planId);
              setView("traces");
            }}
          />
        )}
        {view === "graph" && <GraphPage />}
        {view === "traces" && <TracesPage initialPlanId={selectedPlanId} />}
        {view === "status" && <StatusPage />}
      </div>
    </div>
  );
}
