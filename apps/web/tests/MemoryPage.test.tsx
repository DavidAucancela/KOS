import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MemoryPage } from "../src/features/memory/MemoryPage";
import type { MemoryItem } from "../src/features/memory/types";

function memory(overrides: Partial<MemoryItem> = {}): MemoryItem {
  return {
    memory_id: "mem-1",
    type: "semantic",
    content: "El usuario prefiere Postgres sobre MySQL.",
    entities: ["Postgres"],
    sources: [{ doc_id: "doc-a", confidence: 0.8 }],
    confidence: 0.6,
    salience: 0.5,
    created_at: "2026-08-20T00:00:00Z",
    last_accessed_at: "2026-08-25T00:00:00Z",
    archived_at: null,
    superseded_by: null,
    locked: false,
    prune_candidate: false,
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

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("MemoryPage", () => {
  it("lista las memorias al cargar", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ items: [memory()], next_cursor: null })),
    );

    render(<MemoryPage />);

    expect(
      await screen.findByText("El usuario prefiere Postgres sobre MySQL."),
    ).toBeInTheDocument();
    expect(screen.getByText(/1 fuente/)).toBeInTheDocument();
  });

  it("pasa el tipo y el texto como query params al buscar", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ items: [memory()], next_cursor: null }));
    vi.stubGlobal("fetch", fetchMock);

    render(<MemoryPage />);
    await screen.findByText("El usuario prefiere Postgres sobre MySQL.");

    fireEvent.change(screen.getByLabelText("Filtrar por tipo de memoria"), {
      target: { value: "preference" },
    });
    fireEvent.change(screen.getByLabelText("Buscar en la memoria"), {
      target: { value: "postgres" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Buscar" }));

    const lastUrl = fetchMock.mock.calls.at(-1)?.[0] as string;
    expect(lastUrl).toContain("type=preference");
    expect(lastUrl).toContain("q=postgres");
  });

  it("corrige una memoria vía PATCH y refleja el ítem actualizado", async () => {
    const corrected = memory({ content: "Corregido.", locked: true, confidence: 1 });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init?: RequestInit) => {
        if (init?.method === "PATCH") return jsonResponse(corrected);
        return jsonResponse({ items: [memory()], next_cursor: null });
      }),
    );

    render(<MemoryPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Corregir" }));
    fireEvent.change(screen.getByLabelText("Contenido de la memoria"), {
      target: { value: "Corregido." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar corrección" }));

    expect(await screen.findByText("Corregido.")).toBeInTheDocument();
    expect(screen.getByText("corregida")).toBeInTheDocument();
  });

  it("archiva una memoria vía DELETE y la saca de la lista", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init?: RequestInit) => {
        if (init?.method === "DELETE") return jsonResponse(null, 204);
        return jsonResponse({ items: [memory()], next_cursor: null });
      }),
    );

    render(<MemoryPage />);
    const row = (await screen.findByText("El usuario prefiere Postgres sobre MySQL."))
      .closest("[data-slot='card']") as HTMLElement;
    fireEvent.click(within(row).getByRole("button", { name: /Archivar/ }));

    expect(
      await screen.findByText("Sin memorias para estos filtros."),
    ).toBeInTheDocument();
  });

  it("colapsa el contenido largo tras 3 líneas y lo expande con 'Ver más'", async () => {
    const largo = memory({ content: "a".repeat(400) });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ items: [largo], next_cursor: null })),
    );

    render(<MemoryPage />);
    const toggle = await screen.findByRole("button", { name: "Ver más" });
    const paragraph = screen.getByText("a".repeat(400));
    expect(paragraph.className).toContain("line-clamp-3");

    fireEvent.click(toggle);

    expect(screen.getByRole("button", { name: "Ver menos" })).toBeInTheDocument();
    expect(paragraph.className).not.toContain("line-clamp-3");
  });

  it("no ofrece 'Ver más' para contenido corto", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ items: [memory()], next_cursor: null })),
    );

    render(<MemoryPage />);
    await screen.findByText("El usuario prefiere Postgres sobre MySQL.");
    expect(screen.queryByRole("button", { name: "Ver más" })).not.toBeInTheDocument();
  });

  it("muestra un error si la carga falla", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "boom" }, 500)));

    render(<MemoryPage />);

    expect(await screen.findByText("boom")).toBeInTheDocument();
  });
});
