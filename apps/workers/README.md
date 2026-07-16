# apps/workers

**Workers asíncronos de KOS** — Celery + Redis.

Ejecutan todo lo que no debe bloquear al usuario: ingesta de fuentes, pipeline del parser, embeddings, entity resolution, pipeline de aprendizaje y jobs de consolidación de memoria.

- Pipeline de ingesta: [docs/05-ingesta-y-actualizacion.md](../../docs/05-ingesta-y-actualizacion.md)
- Pipeline de aprendizaje: [docs/04-memoria-y-aprendizaje.md](../../docs/04-memoria-y-aprendizaje.md)
- Se scaffoldea en el **Sprint 1**.
