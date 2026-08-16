import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GraphCanvas } from "../src/features/graph/GraphCanvas";
import type { GraphNode, GraphRelation } from "../src/features/graph/types";

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

function relation(overrides: Partial<GraphRelation> = {}): GraphRelation {
  return {
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
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
});

describe("GraphCanvas", () => {
  it("muestra un mensaje si no hay nodos", () => {
    render(<GraphCanvas nodes={[]} relations={[]} selectedId={null} onSelect={() => {}} />);
    expect(screen.getByText("Sin nodos para dibujar.")).toBeInTheDocument();
  });

  it("dibuja un nodo por cada elemento y una línea por cada relación inducida", () => {
    const nodes = [node(), node({ id: "node-2", canonical_name: "proyecto-kos" })];
    const { container } = render(
      <GraphCanvas nodes={nodes} relations={[relation()]} selectedId={null} onSelect={() => {}} />,
    );

    expect(screen.getByText("docker")).toBeInTheDocument();
    expect(screen.getByText("proyecto-kos")).toBeInTheDocument();
    expect(container.querySelectorAll("circle")).toHaveLength(2);
    expect(container.querySelectorAll("line")).toHaveLength(1);
  });

  it("no dibuja relaciones hacia un nodo fuera del conjunto mostrado", () => {
    const nodes = [node()];
    const { container } = render(
      <GraphCanvas nodes={nodes} relations={[relation()]} selectedId={null} onSelect={() => {}} />,
    );

    expect(container.querySelectorAll("line")).toHaveLength(0);
  });

  it("clickear un nodo llama a onSelect con su id", () => {
    const onSelect = vi.fn();
    render(
      <GraphCanvas nodes={[node()]} relations={[]} selectedId={null} onSelect={onSelect} />,
    );

    fireEvent.click(screen.getByText("docker"));

    expect(onSelect).toHaveBeenCalledWith("node-1");
  });

  it("resalta el nodo seleccionado con un trazo distinto", () => {
    const nodes = [node(), node({ id: "node-2", canonical_name: "proyecto-kos" })];
    const { container } = render(
      <GraphCanvas nodes={nodes} relations={[]} selectedId="node-2" onSelect={() => {}} />,
    );

    const circles = Array.from(container.querySelectorAll("circle"));
    const selected = circles.find((circle) => circle.getAttribute("stroke-width") === "3");
    expect(selected).toBeDefined();
  });
});
