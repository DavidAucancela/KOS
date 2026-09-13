# 14 — Despliegue en Railway (single-tenant, techo de $3/mes)

**Estado:** 🟡 Borrador (fases 0/A/B construidas y verificadas; falta C — infra Railway real) · **Última actualización:** 2026-09-12 · **Habilita:** una opción concreta
de despliegue para la etapa "v1.0 / self-hosting single-node" de
[09 — Guía de desarrollo y despliegue](09-guia-desarrollo-y-despliegue.md) §7

> Doc 09 §7 dice: "v1.0 → imágenes versionadas + compose de producción para self-hosting
> single-node; Kubernetes solo cuando haya una razón medida". Este documento no cambia esa
> estrategia — describe **una alternativa gestionada** para quien no quiere operar un host propio:
> desplegar KOS en [Railway](https://railway.app) con un **techo duro de ~$3/mes de consumo
> Railway**, aceptando las concesiones que eso obliga. No está en el roadmap (doc 07); es trabajo
> nuevo y se apoya en tres ADR aceptados (§13). Sigue siendo `docs/` la fuente de verdad — construir esto es
> una PR sobre este doc primero.

**Cambio respecto a la versión del 2026-08-27:** aquella dibujaba la topología cómoda
(api + workers + Postgres + Redis en Railway, ~$11–20/mes) y dejaba el ahorro como apéndice. El
techo de $3 invierte eso: **Postgres sale de Railway, el beat desaparece y el worker pasa a ser un
cron job**. Celery se conserva (no hay refactor de la cadena de tasks, a diferencia del antiguo
§10, que se descarta).

## 1. Problema y alcance

KOS se diseñó local-first (ADR-0006): toda la infraestructura corre en Docker Compose en la
máquina del usuario (`make up`: Postgres+pgvector, Neo4j, Redis, MinIO, Ollama), y las apps
(`apps/api`, `apps/workers`) corren nativas contra ella. Eso es lo mejor para privacidad y coste
marginal cero, pero ata el sistema a una máquina encendida.

Este documento especifica cómo llevar el mismo sistema — **un solo usuario, un solo vault** — a
Railway por **≤$3/mes de consumo Railway**, y qué hay que construir para lograrlo. No cubre
multi-tenant, alta disponibilidad, ni autoscaling (nada de eso aplica a un sistema de conocimiento
personal).

**Objetivo medible:** factura Railway < $3/mes en régimen (el plan Hobby cuesta $5/mes e incluye
$5 de uso, así que ≤$3 de consumo = $0 de excedente, con margen). Los servicios gratuitos externos
(Supabase, Neo4j Aura, Cloudflare R2) no cuentan contra ese techo; el gasto de LLM/embeddings
cloud tampoco (§10) — es una factura aparte y variable.

## 2. Las dos restricciones que mandan

### 2.1 Railway no tiene GPU

- **Ollama no puede correr ahí de forma razonable.** `bge-m3` (embeddings) y cualquier LLM local
  sobre CPU compartida serían de decenas de segundos por llamada — inviable para una ingesta de
  miles de chunks (ya es lento en un Mac con GPU, ver doc 12 §10.2).
- Por lo tanto, **desplegar en Railway obliga al camino cloud de ADR-0006**: LLM y embeddings pasan
  a proveedores externos, y ya no como opt-in por tarea (ADR-0007) sino como **default del
  entorno**. Esa es la decisión estructural del despliegue → **ADR-0008** (§13).

### 2.2 "Serverless" de Railway se mide por tráfico **saliente**

Verificado en la doc de Railway (2026-09-12): un servicio se considera inactivo tras ~5 min **sin
emitir paquetes salientes**, y despierta con la primera request entrante. Consecuencias que
cambian el diseño, no detalles de operación:

- **Un worker Celery nunca duerme**: su conexión al broker Redis es tráfico saliente permanente.
  Un servicio "workers" encendido 24/7 es, por sí solo, más de la mitad del techo de $3.
  → El worker deja de ser un proceso vivo y pasa a ser un **Railway Cron Job** (§4).
- **La API solo duerme si cierra sus conexiones**: pools de Postgres/Neo4j/Redis con conexiones
  ociosas abiertas, o un exporter de tracing con push periódico, la mantienen despierta para
  siempre. → §6 lista lo que hay que tocar en el arranque de `apps/api`.
- Cold boot: la primera request tras dormir tarda unos segundos y **puede devolver 502**. El
  cliente (web y conector) tiene que reintentar una vez.

## 3. Arquitectura de servicios

| Componente KOS | Dónde va | Por qué / notas |
|---|---|---|
| **`apps/api`** (FastAPI + web estático) | **Railway**, servicio con *serverless* activado | Duerme entre usos (§2.2). Sirve el build de `apps/web` con `StaticFiles` en la misma app → un servicio menos. |
| **`apps/workers`** (Celery) | **Railway**, servicio con **Cron Schedule** (`0 0,12 * * *` UTC — 2×/día) | Arranca, sincroniza el vault, drena la cola y **sale** (§4). Se factura solo el tiempo de ejecución. Sin `-B`: el beat lo reemplaza el cron de Railway → **ADR-0009**. |
| **Redis** | **Railway** (servicio Redis) | Broker/backend de Celery. Huella ~30–60 MB, siempre encendido, ~$0.3–0.5/mes. Es la pieza que permite no refactorizar la cadena de tasks. |
| **PostgreSQL + pgvector** | **Supabase Free** (fuera de Railway) | 500 MB de límite; la base local medida hoy son **138 MB** (`chunks` 66 MB, `node_embeddings` 59 MB) → entra con ~3,6× de margen. pgvector viene habilitado. Sacarlo de Railway ahorra ~$3–4/mes, que es justo el techo entero. |
| **Neo4j** | **Neo4j AuraDB Free** (fuera de Railway) | Free = 50k nodos / 175k relaciones. El grafo real medido hoy: **5.074 nodos** → entra con margen enorme. Aura Free se pausa tras días de inactividad; el cron de 15 min la mantiene viva. |
| **Object storage** (hoy MinIO) | **Cloudflare R2** (fuera de Railway) | 10 GB gratis, sin egress. El vault son ~200 MB. S3-compatible → solo cambia `endpoint_url` + credenciales. |
| **Vault Obsidian** | repo git privado, clonado en un **volumen** del servicio cron | §5. |
| **Ollama** | **eliminado** | Reemplazado por §10. |
| **Prometheus/Grafana** | fuera de alcance | Perfil `observability` del compose; no se despliega. Railway da métricas básicas por servicio. |

`api` y `workers` comparten imagen (mismo Dockerfile, mismo repo) y se despliegan como **dos
servicios Railway** con start command distinto.

**Por qué Postgres fuera y Redis dentro:** Postgres es el servicio con volumen y RAM que más cuesta
en Railway y tiene un equivalente gratuito holgado para 138 MB. Redis no: los free tiers por
comandos (Upstash: 10k/día) son frágiles frente al polling de Celery, y su coste en Railway es de
centavos. Se acepta perder la red privada para Postgres (la conexión sale a internet con TLS).

## 4. El worker como Cron Job (el corazón del ahorro)

Railway ejecuta el start command de un servicio según un crontab (horario **UTC**, mínimo cada
5 min) y **espera que el proceso termine**; si una ejecución sigue viva cuando toca la siguiente,
la salta sin avisar.

**Cadencia elegida: dos ejecuciones al día** — `0 0,12 * * *` UTC ≈ 19:00 y 07:00 en UTC-5
(ajustar el offset si la zona es otra). Es el punto más barato del diseño y basta para mantener
despiertas Supabase Free y Aura Free, que se pausan por inactividad. El precio es latencia: una
nota puede tardar **hasta ~12 h** en indexarse sola (§5 da el camino inmediato).

Comando del servicio `workers`: un script nuevo `scripts/railway_drain.py` que hace, en orden:

1. `git -C $VAULT_PATH pull --ff-only` sobre el clon del vault (§5).
2. Encola `kos.sync_all_sources` — lo que antes hacía el beat cada `KOS_SYNC_POLL_SECONDS`.
3. Si han pasado ≥`KOS_MEMORY_CONSOLIDATION_HOURS` desde la última consolidación (estado en
   Postgres, no en el filesystem efímero), encola también `kos.memory_consolidate`.
4. Arranca un worker Celery embebido (`--concurrency=1`, pool solo) y **lo detiene cuando la cola
   queda vacía y no hay tareas activas** durante N segundos consecutivos.
5. Si la ingesta creó notas (WritingAgent, §5), `git commit && git push`.
6. Registra la ejecución (inicio, fin, resultado, tareas drenadas) en Postgres, cierra pools
   (Postgres, Neo4j, Redis) y sale con código 0.

Reglas que hacen que el patrón no falle en silencio:

- **Timeout duro de 30 min.** Al vencer, el script para el worker, registra la ejecución como
  truncada y sale limpio; lo que no dio tiempo a procesar **queda en Redis** y lo drena el ciclo
  siguiente. Con 12 h entre ciclos nunca choca con la ejecución siguiente. Sin timeout, una tarea
  colgada correría indefinidamente — el único fallo caro de esta topología.
- **Salir de verdad.** Si el proceso no termina, Railway salta todas las ejecuciones siguientes y
  la ingesta se detiene sin error visible.
- **Cadena de tasks encadenadas.** `graph_sync → cross_doc_relations → cooccurrence_relations →
  recommend_from_graph_update` (doc 11 §3, doc 12 §4/§10.5) puede no caber en una ejecución; lo
  pendiente espera en Redis. Por eso Redis se queda.
- **Visibilidad**: `GET /v1/ops/status` expone la última ejecución y la web muestra un aviso si es
  más antigua de lo esperado (>18 h). Es el único mecanismo que convierte "el cron murió" en algo
  que se nota; la contrapartida es que solo se ve al abrir la app (ADR-0009).
- **Backfill / `reindex`**: no cabe en ventanas de 30 min y costaría caro en LLM cloud. Se corre
  desde el Mac local contra la base gestionada, no desde Railway (§9).

## 5. El vault: repo git + sync manual desde la Mac

En Railway no hay carpeta de Obsidian. El vault vive en un **repo git privado** (Obsidian Git lo
empuja desde la Mac y desde móvil), y el despliegue lo consume así:

- **Camino por defecto (automático, funciona con la Mac apagada, 2×/día):** el servicio cron mantiene un
  clon del vault en un **volumen Railway de 1 GB** (~$0.15/mes) y hace `git pull --ff-only` al
  inicio de cada ejecución. Se sigue usando **`ObsidianConnector`**, no `GitConnector`: el
  conector git trata los `.md` como documentación genérica y perdería wikilinks y frontmatter
  (`packages/connectors/.../obsidian/`). El git es solo transporte.
- **Camino inmediato (desde cualquier dispositivo):** `POST /v1/ops/sync-now`. Con 2 ciclos al
  día **este camino es parte del uso normal**, no un extra.

  La API **no puede ingerir por sí misma**: el vault vive en el volumen del servicio cron y un
  volumen de Railway se adjunta a un solo servicio, así que el filesystem del vault no existe en
  el contenedor de la API — y ejecutar el pipeline ahí, además, chocaría con la regla de
  dependencias del proyecto (`apps/api` no importa `kos_workers`, verificado por `lint-imports`).
  Lo que hace el endpoint es pedirle a Railway que **ejecute ahora el servicio cron**
  (`serviceInstanceRedeploy`), que sí tiene el vault. Devuelve 501 fuera del despliegue
  gestionado, 409 si ya hay un drain corriendo, y está limitado a
  `KOS_SYNC_NOW_PER_HOUR` disparos por hora porque cada uno arranca un contenedor.

**Consecuencia asumida:** un volumen Railway se adjunta a **un solo servicio**, y lo tiene el cron.
Por lo tanto `apps/api` **no ve el filesystem del vault**: con `KOS_DEFER_VAULT_WRITES=true`, las
herramientas de escritura (`obsidian.create_note`/`update_note`/`create_folder`, el comando
`/crear-nota` del chat y `POST /v1/notes`) dejan de escribir en disco y **encolan la intención** en
`pending_vault_writes`; el drain la materializa al inicio del ciclo siguiente —antes de encolar la
sincronización, así la nota entra al índice en esa misma pasada— y empuja el resultado al repo.
Una nota creada desde el chat aparece en el vault en minutos, no en segundos, y la respuesta lo
dice explícitamente en vez de fingir que ya existe. El gate de `confirm=true` de `permissions.py`
no cambia: sigue siendo la API quien lo exige antes de encolar.

`obsidian.read_note` es la excepción: **una lectura no se puede diferir**. En este modo devuelve un
mensaje que remite a las herramientas de recuperación sobre el contenido ya indexado (Postgres/R2),
que es donde vive lo que el sistema sabe.

## 6. Lo que hay que tocar en el código

Ninguna de estas piezas existe hoy; todas son requisito, no mejora.

| Ítem | Dónde | Por qué |
|---|---|---|
| `Dockerfile` multi-stage con `uv` + stage Node para `apps/web` | raíz | No hay ninguno: `make dev` corre procesos nativos. Una sola imagen para `api` y `workers`. |
| `railway.json` (build por Dockerfile, watch paths) | raíz | Evita redeployar `api` cuando solo cambian los workers. |
| `scripts/railway_drain.py` | `scripts/` | §4. |
| `database_url` / `redis_url` como URL completa + `sslmode` | `packages/core/.../config.py` | Hoy `postgres_dsn` se arma de 5 piezas sueltas; Supabase y Railway entregan **una URL**. Sin esto no hay forma limpia de cablear el entorno. |
| Cliente de embeddings HTTP (`base_url` + API key) | `packages/core/.../llm/` | Hoy solo existe el de Ollama. Es el bloqueante real de §10. |
| Pools que se cierren en reposo (`pool_size` mínimo, `pool_recycle`, Neo4j driver lazy) + tracing sin exporter periódico | `apps/api` | Sin esto la API **nunca duerme** y el techo de $3 se rompe (§2.2). |
| Middleware de **claves nombradas** (`KOS_API_KEYS`), Basic auth sobre **todas** las rutas incluida la web, `X-API-Key` para clientes sin navegador, + **rate limit** en memoria | `apps/api/.../middleware.py` | Hoy no hay autenticación: la API expuesta es acceso abierto a todo el conocimiento personal, y un escaneo dispara gasto de LLM cloud. → **ADR-0010**. |
| Cadena de proveedores cloud (`KOS_LLM_PROVIDER_CHAIN`) en el factory | `apps/api/.../llm/factory.py` | ADR-0008: el fallback deja de ser cloud→local y pasa a ser cloud→cloud; en producción Ollama no entra en la cadena. |
| Tabla de ejecuciones del cron + `GET /v1/ops/status` + aviso en la web | `apps/api`, `apps/workers`, `apps/web` | ADR-0009: sin esto, que el cron deje de correr es invisible. |
| `POST /v1/ops/sync-now` → `serviceInstanceRedeploy` de Railway | `apps/api/.../ops/railway.py` | Camino inmediato de §5. Único punto del código acoplado a la plataforma: si el despliegue se muda, se reemplaza este módulo y nada más. |
| Cola `pending_vault_writes` + aplicador en el drain | `packages/core`, `apps/workers` | Consecuencia del volumen único (§5). La decisión de escribir o encolar vive en un solo punto (`kos_core.notes.*_or_enqueue`), para que los tres call sites se comporten igual. |
| Release command `alembic upgrade head` | Railway | Migraciones antes de cambiar tráfico. Neo4j no tiene migraciones: sus constraints se crean idempotentes al arrancar — verificar que ese arranque tolere Aura. |
| `kos_guardian_enabled=false`, beat desactivado | config | El `docker_guardian` (doc 09 §8) no aplica en Railway; su equivalente es el serverless. |

## 7. Configuración y secretos

Todo pasa por `pydantic-settings` en `core.config` (doc 09 §5): el despliegue es un set de
variables por servicio.

| Variable | Valor en Railway | Origen |
|---|---|---|
| `DATABASE_URL` | URL de Supabase (pooler, `sslmode=require`) | Supabase dashboard |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` | servicio Railway |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | `neo4j+s://<id>.databases.neo4j.io` | Neo4j Aura console |
| `MINIO_ENDPOINT` / `*_ACCESS_KEY` / `*_SECRET_KEY` / `*_BUCKET` | endpoint y token de R2 | Cloudflare dashboard |
| `KOS_LLM_PROVIDER_CHAIN` | `openai,openrouter` | ADR-0008 |
| `OPENAI_API_KEY` / `OPENAI_LLM_MODEL` | secreto / `gpt-4o-mini` | proveedor primario |
| `OPENROUTER_API_KEY` / `OPENROUTER_BASE_URL` | secreto / `https://openrouter.ai/api/v1` | proveedor de reserva (ADR-0008) |
| `KOS_EMBEDDING_BASE_URL` / `KOS_EMBEDDING_API_KEY` / `KOS_EMBEDDING_MODEL` | endpoint bge-m3 hospedado / `bge-m3` | proveedor (§10) |
| `KOS_API_KEYS` | `web:…,mac:…,movil:…` | ADR-0010 |
| `VAULT_REPO_URL` / `VAULT_PATH` / deploy key | repo privado del vault / `/data/vault` | GitHub |
| `RAILWAY_API_TOKEN` / `RAILWAY_CRON_SERVICE_ID` / `RAILWAY_ENVIRONMENT_ID` | token de cuenta e ids del servicio cron | §5, disparo inmediato |
| `KOS_SYNC_NOW_PER_HOUR` | `4` | tope de disparos manuales |
| `KOS_ENV=production`, `KOS_LOG_LEVEL=INFO`, `KOS_GUARDIAN_ENABLED=false` | — | — |

Los secretos viven en shared variables del proyecto Railway; nunca en el repo (doc 09 §5).

## 8. Migración de datos local → gestionado

Una sola vez, con el sistema local como origen de verdad:

1. **Postgres**: `pg_dump` del `kos` local (138 MB) → `psql` contra Supabase. Requiere
   `CREATE EXTENSION vector` antes. Incluye `documents`, `chunks` (con `embedding` y
   `entity_node_ids`), `node_embeddings`, memoria, recomendaciones, planes, conversaciones.
2. **Neo4j**: dump local (5.074 nodos) → import de Aura. Si el dump 5-community no es compatible,
   plan B `apoc.export.cypher` + `cypher-shell`. **Verificar en una migración de prueba.**
3. **Object storage**: `rclone sync` MinIO local → R2.
4. **Vault**: `git init` + push del vault al repo privado.
5. **Verificación de humo**: `alembic current` coincide; conteos de nodos/relaciones/chunks
   coinciden origen↔destino; un `POST /v1/query` devuelve `evidence[]` (regla 4 del proyecto).

Desplegar limpio y re-ingerir desde cero queda descartado: cuesta el backfill completo de LLM
cloud (§10) por nada, teniendo el estado local ya calculado.

## 9. División de trabajo local ↔ Railway

Esta topología es **híbrida a propósito**, y conviene decirlo explícito:

| Operación | Dónde corre |
|---|---|
| Consulta interactiva, agentes, recomendador, web | Railway |
| Ingesta incremental del vault (unas notas/día) | Railway (cron, §4) |
| `kos reindex` / backfill completo de grafo (~70 s/doc × 755 docs ≈ 15 h) | **Mac local** contra las bases gestionadas, con Ollama → $0 de LLM cloud |
| Experimentos de calidad (doc 12), tuning de umbrales | Mac local |

## 10. LLM y embeddings cloud

- **LLM**: OpenAI como primario, ya construido (`apps/api/.../llm/openai_client.py`, factory con
  `FallbackLLMClient`, ADR-0007), con **un segundo proveedor cloud OpenAI-compatible** (OpenRouter
  o Groq) como reserva: `KOS_LLM_PROVIDER_CHAIN`. En `KOS_ENV=production` Ollama no entra en la
  cadena. Si se agota la cadena, la petición falla visiblemente.
- **Embeddings**: **bge-m3, 1024 dimensiones, sin excepción**. Un endpoint OpenAI-compatible de
  bge-m3 (Deepinfra, Together…) permite reutilizar el cliente cambiando `base_url` + auth y **no
  obliga a re-embeder** ni a migrar el schema (`vector(1024)`, ADR-0002). Cambiar a
  `text-embedding-3-*` forzaría re-embeder los ~66 MB de chunks y los 59 MB de `node_embeddings`:
  descartado.
- **Auditoría de coste**: el SDK llm-observatory ya envuelve OpenAI; con un proveedor
  OpenAI-compatible no listado en `OPENAI_PRICING` el coste sale marcado `cost_confidence=unknown`
  (doc 15 §2.1) — tokens y latencia siguen siendo correctos.
- **`cloud_safe`**: ADR-0008 le da un único significado aquí — una fuente con `cloud_safe=false`
  **no se ingiere** en el despliegue gestionado (el worker la salta y lo registra) y vive solo en
  el modo local. Es la válvula para material que no debe salir de la máquina.

## 11. Coste

**Railway** (objetivo del documento; cobra uso real, no asignación):

| Servicio | Régimen | Coste/mes |
|---|---|---|
| `api` (256–512 MB, serverless) | despierta con cada uso, duerme a los ~5–10 min | ~$0.8–1.5 |
| `workers` (cron 2×/día, ≤30 min por ejecución) | ~15–30 h de CPU-mes en el peor caso; típicamente minutos | ~$0.1–0.4 |
| Redis (30–60 MB, siempre encendido) | — | ~$0.3–0.5 |
| Volumen vault (1 GB) | — | ~$0.15 |
| **Total Railway** | | **~$1,3–2,5** ✅ (holgado bajo el techo de $3 y cubierto por los $5 del Hobby) |

**Fuera de Railway:** Supabase Free $0 · Neo4j Aura Free $0 · Cloudflare R2 $0 ·
embeddings bge-m3 hospedados ~$0–2 · LLM cloud (consultas + ingesta incremental) ~$1–5 ·
backfill inicial, si se hiciera en cloud, ~$15–50 **una vez** (por eso §9 lo manda al Mac).

**Qué rompe el techo**, en orden de probabilidad: (a) que la API no duerma por pools abiertos
(§2.2) → ~+$2/mes; (b) subir la frecuencia del cron (cada 15 min costaría ~$1/mes más);
(c) que la base pase de 500 MB y Supabase Free deje de servir (hoy 138 MB, crece con chunks y
`node_embeddings`); (d) correr un `reindex` desde Railway.

El margen que deja la cadencia de 2×/día es deliberado: es el presupuesto con el que se puede
subir a 4×/día o 1×/hora más adelante sin renegociar el techo.

## 12. Riesgos y no-objetivos

| Riesgo | Tratamiento |
|---|---|
| **Privacidad**: el conocimiento personal viaja a OpenAI/proveedor de embeddings y vive en Supabase/Aura/R2 | Concesión explícita del modo, registrada en ADR-0008. Quien no la acepte se queda en el modo local de doc 09. Mitigación parcial: proveedor con retención cero / no-training (verificar términos). |
| **API pública sin auth** | Bloqueante de despliegue, no mejora: claves nombradas + Basic sobre todas las rutas + rate limit antes del primer deploy con datos reales (ADR-0010). |
| **El cron no termina** → se saltan todas las ejecuciones siguientes y la ingesta muere en silencio | Timeout duro de 30 min en `railway_drain.py` + `GET /v1/ops/status` con aviso en la web si la última ejecución tiene >18 h. Es el fallo más probable del diseño, y el aviso **solo se ve al abrir la app** (ADR-0009). |
| **Latencia de ingesta de hasta ~12 h** con 2 ciclos al día | Asumido a cambio del coste. `POST /v1/ops/sync-now` cubre la prisa desde cualquier dispositivo; si aun así estorba, subir a 4×/día cuesta ~$0.2/mes. |
| **Token de Railway dentro de la app** para el disparo inmediato | Es un secreto con permisos sobre el proyecto entero: vive solo en las variables del servicio `api`, y el endpoint que lo usa exige credencial y está limitado por hora. Si se filtra, se rota en Railway. |
| **Dos proveedores cloud** en vez de uno (cadena de ADR-0008) | Más superficie de privacidad: hay que auditar los términos del de reserva igual que los del primario. Su coste se audita como `cost_confidence=unknown` (doc 15 §2.1). |
| **Basic auth**: cerrar sesión en el navegador es incómodo y las claves viajan en cada petición | TLS obligatorio (Railway lo da por defecto); nunca exponer por HTTP plano. Revocación por cliente gracias a las claves nombradas (ADR-0010). |
| **La API no duerme** por pools/telemetría | Verificar con la gráfica de uso de Railway en la primera semana; si no baja a cero, el techo no se cumple. |
| Supabase Free se pausa por inactividad y tiene límite de 500 MB | El cron cada 15 min la mantiene activa. Vigilar el tamaño: `node_embeddings` es el que más crece. |
| Aura Free se pausa / límite 50k nodos | 5.074 hoy; margen de años. Si se superara, tier pago (~$65/mes) → reevaluar todo el modo. |
| Cold start con 502 en la primera request | Reintento en el cliente web y en el conector. |
| `neo4j-admin dump` incompatible con Aura | Plan B `apoc`; verificar en migración de prueba antes de la real. |
| Escrituras del chat con minutos de latencia (§5) | Aceptado al elegir el techo de $3. Si molesta, el camino es un volumen para la API y el vault del lado de la API — con su propio coste. |

**Fuera de alcance:** multi-tenant y múltiples vaults (Fase 6, doc 07) · alta disponibilidad y
réplicas · observabilidad completa (Prometheus/Grafana, deuda de doc 09 §6) · mantener Ollama en
Railway (descartado en §2.1) · CD automático desde `main` (Railway lo hace nativo; se suma después).

## 13. ADRs que este despliegue requiere

| ADR | Decisión |
|---|---|
| **0008** | Proveedor cloud (LLM + embeddings) como **default del entorno** en el despliegue gestionado, y qué pasa con la puerta `cloud_safe` de ADR-0007. |
| **0009** | La planificación la hace el **cron de Railway**, no Celery beat: el worker es un proceso efímero que drena y sale. |
| **0010** | **Autenticación por API key** + rate limit para cualquier despliegue expuesto a internet. |

Ninguno revierte ADR-0006 ni ADR-0007 para el modo local: los complementan para el modo Railway.

## 14. Fases de trabajo

| Fase | Qué cubre | Criterio de salida |
|---|---|---|
| ~~0 — ADRs~~ | 0008, 0009, 0010 | ✅ Cerrada el 2026-09-12: los tres en estado Aceptado |
| ~~A — código habilitante~~ | `DATABASE_URL` en config · cliente de embeddings HTTP (falla si el proveedor no devuelve 1024 dim) · claves nombradas + Basic + rate limit · cadena de proveedores cloud (`ChainLLMClient`) · pools que duermen (NullPool en Postgres, sin keepalive en Redis, vida corta en Neo4j) · `POST /v1/ops/sync-now` vía `serviceInstanceRedeploy` · tabla `cron_runs` + `GET /v1/ops/status` | ✅ Cerrada el 2026-09-12. Verificado: 505 tests, `mypy --strict` limpio en `core`, `lint-imports` sin contratos rotos. De paso se corrigió `alembic upgrade head` (0012 tenía dos migraciones con el mismo id — el release command de Railway habría fallado). |
| ~~B — imágenes~~ | `Dockerfile` multi-stage (uv + build de `apps/web`) · `kos_workers/drain.py` (drena, consolida memoria si toca, timeout de 30 min con salida forzada si el worker no para) · `pending_vault_writes` + encolado de `obsidian.*` (decisión centralizada en `kos_core.notes.*_or_enqueue`) · `railway.json` | ✅ Cerrada el 2026-09-12. Verificado con la imagen real contra la infra local: 401 sin credencial, `/health` 200 abierto, HTML servido con credencial, `python -m kos_workers.drain` saliendo con código 0, y `POST /v1/notes` encolando de verdad (sin crear el archivo) contra Postgres real. |
| **C — infra gestionada** | Proyecto Railway (api + workers-cron `0 0,12 * * *` + Redis + volumen) · Supabase · Aura · R2 · repo privado del vault · variables (§7) | Deploy verde; `/health` responde sin credencial y `/` la pide; el cron ejecuta y termina |
| **D — migración** | §8 sobre datos reales + verificación de humo | Conteos coinciden; `/v1/query` devuelve `evidence[]` |
| **E — corte y medición** | Obsidian Git empujando al repo; uso normal 7 días | **Factura Railway proyectada < $3/mes**; las 2 ejecuciones diarias del cron aparecen en `/v1/ops/status` sin intervención; la API llega a dormir (gráfica de uso a cero entre sesiones) |

El criterio de salida de la fase E es el que decide si este modo se queda. Si no baja de $3, la
palanca siguiente es eliminar Redis y el servicio cron (ingesta síncrona en la API), que **sí**
exige refactorizar la cadena de tasks y su propio ADR.

**Deuda que las fases A/B no cierran** (no bloquea C): la migración del `.env.example` documenta
las variables pero nadie las ha usado contra un Supabase/Aura reales todavía — la fase C es la
primera vez que este código corre contra infraestructura gestionada de verdad, no solo contra la
infra local con las banderas de modo gestionado activadas.
