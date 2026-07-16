# ADR-0006 — Local-first: Ollama como runtime de LLM por defecto

**Estado:** Aceptado
**Fecha:** 2026-07-11

## Contexto

KOS procesa la totalidad del conocimiento personal del usuario: notas, correos, conversaciones, documentos privados. Enviar todo eso a una API cloud es un problema de privacidad y de coste (la ingesta y el aprendizaje continuo hacen millones de llamadas pequeñas). A la vez, los modelos locales son más débiles que los frontier para razonamiento complejo.

## Decisión

**Ollama** es el runtime por defecto para embeddings (bge-m3 / nomic-embed-text) y para el LLM de las tareas de pipeline (resúmenes, extracción de entidades, clasificación). El acceso al LLM pasa por una **interfaz abstracta** en `packages/core` con implementaciones intercambiables; el usuario puede configurar un proveedor cloud por tarea (p. ej., solo la síntesis final) de forma explícita y opt-in.

## Alternativas consideradas

- **Cloud-first (API de un proveedor)** — mejor calidad inmediata, pero rompe el principio P4 (local-first), crea coste variable por cada nota ingerida y una dependencia estructural. Descartada como default.
- **Solo local, sin escape a cloud** — puro pero poco pragmático: la extracción de relaciones puede necesitar un modelo mayor puntualmente. Descartada.
- **llama.cpp / vLLM directos** — más control y rendimiento, más operación manual. Ollama da gestión de modelos y API uniforme; suficiente para v0.x. Reevaluable.

## Consecuencias

- Positivas: privacidad por defecto; coste marginal cero por ingesta; el sistema funciona sin conexión.
- Negativas: calidad de extracción dependiente del hardware del usuario; hay que diseñar prompts/validación para modelos medianos (salida estructurada validada contra la ontología + confidence score, ver doc 05).
- La interfaz abstracta obliga a mantener contratos de LLM neutrales al proveedor — que es exactamente el principio P3 (el LLM es reemplazable).
