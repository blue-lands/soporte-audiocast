# CLAUDE.md

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

## Estado de las fases

| # | Qué | Estado |
|---|---|---|
| F1 | App base, directorio de tiendas, lectura de la central | **Hecha.** Servicio `soporte-audiocast` instalado, activo y `enabled` |
| F2 | Herramienta `consultar_tienda` + webhook de fin (HMAC) + panel | **Hecha** y desplegada, con 156 pruebas. **Nunca ha recibido una conversación real de ElevenLabs** |
| F4 | Publicar en internet | **Hecha** en `https://central.mediaflow.cl/soporte/`, con enlaces en los dos sentidos con la central |
| F3 | Agente en ElevenLabs por API | **Pendiente: espera el OK de hrm** (usa la API key compartida y consume minutos). Propuesta hecha: saludo "Aló, soporte Audiocast, ¿en qué le puedo ayudar?" y voz Cristina Campos |
| F5 | Número Zadarma → ElevenLabs | Pendiente, después de F3. Número nuevo: **+56 2 2583 1900** (`+56225831900`). Falta que hrm confirme que está activo |
| F6 | Ensayo del demo (3 llamadas: equipo bien, en música de respaldo, caído) | Pendiente |

Lo que **no está verificado**:

- Entrar al panel con una sesión real de la central: solo se probó con una central simulada y, por internet, que sin
  sesión redirige. Se le preguntó a hrm si le abrió; no ha contestado.
- Todo lo que dice la asistente sale hoy de la **flota de ejemplo** (`ejemplos/units-mixto.json`), no de la central.
- Las tres cajas reales del ejemplo son inventadas, incluida `minipc-lab-01`.

En la base real hay una consulta de prueba (`conversation_id` = `prueba-publicacion`); no aparece como caso.

## Próximos pasos

**F3, cuando hrm dé el OK** (referencia: guía §6 y §7; leer el agente de SuperPet por API y copiar lo que sirva, sin
modificarlo):

1. Crear el webhook de fin en ElevenLabs (tipo HMAC) hacia `…/soporte/webhooks/elevenlabs`. Entrega el secreto: va en
   `ELEVENLABS_WEBHOOK_SECRET` del `.env` y hay que reiniciar el servicio.
2. Crear el agente: idioma `es`, LLM `claude-haiku-4-5`, voz Cristina Campos, `end_call` activado (por API no viene
   activo), `summary_language: es`, ficha de la guía §0.4 y la herramienta `consultar_tienda` con `X-Soporte-Token`.
   En el cuerpo de la herramienta: `tienda` y `tienda_id` los llena el modelo; `conversation_id` va atado a la variable
   `system__conversation_id`.
3. El prompt: tratar de usted, preguntar tienda y nombre, **confirmar la tienda antes de decir el estado**, decir el
   estado con las palabras que entrega la herramienta, "Tóttus" con tilde, no prometer lo que no existe.
4. Probar desde el navegador de ElevenLabs y revisar que el caso llegue al panel con tienda, ficha y transcripción.
5. **Trampa**: un PATCH a `workspace_overrides` reemplaza el bloque entero. Después de que hrm publique algo en el
   dashboard de ElevenLabs, revisar por API que sigan el prompt, la ficha y el webhook.

**F5**: hrm, en Zadarma, crea una extensión nueva con su propio flujo (sin menú ni buzón de voz) y le deja el desvío
siempre activo a `+56225831900@sip.rtc.elevenlabs.io`. Claude importa el número en ElevenLabs (SIP trunk) y le asigna
el agente. WhatsApp queda fuera del demo.

**Después del demo**: ficha por sucursal (estado del equipo ahora + historial de conversaciones + enlace a su caja en
la central), cuentas por persona con registro de quién vio qué (Ley 21.719, rige desde el 1-dic-2026), WhatsApp.

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

systemctl restart soporte-audiocast      # tras cambiar código o .env. Pedir confirmación a hrm
journalctl -u soporte-audiocast
```

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
| Herramienta (para F3) | `POST https://central.mediaflow.cl/soporte/herramientas/consultar_tienda` |
| Webhook de fin (para F3) | `POST https://central.mediaflow.cl/soporte/webhooks/elevenlabs` |

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
    `conversation_id` (en F3 se llena con la variable `system__conversation_id`; también vale `X-Conversation-Id`).
    Cada consulta queda en la tabla `consultas` con la caja cruda.
  - `POST /webhooks/elevenlabs` — firma HMAC sobre el **cuerpo crudo**. Solo guarda `post_call_transcription`.
    Idempotente por `conversation_id`. Sin secreto configurado responde 503.
  - Panel: `/` (casos) y `/casos/<id>`, con la sesión de la central. `/salud` es abierto y solo da cuentas.
- `app/casos.py` — la tienda de un caso es **la que consultó la asistente**; si no consultó, la que se entienda de la
  ficha (y si es dudosa, queda sin tienda). Un caso es urgente si lo dice la ficha **o** si el equipo estaba en un
  estado urgente al consultarlo.
- `app/elevenlabs.py` — firma y traducción de la conversación a un caso. Las pruebas del navegador de ElevenLabs quedan
  como canal `prueba` y **sí** son casos (en el demo sin número, son los casos).
- `app/avisos.py` — Telegram para casos urgentes, una vez por caso. Apagado mientras `TELEGRAM_*` esté vacío.
- `app/seguridad.py` — comparación de tokens en tiempo constante. No hay usuarios ni claves.
- Panel: `app/plantillas/` + `app/estaticos/estilo.css`, con los tokens de `DESIGN.md` de Audiocast (tema oscuro único,
  px fijos). CSP sin scripts: el panel no usa JavaScript.
- `app/datos/tottus_tiendas.py` — las 71 tiendas. Difiere de la fuente en una cosa: 5 tiendas de O'Higgins venían bajo
  "Región de Valparaíso".
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
