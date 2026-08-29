# 14 — Despliegue en Railway (single-tenant, mínimo coste)

**Estado:** 🟡 Borrador · **Última actualización:** 2026-08-27 · **Habilita:** una opción concreta
de despliegue para la etapa "v1.0 / self-hosting single-node" de
[09 — Guía de desarrollo y despliegue](09-guia-desarrollo-y-despliegue.md) §7

> Doc 09 §7 dice: "v1.0 → imágenes versionadas + compose de producción para self-hosting
> single-node; Kubernetes solo cuando haya una razón medida". Este documento no cambia esa
> estrategia — describe **una alternativa gestionada** para quien no quiere operar un host propio:
> desplegar KOS en [Railway](https://railway.app) con el menor coste mensual posible, aceptando las
> concesiones que eso obliga. No está en el roadmap (doc 07); es trabajo nuevo y requiere su ADR
> (ver §5 y §12). Sigue siendo `docs/` la fuente de verdad — construir esto es una PR sobre este
> doc primero.

## 1. Problema y alcance

KOS se diseñó local-first (ADR-0006): toda la infraestructura corre en Docker Compose en la
máquina del usuario (`make up`: Postgres+pgvector, Neo4j, Redis, MinIO, Ollama), y las apps
(`apps/api`, `apps/workers`) corren nativas contra ella. Eso es lo mejor para privacidad y coste
marginal cero, pero ata el sistema a una máquina encendida.

Este documento especifica cómo llevar el mismo sistema — **un solo usuario, un solo vault** — a
Railway con la factura mensual más baja alcanzable, y qué hay que construir para lograrlo. No
cubre multi-tenant, alta disponibilidad, ni autoscaling (nada de eso aplica a un sistema de
conocimiento personal).

## 2. La restricción central: Railway no tiene GPU

Railway corre contenedores sobre CPU/RAM, sin acceso a GPU. Consecuencias directas:

- **Ollama no puede correr ahí de forma razonable.** `bge-m3` (embeddings) y cualquier LLM local
  sobre CPU compartida serían de decenas de segundos por llamada — inviable para una ingesta de
  miles de chunks (ya es lento en un Mac con GPU, ver doc 12 §10.2).
- Por lo tanto, **desplegar en Railway obliga al camino cloud opt-in de ADR-0006**: LLM y
  embeddings pasan a proveedores externos. Esta es la decisión estructural de este doc; ADR-0006
  ya la contempla como opción explícita, pero elegirla como default de un despliegue concreto
  merece un ADR propio (§5).
- El resto de la infra (Postgres, Neo4j, Redis, object storage) sí corre en Railway o en tiers
  gestionados gratuitos — §3–§4.

## 3. Arquitectura de servicios

| Componente KOS | Dónde va | Por qué / notas |
|---|---|---|
| **Neo4j** | **Neo4j AuraDB Free** (fuera de Railway) | Free tier = 50k nodos / 175k relaciones. KOS tras el backfill de doc 12 §10: del orden de ~3k nodos / ~6k relaciones — entra con margen enorme. `NEO4J_URI` pasa a `neo4j+s://<id>.databases.neo4j.io`. AuraDB Free se pausa tras varios días de inactividad y se reanuda al conectar (aceptable para uso personal). |
| **Object storage** (hoy MinIO) | **Cloudflare R2** (fuera de Railway) | 10 GB gratis, sin cargos de egress. El vault entero son ~200 MB (746 notas + ~455 adjuntos). R2 es S3-compatible → el cliente `minio`/`boto3` solo cambia `endpoint_url` + credenciales. Alternativa equivalente: Backblaze B2. |
| **PostgreSQL + pgvector** | **Railway** (plugin Postgres) | El plugin de Railway permite `CREATE EXTENSION vector`. Datos ~200 MB + índices. Instancia mínima + volumen 1 GB. Alternativa: desplegar `pgvector/pgvector:pg16` como servicio propio con volumen — mismo coste, más control de versión. |
| **Redis** | **Railway** (plugin Redis) | Broker y backend de Celery. Instancia mínima. Upstash Redis free (10k comandos/día) queda corto para el polling de Celery beat — mejor el servicio de Railway. |
| **`apps/api`** (FastAPI) | **Railway** (servicio, con *serverless*/sleep) | Se despierta en frío ante la primera request. Sirve además el build estático de `apps/web` vía `StaticFiles` montado en la misma app → un servicio menos, cero coste extra de frontend. |
| **`apps/workers`** (Celery worker + beat) | **Railway** (servicio) | Un único proceso `celery -A kos_workers worker -B` — el `-B` embebe el beat en el worker (válido para single-node; Railway no lo desaconseja para 1 réplica). No puede dormir si el beat tiene que hacer polling de fuentes (doc 05 §2). Ver §10 para evitarlo. |
| **`apps/web`** | dentro de `apps/api` (o Cloudflare Pages, gratis) | No merece un servicio propio. |
| **Ollama** | **eliminado** | Reemplazado por §5. |
| **Prometheus/Grafana** | fuera de alcance | Perfil `observability` del compose; no se despliega en esta topología mínima (doc 09 §6 ya reconoce que las métricas están incompletas). Railway expone métricas básicas de servicio por sí solo. |

`apps/api` y `apps/workers` comparten imagen base pero se despliegan como **dos servicios Railway
distintos con el mismo repo** (root directory del monorepo + start command distinto por servicio).

## 4. Datastores gestionados fuera de Railway

Se sacan de Railway a propósito, porque su tier gratuito es más barato que correrlos como servicio
con volumen:

- **Neo4j → AuraDB Free.** Único costo real evitado: una instancia Neo4j en Railway necesita
  ~1 GB de RAM (JVM) → sería el servicio más caro de todos. Aura Free lo pone en $0 para el
  tamaño de grafo de KOS.
- **MinIO → R2.** MinIO en Railway con volumen es barato pero no gratis; R2 a este volumen es $0 y
  además quita un servicio con estado del despliegue.

Postgres y Redis sí se quedan en Railway porque su footprint es chico y tenerlos en la misma red
privada del proyecto simplifica la config (variables `${{Postgres.DATABASE_URL}}` /
`${{Redis.REDIS_URL}}` inyectadas automáticamente).

## 5. LLM y embeddings en la nube — requiere ADR

Hoy `packages/core/src/kos_core/llm/base.py` define la interfaz abstracta que exige ADR-0006, pero
la **única implementación es `ollama.py`**. Esta topología necesita:

1. **Cliente LLM cloud** implementando `base.py` (Anthropic como opción de referencia — ver doc 12
   §addendum sobre coste). Se enchufa por config, sin tocar los llamadores
   (`tasks/graph_sync.py`, `tasks/enrich.py`, `packages/agents`).
2. **Embeddings hospedados que preserven el modelo.** Clave: seguir usando **bge-m3, 1024
   dimensiones**. Un endpoint OpenAI-compatible de bge-m3 (Deepinfra, Together, etc.) permite
   reutilizar `OllamaEmbeddingClient` casi tal cual (solo cambia `base_url` + auth) y **no obliga a
   re-embeder** los chunks existentes ni a migrar el schema (`vector(1024)`, ADR-0002). Cambiar a
   `text-embedding-3-*` de OpenAI cambiaría `EMBEDDING_DIM` y forzaría un re-embed completo —
   descartado por coste y riesgo.
3. **ADR nuevo**: "Proveedor cloud de LLM/embeddings para despliegue gestionado". Registra que,
   para este modo de despliegue, el opt-in de ADR-0006 deja de ser por-tarea y pasa a ser el
   default del entorno; y las consecuencias de privacidad (todo el conocimiento personal viaja a
   un tercero) que ADR-0006 explícitamente quería evitar. No revierte ADR-0006 para el modo local
   — lo complementa para el modo Railway.

Coste estimado del proveedor: ver §9.

## 6. Imágenes y arranque

No existen Dockerfiles todavía (`make dev` corre procesos nativos). Hace falta:

- **`Dockerfile` multi-stage con `uv`** para las apps Python: stage de build con `uv sync
  --frozen`, stage runtime slim con solo el venv + el código. Una sola imagen sirve para `api` y
  `workers`; el comando de arranque lo pone Railway por servicio.
- **`api`**: `uvicorn kos_api.main:app --host 0.0.0.0 --port $PORT`. Antes, servir el build de
  `apps/web` (`pnpm --filter web build` en el stage de build de Node, copiado a la imagen y
  montado con `StaticFiles`).
- **`workers`**: `celery -A kos_workers.celery_app worker -B --concurrency=2`.
- **Release command** (Railway lo corre antes de cambiar tráfico al deploy nuevo):
  `alembic upgrade head`. Neo4j no tiene migraciones versionadas — sus constraints se crean
  idempotentes al arrancar la API (revisar que ese arranque tolere Aura).
- **`railway.json`** en la raíz o config por servicio en el dashboard (build = Dockerfile, watch
  paths para no redeployar `api` cuando solo cambian los workers).

## 7. Configuración y secretos

Todo pasa por `pydantic-settings` en `core.config` (doc 09 §5), así que el despliegue es un set de
variables de entorno por servicio en Railway:

| Variable | Valor en Railway | Origen |
|---|---|---|
| `POSTGRES_*` / `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | plugin Railway |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` | plugin Railway |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | credenciales de AuraDB | Neo4j Aura console |
| `MINIO_ENDPOINT` / `*_ACCESS_KEY` / `*_SECRET_KEY` / `*_BUCKET` | endpoint y token de R2 | Cloudflare dashboard |
| `KOS_LLM_PROVIDER` + API key del proveedor | nuevo (parte del ADR de §5) | secreto del proveedor |
| `OLLAMA_EMBEDDING_*` → `KOS_EMBEDDING_BASE_URL` + key | endpoint de bge-m3 hospedado | proveedor |
| `KOS_LOG_LEVEL`, feature flags `KOS_FEATURE_*` | según entorno | — |

Los secretos viven en el "shared variables" del proyecto Railway o por servicio; nunca en el repo
(doc 09 §5). El `docker_guardian` (doc 09 §8) **no aplica** en Railway — su equivalente es el modo
*serverless*/sleep de los servicios (§10).

## 8. Migración de datos local → producción

Una sola vez, con el sistema local como origen de verdad:

1. **Postgres**: `pg_dump` del `kos` local → `psql` contra `DATABASE_URL` de Railway. Incluye
   `documents`, `chunks` (con `embedding` y `entity_node_ids`), `node_embeddings`, memoria,
   recomendaciones, planes, conversaciones.
2. **Neo4j**: `neo4j-admin database dump` local → herramienta de import de Aura (o `cypher-shell`
   con `apoc.export/import` si el dump no es compatible entre versiones).
3. **Object storage**: `rclone sync` del bucket MinIO local → R2.
4. **Verificación**: `alembic current` coincide; conteos de nodos/relaciones/chunks coinciden
   entre origen y destino; una consulta `/v1/query` de humo devuelve `evidence[]` (regla 4 del
   proyecto).

Alternativa si no interesa migrar el estado: desplegar limpio y re-ingerir el vault desde cero
apuntando el conector a una copia del vault (más caro en llamadas LLM cloud — ver §9).

## 9. Coste mensual estimado

Órdenes de magnitud, no cotización. Railway Hobby: $5/mes que incluyen $5 de uso, luego
consumo-based (RAM ~$10/GB-mes, vCPU ~$20/vCPU-mes, volumen ~$0.15/GB-mes).

| Concepto | Coste/mes |
|---|---|
| `api` (512 MB, con sleep) | ~$2–4 |
| `workers` (512 MB, siempre encendido por el beat) | ~$3–6 |
| Postgres (256–512 MB + 1 GB volumen) | ~$3–4 |
| Redis (256 MB + volumen chico) | ~$2–3 |
| Neo4j AuraDB Free | $0 |
| Cloudflare R2 (200 MB) | $0 |
| Embeddings bge-m3 hospedado (uso incremental) | ~$0–2 |
| LLM cloud (ingesta incremental de notas nuevas/editadas) | ~$1–5 |
| **Total recurrente** | **~$11–20/mes** |
| Backfill inicial de extracción (una vez, ver doc 12 §addendum) | ~$15–50 |

El compute de Railway domina la factura. El coste del LLM recurrente es bajo mientras la ingesta
sea incremental (unas pocas notas por día); un `kos reindex` completo vuelve a costar como el
backfill inicial.

## 10. Modo económico agresivo (requiere refactor)

Para bajar a **~$5–8/mes**: eliminar Redis + Celery del despliegue.

- La ingesta pasa a ser síncrona dentro de `apps/api`: un endpoint `/v1/admin/sync` (o webhook
  del proveedor del vault) que corre el pipeline en `BackgroundTasks` de FastAPI, sin cola.
- Sin Celery beat → sin polling programado; la sincronización se dispara a mano o por webhook.
- Railway queda con **`api` + Postgres** (+ Aura + R2 gratis). `api` puede dormir del todo entre
  usos.
- **Coste**: Celery hoy es la columna del pipeline encadenado
  (`graph_sync → cross_doc_relations → cooccurrence_relations → recommend_from_graph_update`,
  doc 11 §3, doc 12 §4/§10.5). Reescribir eso como llamadas directas encadenadas en proceso es
  trabajo real y hay que cuidar que un fallo a mitad de cadena no deje el grafo inconsistente
  (hoy Celery reintenta). Es una decisión con su propio ADR; no es "config".

Recomendación: empezar con la topología de §3 (Celery incluido) y solo pasar a §10 si la factura
de Railway lo justifica con números reales.

## 11. Riesgos y no-objetivos

| Riesgo | Tratamiento |
|---|---|
| **Privacidad**: todo el conocimiento personal viaja a proveedores cloud (LLM, embeddings) y vive en Aura/R2 | Es la concesión explícita de este modo de despliegue; se documenta en el ADR de §5. Quien no la acepte se queda en el modo local de doc 09. Mitigación parcial: proveedor con retención cero / no-training (verificar términos). |
| AuraDB Free se pausa tras inactividad y tiene límites duros | Aceptable para uso personal; el primer request tras la pausa reconecta con latencia. Si el grafo supera 50k nodos (improbable en años), toca tier pago (~$65/mes) — reevaluar entonces. |
| Cold start del `api` con sleep | Uso personal tolera segundos de arranque en frío. Si molesta, desactivar sleep en `api` (~$2–4/mes extra). |
| Deriva de coste del LLM si se hace `reindex` seguido | El `reindex` completo cuesta como el backfill (§9). Documentar que es una operación cara en este modo, no rutinaria. |
| `neo4j-admin dump` incompatible entre la versión local (5-community) y Aura | Plan B: export/import vía `apoc` o `cypher-shell` con `CALL apoc.export.cypher`. Verificar en la migración de prueba antes de la real. |
| Un solo worker con `-B`: si el proceso muere, no hay beat ni ingesta hasta el restart | Railway reinicia el servicio al caer. Aceptable para single-node; monitorear con un healthcheck del worker. |

**Fuera de alcance:**
- Multi-tenant, múltiples vaults, aislamiento por workspace (Fase 6, doc 07).
- Alta disponibilidad / múltiples réplicas / autoscaling.
- CD automático desde `main` — se puede sumar después (Railway lo hace nativo con GitHub), no es
  parte del diseño de arquitectura.
- Observabilidad completa (Prometheus/Grafana) — depende de cerrar la deuda de monitoreo (doc 09
  §6), no de este doc.
- Mantener Ollama como opción en Railway — descartado por §2, no se re-evalúa aquí.

## 12. Trabajo requerido y evolución por fases

| Fase | Qué cubre |
|---|---|
| **Prerrequisito (código)** | Cliente LLM cloud sobre `llm/base.py`; cliente de embeddings HTTP (o `OllamaEmbeddingClient` con `base_url` configurable); **ADR** del proveedor cloud (§5). Sin esto, nada de lo demás sirve. |
| **Fase A — imágenes** | Dockerfiles multi-stage `uv` para `api`/`workers`; build de `apps/web` embebido en `api`; `alembic upgrade head` como release command; `railway.json`. |
| **Fase B — infra gestionada** | Crear proyecto Railway (Postgres + Redis); AuraDB Free; bucket R2. Cablear variables (§7). |
| **Fase C — migración** | Ejecutar §8 sobre datos reales; verificación de humo. |
| **Fase D — corte** | Apuntar el conector del vault al despliegue; desactivar el sistema local o dejarlo como respaldo/origen de `reindex`. |
| Opcional posterior | Modo económico agresivo (§10) si la factura lo pide; CD desde `main`; observabilidad. |

Ninguna de estas fases está planificada en el roadmap (doc 07); es trabajo nuevo que se aborda
solo si se decide que KOS necesita vivir fuera de una máquina propia.
