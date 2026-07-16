# 02 — Modelo de dominio y ontología del grafo

**Estado:** 🟢 Aprobado (2026-07-13) · **Última actualización:** 2026-07-11

## 1. Principio

El grafo **no guarda texto, guarda conocimiento**: entidades tipadas con propiedades, conectadas por relaciones tipadas, cada una con evidencia y nivel de confianza. El texto original vive en el almacén de documentos; el grafo solo lo referencia.

## 2. Modelo de documentos (capa de ingesta)

Antes del grafo existe el modelo unificado de documentos, común a todos los conectores:

```
RawDocument            # lo que produce un conector
├── source_id          # identidad en la fuente (ruta del vault, URL, message-id…)
├── connector          # "obsidian" | "pdf" | "git" | …
├── content            # bytes o texto original
├── mime_type
├── source_metadata    # dict libre propio del conector
└── fetched_at

ParsedDocument         # lo que produce el parser
├── doc_id             # UUID estable (hash de source_id + connector)
├── title
├── summary
├── author
├── created_at / modified_at
├── language
├── chunks[]           # ver abajo
├── entities[]         # menciones detectadas (candidatas al grafo)
├── relations[]        # relaciones detectadas (candidatas al grafo)
├── keywords[]
├── links[]            # enlaces salientes (wikilinks, URLs, imports…)
└── confidence         # calidad global del parseo (0–1)

Chunk
├── chunk_id
├── doc_id
├── text
├── position           # offset y orden dentro del documento
├── embedding          # vector (pgvector)
└── metadata           # encabezado padre, tipo de bloque…
```

## 3. Ontología del grafo — v1

### 3.1 Tipos de nodo

| Tipo | Descripción | Propiedades clave (además de las comunes) |
|---|---|---|
| `Person` | Personas (autores, colegas, referentes) | `name`, `aliases[]`, `roles[]` |
| `Project` | Proyectos propios o de terceros | `name`, `status`, `started_at`, `repo_url` |
| `Technology` | Frameworks, lenguajes, herramientas | `name`, `category`, `language`, `homepage` |
| `Concept` | Ideas abstractas, técnicas, patrones | `name`, `definition`, `domain` |
| `Document` | Referencia a un documento ingerido | `doc_id`, `title`, `connector` |
| `Task` | Tareas y objetivos | `title`, `status`, `due_date` |
| `Organization` | Empresas, comunidades, equipos | `name`, `kind` |
| `Event` | Reuniones, hitos, sucesos fechados | `name`, `occurred_at` |
| `Skill` | Capacidad del usuario (deducida o declarada) | `name`, `level`, `evidence_count` |

**Propiedades comunes a todo nodo:**

```
id              # UUID
canonical_name  # nombre normalizado (clave de deduplicación)
aliases[]       # variantes ("FastAPI", "fast-api", "fastapi")
created_at / updated_at
confidence      # 0–1: cuánta evidencia sostiene la existencia del nodo
sources[]       # doc_ids que lo mencionan
version         # versionado optimista
```

### 3.2 Tipos de relación

| Relación | Origen → Destino | Ejemplo |
|---|---|---|
| `USES` | Project → Technology | Proyecto IA `USES` FastAPI |
| `RELATED_TO` | * → * | FastAPI `RELATED_TO` Docker |
| `AUTHORED_BY` | Document/Technology → Person | FastAPI `AUTHORED_BY` Sebastián Ramírez |
| `PART_OF` | * → Project/Organization | módulo `PART_OF` proyecto |
| `DEPENDS_ON` | Technology/Concept → Technology/Concept | Kubernetes `DEPENDS_ON` contenedores |
| `PREREQUISITE_OF` | Concept/Skill → Concept/Skill | Docker `PREREQUISITE_OF` Kubernetes |
| `MENTIONS` | Document → * | nota `MENTIONS` FastAPI |
| `KNOWS` | Person(usuario) → Skill/Technology/Concept | deducida por el recomendador |
| `CONTRADICTS` | Document/Claim → Document/Claim | detección de contradicciones (Fase 5) |
| `SUPERSEDES` | Document → Document | versiones/duplicados |

**Propiedades comunes a toda relación:**

```
confidence      # 0–1
sources[]       # evidencia: doc_ids + chunk_ids que la sostienen
extracted_at
extracted_by    # "parser@vX" | "user" | "recommender"
valid_from / valid_to   # vigencia temporal (opcional)
```

### 3.3 Ejemplo canónico

```cypher
(fastapi:Technology {canonical_name: "fastapi", name: "FastAPI",
                     category: "framework", language: "Python"})
(fastapi)-[:AUTHORED_BY {confidence: 0.98}]->(:Person {name: "Sebastián Ramírez"})
(:Project {name: "Proyecto IA"})-[:USES {confidence: 0.9}]->(fastapi)
(fastapi)-[:RELATED_TO {confidence: 0.7}]->(:Technology {name: "Docker"})
(fastapi)-[:RELATED_TO {confidence: 0.6}]->(:Technology {name: "Railway"})
```

## 4. Reglas de la ontología

1. **Ontología cerrada, propiedades abiertas.** Los tipos de nodo y relación de v1 son fijos; añadir un tipo requiere ADR. Las propiedades pueden crecer libremente.
2. **Deduplicación por `canonical_name` + tipo.** El parser propone; un paso de *entity resolution* fusiona (normalización + similitud de embeddings + veredicto del LLM en casos dudosos).
3. **Nada sin evidencia.** Todo nodo/relación referencia los documentos que lo sostienen. Si la evidencia desaparece (documento borrado), la confianza decae y el elemento puede podarse.
4. **La confianza se acumula.** Cada nueva mención sube `confidence`; las contradicciones la bajan. Los umbrales de visualización/poda se configuran (defaults: mostrar ≥0.5, podar <0.2).
5. **El usuario siempre gana.** Una corrección manual fija `extracted_by: "user"` y `confidence: 1.0`, y el parser no puede sobreescribirla.

## 5. Sincronización pgvector ↔ Neo4j

- **pgvector** responde "¿qué texto se parece a esto?" (búsqueda semántica sobre chunks).
- **Neo4j** responde "¿qué se conecta con esto y cómo?" (caminos, vecindarios, deducciones).
- La clave compartida es `doc_id`/`chunk_id`: desde un resultado vectorial se salta al grafo (nodos `MENTIONS` del chunk) y viceversa (de una entidad a sus chunks de evidencia).
- La consistencia es **eventual**: el pipeline de aprendizaje (dominio 8) reconcilia ambos almacenes tras cada ingesta; ninguna consulta requiere transacciones cross-store.

## 6. Evolución prevista

| Versión | Cambio |
|---|---|
| v1 (Fase 2) | Ontología de esta página |
| v1.1 (Fase 3) | `Claim` como nodo de primera clase (afirmaciones atómicas con vigencia temporal) para memoria semántica y contradicciones |
| v2 (Fase 6) | Espacios de nombres por workspace; ontologías extensibles por plugin |
