import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChatPage } from "../src/features/chat/ChatPage";
import type { Evidence, QueryResponse } from "../src/features/chat/types";

function evidence(n: number): Evidence {
  return {
    doc_id: `doc-${n}`,
    chunk_id: `chunk-${n}`,
    quote: `fragmento citado ${n}`,
    title: `Nota ${n}`,
    source_id: `Nota${n}.md`,
    connector: "obsidian",
    score: 0.5 - n * 0.1,
  };
}

function queryResponse(overrides: Partial<QueryResponse> = {}): QueryResponse {
  return {
    query: "¿qué es docker?",
    answer: "Docker es contenedores [1] y también volúmenes [2].",
    evidence: [evidence(1), evidence(2)],
    confidence: 0.7,
    plan: [],
    degraded: false,
    trace_id: "trace-1",
    ...overrides,
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

async function askQuestion() {
  fireEvent.change(screen.getByLabelText("Pregunta"), { target: { value: "¿qué es docker?" } });
  fireEvent.click(screen.getByLabelText("Enviar"));
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ChatPage", () => {
  it("muestra la respuesta y sus dos citas", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(queryResponse())));

    render(<ChatPage />);
    await askQuestion();

    expect(await screen.findByText(/Docker es contenedores/)).toBeInTheDocument();
    expect(screen.getByText("Nota 1")).toBeInTheDocument();
    expect(screen.getByText("Nota 2")).toBeInTheDocument();
    expect(screen.getByText("Confianza: 70%")).toBeInTheDocument();
  });

  it("renderiza los marcadores [1] y [2] como elementos interactivos", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(queryResponse())));

    render(<ChatPage />);
    await askQuestion();

    expect(await screen.findByLabelText("Abrir cita 1")).toBeInTheDocument();
    expect(screen.getByLabelText("Abrir cita 2")).toBeInTheDocument();
  });

  it("avisa cuando la respuesta viene degradada", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(queryResponse({ degraded: true }))),
    );

    render(<ChatPage />);
    await askQuestion();

    expect(await screen.findByText(/Respuesta degradada/)).toBeInTheDocument();
  });

  it("muestra un mensaje de error si el modelo no está disponible (503)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "sin ollama" }, 503)));

    render(<ChatPage />);
    await askQuestion();

    await waitFor(() =>
      expect(screen.getByText(/Ollama.*no está disponible/i)).toBeInTheDocument(),
    );
  });
});
