# ADR-0008 — Proveedor cloud por defecto en el despliegue gestionado

**Estado:** Aceptado
**Fecha:** 2026-09-12

## Contexto

ADR-0006 fijó local-first con Ollama; ADR-0007 abrió una ruta cloud **opt-in por tarea**
(Planner y WritingAgent) dejando ingesta, grafo, memoria y embeddings exclusivamente locales.

El despliegue gestionado de [doc 14](../14-despliegue-en-railway.md) rompe la premisa física de
ADR-0006: Railway no ofrece GPU, y `bge-m3` o un LLM local sobre CPU compartida hacen inviable la
ingesta (doc 12 §10.2). No hay una variante "local" de ese entorno: o el LLM y los embeddings son
remotos, o no hay despliegue.

Hechos medidos (2026-09-12): la base local son 138 MB, de los cuales 66 MB son `chunks.embedding`
y 59 MB `node_embeddings`, todos en `vector(1024)` producidos por bge-m3 (ADR-0002).

## Decisión

En el entorno de despliegue gestionado (`KOS_ENV=production` sobre la topología de doc 14), el
proveedor cloud deja de ser opt-in por tarea y pasa a ser el **default del entorno** para **todas**
las tareas de LLM (Planner, Writing, ingesta, extracción de grafo, memoria, recomendador) y para
los **embeddings**.

Tres restricciones que la decisión incluye:

1. **El modelo de embeddings no cambia**: bge-m3 a 1024 dimensiones, servido por un endpoint
   OpenAI-compatible. Cambiar de modelo obligaría a re-embeder todo y a migrar el schema.
2. **Cadena de proveedores cloud, no fallback local.** El `FallbackLLMClient` de ADR-0007 se
   generaliza a una cadena ordenada de proveedores **todos cloud**:
   `KOS_LLM_PROVIDER_CHAIN=openai,openrouter`. Si el primario devuelve error o timeout, se
   reintenta con el siguiente; si se agota la cadena, la petición falla de forma visible. En
   `KOS_ENV=production` **Ollama nunca entra en la cadena** (no existe en ese entorno), y la
   respuesta registra qué proveedor la sirvió.
3. **El proveedor de reserva es de la misma familia de wire format** (OpenAI-compatible: OpenRouter,
   Groq, DeepSeek…), para que baste `base_url` + clave sin código nuevo por proveedor (doc 15
   §2.1). Su coste se audita con `cost_confidence="unknown"` porque no está en `OPENAI_PRICING`:
   los tokens y la latencia siguen siendo correctos, el importe no es de fiar. Es aceptable para
   un camino de excepción; no lo sería para el primario.

La puerta `cloud_safe` por fuente de ADR-0007 **deja de filtrar por tarea** en este entorno —
todo el contenido ingerido viaja a cloud por definición — y pasa a significar una sola cosa:
**una fuente con `cloud_safe=false` no se ingiere en el despliegue gestionado**. El worker la
salta en el sync y queda registrada como omitida; se sincroniza solo en el modo local. Es la
válvula para material que no debe salir de la máquina.

El modo local de doc 09 no cambia: sigue siendo Ollama por defecto y ADR-0007 sigue rigiendo ahí.

## Alternativas consideradas

- **Mantener el opt-in por tarea también en producción** — no resuelve nada: las tareas no
  configurables a cloud (ingesta, grafo, embeddings) son justamente las que no pueden correr sin
  GPU. Sería un despliegue que no puede ingerir.
- **Sin fallback, un único proveedor** — más simple y con auditoría de coste fiable siempre, pero
  una caída del proveedor deja el sistema sin consultas **y sin ingesta** hasta que vuelva.
  Descartado: la resiliencia vale las ~15 líneas de factory.
- **Fallback al Ollama de la Mac por túnel** — mantiene el espíritu de ADR-0006 y cuesta $0, pero
  solo funciona con la Mac encendida y accesible, que es justo la dependencia que este despliegue
  elimina.
- **Embeddings de OpenAI (`text-embedding-3-*`)** — cambia `EMBEDDING_DIM`, fuerza re-embeder
  ~125 MB de vectores y migrar el schema de ADR-0002, y rompe la comparabilidad con lo ya
  indexado. Descartado por coste y riesgo, no por preferencia de proveedor.
- **Ollama en CPU dentro de Railway** — decenas de segundos por llamada; inviable (doc 14 §2.1).
- **Ingesta solo local, Railway solo consulta** — deja el conocimiento remoto congelado cuando el
  Mac está apagado, que es justo el problema a resolver.

## Consecuencias

- **Positivas:** el sistema deja de depender de una máquina encendida; las consultas dejan de
  pagar la latencia de generación local; no hay re-embed ni migración de schema; una caída del
  proveedor primario degrada la calidad, no la disponibilidad.
- **Negativas / deuda aceptada:** todo el conocimiento personal ingerido viaja a terceros (LLM y
  embeddings) y reside en Supabase/Aura/R2 — exactamente lo que ADR-0006 quería evitar; **son dos
  proveedores, no uno**, y el de reserva hay que auditarlo en términos igual que el primario; el
  coste deja de ser marginal cero y pasa a ser variable por uso, con importes no fiables cuando
  responde la reserva; un `reindex` completo en cloud es caro, por lo que doc 14 §9 lo manda al
  Mac local con Ollama.
- **Mitigación exigida:** proveedores con retención cero / sin entrenamiento, verificados en sus
  términos antes del corte; `cloud_safe=false` disponible para excluir fuentes sensibles del
  despliegue gestionado.
- **Si se revierte:** se vuelve al modo local de doc 09 sin migración de datos (el schema y los
  vectores son los mismos); solo hay que reapuntar las variables de entorno y reactivar Ollama.
