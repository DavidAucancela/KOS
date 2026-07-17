# Set de evaluación — vault real

**Estado:** 🟡 borrador · **Fecha:** 2026-07-15

Preguntas construidas a mano leyendo notas reales del vault (`/Users/david/Documents/Obsidian Vault`,
fuente `vault-real`). Cada pregunta tiene el archivo fuente esperado y un hecho/string clave que debe
aparecer en la respuesta o en la cita de `POST /v1/query`. Criterio de cierre de v0.2 (doc 08, Sprint 4):
**>90% de las preguntas con ≥1 cita correcta**.

| # | Pregunta | Archivo fuente esperado | Respuesta/hecho clave esperado |
|---|---|---|---|
| 1 | ¿Qué comando de nmap muestra la versión de los servicios en los puertos abiertos? | Security/Nmap.md | `nmap -sV` |
| 2 | ¿Qué puertos TCP quedaron abiertos en la prueba de nmap, según mis notas? | Security/Nmap.md | 135, 139, 445 |
| 3 | ¿Qué protocolo corre sobre el puerto 445 según mis notas de Nmap? | Security/Nmap.md | SMB |
| 4 | ¿Qué comando uso en Linux para generar una contraseña aleatoria en base64 desde la terminal? | Security/generar contraseñas en el terminal.md | `openssl rand -base64 32` |
| 5 | En Windows, ¿qué comando de PowerShell genero para crear una contraseña/GUID? | Security/generar contraseñas en el terminal.md | `[guid]::NewGuid().ToString("N")` |
| 6 | ¿Cuál fue el primer virus informático mundialmente reconocido, según mis notas de malware? | Security/Malware.md | ILOVEYOU |
| 7 | ¿Qué gusano informático usaron los atacantes para dañar las centrifugadoras de procesamiento de uranio en Irán? | Security/Malware.md | Stuxnet |
| 8 | ¿Qué troyano robaba credenciales bancarias propagándose por fuerza bruta, según mis notas? | Security/Malware.md | Emotet |
| 9 | ¿Cuál es uno de los ataques de ransomware más conocidos que mencioné en mis notas de malware? | Security/Malware.md | WannaCry |
| 10 | ¿En qué empresa ocurrió el ejemplo famoso de ataque con bomba lógica que anoté? | Security/Malware.md | Siemens |
| 11 | ¿Qué es Dark Hotel según mis notas? | Security/Malware.md | ataque de keylogger en redes wifi de hoteles |
| 12 | ¿Qué es la dark web según mis notas? | Security/Dark web.md | subconjunto de Internet accesible solo con navegadores especializados, cifrado/anónimo |
| 13 | ¿Qué comando del asistente jonathan.sec muestra el perfil (rol, clearance, stack, contacto)? | Security/jonathan.sec comands.md | `whoami` |
| 14 | ¿Qué comando de jonathan.sec muestra los detalles del proyecto SecuraBank? | Security/jonathan.sec comands.md | `cat securabank.md` |
| 15 | Menciona un puesto de trabajo de ciberseguridad que anoté en mis vacantes de seguridad. | Security/Vacantes en Seguridad Informática.md | Analista de ciberseguridad / Probador de penetración / Analista de malware |
| 16 | ¿Cuál es la estructura del Zero Conditional en inglés? | English/Conditionals.md | `If + present simple, present simple` |
| 17 | ¿Cuál es la estructura del First Conditional? | English/Conditionals.md | `If + present simple, will + verb` |
| 18 | ¿Qué significa el modal verb "must" según mis notas de inglés? | English/Modal verbs.md | deber / obligación o necesidad más fuerte que should |
| 19 | ¿Cuál es la diferencia entre "who" y "whose" según mis notas? | English/WHO or WHOSE.md | who = pregunta sobre acción/quién; whose = pertenencia/de quién |
| 20 | En reported speech, ¿en qué se convierte "will" en estilo indirecto? | English/Reported speech.md | would |
| 21 | ¿En qué se convierte "can" cuando se pasa a reported speech? | English/Reported speech.md | could |
| 22 | ¿Qué diferencia hay entre present perfect y present perfect continuous según mis notas? | English/Present perfect and present continuous.md | present perfect enfatiza el resultado; continuous enfatiza la duración/proceso |
| 23 | ¿Cuándo se usa "be going to" en vez de "will" para hablar del futuro? | English/Going to y will.md | planes/intenciones decididas antes de hablar o predicciones con evidencia visible |
| 24 | Según mis notas de inglés, ¿para qué se usa la preposición "for"? | English/For, at and on.md | duración o propósito |
| 25 | ¿Qué parámetros de generación de un LLM mencioné en mis notas de GDG sobre prompts (temperatura, top k, top p)? | GDG/Escribir bien prompts.md | temperatura 0.2, top k 30, top p 0.95 |
| 26 | En mi diseño de prompts para KOS, ¿en qué formato debe responder el Prompt 1 de clasificación de consultas? | GDG/structura prompt.md | JSON con categoría, confianza y palabras clave |
| 27 | ¿Qué debe hacer el Prompt 2 de mi diseño de prompts, según mis notas de GDG? | GDG/structura prompt.md | detectar el problema explícito o implícito del usuario |
| 28 | En el proyecto Nunna, ¿qué variables de entorno de Supabase hay que configurar en Railway? | Work/Nunna/Nunna - login - supabase.md | NEXT_PUBLIC_SUPABASE_URL y NEXT_PUBLIC_SUPABASE_ANON_KEY |
| 29 | ¿Qué RPC de Supabase se aplica junto con el schema.sql en el proyecto Nunna? | Work/Nunna/Nunna - login - supabase.md | redeem_code |
| 30 | ¿Qué personajes de Nunna faltan por tener imágenes, según mi roadmap? | Work/Nunna/Nunna - login - supabase.md | Curiquingue, Sacha Runa, Rey Moro, Capitán, Ángel |
| 31 | ¿Qué imagen oficial de broker MQTT usé en mi práctica de Docker? | IEEE - CS/Docker/Broker MQTT.md | Eclipse Mosquitto |
| 32 | ¿Qué comando crea el archivo de configuración mosquitto.conf con acceso anónimo permitido? | IEEE - CS/Docker/Broker MQTT.md | `echo " listener 1883 allow_anonymous true " > mosquitto.conf` |
| 33 | ¿Con qué comando se genera el archivo de contraseñas para Mosquitto (MQTT)? | IEEE - CS/Docker/Certificados TLS y ACL.md | `mosquitto_passwd` |
| 34 | ¿Qué son las ACL en el contexto de MQTT/Mosquitto según mis notas? | IEEE - CS/Docker/Certificados TLS y ACL.md | definen quién puede publicar o suscribirse a qué tópicos |
| 35 | Según mis notas de DevOps de Octavo, ¿cuál es la desventaja principal de los contenedores frente a la virtualización? | Octavo/DevOps/Clase 13 - contenedores vs virtualización.md | trabajan directo sobre el kernel, lo que puede causar errores |
| 36 | ¿Qué orquestador de contenedores mencioné en mis notas de DevOps de Octavo? | Octavo/DevOps/Clase 13 - contenedores vs virtualización.md | Kubernetes |
| 37 | ¿Qué comando de Git configura el nombre de usuario global? | DeTo/Git comandos básicos.md | `git config --global user.name` |
| 38 | ¿Qué comando hace el primer push y establece el upstream en Git? | DeTo/Git comandos básicos.md | `git push -u origin main` |
