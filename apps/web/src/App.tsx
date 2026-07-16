import { useState } from "react";
import { Activity, MessagesSquare } from "lucide-react";

import { cn } from "@/lib/utils";
import { ChatPage } from "./features/chat/ChatPage";
import { StatusPage } from "./features/status/StatusPage";

// Shell de la app: semilla del layout IDE del doc 10 §4. Por ahora dos vistas
// (Chat y Estado); el grafo y las trazas llegan en fases posteriores.
type View = "chat" | "status";

const NAV: { id: View; label: string; icon: typeof Activity }[] = [
  { id: "chat", label: "Chat", icon: MessagesSquare },
  { id: "status", label: "Estado", icon: Activity },
];

export default function App() {
  const [view, setView] = useState<View>("chat");

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
        {view === "chat" ? <ChatPage /> : <StatusPage />}
      </div>
    </div>
  );
}
