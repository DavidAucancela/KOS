# 00 — Visión y objetivos del producto

**Estado:** 🟢 Aprobado (2026-07-13) · **Última actualización:** 2026-07-11

## 1. La visión

KOS (Knowledge Operating System) es un **motor de conocimiento independiente**. No es "un chat sobre mis notas de Obsidian": es una plataforma que construye una representación digital del conocimiento de una persona (y más adelante, de un equipo) y permite que una IA razone sobre él.

La pregunta que define el producto:

> **¿Cómo hago que una IA piense utilizando exactamente el mismo conocimiento que tengo yo, pero mejor organizado que mi propia memoria?**

Esto cambia el enfoque por completo: no se trata de buscar archivos, se trata de **modelar conocimiento**.

## 2. Principios de producto

| # | Principio | Implicación práctica |
|---|---|---|
| P1 | El núcleo no depende de ninguna fuente | Obsidian es un conector más; mañana lo serán Notion, Gmail, Slack, GitHub… |
| P2 | El activo es el modelo de conocimiento | Ontología + grafo + memoria valen más que cualquier LLM concreto |
| P3 | El LLM es un componente reemplazable | Nunca accede directamente a los datos; siempre media el planner |
| P4 | Local-first | Todo funciona en local; la nube es opcional, nunca obligatoria |
| P5 | El sistema aprende y propone | No solo responde: detecta lagunas, contradicciones y oportunidades |
| P6 | Plataforma, no aplicación | Conectores, herramientas MCP y APIs públicas desde el diseño |

## 3. Qué es y qué NO es

**KOS es:**

- Un pipeline de ingesta multi-fuente hacia un modelo interno común.
- Un grafo de conocimiento con ontología propia (entidades + relaciones, no texto).
- Un sistema de memoria de largo plazo (episódica, semántica, procedimental, temporal, de preferencias).
- Una orquestación de agentes donde cada consulta se resuelve con un plan de ejecución.
- Un recomendador proactivo que deduce lo que sabes y lo que te falta.

**KOS NO es:**

- Un plugin de Obsidian.
- Un wrapper de RAG genérico sobre una carpeta de markdown.
- Un cliente de chat con "contexto de archivos".
- Dependiente de ningún proveedor de LLM en la nube.

## 4. Usuario objetivo

| Horizonte | Usuario | Necesidad |
|---|---|---|
| v0.x | El fundador (dogfooding) | Razonar sobre ~1.000 notas de Obsidian + PDFs + repos |
| v1.0 | Knowledge workers técnicos | Un segundo cerebro consultable y proactivo |
| v2.x+ | Equipos y organizaciones | Espacios de trabajo compartidos, permisos, marketplace |

## 5. Casos de uso canónicos

Estos cinco casos guían todas las decisiones de diseño. Si una funcionalidad no sirve a ninguno, no se construye.

1. **Consulta con evidencia** — "¿Qué sé sobre X?" → respuesta sintetizada con citas a las fuentes originales.
2. **Navegación por relaciones** — "¿Qué conecta FastAPI con mi proyecto de agentes?" → camino en el grafo, no similitud de texto.
3. **Memoria de contexto** — "¿Qué decidimos sobre esto hace seis meses?" → memoria episódica versionada.
4. **Detección de lagunas** — "Sabes Docker, FastAPI, Linux y Git; te falta Kubernetes" → deducido por el grafo, no escrito por nadie.
5. **Mantenimiento automático** — nueva nota → embeddings, grafo, memoria y roadmap se actualizan solos.

## 6. Métricas de éxito

| Fase | Métrica |
|---|---|
| Fase 1 | Responder preguntas sobre el vault con ≥1 cita correcta en >90% de los casos |
| Fase 2 | Extraer entidades y relaciones con precisión validada manualmente >80% |
| Fase 3 | Cambios en fuentes reflejados en el sistema en <5 minutos, sin intervención |
| Fase 4 | Consultas complejas resueltas con planes multi-agente trazables |
| Fase 5 | ≥1 recomendación útil por semana que el usuario no había pedido |
| Fase 6 | Un tercero puede escribir un conector sin tocar el núcleo |

## 7. Riesgos principales

| Riesgo | Mitigación |
|---|---|
| Sobre-ingeniería antes de tener valor | Cada fase termina con una meta usable (ver [roadmap](07-roadmap-versiones.md)) |
| Extracción de entidades de baja calidad | Nivel de confianza por afirmación + revisión humana en v0.x |
| LLM local insuficiente para extracción | Interfaz de LLM abstracta: se puede enchufar API cloud para tareas concretas |
| El grafo se degrada con el volumen | Ontología estricta + deduplicación + versionado desde Fase 2 |
| Scope creep de conectores | Núcleo cerrado a fuentes; solo se añaden conectores, nunca lógica especial |

## 8. Nombre

Nombre de trabajo: **KOS (Knowledge Operating System)**. El directorio del repo (`Obsidian-ultra`) es histórico y no compromete el nombre del producto.
