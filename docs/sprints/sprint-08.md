# Retro — Sprint 8: "No fabricar plantillas"

**Estado:** ✅ Cerrado 2026-07-25 (backfill del vault real completado: 689 `content` + 9
`template` = 698 documentos) · Fuera del plan original de sprints (pedido directo del usuario,
igual que el Sprint 7) — se documenta igual con el mismo formato para no perder el hilo.

## Motivación

Al usar "Preguntar al conocimiento" con una pregunta del tipo "quiero crear información para
describir un proyecto, ¿qué plantilla me sirve?", el sistema **fabricó** una plantilla
combinando fragmentos de una plantilla real (`_Templates/Proyecto.md`), un README de otro
proyecto, notas de tags y una nota de ciberseguridad irrelevante, presentándolo todo como si
fuera una sola estructura coherente. Causa raíz: el pipeline fijo de `answer_query` numera toda
la evidencia sin distinguir "nota de plantilla" de "nota de contenido", y el system prompt
permite explícitamente "conectar/resumir lo que varios fragmentos dicen en conjunto" — la
licencia que produjo la fabricación.

Coincide con deuda ya anotada en la retro del Sprint 7: *"solo un comando (`/nueva-maquina`),
no un mecanismo genérico de comandos multi-plantilla en el chat"*.

## Qué se construye

- **Campo `doc_type`** (`"content" | "template"`) en el modelo de documento (doc 02 §2):
  decidido por el conector Obsidian (carpeta `_Templates/` + frontmatter, lógica
  fuente-específica dentro de ADR-0001) y promovido a campo genérico en el bootstrap del
  pipeline de workers. Se propaga hasta `SearchHit` → `EvidenceRef` → respuesta de `/v1/query`
  y hasta la UI (badge "Plantilla" en las citas).
- **Detección de intención de plantilla** (`s0` del pipeline fijo de `answer_query`): heurística
  determinista por palabras clave (sin LLM), generalizando el mismo patrón que ya usaba
  `/nueva-maquina` (bypass del pipeline por texto de la query) — consistente con la regla de
  CLAUDE.md de que el LLM nunca media directamente pre-Fase 4.
- **Respuesta sin fabricación** ante esa intención: si hay una plantilla candidata clara, se
  cita de verdad y se sugiere el comando exacto para crearla (`confidence=1.0`, sin pasar por el
  LLM); si es ambigua, se devuelve una pregunta de aclaración fija con la lista real de
  plantillas existentes — nunca una síntesis libre.
- **Comando genérico `/crear-nota <template>|<folder>|<título>`**, generalización de
  `/nueva-maquina` (que queda como alias de compatibilidad), reutilizando
  `notes_service.create_note()` sin cambios.
- **Refuerzo del system prompt** de `answer_query` como segunda línea de defensa: cada bloque de
  evidencia indica su tipo (plantilla/nota), y se prohíbe explícitamente presentar contenido de
  documentos distintos y no relacionados como si fuera una sola entidad coherente.

## Incidente y aprendizaje del sprint

**Bug real atrapado solo por la prueba manual contra la API real, no por los tests mockeados.**
Los filtros opcionales `doc_type` añadidos a `lexical_search`/`title_search`/`vector_search`
(`packages/core/src/kos_core/storage/search.py`) usaban `(:doc_type IS NULL OR d.doc_type =
:doc_type)` en SQL textual (`sqlalchemy.text`); Postgres no puede inferir el tipo de un parámetro
que solo aparece en comparaciones con `NULL`/columna sin ningún literal tipado de referencia
(`psycopg.errors.AmbiguousParameter: could not determine data type of parameter $2`). Los 188
tests unitarios (con `search_storage` mockeado) no lo detectaron; sí lo hizo la prueba manual
end-to-end contra Postgres real de este sprint. **Arreglado** con `CAST(:doc_type AS text)`
explícito en las tres queries. **Lección**: cualquier parámetro SQL textual que solo se compara
contra `NULL` (patrón "filtro opcional") necesita cast explícito — Postgres no tiene de dónde
inferir el tipo sin él.

**Reindex del vault real (`vault-real`, 692 documentos) en curso, no completado en este sprint.**
`kos reindex --source vault-real` se encoló para poblar `doc_type` en los datos ya indexados
(la columna nueva tiene default `content` para todo lo existente hasta que se reprocesa). Con
692 documentos y las etapas de resumen/keywords vía LLM local por documento, el backfill completo
toma bastante más que la duración de este sprint — se deja corriendo en segundo plano (barato,
reentrante, no bloquea el resto de la funcionalidad) en vez de esperarlo. Verificado en su lugar
con pruebas dirigidas: `ObsidianConnector.fetch()` + `run_pipeline()` sobre
`_Templates/Proyecto.md` en el vault real confirmado con `doc_type="template"`; el comando
`/crear-nota Proyecto | <folder> | <título>` probado end-to-end contra la API real y el vault
real (nota creada y verificada con el contenido correcto de la plantilla, luego eliminada por ser
solo de prueba). La rama `s0` de intención de plantilla también se probó en vivo: no fabricó
nada (respondió honestamente "no encontré ninguna plantilla" mientras el backfill no había
llegado a `_Templates/` todavía) y no llamó al LLM.

## Seguimiento tras pruebas manuales del usuario (2026-07-25)

Dos hallazgos reales de una tanda de 15 pruebas manuales contra la API real, ambos corregidos:

1. **`intent_service.py` no cubría órdenes imperativas.** "voy a tener una reunion, crea una
   planilla para los apuntes" no activaba `s0` (solo cubría preguntas tipo "¿qué plantilla...?"),
   así que caía al pipeline normal — y ahí el LLM local **violó el refuerzo del prompt** del
   punto 5 y fabricó una "plantilla" combinando el comentario Templater de `Reunion` con una nota
   real de otra reunión y una nota de coaching de consumo totalmente ajena. Confirma que el
   refuerzo del prompt es, como estaba documentado, una defensa débil de segunda línea — la
   heurística de intención es la que realmente evita la fabricación. Se agregaron patrones para
   "crea/hazme/necesito/dame/genera (una) plantilla", y se trató "planilla" como alias real de
   "plantilla" (sinónimo regional en varios países hispanohablantes, no solo un typo) en todos
   los patrones. Regresión cubierta en `test_intent_service.py`.
2. **Bug preexistente de título expuesto por el listado nuevo** (`_Templates/*.md` mostraba
   `<% tp.file.title %>` como título porque el frontmatter de las plantillas trae ese placeholder
   de Templater sin instanciar, y `s2_metadata.py` lo tomaba como título real). Arreglado con un
   filtro genérico de "esto es sintaxis de plantilla sin resolver" (`<% %>`, `{{ }}`) tanto en el
   título de frontmatter como en el del primer encabezado, cayendo al stem del archivo cuando
   aplica. No es específico de Obsidian/Templater — cualquier motor de plantillas con esos
   marcadores queda cubierto. Regresión en `test_pipeline_s2_metadata.py`. Verificado
   reingestando en vivo las 9 plantillas del vault real (sin esperar el resto del backfill).

## Qué se recorta (deuda visible)

- El umbral de score para decidir "candidata clara" vs. "ambiguo" es un valor inicial
  conservador (referencia: `_TITLE_SIMILARITY_THRESHOLD` de `search.py`), pendiente de ajustar
  con uso real del vault — documentado como heurística a refinar, no una constante definitiva.
- La detección de intención es heurística de palabras clave en español; no cubre paráfrasis
  fuera de los patrones cubiertos. El refuerzo del prompt es la red de seguridad para esos casos
  límite, no una solución completa.
- Sin test determinista posible contra el LLM real para "no fabricación" en el caso general
  (fuera de la rama `s0`) — la verificación de esa parte es cualitativa/manual, documentada en
  este sprint.
- La aclaración de qué mide `confidence` en la UI se trata como mejora menor; si no hay margen
  en el sprint, queda como deuda para el siguiente.
- ~~El backfill de `doc_type` sobre `vault-real` sigue corriendo en segundo plano~~ — **completado**:
  689 `content` + 9 `template` = 698 documentos verificado en Postgres al cerrar el sprint.

## Qué se aprendió

- El patrón de bypass por texto de query que ya existía para `/nueva-maquina` generaliza bien a
  "intención en lenguaje natural" sin necesitar un planner real ni una llamada LLM adicional —
  confirma que el pipeline fijo pre-Fase 4 puede cubrir más casos de los que parecía sin romper
  la regla de "LLM nunca accede a datos directamente".
- Indexar plantillas exactamente igual que notas de contenido (sin ningún marcado) fue el hueco
  que permitió la fabricación: cualquier fuente que mezcle "artefactos reutilizables" con
  "contenido" necesita esta distinción desde el conector, no como parche en el prompt.
