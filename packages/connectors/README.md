# packages/connectors

**Conectores de ingesta** — un paquete por fuente. Solo dependen de `packages/core`.

Todo conector implementa la interfaz `Connector` (`discover` / `fetch` / `watch`) y produce `RawDocument`. Un conector no parsea, no hace chunking, no toca bases de datos ([ADR-0001](../../docs/adr/0001-nucleo-independiente-de-fuentes.md)).

| Conector | Fase |
|---|---|
| `obsidian/` | 1 (Sprint 2) |
| `pdf/` | 1 (Sprint 5) |
| `git/` | 1 (Sprint 5) |
| ChatGPT/Claude JSON, email, HTML/web, DOCX, CSV… | Post-v0.2 |

Especificación completa: [docs/05-ingesta-y-actualizacion.md](../../docs/05-ingesta-y-actualizacion.md).
