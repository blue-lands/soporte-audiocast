# CLAUDE.md

> **Desde 2026-09-30 esta app la escribe y la despliega la instancia de vps7. La instancia de vps4 solo lee.**
> Decisión de hrm: una sola instancia (vps7) es la fuente de verdad de todo Audiocast. El traspaso está en
> `docs/HANDOFF-2026-09-30.md`. Lo que sigue se escribió cuando la app la hacía vps4: donde dice «esta instancia» o
> «vps4 la construye», hoy vale vps7.

## Qué es

**Soporte Audiocast**: asistente telefónica (ElevenLabs Agents) + panel de casos para las tiendas que usan las cajas
Audiocast. Primer uso: **demo con la gerencia de marketing de Tottus**. Básico y general.

La construye y la opera la instancia de Claude de este VPS (vps4), a pedido de hrm. Todo lo hecho hasta ahora es del
2026-09-28. **Hablarle a hrm sin jerga interna**: "el #7", "F3" o "el token" no le dicen nada si no se explican.

**Hacia dónde va** (visión de hrm): una persona dedicada al soporte que mira a la vez la central (cajas en vivo) y este
panel (conversaciones de cada sucursal, por teléfono o WhatsApp). Central y soporte son un mismo puesto de trabajo: por
eso comparten dominio y sesión.

Guías de origen (con credenciales; viven fuera de git, **no copiarlas aquí**):

- `/var/www/secretaria/privado/guia-asistente-app-audio.md` — **sección 0 manda** (decisiones de hrm y fases F1–F6).
- `/var/www/secretaria/privado/soporte-audiocast-central-y-tiendas.md` — la central, la tabla de estados y las tiendas.

## Reglas

- **La central es de otra instancia** (MediaFlow, vps7). Esta app solo le hace `GET /api/units` y `GET /api/me`. Nunca `POST`. No editar
  `/var/www/central-audiocast` ni reiniciar sus servicios (ni dejarle `.pyc`: importar su simulador con
  `sys.dont_write_bytecode`).
- **El VPS es producción compartida** (SpotyFlow, Asiste, Remates). No tocar PM2, nginx ni nada fuera de esta carpeta sin
  el OK de hrm. Pedir confirmación antes de instalar, reiniciar o detener cualquier servicio, incluido el propio.
- **No leer ni copiar nada de Asiste** salvo como referencia (`/var/www/secretaria` es solo lectura).
- La piloto `nataniel-cox-01` **no se muestra ni se menciona** (`SOPORTE_CAJAS_OCULTAS`).
- El cliente es **Tóttus** (con tilde en todo lo que lea la voz). No nombrar otras marcas.
- Nada de acciones sobre las cajas durante la llamada: es una etapa posterior.
- La asistente recibe **frases**, no campos: la traducción se hace en `app/estado.py`, no en el prompt.
- Llamadas salientes, WhatsApp a personas, planes: cuestan dinero o molestan a terceros. Solo con permiso de hrm para
  esa acción concreta.

## Estado (2026-09-28)

**Funciona de punta a punta por teléfono**: se llama al **+56 2 2583 1900**, contesta la asistente, consulta el equipo de
la tienda, el caso llega al panel con número, ficha y transcripción (primera llamada completa: caso N° 0003).

| # | Qué | Estado |
|---|---|---|
| F1 | App base, directorio de tiendas, lectura de la central | **Hecha.** Servicio `soporte-audiocast` activo y `enabled` |
| F2 | Herramienta `consultar_tienda` + webhook de fin (HMAC) + panel | **Hecha.** 171 pruebas |
| F4 | Publicar en internet | **Hecha** en `https://central.mediaflow.cl/soporte/`, con enlaces en los dos sentidos con la central |
| F3 | Asistente en ElevenLabs | **Hecha** (ver «ElevenLabs, Zadarma y WhatsApp») |
| F5 | Número Zadarma → ElevenLabs | **Hecho.** Llamadas reales funcionan |
| F5b | WhatsApp oficial del 1900 + WhatsApp con N° de caso a quien llama | Número inscrito en Meta y atendido por la asistente. **Hecho**: el WhatsApp con N° de caso funciona desde el 2026-09-29 (caso 7) |
| F6 | Ensayo del demo (3 llamadas: equipo bien, en música de respaldo, caído) | Pendiente. Necesita que el simulador de la central muestre problemas y el token `soporte` |

**Plantilla `caso_registrado` destrabada:** el 2026-09-28 Meta la rechazaba (`#132001 ... does not exist in es`, caso 5).
El 2026-09-29 22:09 (Chile) el caso 7 quedó `whatsapp_estado=enviado` y a las 22:10 la persona contestó por WhatsApp
(caso 8): llegó. Pendiente solo si hrm lo quiere: `deploy/cli.sh reenviar-whatsapp 5` (manda un WhatsApp real).

Lo que **no está verificado**:

- Entrar al panel con una sesión real de la central (hrm no lo ha confirmado).
- Todo lo que dice la asistente sale de la **flota de ejemplo** (`ejemplos/units-mixto.json`), no de la central. Las
  tres cajas reales del ejemplo son inventadas, incluida `minipc-lab-01`.

En la base hay consultas de prueba (`prueba-publicacion`, `prueba-f3`) que no son casos. Casos 1 y 2 son llamadas de
prueba de hrm (la 1 sin audio: la asistente no alcanzó a hablar; la 2 cortó tras el saludo). El 4 es un WhatsApp de hrm.

## ElevenLabs, Zadarma y WhatsApp

**ElevenLabs** (API key compartida de la guía §3, también en `.env` como `ELEVENLABS_API_KEY`):

| Qué | Id |
|---|---|
| Asistente «Soporte Audiocast (Tóttus demo)» | `agent_0501m3m03g3xesfrmyy837j70q5a` |
| Herramienta `consultar_tienda` (webhook con `X-Soporte-Token`) | `tool_7801m3m02gw7e8tv98pmhh87jswa` |
| Webhook de fin «Soporte Audiocast (panel)», HMAC | `3f87fc5a1ca6414b8dfdf520b46146fe` (secreto en `.env`) |
| Número `+56225831900` (SIP trunk, solo entrantes, abierto a cualquier IP como SuperPet: decisión de hrm) | `phnum_7901m3m0hbzefj6rsvx299m8vpta` |
| WhatsApp «Audiocast» (+56 2 2583 1900), cuenta Meta «Mediaflow» (WABA `1388001310155966`) | phone_number_id `1366498186551130` |

- Voz Cristina Campos (`nTkjq09AuYgsNR8E4sDe`, `eleven_v3_conversational`), LLM `claude-haiku-4-5@20251001` a 0,3,
  `end_call` activo, `summary_language: es`, `text_only` permitido (WhatsApp). Saludo: «Aló, soporte Audiocast, ¿en qué
  le puedo ayudar?».
- **El prompt y la ficha que valen son copias de `deploy/agente/`**: se editan ahí y se suben con `PATCH
  /v1/convai/agents/{id}` mandando `prompt`, `llm`, `temperature`, `tool_ids` y `built_in_tools.end_call` juntos; después
  leer el agente y comprobar prompt, herramienta, `end_call`, 9 campos de ficha y el webhook.
- **Trampas**: un PATCH a `workspace_overrides` reemplaza el bloque entero. Si hrm publica algo en el dashboard, revisar
  por API que sigan prompt, ficha y webhook. **La asistente no debe leer números**: dijo «empieza con nueve seis» de un
  celular que empieza con 99 (Haiku inventa dígitos); el prompt se lo prohíbe.
- No tocar nada de SuperPet (`agent_8001m3bb6yy8e78s86c6yeda765a`, 7395, webhook `b563…`).

**Zadarma** (centralita `591475`; la API se usó con una clave que hrm dio en el chat, **no guardada**):

| Extensión | Qué hace | Número |
|---|---|---|
| 100 | desvío a Retell | 7279 (regla general, suena con la 102) |
| 101 | desvío a ElevenLabs SuperPet | 7395 (regla «ElevenLabs 7395») |
| 102 | sin desvío; suena en la regla general del 7279 | — |
| **103** | **desvío siempre a `+56225831900@sip.rtc.elevenlabs.io`** | **1900** (regla «Soporte Audiocast 1900», solo la 103) |

- La 103 la creó hrm en la web (crear extensiones por API lo frenó el control de permisos por posible costo). También
  está en la app de Zadarma de su celular: con el desvío encendido no le suena; apagándolo (API `POST
  /v1/pbx/redirection/` `status=off`) le suena a él (así se verificó el número en Meta).
- La API de Zadarma no muestra qué número activa cada regla.

**WhatsApp con N° de caso** (`app/whatsapp.py`): plantilla `caso_registrado` (Utilidad, `es`, 4 variables en orden:
nombre, N° de caso, tienda, problema) por `POST /v1/convai/whatsapp/outbound-message`, desde el WhatsApp «Audiocast».
Si la persona contesta, la atiende la asistente y queda como caso de canal `whatsapp`.

## Próximos pasos

1. Pedir a hrm que confirme que el panel le abre desde la central.
2. Para el demo: token `soporte` de la central y un plan del simulador con problemas (los hace la instancia de
   MediaFlow). Luego ensayo con 3 llamadas.

**Después del demo**: ficha por sucursal (estado del equipo ahora + historial de conversaciones + enlace a su caja en
la central), cuentas por persona con registro de quién vio qué (Ley 21.719, rige desde el 1-dic-2026).

## Comandos

```bash
cd /var/www/soporte-audiocast
.venv/bin/python -m pytest                       # todas las pruebas (no tocan la central ni /var/lib)

# Consola, con una base de juguete:
export SOPORTE_DB=/tmp/soporte.db CENTRAL_ARCHIVO=ejemplos/units-mixto.json PYTHONDONTWRITEBYTECODE=1
.venv/bin/python -m app.cli cargar-tiendas       # llena y asocia; se puede repetir
.venv/bin/python -m app.cli consultar "el de viña"

# Servidor de desarrollo:
.venv/bin/uvicorn --factory app.principal:crear_app --host 127.0.0.1 --port 8392
curl -s 127.0.0.1:8392/salud

python3 ejemplos/generar.py > ejemplos/units-mixto.json   # rehacer el ejemplo (no habla con la central)
```

Sobre el servicio instalado, las tareas de consola van por `deploy/cli.sh` (mismo usuario y base que el servicio; si
root escribe en la base, el servicio después no puede):

```bash
deploy/cli.sh cargar-tiendas
deploy/cli.sh consultar "la de nataniel"
deploy/cli.sh reenviar-whatsapp 5            # vuelve a mandar el WhatsApp del caso N° 0005 si falló (manda un WhatsApp real)

systemctl restart soporte-audiocast      # tras cambiar código o .env. Ver abajo: lo corre hrm
journalctl -u soporte-audiocast
```

**Reinicios**: el control de permisos no deja a Claude reiniciar el servicio. Se le pide a hrm que escriba
`! systemctl restart soporte-audiocast` con el `!` como **primer carácter** (con espacios antes no corre) y luego se
verifica con `/salud`. `deploy/cli.sh` sí funciona (probado el 2026-09-28).

**Detener servidores de prueba por PID exacto, nunca por patrón**: Asiste corre con la misma línea de comando
(`uvicorn --factory app.principal:crear_app`, puerto 8391) y es producción.

Panel: `https://central.mediaflow.cl/soporte/`. **Sin entrada propia** (ver «Quién entra»).

## Quién entra

Decisión de hrm (2026-09-28): **ni páginas de ingreso nuevas ni claves nuevas.** Al soporte se llega con un enlace desde
la central y entra quien ya tiene sesión abierta ahí.

- La galleta de sesión de la central (`ac_session`, `Path=/`) llega sola a `/soporte/` porque comparten dominio. La app
  no la entiende: se la muestra a la central (`GET /api/me`) y usa el `user` que responde. Lo recuerda 30 s.
- Sin sesión válida: la página se vuelve a pedir una vez a sí misma (`?v=1`; la galleta es `SameSite=Strict` y el
  navegador no la manda al llegar desde otro sitio, p. ej. el enlace de un aviso) y, si tampoco, redirige a la central,
  que muestra su propia entrada.
- Quien entra a la central **con token** (no con usuario y clave) no tiene galleta: el soporte no lo reconoce.
- Si la central no responde, el panel no abre (503). La herramienta y el webhook no dependen de esto.
- El panel es **solo lectura**: sin formularios, sin JavaScript, sin galletas propias. No tiene «Salir»: se sale en la
  central.
- El enlace «Soporte» del panel de la central lo puso la instancia del #7 (desplegado aquí el 2026-09-28); el
  pedido original está en `deploy/para-la-central.md`. De vuelta, el soporte tiene «Central de flota».

## Publicación

| Qué | Dirección |
|---|---|
| Panel | `https://central.mediaflow.cl/soporte/` |
| Herramienta | `POST https://central.mediaflow.cl/soporte/herramientas/consultar_tienda` |
| Webhook de fin | `POST https://central.mediaflow.cl/soporte/webhooks/elevenlabs` |

- nginx: el sitio `central.mediaflow.cl` incluye `/etc/nginx/snippets/soporte-audiocast.conf` (copia en
  `deploy/nginx-snippet-soporte-audiocast.conf`). **nginx quita el prefijo** (`/soporte/casos/x` llega como `/casos/x`) y
  la app lo pone en todo lo que responde (`SOPORTE_PREFIJO`): enlaces y redirecciones. Las rutas
  de `app/principal.py` se escriben sin prefijo; en las plantillas, todo enlace interno empieza con `{{ base }}`.
- `/soporte/salud` responde 404 hacia afuera: es solo para `curl 127.0.0.1:8392/salud`.
- Cloudflare atiende el HTTPS; el tramo Cloudflare → VPS va por el puerto 80 sin cifrar, como el resto de los sitios de
  este VPS.
- Para pasar a un dominio propio: `SOPORTE_PREFIJO=` vacío, `SOPORTE_HOSTS`, `SOPORTE_BASE_URL`, sitio nginx nuevo y
  las dos direcciones del agente en ElevenLabs.
- Por `http://127.0.0.1:8392` el panel no abre (no llega la galleta de la central); `/salud` y la herramienta sí.

## Arquitectura

Stack de Asiste: FastAPI + SQLite + Jinja, un servicio systemd (`deploy/soporte-audiocast.service`, `DynamicUser`,
`MemoryMax=150M`, `127.0.0.1:8392`). Comentarios y nombres en español.

- `app/central.py` — único punto que habla con la central, y solo con `GET`: `/api/units` (cajas) y `/api/me` (de
  quién es la sesión). Timeout 2 s, caché 10 s, quita las cajas ocultas. Cualquier falla
  sale como `CentralNoDisponible`. Acepta `{"units": [...]}` (lo que responde la central de verdad) y la lista suelta.
  `CENTRAL_ARCHIVO` reemplaza a la central por un JSON mientras no exista el token `soporte`.
- `app/estado.py` — la tabla de estados de la guía (§3), en orden: la primera regla que calza manda. Función pura
  (`describir(caja, ahora)`). **Trampa:** en Local First (`mode == "local_first"`) `FALLBACK` es el estado sano.
- `app/directorio.py` — `asociar()` reparte cajas (real → misma comuna → misma región → cualquiera libre), `buscar()`
  encuentra la tienda que nombra la persona. Si calzan varias, las devuelve todas: equivocarse de tienda es peor que
  preguntar. La corrección por parecido (errores del reconocimiento de voz) solo vale si todo lo dicho es de la tienda.
- `app/consulta.py` — junta lo anterior. `consultar_tienda()` devuelve `estado` (frases) y `caja` (JSON crudo, para el
  caso); `para_la_asistente()` es lo único que sale hacia ElevenLabs: frases e indicaciones, nada técnico.
- `app/principal.py` — las rutas:
  - `POST /herramientas/consultar_tienda` — encabezado `X-Soporte-Token` (o `Authorization: Bearer`). Cuerpo:
    `tienda` (lo que dijo la persona), `tienda_id` (solo en la segunda vuelta, cuando ya eligió entre varias opciones) y
    `conversation_id` (ElevenLabs lo llena con la variable `system__conversation_id`; también vale `X-Conversation-Id`).
    Cada consulta queda en la tabla `consultas` con la caja cruda.
  - `POST /webhooks/elevenlabs` — firma HMAC sobre el **cuerpo crudo**. Solo guarda `post_call_transcription`.
    Idempotente por `conversation_id`. Sin secreto configurado responde 503. Tras guardar, en segundo plano: aviso por
    Telegram y WhatsApp a quien llamó.
  - Panel: `/` (casos) y `/casos/<id>`, con la sesión de la central. `/salud` es abierto y solo da cuentas.
- `app/casos.py` — cada caso recibe un **número correlativo** (`numero`, N° 0005) al llegar; un reintento no lo cambia
  (los casos anteriores lo recibieron en `db._migrar`, por orden de `inicio`). La tienda de un caso es **la que consultó la asistente**; si no consultó, la que se entienda de la
  ficha (y si es dudosa, queda sin tienda). Un caso es urgente si lo dice la ficha **o** si el equipo estaba en un
  estado urgente al consultarlo.
- `app/elevenlabs.py` — firma y traducción de la conversación a un caso. Las pruebas del navegador de ElevenLabs quedan
  como canal `prueba` y **sí** son casos (en el demo sin número, son los casos).
- `app/whatsapp.py` — WhatsApp a quien llamó con el N° de caso. Solo llamadas desde un celular chileno (`569…`) en que
  la persona habló y el problema no se resolvió. Una sola vez por caso (`whatsapp_estado`: enviando → enviado / omitido /
  error, con el motivo en `whatsapp_detalle`); el panel lo muestra. Un error no se reintenta solo:
  `deploy/cli.sh reenviar-whatsapp <N°>`. Una conversación de WhatsApp sin nada de la persona (la plantilla que nadie
  contestó) no se guarda como caso.
- `app/avisos.py` — Telegram para casos urgentes, una vez por caso. Apagado mientras `TELEGRAM_*` esté vacío.
- `app/seguridad.py` — comparación de tokens en tiempo constante. No hay usuarios ni claves.
- Panel: `app/plantillas/` + `app/estaticos/estilo.css`, con los tokens de `DESIGN.md` de Audiocast (tema oscuro único,
  px fijos). CSP sin scripts: el panel no usa JavaScript.
- `app/datos/tottus_tiendas.py` — las 71 tiendas. Difiere de la fuente en una cosa: 5 tiendas de O'Higgins venían bajo
  "Región de Valparaíso". `DIRECCIONES`: calle y número de tottus.cl (lista de hrm, 2026-09-30), 69 de 71: Piedra Roja
  y El Bosque venían malas en la fuente. La central no sirve para cotejarlas: sus cajas reales no mandan dirección y las
  simuladas la inventan.
- `app/palabras.py` — números en palabras. La asistente recibe `direccion` (escrita, para WhatsApp) y
  `direccion_para_decir` (sin cifras, para la voz) y la indicación de decirla al confirmar la tienda. El prompt de
  ElevenLabs no cambió.
- `ejemplos/units-mixto.json` — la flota simulada en plan `mixto` (ids reales: el simulador tiene semilla fija) + 3 cajas
  reales **inventadas** según la descripción de la guía.

## Pendiente de otros

- **Token `soporte` de la central** y **rol de solo lectura**: los hace la instancia de MediaFlow (vps7) con el OK de
  hrm. Los tokens de la central viven en `/etc/audiocast-central/tokens.json` y entran por `LoadCredential`: no leerlos.
  Al llegar el token: `CENTRAL_TOKEN` en `.env`, vaciar `CENTRAL_ARCHIVO`, reiniciar el servicio, `cargar-tiendas` de
  nuevo y comparar la asociación con la del ejemplo.
- **Plan del simulador**: hoy `pausa` (todas "aún no activadas"). Para el demo, `mixto` o un plan propio. Decisión de
  hrm; lo ejecuta la instancia de MediaFlow.
- **Avisos por Telegram**: la guía propone el bot de alertas de la central. Su credencial está en
  `/etc/audiocast-central/telegram_bot_token`; no se leyó. Las entrega hrm (o un bot propio) y van en
  `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`.
- **San Vicente queda sin caja**: son 71 tiendas y 70 cajas (69 simuladas + `minipc-lab-01`). hrm no ha decidido si
  se le asigna `x98h-lab-02` (frágil).
- **`tottus-stores.ts` de MediaFlow** tiene 5 tiendas de O'Higgins bajo "Región de Valparaíso": conviene corregirlo allá.
