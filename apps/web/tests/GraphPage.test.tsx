import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GraphPage } from "../src/features/graph/GraphPage";
import type { GraphNeighbor, GraphNode, NodeWithNeighborhood } from "../src/features/graph/types";

function node(overrides: Partial<GraphNode> = {}): GraphNode {
  return {
    id: "node-1",
    node_type: "Technology",
    canonical_name: "docker",
    name: "Docker",
    aliases: [],
    confidence: 0.4,
    sources: ["doc-a"],
    extracted_by: "parser@v1",
    locked: false,
    created_at: null,
    updated_at: null,
    prune_candidate: false,
    ...overrides,
  };
}

function neighbor(overrides: Partial<GraphNeighbor> = {}): GraphNeighbor {
  return {
    relation: {
      id: "rel-1",
      relation_type: "USES",
      source_id: "node-1",
      target_id: "node-2",
      confidence: 0.7,
      sources: ["doc-a"],
      extracted_by: "parser@v1",
      extracted_at: null,
      rejected: false,
      prune_candidate: false,
    },
    node: node({ id: "node-2", canonical_name: "proyecto-kos", node_type: "Project" }),
    direction: "outgoing",
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

describe("GraphPage", () => {
  it("busca nodos al cargar y los muestra en la tabla", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ template: "most_connected", nodes: [node()] })),
    );

    render(<GraphPage />);

    expect(await screen.findByText("docker")).toBeInTheDocument();
  });

  it("arranca en vista de grafo (SVG) y el botón Tabla cambia a la tabla", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ template: "subgraph", nodes: [node()], relations: [] })),
    );

    render(<GraphPage />);
    await screen.findByText("docker");

    expect(screen.getByRole("img", { name: /grafo de conocimiento/i })).toBeInTheDocument();

    fireEvent.click(screen.getByText("Tabla"));

    expect(screen.getByRole("columnheader", { name: "Nombre" })).toBeInTheDocument();
  });

  it("al seleccionar un nodo muestra su vecindario", async () => {
    const detail: NodeWithNeighborhood = { node: node(), neighbors: [neighbor()] };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.startsWith("/v1/graph/nodes/")) return jsonResponse(detail);
        return jsonResponse({ template: "most_connected", nodes: [node()] });
      }),
    );

    render(<GraphPage />);
    fireEvent.click(await screen.findByText("docker"));

    expect(await screen.findByText(/proyecto-kos/)).toBeInTheDocument();
    expect(screen.getByText("Vecinos (1)")).toBeInTheDocument();
  });

  it("corrige un nodo y refresca el detalle con el badge de corregido", async () => {
    const original: NodeWithNeighborhood = { node: node(), neighbors: [] };
    const corrected: NodeWithNeighborhood = {
      node: node({ locked: true, extracted_by: "user", confidence: 1.0 }),
      neighbors: [],
    };
    let patched = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (init?.method === "PATCH") {
          patched = true;
          return jsonResponse(corrected.node);
        }
        if (url.startsWith("/v1/graph/nodes/")) {
          return jsonResponse(patched ? corrected : original);
        }
        return jsonResponse({ template: "most_connected", nodes: [node()] });
      }),
    );

    render(<GraphPage />);
    fireEvent.click(await screen.findByText("docker"));
    fireEvent.click(await screen.findByText("Corregir nodo"));

    expect(await screen.findByText("corregido")).toBeInTheDocument();
  });

  it("rechaza una relación y el vecindario queda vacío", async () => {
    const withNeighbor: NodeWithNeighborhood = { node: node(), neighbors: [neighbor()] };
    const withoutNeighbor: NodeWithNeighborhood = { node: node(), neighbors: [] };
    let rejected = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (init?.method === "DELETE") {
          rejected = true;
          return jsonResponse(null, 204);
        }
        if (url.startsWith("/v1/graph/nodes/")) {
          return jsonResponse(rejected ? withoutNeighbor : withNeighbor);
        }
        return jsonResponse({ template: "most_connected", nodes: [node()] });
      }),
    );

    render(<GraphPage />);
    fireEvent.click(await screen.findByText("docker"));
    fireEvent.click(await screen.findByText("Rechazar"));

    expect(await screen.findByText("Sin relaciones activas.")).toBeInTheDocument();
  });

  it("modo 'Resaltar camino': elegir dos nodos pide /v1/graph/path y resalta", async () => {
    const nodes = [node(), node({ id: "node-2", canonical_name: "proyecto-kos" })];
    const fetchMock = vi.fn(async (url: string) => {
      if (url.startsWith("/v1/graph/path")) {
        return jsonResponse({ nodes, relations: [neighbor().relation] });
      }
      return jsonResponse({ template: "subgraph", nodes, relations: [neighbor().relation] });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<GraphPage />);
    await screen.findByText("docker");

    fireEvent.click(screen.getByRole("button", { name: /Resaltar camino/ }));
    expect(screen.getByText("Elegí el nodo de origen.")).toBeInTheDocument();

    fireEvent.click(screen.getByText("docker"));
    expect(screen.getByText("Elegí el nodo de destino.")).toBeInTheDocument();
    fireEvent.click(screen.getByText("proyecto-kos"));

    expect(await screen.findByText(/Camino resaltado: 2 nodos/)).toBeInTheDocument();
    const pathCall = fetchMock.mock.calls.find((c) => String(c[0]).startsWith("/v1/graph/path"));
    expect(pathCall?.[0]).toContain("from_id=node-1");
    expect(pathCall?.[0]).toContain("to_id=node-2");
  });

  it("muestra un error si la búsqueda falla", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "boom" }, 500)));

    render(<GraphPage />);

    expect(await screen.findByText("boom")).toBeInTheDocument();
  });
});
