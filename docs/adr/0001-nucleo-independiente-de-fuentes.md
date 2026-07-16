# ADR-0001 — El núcleo es independiente de las fuentes; Obsidian es un conector

**Estado:** Aceptado
**Fecha:** 2026-07-11

## Contexto

El proyecto nace de la necesidad de razonar sobre un vault de Obsidian (~1.000 notas), pero en el horizonte hay muchas más fuentes: Notion, Google Drive, Gmail, Slack, Discord, GitHub, Jira, Confluence, exportaciones de WhatsApp, transcripciones, vídeo, audio, bases SQL y APIs. Si el núcleo asume estructuras de Obsidian (vault, wikilinks, frontmatter), cada nueva fuente exigirá tocar el núcleo, y el sistema quedará limitado en un año.

## Decisión

El producto es un **motor de conocimiento independiente** (KOS). Toda fuente, incluida Obsidian, se integra mediante un conector que implementa la interfaz `Connector` (`discover`/`fetch`/`watch`) y produce el modelo interno común (`RawDocument`). Ninguna estructura de una fuente concreta cruza la frontera del conector.

## Alternativas consideradas

- **Plugin de Obsidian / "Obsidian AI"** — máximo aprovechamiento del ecosistema Obsidian, pero acopla el producto a una app de terceros y bloquea las demás fuentes. Descartada.
- **Núcleo con "casos especiales" por fuente** — más rápido al principio, degenera en un núcleo inmantenible. Descartada.

## Consecuencias

- Positivas: añadir una fuente = escribir un conector; el núcleo no cambia. Habilita el SDK de conectores de v1.0.
- Negativas: los conceptos ricos de Obsidian (wikilinks, tags) deben mapearse a conceptos genéricos (`links[]`, `keywords[]`), perdiendo algo de fidelidad al principio.
- Si se revierte: el nombre, la ontología y la interfaz de conectores tendrían que rediseñarse alrededor de Obsidian.
