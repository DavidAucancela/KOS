# 08 — Resultados del set de evaluación (vault real)

**Estado:** 🟢 completo · **Fecha:** 2026-07-16

Corrida contra `POST /v1/query` (modo `hybrid`, límite por defecto) sobre el vault real ya ingerido (`vault-real`).
Acierto = al menos una referencia en `evidence[].source_id` coincide con el archivo fuente esperado
(comparación normalizada Unicode NFC, ya que el filesystem de macOS entrega nombres en NFD).

| # | Pregunta | Doc esperado | Doc(s) citado(s) (top 3) | Acierto |
|---|---|---|---|---|
| 1 | ¿Qué comando de nmap muestra la versión de los servicios en los puertos abiertos? | `Security/Nmap.md` | `Security/Nmap.md`, `Security/IBM/Gestión de vulnerabilidades.md`, `Security/HackTheBox/Máquinas/Capitan - HTTP.md` | ✅ |
| 2 | ¿Qué puertos TCP quedaron abiertos en la prueba de nmap, según mis notas? | `Security/Nmap.md` | `Security/Nmap.md`, `Security/IBM/Gestión de vulnerabilidades.md`, `Security/HackTheBox/Máquinas/N2.1 Appointment - Linux.md` | ✅ |
| 3 | ¿Qué protocolo corre sobre el puerto 445 según mis notas de Nmap? | `Security/Nmap.md` | `Security/Nmap.md`, `Security/HackTheBox/Máquinas/3. Dancing - SMB.md`, `Security/IBM/Gestión de vulnerabilidades.md` | ✅ |
| 4 | ¿Qué comando uso en Linux para generar una contraseña aleatoria en base64 desde la terminal? | `Security/generar contraseñas en el terminal.md` | `Security/_INDEX.md`, `_MOCs/Seguridad MOC.md`, `Security/generar contraseñas en el terminal.md` | ✅ |
| 5 | En Windows, ¿qué comando de PowerShell genero para crear una contraseña/GUID? | `Security/generar contraseñas en el terminal.md` | `_MOCs/Seguridad MOC.md`, `Security/_INDEX.md`, `Security/generar contraseñas en el terminal.md` | ✅ |
| 6 | ¿Cuál fue el primer virus informático mundialmente reconocido, según mis notas de malware? | `Security/Malware.md` | `Security/Malware.md`, `Security/Malware.md`, `Security/Malware.md` | ✅ |
| 7 | ¿Qué gusano informático usaron los atacantes para dañar las centrifugadoras de procesamiento de uranio en Irán? | `Security/Malware.md` | `Security/Malware.md`, `Security/IBM/Seguridad del sistema.md`, `Security/IBM/Seguridad Ofensiva.md` | ✅ |
| 8 | ¿Qué troyano robaba credenciales bancarias propagándose por fuerza bruta, según mis notas? | `Security/Malware.md` | `Security/Malware.md`, `DeTo/07-Seguridad/Zero Trust (SGT)/Zero Trust arquitectura.md`, `Security/IBM/Seguridad del sistema.md` | ✅ |
| 9 | ¿Cuál es uno de los ataques de ransomware más conocidos que mencioné en mis notas de malware? | `Security/Malware.md` | `Security/Malware.md`, `Security/Malware.md`, `Security/IBM/Seguridad Ofensiva.md` | ✅ |
| 10 | ¿En qué empresa ocurrió el ejemplo famoso de ataque con bomba lógica que anoté? | `Security/Malware.md` | `Security/Malware.md`, `English/Cambridge/mid term 7th.md`, `English/Cambridge/mid term 7th.md` | ✅ |
| 11 | ¿Qué es Dark Hotel según mis notas? | `Security/Malware.md` | `Security/Dark web.md`, `Security/Malware.md`, `Security/_INDEX.md` | ✅ |
| 12 | ¿Qué es la dark web según mis notas? | `Security/Dark web.md` | `Security/Dark web.md`, `Security/_INDEX.md`, `Security/IBM/Seguridad Ofensiva.md` | ✅ |
| 13 | ¿Qué comando del asistente jonathan.sec muestra el perfil (rol, clearance, stack, contacto)? | `Security/jonathan.sec comands.md` | `Octavo/Aplicaciones 2/SGT/Sprint 10  - sistema v1.md`, `DeTo/01-Backend/Python/Celery.md`, `Octavo/Aplicaciones 2/SGT/Tecnologías.md` | ❌ |
| 14 | ¿Qué comando de jonathan.sec muestra los detalles del proyecto SecuraBank? | `Security/jonathan.sec comands.md` | `Security/_INDEX.md`, `Security/HackTheBox/Máquinas/Capitan - HTTP.md`, `DeTo/03-Bases de datos/Supabase/Autenticación Supabase.md` | ✅ |
| 15 | Menciona un puesto de trabajo de ciberseguridad que anoté en mis vacantes de seguridad. | `Security/Vacantes en Seguridad Informática.md` | `Security/_INDEX.md`, `Security/Vacantes en Seguridad Informática.md`, `Security/IBM/Amenazas emergentes y el futuro de las tecnologías de ciberseguridad.md` | ✅ |
| 16 | ¿Cuál es la estructura del Zero Conditional en inglés? | `English/Conditionals.md` | `DeTo/07-Seguridad/Zero Trust (SGT)/Zero Trust arquitectura.md`, `DeTo/09-Conceptos fundamentales/Otros/Null or NoNull.md`, `DeTo/07-Seguridad/Zero Trust (SGT)/Zero Trust arquitectura.md` | ❌ |
| 17 | ¿Cuál es la estructura del First Conditional? | `English/Conditionals.md` | `English/Conditionals.md`, `English/Present perfect and present continuous.md`, `English/Second an Third Conditional.md` | ✅ |
| 18 | ¿Qué significa el modal verb "must" según mis notas de inglés? | `English/Modal verbs.md` | `English/_Templates/_Template - Autoevaluacion mensual.md`, `English/Modal verbs.md`, `English/Indirect questions.md` | ✅ |
| 19 | ¿Cuál es la diferencia entre "who" y "whose" según mis notas? | `English/WHO or WHOSE.md` | `English/BHIN/B1/Relative clauses.md`, `English/WHO or WHOSE.md`, `DeTo/99-Personal/_INDEX.md` | ✅ |
| 20 | En reported speech, ¿en qué se convierte "will" en estilo indirecto? | `English/Reported speech.md` | `English/Reported speech 1.md`, `English/Indirect questions.md`, `English/English - MOC.md` | ✅ |
| 21 | ¿En qué se convierte "can" cuando se pasa a reported speech? | `English/Reported speech.md` | `English/Reported speech 1.md`, `English/Indirect questions.md`, `English/Reported speech.md` | ✅ |
| 22 | ¿Qué diferencia hay entre present perfect y present perfect continuous según mis notas? | `English/Present perfect and present continuous.md` | `English/Going to y will.md`, `English/Present perfect and present continuous.md`, `English/_Templates/_Template - Autoevaluacion mensual.md` | ✅ |
| 23 | ¿Cuándo se usa "be going to" en vez de "will" para hablar del futuro? | `English/Going to y will.md` | `English/Future continous-progressive.md`, `English/Going to y will.md`, `English/Going to y will.md` | ✅ |
| 24 | Según mis notas de inglés, ¿para qué se usa la preposición "for"? | `English/For, at and on.md` | `English/prepositions to, for, at.md`, `English/English - MOC.md`, `English/For, at and on.md` | ✅ |
| 25 | ¿Qué parámetros de generación de un LLM mencioné en mis notas de GDG sobre prompts (temperatura, top k, top p)? | `GDG/Escribir bien prompts.md` | `GDG/Escribir bien prompts.md`, `DeTo/10-Proyectos/LLM Observatory/SDK python - LLM observatory.md`, `DeTo/06-IA y ML/Conceptos/RAG.md` | ✅ |
| 26 | En mi diseño de prompts para KOS, ¿en qué formato debe responder el Prompt 1 de clasificación de consultas? | `GDG/structura prompt.md` | `GDG/structura prompt.md`, `Tesis/Otros/cursor_Informe de implementación del modelo CRISP-DM para panel semántico.md`, `DeTo/10-Proyectos/LLM Observatory/SDK python - LLM observatory.md` | ✅ |
| 27 | ¿Qué debe hacer el Prompt 2 de mi diseño de prompts, según mis notas de GDG? | `GDG/structura prompt.md` | `GDG/structura prompt.md`, `GDG/structura prompt.md`, `DeTo/10-Proyectos/LLM Observatory/SDK python - LLM observatory.md` | ✅ |
| 28 | En el proyecto Nunna, ¿qué variables de entorno de Supabase hay que configurar en Railway? | `Work/Nunna/Nunna - login - supabase.md` | `Work/Nunna/Nunna - login - supabase.md`, `DeTo/03-Bases de datos/Supabase/steps Supabase.md`, `Work/_INDEX.md` | ✅ |
| 29 | ¿Qué RPC de Supabase se aplica junto con el schema.sql en el proyecto Nunna? | `Work/Nunna/Nunna - login - supabase.md` | `Work/_INDEX.md`, `DeTo/03-Bases de datos/Supabase/Supabase.md`, `Work/Nunna/_README.md` | ❌ |
| 30 | ¿Qué personajes de Nunna faltan por tener imágenes, según mi roadmap? | `Work/Nunna/Nunna - login - supabase.md` | `Work/Nunna/_README.md`, `Work/Nunna/_README.md`, `Work/_INDEX.md` | ✅ |
| 31 | ¿Qué imagen oficial de broker MQTT usé en mi práctica de Docker? | `IEEE - CS/Docker/Broker MQTT.md` | `IEEE - CS/Docker/Broker MQTT.md`, `IEEE - CS/Docker/Broker MQTT.md`, `IEEE - CS/Docker/VirtualBox vs Docker.md` | ✅ |
| 32 | ¿Qué comando crea el archivo de configuración mosquitto.conf con acceso anónimo permitido? | `IEEE - CS/Docker/Broker MQTT.md` | `IEEE - CS/Docker/Broker MQTT.md`, `IEEE - CS/Docker/Certificados TLS y ACL.md`, `IEEE - CS/Docker/VirtualBox vs Docker.md` | ✅ |
| 33 | ¿Con qué comando se genera el archivo de contraseñas para Mosquitto (MQTT)? | `IEEE - CS/Docker/Certificados TLS y ACL.md` | `IEEE - CS/Docker/Certificados TLS y ACL.md`, `IEEE - CS/Docker/Broker MQTT.md`, `IEEE - CS/Docker/VirtualBox vs Docker.md` | ✅ |
| 34 | ¿Qué son las ACL en el contexto de MQTT/Mosquitto según mis notas? | `IEEE - CS/Docker/Certificados TLS y ACL.md` | `IEEE - CS/Docker/Certificados TLS y ACL.md`, `IEEE - CS/Docker/Broker MQTT.md`, `IEEE - CS/Docker/Broker MQTT.md` | ✅ |
| 35 | Según mis notas de DevOps de Octavo, ¿cuál es la desventaja principal de los contenedores frente a la virtualización? | `Octavo/DevOps/Clase 13 - contenedores vs virtualización.md` | `Octavo/DevOps/Clase 13 - contenedores vs virtualización.md`, `DeTo/05-DevOps y herramientas/Entornos/Máquinas virtuales - Presentación.md`, `IEEE - CS/Docker/RUBY ioT.md` | ✅ |
| 36 | ¿Qué orquestador de contenedores mencioné en mis notas de DevOps de Octavo? | `Octavo/DevOps/Clase 13 - contenedores vs virtualización.md` | `Graphify.md`, `_HOME.md`, `Octavo/DevOps/Clase 13 - contenedores vs virtualización.md` | ✅ |
| 37 | ¿Qué comando de Git configura el nombre de usuario global? | `DeTo/Git comandos básicos.md` | `DeTo/Git comandos básicos.md`, `DeTo/05-DevOps y herramientas/Git y GitHub/GitHub comandos básicos.md`, `DeTo/Git comandos básicos.md` | ✅ |
| 38 | ¿Qué comando hace el primer push y establece el upstream en Git? | `DeTo/Git comandos básicos.md` | `DeTo/Git comandos básicos.md`, `DeTo/05-DevOps y herramientas/Git y GitHub/GitHub comandos básicos.md`, `DeTo/05-DevOps y herramientas/Git y GitHub/GitHub comandos básicos.md` | ✅ |

## Resultado final

**35/38 = 92.1%** de preguntas con ≥1 cita correcta.

Criterio de cierre de v0.2 (doc 08, Sprint 4): **>90% con ≥1 cita correcta** → **cumplido**.

### Fallos reales (no infraestructura)

3 de 38 preguntas fallaron por retrieval, no por caída de servicios (los errores HTTP 500 de las preguntas 32–38
en la primera corrida fueron por caída de Docker Desktop —no solo los contenedores, el daemon— y se resolvieron
reiniciando Docker y reintentando solo esas preguntas; los 3 fallos de abajo persistieron tras el reintento del servicio):

- **#13** *(¿Qué comando del asistente jonathan.sec muestra el perfil?)* — esperaba `Security/jonathan.sec comands.md`;
  la búsqueda híbrida no trajo esa nota entre la evidencia (sí lo hizo en la pregunta #14, casi idéntica, lo que sugiere
  sensibilidad del ranking a la formulación más que ausencia del contenido).
- **#16** *(Zero Conditional)* — esperaba `English/Conditionals.md`; la evidencia devuelta fue de notas de Zero Trust/Octavo,
  probable colisión léxica de "zero" entre "Zero Conditional" y "Zero Trust" en el ranking híbrido.
- **#29** *(RPC de Supabase en Nunna)* — esperaba `Work/Nunna/Nunna - login - supabase.md`; trajo en su lugar
  `Work/_INDEX.md` y notas genéricas de Supabase (`DeTo/03-Bases de datos/Supabase/Supabase.md`), homónimo temático
  (Supabase aparece en varias notas del vault, no solo en la de Nunna).

**Patrón:** los 3 fallos son de *desambiguación* (preguntas cortas o con términos que colisionan con otras notas del
vault — "zero", "supabase", comandos de un asistente vs. otro), no de ausencia de contenido ni de notas vacías.
No hay patrón por carpeta: los fallos están repartidos entre Security, English y Work.

### Nota de infraestructura

Durante la corrida, Docker Desktop se cayó por completo (no solo los contenedores; Neo4j salió con exit code 137,
probablemente OOM). Se reinició Docker Desktop y `docker compose up -d`; el worker Celery reconectó solo a Redis.
Confirma lo ya anotado en la memoria del proyecto: la máquina sufre presión de recursos bajo carga sostenida de Ollama
+ Postgres + Neo4j + Redis + MinIO simultáneos.

