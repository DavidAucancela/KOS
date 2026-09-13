# ADR-0010 — Autenticación por API key para despliegues expuestos

**Estado:** Aceptado
**Fecha:** 2026-09-12

## Contexto

`apps/api` no tiene ningún mecanismo de autenticación: no hay dependencia de API key, bearer ni
sesión en `apps/api/src/kos_api/` (verificado 2026-09-12). Es coherente con el diseño local-first
—la API escucha en `localhost` de la máquina del usuario— pero deja de serlo en cuanto el
despliegue de doc 14 le da un dominio público.

Sin autenticación, cualquiera con la URL puede leer todo el conocimiento personal vía `/v1/query`,
escribir memoria y disparar llamadas a un LLM cloud de pago. Esto último convierte un escaneo
rutinario de internet en gasto real. Además, en esa topología la API sirve también el HTML de
`apps/web` desde el mismo origen (doc 14 §3).

## Decisión

Todo despliegue expuesto a internet exige credencial **en todas las rutas, incluido el HTML de la
web**. Solo `/health` queda abierto (lo necesitan Railway y el monitoreo).

**Credenciales: varias claves nombradas.** `KOS_API_KEYS` es una lista `nombre:clave`
(p. ej. `web:…,mac:…,movil:…`). Cada petición se atribuye a un nombre, que va al log y a la tabla
de acceso; una clave comprometida se revoca sola, sin tocar los demás clientes.

**Dos formas de presentar la misma credencial**, ambas contra la misma lista:

- **HTTP Basic** (`usuario` = nombre de la clave, `contraseña` = la clave) — es lo que usa el
  navegador. Al pedir el HTML sin credencial, la API responde `401` con
  `WWW-Authenticate: Basic`, el navegador muestra su diálogo y a partir de ahí **envía la cabecera
  en todas las peticiones del mismo origen**, incluidas las `fetch` de la SPA. No hace falta
  ningún flujo de sesión, ni token en `localStorage`, ni CSRF: no hay cookie que un tercero pueda
  hacer viajar.
- **Cabecera `X-API-Key: <clave>`** — es lo que usan la Mac, el conector y el CLI, que no tienen
  navegador. Equivalente en permisos.

**Rate limit por IP**, en dos niveles: uno general y otro más estricto para lo que gasta LLM cloud
(`/v1/query` y agentes). Superarlo devuelve `429`. El contador vive en memoria del proceso: hay una
sola réplica y el servicio duerme, así que meterlo en Redis añadiría tráfico saliente que
impediría dormir a la API (doc 14 §2.2) — exactamente lo contrario de lo que busca el despliegue.

Si `KOS_API_KEYS` está vacía, la API solo acepta conexiones locales y registra un aviso al
arrancar: el modo local de doc 09 sigue funcionando sin configurar nada.

Esto es **autenticación de despliegue single-tenant**, no un modelo de usuarios: no hay cuentas,
roles ni sesiones. El multi-tenant real es Fase 6 (doc 07) y tendrá su propio ADR.

## Alternativas consideradas

- **Una sola clave compartida** — más simple, pero rotarla obliga a reconfigurar todos los
  clientes a la vez y los logs no distinguen quién llamó.
- **Clave en `localStorage` + cabecera desde la SPA** — evita el diálogo tosco del navegador, pero
  deja el HTML servido sin credencial y expone la clave a un XSS en la propia SPA.
- **Cookie de sesión HttpOnly tras un `/v1/auth/login`** — más cómodo de usar, pero introduce
  sesiones y obliga a manejar CSRF en todos los POST; demasiada maquinaria para un solo usuario.
- **Proxy con Cloudflare Access / login Google delante** — cero código en la API, pero rompe el
  acceso programático desde el conector, la Mac y el CLI, que es el uso principal.
- **Sin auth, confiando en una URL no publicada** — las URLs de Railway son predecibles y se
  indexan; y el riesgo no es solo lectura, es gasto.

## Consecuencias

- **Positivas:** nada de la app se sirve sin credencial, ni siquiera el HTML; un único mecanismo
  cubre navegador, CLI y conector; se puede revocar un cliente sin tocar los otros; el gasto de
  LLM queda acotado por el rate limit.
- **Negativas / deuda aceptada:** el diálogo de Basic auth es tosco y **cerrar sesión en el
  navegador es incómodo** (hay que cerrar la ventana o limpiar credenciales); las claves viajan en
  cada petición, así que **TLS es obligatorio** (Railway lo da por defecto, pero prohíbe exponer
  esto por HTTP plano); el rate limit en memoria se reinicia cada vez que el servicio despierta,
  lo que relaja el límite justo tras un arranque en frío; sin rotación automática — si una clave
  se filtra, se edita la variable a mano.
- **Si se revierte** (volver a solo local): dejar `KOS_API_KEYS` vacía; el middleware pasa a
  permitir solo conexiones locales y no hay más cambios.
