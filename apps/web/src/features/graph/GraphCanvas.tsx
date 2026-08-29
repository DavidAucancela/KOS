import type { PointerEvent as ReactPointerEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation } from "d3-force";
import type { SimulationNodeDatum } from "d3-force";

import { Button } from "@/components/ui/button";
import { NODE_TYPE_COLORS, type GraphNode, type GraphRelation } from "./types";

// Visualización del grafo (doc 06 §2 `subgraph`, Sprint 10): layout de fuerzas
// con d3-force solo para la física (el render lo controla React vía SVG).
//
// doc 13 §5.1: en la primera carga el layout se resuelve de una sola pasada
// síncrona (como desde Sprint 10). Cuando llegan datos nuevos y ya había un
// layout en pantalla (re-fetch tras `graph.updated`), el reacomodo se anima
// unos frames desde las posiciones actuales y se detiene solo al estabilizarse
// — nunca queda una simulación corriendo en reposo. Los nodos que el usuario
// arrastró quedan fijados (`fx`/`fy`) para que la animación no se los mueva.
// `prefers-reduced-motion` fuerza la pasada síncrona.
//
// Zoom/pan (mejora de interfaz posterior): manual sobre el `viewBox` fijo, sin
// traer `d3-zoom`/`d3-selection` — mismo criterio que el arrastre de nodos.
const WIDTH = 800;
const HEIGHT = 520;
const TICKS = 300;
const TICKS_PER_FRAME = 3;
const MIN_ZOOM = 0.3;
const MAX_ZOOM = 3;

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

interface SimNode extends SimulationNodeDatum {
  id: string;
}

interface Point {
  x: number;
  y: number;
}

interface Transform {
  x: number;
  y: number;
  k: number;
}

const IDENTITY_TRANSFORM: Transform = { x: 0, y: 0, k: 1 };

export function GraphCanvas({
  nodes,
  relations,
  selectedId,
  onSelect,
  highlightNodeIds,
  highlightRelationIds,
  endpointIds,
}: {
  nodes: GraphNode[];
  relations: GraphRelation[];
  selectedId: string | null;
  onSelect: (nodeId: string) => void;
  // doc 13 §5.2: resaltado de un camino (`GET /v1/graph/path`). Con un set no
  // vacío, lo que no está en él se atenúa.
  highlightNodeIds?: ReadonlySet<string>;
  highlightRelationIds?: ReadonlySet<string>;
  // Nodos elegidos como extremos mientras se está armando el camino.
  endpointIds?: readonly string[];
}) {
  const [positions, setPositions] = useState<Record<string, Point>>({});
  const positionsRef = useRef(positions);
  positionsRef.current = positions;
  const [transform, setTransform] = useState<Transform>(IDENTITY_TRANSFORM);
  const svgRef = useRef<SVGSVGElement>(null);
  const draggingId = useRef<string | null>(null);
  const panStart = useRef<{ x: number; y: number; tx: number; ty: number } | null>(null);
  // Posiciones de los nodos que el usuario arrastró a mano: se fijan (`fx`/`fy`)
  // al reanimar el layout con datos nuevos (doc 13 §5.1) para no moverlos.
  const pinnedRef = useRef<Record<string, Point>>({});

  const highlightActive = highlightNodeIds !== undefined && highlightNodeIds.size > 0;

  const degree = useMemo(() => {
    const counts = new Map<string, number>();
    for (const rel of relations) {
      counts.set(rel.source_id, (counts.get(rel.source_id) ?? 0) + 1);
      counts.set(rel.target_id, (counts.get(rel.target_id) ?? 0) + 1);
    }
    return counts;
  }, [relations]);

  useEffect(() => {
    if (nodes.length === 0) {
      setPositions({});
      return;
    }
    // Conserva la posición si el nodo ya estaba (re-fetch tras una corrección):
    // evita que el layout entero salte cuando solo cambió un campo.
    const previous = positionsRef.current;
    const pinned = pinnedRef.current;
    const simNodes: SimNode[] = nodes.map((node) => {
      const base: SimNode = { id: node.id, ...previous[node.id] };
      const pin = pinned[node.id];
      if (pin) {
        base.fx = pin.x;
        base.fy = pin.y;
      }
      return base;
    });
    const nodeIds = new Set(nodes.map((node) => node.id));
    const simLinks = relations
      .filter((rel) => nodeIds.has(rel.source_id) && nodeIds.has(rel.target_id))
      .map((rel) => ({ source: rel.source_id, target: rel.target_id }));

    const simulation = forceSimulation<SimNode>(simNodes)
      .force("charge", forceManyBody().strength(-260))
      .force(
        "link",
        forceLink<SimNode, { source: string; target: string }>(simLinks)
          .id((node) => node.id)
          .distance(100),
      )
      .force("center", forceCenter(WIDTH / 2, HEIGHT / 2))
      .force("collide", forceCollide(32))
      .stop();

    const flush = () => {
      const next: Record<string, Point> = {};
      for (const simNode of simNodes) {
        next[simNode.id] = { x: simNode.x ?? WIDTH / 2, y: simNode.y ?? HEIGHT / 2 };
      }
      setPositions(next);
    };

    // Anima solo si ya había un layout en pantalla para animar desde él
    // (doc 13 §5.1). Primera carga o `prefers-reduced-motion` → pasada síncrona.
    const hadLayout = nodes.some((node) => previous[node.id] !== undefined);
    if (!hadLayout || prefersReducedMotion()) {
      for (let i = 0; i < TICKS; i += 1) simulation.tick();
      flush();
      return;
    }

    simulation.alpha(0.6).alphaDecay(0.05);
    let raf = 0;
    const step = () => {
      for (let i = 0; i < TICKS_PER_FRAME; i += 1) simulation.tick();
      flush();
      if (simulation.alpha() > simulation.alphaMin()) {
        raf = requestAnimationFrame(step);
      }
    };
    raf = requestAnimationFrame(step);
    return () => {
      cancelAnimationFrame(raf);
      simulation.stop();
    };
  }, [nodes, relations]);

  // Listener nativo (no `onWheel` de React): React marca `wheel` como pasivo
  // por defecto en el listener raíz, así que `preventDefault()` en un
  // handler JSX no evita el scroll de la página — hace falta un listener
  // agregado a mano con `{ passive: false }`. Depende de `nodes.length > 0`
  // (no `[]`) porque el `<svg>` no existe en el DOM hasta que hay nodos que
  // dibujar — con `[]` el efecto correría una sola vez, antes de que el
  // `ref` tuviera algo que atar.
  const hasNodes = nodes.length > 0;
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    function onWheel(event: WheelEvent) {
      event.preventDefault();
      const rect = svg!.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;
      const viewX = ((event.clientX - rect.left) / rect.width) * WIDTH;
      const viewY = ((event.clientY - rect.top) / rect.height) * HEIGHT;
      setTransform((current) => {
        const factor = event.deltaY < 0 ? 1.1 : 1 / 1.1;
        const nextK = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, current.k * factor));
        // Mantiene el punto bajo el cursor fijo mientras cambia el zoom.
        const nextX = viewX - ((viewX - current.x) / current.k) * nextK;
        const nextY = viewY - ((viewY - current.y) / current.k) * nextK;
        return { x: nextX, y: nextY, k: nextK };
      });
    }
    svg.addEventListener("wheel", onWheel, { passive: false });
    return () => svg.removeEventListener("wheel", onWheel);
  }, [hasNodes]);

  function toWorldPoint(clientX: number, clientY: number): Point | null {
    const svg = svgRef.current;
    if (!svg) return null;
    const rect = svg.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return null;
    const viewX = ((clientX - rect.left) / rect.width) * WIDTH;
    const viewY = ((clientY - rect.top) / rect.height) * HEIGHT;
    return {
      x: (viewX - transform.x) / transform.k,
      y: (viewY - transform.y) / transform.k,
    };
  }

  function handleNodePointerDown(nodeId: string) {
    return (event: ReactPointerEvent<SVGCircleElement>) => {
      draggingId.current = nodeId;
      event.currentTarget.setPointerCapture(event.pointerId);
    };
  }

  function handleBackgroundPointerDown(event: ReactPointerEvent<SVGRectElement>) {
    panStart.current = {
      x: event.clientX,
      y: event.clientY,
      tx: transform.x,
      ty: transform.y,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function handleSvgPointerMove(event: ReactPointerEvent<SVGSVGElement>) {
    if (draggingId.current !== null) {
      const point = toWorldPoint(event.clientX, event.clientY);
      if (point) {
        const id = draggingId.current;
        pinnedRef.current[id] = point;
        setPositions((current) => ({ ...current, [id]: point }));
      }
      return;
    }
    if (panStart.current) {
      const svg = svgRef.current;
      if (!svg) return;
      const rect = svg.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;
      const dx = ((event.clientX - panStart.current.x) / rect.width) * WIDTH;
      const dy = ((event.clientY - panStart.current.y) / rect.height) * HEIGHT;
      const start = panStart.current;
      setTransform((current) => ({ ...current, x: start.tx + dx, y: start.ty + dy }));
    }
  }

  function handleSvgPointerUp() {
    draggingId.current = null;
    panStart.current = null;
  }

  if (nodes.length === 0) {
    return (
      <div className="text-muted-foreground border-border flex h-[520px] w-full items-center justify-center rounded-lg border text-sm">
        Sin nodos para dibujar.
      </div>
    );
  }

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="border-border bg-card h-[520px] w-full touch-none rounded-lg border"
        onPointerMove={handleSvgPointerMove}
        onPointerUp={handleSvgPointerUp}
        onPointerLeave={handleSvgPointerUp}
        role="img"
        aria-label="Visualización del grafo de conocimiento"
      >
        <rect
          x={0}
          y={0}
          width={WIDTH}
          height={HEIGHT}
          fill="transparent"
          onPointerDown={handleBackgroundPointerDown}
          className="cursor-grab active:cursor-grabbing"
        />
        <g transform={`translate(${transform.x}, ${transform.y}) scale(${transform.k})`}>
          <g>
            {relations.map((rel) => {
              const from = positions[rel.source_id];
              const to = positions[rel.target_id];
              if (!from || !to) return null;
              const onPath = highlightRelationIds?.has(rel.id) ?? false;
              return (
                <line
                  key={rel.id}
                  x1={from.x}
                  y1={from.y}
                  x2={to.x}
                  y2={to.y}
                  stroke={onPath ? "var(--primary)" : "var(--border)"}
                  strokeWidth={onPath ? 2.5 : 1}
                  opacity={highlightActive && !onPath ? 0.12 : 1}
                />
              );
            })}
          </g>
          <g>
            {nodes.map((node) => {
              const point = positions[node.id];
              if (!point) return null;
              const radius = 10 + Math.min(degree.get(node.id) ?? 0, 8) * 1.5;
              const isSelected = node.id === selectedId;
              const onPath = highlightNodeIds?.has(node.id) ?? false;
              const isEndpoint = endpointIds?.includes(node.id) ?? false;
              return (
                <g
                  key={node.id}
                  transform={`translate(${point.x}, ${point.y})`}
                  onClick={() => onSelect(node.id)}
                  role="button"
                  aria-label={node.canonical_name}
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") onSelect(node.id);
                  }}
                  className="cursor-pointer"
                  opacity={highlightActive && !onPath ? 0.2 : 1}
                >
                  {isEndpoint && (
                    <circle
                      r={radius + 4}
                      fill="none"
                      stroke="var(--primary)"
                      strokeWidth={1.5}
                      strokeDasharray="3 2"
                    />
                  )}
                  <circle
                    r={radius}
                    fill={NODE_TYPE_COLORS[node.node_type]}
                    stroke={
                      isSelected
                        ? "var(--foreground)"
                        : node.locked
                          ? "var(--primary)"
                          : "var(--border)"
                    }
                    strokeWidth={isSelected ? 3 : node.locked ? 2 : 1}
                    onPointerDown={handleNodePointerDown(node.id)}
                  />
                  <text
                    y={radius + 14}
                    textAnchor="middle"
                    fontSize={11}
                    fill="var(--foreground)"
                    className="pointer-events-none select-none"
                  >
                    {node.canonical_name}
                  </text>
                </g>
              );
            })}
          </g>
        </g>
      </svg>
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="bg-card/80 absolute top-2 right-2 backdrop-blur-sm"
        onClick={() => setTransform(IDENTITY_TRANSFORM)}
      >
        Restablecer vista
      </Button>
    </div>
  );
}
