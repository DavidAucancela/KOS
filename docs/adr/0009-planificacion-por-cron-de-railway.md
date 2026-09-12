# ADR-0009 — La planificación la hace el cron de Railway, no Celery beat

**Estado:** Aceptado
**Fecha:** 2026-09-12

## Contexto

`apps/workers/src/kos_workers/celery_app.py` define hoy dos entradas de `beat_schedule`:
`kos.sync_all_sources` cada `KOS_SYNC_POLL_SECONDS` (300 s) y `kos.memory_consolidate` cada 24 h.
El despliegue local corre `celery worker -B`: un proceso vivo permanentemente.

Verificado en la documentación de Railway (2026-09-12): el modo *Serverless* duerme un servicio
solo tras ~5 minutos **sin tráfico saliente**, y una conexión abierta al broker cuenta como
tráfico saliente. Un worker Celery escuchando Redis, por tanto, **nunca duerme** y se factura 24/7;
por sí solo consumiría más de la mitad del techo de $3/mes de doc 14. Railway sí ofrece Cron Jobs
nativos: ejecutan el start command según un crontab (mínimo cada 5 min, horario UTC) y facturan
solo el tiempo de ejecución, con el requisito de que el proceso **termine** — si una ejecución
sigue viva cuando toca la siguiente, Railway **salta** la nueva sin avisar.

## Decisión

En el despliegue gestionado, el scheduler es el **Cron Schedule de Railway**, y el servicio
`workers` es un **proceso efímero**: `scripts/railway_drain.py` hace `git pull` del vault, encola
`kos.sync_all_sources`, drena la cola con un worker embebido de concurrencia 1, empuja al repo las
notas creadas y sale.

Parámetros de la decisión:

- **Frecuencia: dos ejecuciones al día** (`0 0,12 * * *` UTC ≈ 19:00 y 07:00 en UTC-5; ajustable).
  Es el punto más barato del diseño y basta para mantener despiertas Supabase Free y Neo4j Aura
  Free, que se pausan por inactividad prolongada.
- **Timeout duro de 30 minutos.** Al vencer, el script termina el worker, cierra pools y sale con
  código 0 dejando en Redis lo que no dio tiempo a procesar; el ciclo siguiente lo drena. Con 12 h
  entre ciclos nunca puede chocar con la ejecución siguiente.
- **Consolidación de memoria dentro del mismo drain**: el script comprueba si han pasado
  ≥`KOS_MEMORY_CONSOLIDATION_HOURS` desde la última consolidación (estado en Postgres, no en el
  filesystem efímero) y, si toca, encola `kos.memory_consolidate` en esa misma ejecución. No hay
  un segundo servicio.
- **Detección de fallo silencioso dentro del propio sistema**: cada ejecución registra inicio, fin,
  resultado y tareas drenadas en una tabla de Postgres; `GET /v1/ops/status` la expone y la web
  muestra un aviso visible cuando la última ejecución es más antigua de lo esperado. Sin esto, el
  modo de fallo característico del diseño (el cron deja de correr) es invisible.

Celery y Redis **se conservan**: la cadena encadenada
`graph_sync → cross_doc_relations → cooccurrence_relations → recommend_from_graph_update` no se
reescribe. `celery beat` no se despliega. En el modo local sigue siendo el scheduler y no cambia
nada.

## Alternativas consideradas

- **Worker 24/7 con `-B` (topología original de doc 14 §3)** — rompe el techo de coste por sí solo.
- **Cron cada 15 o 30 min** — latencia de ingesta mucho mejor por ~$0.5–1/mes más. Descartado a
  favor del techo de coste: el disparo manual desde la Mac cubre los casos con prisa.
- **Sin timeout, drenar hasta vaciar** — nunca deja trabajo pendiente, pero una tarea colgada
  corre indefinidamente (el fallo caro) y bloquea las ejecuciones siguientes.
- **Segundo cron service para la consolidación de memoria** — separación más limpia y logs
  propios, a cambio de otra pieza en la topología; no lo justifica una tarea diaria.
- **Monitoreo externo tipo healthchecks.io** — avisa aunque el despliegue entero esté caído, que
  es justo cuando hace falta; descartado por no añadir un tercero más, aceptando que el aviso solo
  se ve al abrir la app.
- **Ingesta síncrona en la API, sin Redis ni Celery** — el ahorro adicional es de centavos y el
  coste es reescribir la cadena de tasks perdiendo los reintentos, con riesgo de dejar el grafo a
  medias. Queda como palanca de último recurso si la fase E de doc 14 no baja de $3.
- **Cron externo (GitHub Actions) llamando a `/v1/sources/{id}/sync`** — mantiene la API despierta
  haciendo el trabajo pesado dentro del servicio web y añade una dependencia fuera de Railway.
- **Ingesta inmediata dentro de la API** (`BackgroundTasks`) — inviable por dos motivos
  independientes: el vault vive en el volumen del cron y un volumen solo se adjunta a un servicio,
  y `apps/api` no puede importar `kos_workers` (regla de dependencias del proyecto). El disparo
  inmediato se resuelve pidiéndole a Railway que ejecute ahora el servicio cron
  (`POST /v1/ops/sync-now`, doc 14 §5).

## Consecuencias

- **Positivas:** el compute del worker baja a céntimos al mes; el scheduler es gestionado y
  observable desde Railway; cero refactor de la cadena de tasks; el estado de ejecución queda
  visible en la propia app.
- **Negativas / deuda aceptada:** una nota puede tardar **hasta ~12 h** en indexarse si no se
  dispara la sync a mano con `/v1/ops/sync-now` — el camino manual deja de ser un extra y pasa a ser parte del uso
  normal; en días de mucha escritura el grafo puede ir un ciclo por detrás por el timeout de
  30 min; el aviso de cron muerto solo se ve al abrir la web; la consolidación de memoria hereda
  la cadencia del drain (se ejecuta en el primer ciclo tras cumplirse las 24 h, no a una hora fija).
- **Si se revierte:** basta volver a `celery worker -B` como proceso vivo; el `beat_schedule` no
  se borra del código, solo se deja de usar en producción.
