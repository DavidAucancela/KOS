# 10 — Estructura del proyecto y organización de archivos

**Estado:** 🟢 Aprobado (2026-07-14) · **Última actualización:** 2026-07-14

Este documento fija **dónde vive cada cosa**: el árbol objetivo del monorepo, qué contiene cada directorio y en qué sprint se crea. Es el mapa que evita que el código aterrice "donde caiga". Si un archivo nuevo no encaja en esta estructura, primero se actualiza este documento.

## 1. Árbol completo (objetivo a v0.2, con las extensiones de fases posteriores marcadas)

```
kos/
├── README.md                     # Puerta de entrada del proyecto
├── CLAUDE.md                     # Contexto para asistentes IA
├── Makefile                      # Atajos de desarrollo
├── docker-compose.yml            # Infraestructura local
├── .env.example                  # Variables documentadas (nunca .env real)
├── pyproject.toml                # Raíz del workspace uv + config compartida (Sprint 1)
├── pnpm-workspace.yaml           # Workspace JS (Sprint 1)
├── package.json                  # devDeps JS compartidas: eslint/prettier (Sprint 1)
├── .python-version               # Versión de Python del workspace (Sprint 1)
│
├── docs/                         # ═══ FUENTE DE VERDAD DEL DISEÑO ═══
│   ├── README.md                 # Índice + estados de aprobación
│   ├── 00…10-*.md                # Documentos de arquitectura
│   ├── adr/                      # Decisiones (inmutables una vez aceptadas)
│   └── sprints/                  # Retros por sprint (sprint-00.md, …)
│
├── apps/                         # ═══ DEPLOYABLES ═══
│   ├── api/                      # FastAPI (sección 2)
│   ├── workers/                  # Celery (sección 3)
│   └── web/                      # React (sección 4)
│
├── packages/                     # ═══ LIBRERÍAS ═══
│   ├── core/                     # Contratos, ontología, clientes (sección 5)
│   ├── connectors/               # Un subpaquete por fuente (sección 6)
│   ├── agents/                   # Planner y agentes — Fase 4 (sección 7)
│   └── mcp-tools/                # Servidores MCP (sección 8)
│
├── infra/                        # ═══ CONFIGURACIÓN DE SERVICIOS ═══
│   ├── postgres/init.sql         # Extensiones (vector, pg_trgm, uuid)
│   └── prometheus/prometheus.yml
│
├── scripts/                      # Utilidades de desarrollo (demo_sprint1.py, …) (Sprint 1)
├── .github/workflows/            # ci.yml (hoy) · integration/eval/release (⏳)
└── .data/                        # Datos locales de Docker (gitignored)
```

⏳ = aún no existe; se crea en el sprint indicado.

## 2. `apps/api` — API pública (Sprint 1)

```
apps/api/
├── pyproject.toml
├── src/kos_api/
│   ├── main.py                   # create_app() + registro de routers
│   ├── deps.py                   # Dependencias FastAPI: sesiones de BD, auth
│   ├── middleware.py             # trace_id, errores RFC 9457, CORS
│   ├── routes/                   # UN ARCHIVO POR RECURSO de la API (doc 06)
│   │   ├── health.py             #   GET /health                    Sprint 1
│   │   ├── sources.py            #   /v1/sources*                   Sprint 2
│   │   ├── documents.py          #   /v1/documents*                 Sprint 2
│   │   ├── search.py             #   POST /v1/search                Sprint 3
│   │   ├── query.py              #   POST /v1/query                 Sprint 4
│   │   ├── graph.py              #   /v1/graph/*                    Fase 2
│   │   ├── memory.py             #   /v1/memory*                    Fase 3
│   │   ├── plans.py              #   /v1/plans/*                    Fase 4
│   │   └── recommendations.py    #   /v1/recommendations            Fase 5
│   └── services/                 # Orquestación por caso de uso
│       ├── query_service.py      #   pipeline fijo → planner (Fase 4)
│       ├── document_service.py   #   listado/detalle/chunks     Sprint 2
│       └── source_service.py
└── tests/                        # Espejo de src/: test_routes_health.py, …
```

**Regla:** `routes/` solo valida entrada/salida y delega en `services/`; los `services/` solo componen piezas de `packages/` — la lógica de dominio nunca vive aquí.

## 3. `apps/workers` — Procesamiento asíncrono (Sprint 1)

```
apps/workers/
├── pyproject.toml
├── src/kos_workers/
│   ├── celery_app.py             # Configuración Celery + colas
│   ├── tasks/                    # UNA TASK POR EVENTO del bus (doc 06 §3)
│   │   ├── ingest.py             #   document.ingested → parseo      Sprint 2
│   │   ├── embed.py              #   lotes de embeddings             Sprint 3
│   │   ├── graph_sync.py         #   document.parsed → grafo         Sprint 6
│   │   ├── learning.py           #   pipeline de aprendizaje         Fase 3
│   │   └── consolidate.py        #   consolidación de memoria        Fase 3
│   └── pipeline/                 # LAS 9 ETAPAS DEL PARSER (doc 05 §3)
│       ├── base.py               #   interfaz Stage + composición
│       ├── s1_normalize.py       │
│       ├── s2_metadata.py        │  Sprint 2
│       ├── s3_chunking.py        │
│       ├── s4_embeddings.py      #   Sprint 3
│       ├── s5_summary.py         │  Sprint 4
│       ├── s6_keywords.py        │
│       ├── s7_entities.py        │  Sprint 6
│       ├── s8_relations.py       │
│       └── s9_confidence.py      #   Sprint 6
└── tests/
```

**Regla:** cada etapa `sN_*.py` es una función pura `ParsedDocument → ParsedDocument`, testeable sin Celery ni bases de datos.

## 4. `apps/web` — UI tipo IDE (Sprint 1)

```
apps/web/
├── package.json
├── vite.config.ts · tsconfig.json   # Tailwind v4 se configura en src/index.css (sin tailwind.config)
├── src/
│   ├── main.tsx · App.tsx        # Shell: layout de 4 paneles (doc 01, dominio 10)
│   ├── api/                      # ⚙️ GENERADO desde OpenAPI — no editar a mano
│   ├── features/                 # UNA CARPETA POR PANEL/CAPACIDAD
│   │   ├── status/               #   pantalla de salud               Sprint 1
│   │   ├── chat/                 #   centro: conversación + citas    Sprint 4
│   │   ├── explorer/             #   izquierda: fuentes/entidades    Sprint 4
│   │   ├── graph/                #   derecha: grafo interactivo      Fase 2
│   │   └── traces/               #   abajo: planes y herramientas    Fase 4
│   ├── components/               # shadcn/ui + componentes compartidos
│   └── lib/                      # utilidades sin estado
└── tests/                        # vitest
```

**Regla:** una `feature/` no importa de otra `feature/`; lo compartido baja a `components/` o `lib/`.

## 5. `packages/core` — El corazón compartido (Sprint 1)

```
packages/core/
├── pyproject.toml
├── src/kos_core/
│   ├── config.py                 # Settings tipadas (pydantic-settings)
│   ├── schemas/                  # LOS CONTRATOS (docs 02, 03, 06)
│   │   ├── documents.py          #   RawDocument, ParsedDocument, Chunk
│   │   ├── entities.py           #   EntityCandidate, RelationCandidate
│   │   ├── memory.py             #   MemoryItem                     Fase 3
│   │   ├── agents.py             #   AgentRequest/Response, EvidenceRef
│   │   └── events.py             #   document.ingested, .parsed, …
│   ├── ontology/                 # ONTOLOGÍA COMO CÓDIGO (doc 02 §3)              Sprint 6
│   │   ├── nodes.py              #   Person, Project, Technology, …
│   │   └── relations.py          #   USES, RELATED_TO, PREREQUISITE_OF, …
│   ├── llm/                      # Interfaz abstracta (ADR-0006)
│   │   ├── base.py               #   LLMClient / EmbeddingClient (Protocol)
│   │   └── ollama.py             #   implementación por defecto
│   ├── storage/                  # Clientes de infraestructura
│   │   ├── postgres.py · neo4j.py · minio.py · redis.py
│   │   └── search.py             #   búsqueda híbrida + fusión RRF   Sprint 3
│   ├── alembic/                  # Migraciones de Postgres (core es dueño del esquema)
│   └── observability.py          # Logs estructurados + OTel
└── tests/
```

**Regla:** `core` no importa de ningún otro paquete interno. Es la única dependencia compartida.

## 6. `packages/connectors` — Fuentes (Sprint 2+)

```
packages/connectors/
├── pyproject.toml
├── src/kos_connectors/
│   ├── base.py                   # Protocol Connector + SourceRef + ChangeEvent (doc 05 §2)
│   ├── registry.py               # Descubrimiento de conectores instalados
│   ├── obsidian/                 #   Sprint 2
│   │   ├── connector.py          #   discover/fetch/watch
│   │   ├── wikilinks.py          #   [[...]] → links[]
│   │   └── frontmatter.py        #   YAML → metadata
│   ├── pdf/                      #   Sprint 5
│   └── git/                      #   Sprint 5
└── tests/                        # + fixtures/: mini-vault, PDFs, repo de prueba
```

**Regla:** cada conector es un subpaquete autocontenido; añadir uno nuevo = añadir una carpeta, cero cambios fuera.

## 7. `packages/agents` — Fase 4

```
packages/agents/
├── src/kos_agents/
│   ├── base.py                   # Agent (Protocol) sobre AgentRequest/Response
│   ├── planner/                  #   generación y ejecución de planes (doc 03)
│   │   ├── planner.py · plan.py · executor.py
│   ├── retrieval.py · graph.py · memory.py
│   ├── research.py · writing.py · learning.py
└── tests/
```

Se crea vacío salvo `base.py` (los contratos se usan desde el Sprint 4 en el pipeline fijo).

## 8. `packages/mcp-tools` — Fase 3+

```
packages/mcp-tools/
├── src/kos_mcp/
│   ├── server.py                 # Registro y arranque de servidores MCP
│   ├── permissions.py            # Escrituras requieren aprobación (doc 06 §4)
│   └── tools/                    # UN MÓDULO POR DOMINIO de herramienta
│       ├── vector.py · docs.py                    # lectura     Fase 1
│       ├── graph.py                               # lectura     Fase 2
│       ├── memory.py · obsidian.py                # escritura   Fase 3
│       └── github.py · web.py · roadmap.py        # externas    Fases 4–5
└── tests/
```

## 9. Convenciones transversales

| Tema | Convención |
|---|---|
| Nombres de paquete Python | `kos_<área>` (`kos_core`, `kos_api`, `kos_workers`…) |
| Layout Python | siempre `src/` layout + `tests/` como espejo de `src/` |
| Tests | junto a su paquete, nunca en un `tests/` global |
| Fixtures de datos | `tests/fixtures/` dentro de cada paquete |
| Migraciones | solo en `packages/core/alembic/` — un único dueño del esquema |
| Código generado | marcado con encabezado `# GENERATED` y carpeta propia (`apps/web/src/api/`) |
| Documentos de diseño | `docs/NN-nombre.md`; retros en `docs/sprints/sprint-NN.md` |
| Archivos de sprint futuros | no se crean placeholders vacíos: cada archivo nace en su sprint |

## 10. Cómo leer este documento durante el desarrollo

1. ¿Vas a crear un archivo? Búscalo aquí primero. Si no está previsto, o encaja en una regla existente o se actualiza este doc en la misma PR.
2. Las anotaciones de sprint (`Sprint N` / `Fase N`) se corresponden con [08 — Plan de sprints](08-plan-de-sprints.md) y [07 — Roadmap](07-roadmap-versiones.md).
3. Las reglas de dependencia entre estas carpetas están en [09 — Guía de desarrollo](09-guia-desarrollo-y-despliegue.md) §2 y se verifican en CI.
