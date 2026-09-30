"""Aplicación web: herramienta de la asistente, webhook de fin de conversación y panel de casos.

Arranque: uvicorn --factory app.principal:crear_app
"""

import json
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

import jinja2
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import avisos, casos, central, consulta, db, directorio, elevenlabs, formato, seguridad, whatsapp
from .config import Config, cargar

_CARPETA = Path(__file__).parent

_plantillas = jinja2.Environment(loader=jinja2.FileSystemLoader(_CARPETA / "plantillas"), autoescape=True)
_plantillas.filters.update(
    fecha_hora=formato.fecha_hora, hora=formato.hora, duracion=formato.duracion, minuto=formato.minuto,
    problema=formato.problema, canal=formato.canal, si_no=formato.si_no, turnos=formato.turnos,
    json_legible=formato.json_legible, numero_caso=formato.numero_caso, whatsapp=formato.whatsapp,
)

# El panel no tiene formularios ni JavaScript.
_ENCABEZADOS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'self'; img-src 'self'; form-action 'none'; "
                               "frame-ancestors 'none'; base-uri 'none'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}
_TEXTOS_ERROR = {
    404: ("No encontrado", "La página no existe."),
}
# Rutas que atienden a ElevenLabs: responden JSON o nada, nunca una página.
_DE_MAQUINA = ("/herramientas/", "/webhooks/")
_CUERPO_MAXIMO_HERRAMIENTA = 4096
# Marca de que la página ya se volvió a pedir a sí misma (ver _sin_sesion).
_SEGUNDA_VUELTA = "v"


class _SinSesion(Exception):
    """Una página del panel recibió una visita sin sesión de la central."""


class _CentralCallada(Exception):
    """No se pudo preguntar a la central de quién es la sesión."""


# --- Dependencias ---

def conexion(request: Request):
    con = db.conectar(request.app.state.config.db_path)
    try:
        yield con
    finally:
        con.close()


# --- Trabajo fuera del request ---

def _guardar_caso(config: Config, caso: dict) -> None:
    con = db.conectar(config.db_path)
    try:
        casos.guardar(con, caso)
    finally:
        con.close()


def _avisar_si_es_urgente(config: Config, conversation_id: str, enviar) -> None:
    con = db.conectar(config.db_path)
    try:
        caso = casos.leer(con, conversation_id)
        if caso is not None and caso["urgente"] and not caso["avisado"]:
            if enviar(config, avisos.texto_de_caso(caso, config.base_url)):
                casos.marcar_avisado(con, conversation_id)
    finally:
        con.close()


def _whatsapp_a_quien_llamo(config: Config, conversation_id: str, transporte) -> None:
    con = db.conectar(config.db_path)
    try:
        whatsapp.procesar(config, con, conversation_id, transporte=transporte)
    finally:
        con.close()


def crear_app(config: Config | None = None, *, transporte_central=None, enviar_aviso=None,
              transporte_whatsapp=None) -> FastAPI:
    """`transporte_central`, `enviar_aviso` y `transporte_whatsapp` permiten a las pruebas reemplazar la central,
    Telegram y ElevenLabs."""
    config = config or cargar()
    enviar_aviso = enviar_aviso or avisos.enviar
    # nginx le quita el prefijo a lo que entra (/soporte/casos/x llega como /casos/x); lo que sale lo lleva puesto.
    base = config.prefijo

    def _pagina(plantilla: str, sesion=None, status_code: int = 200, **contexto) -> HTMLResponse:
        html = _plantillas.get_template(plantilla).render(sesion=sesion, base=base, central=config.central_panel,
                                                          **contexto)
        return HTMLResponse(html, status_code=status_code)

    def _mensaje(titulo: str, texto: str, status_code: int = 200) -> HTMLResponse:
        return _pagina("mensaje.html", status_code=status_code, titulo=titulo, texto=texto)

    def sesion_de_la_central(request: Request) -> dict:
        """El panel no tiene entrada propia: entra quien tiene sesión abierta en la central."""
        try:
            usuario = central.usuario_de_sesion(config, request.cookies.get(config.central_galleta),
                                                transporte=transporte_central)
        except central.CentralNoDisponible as error:
            raise _CentralCallada() from error
        if usuario is None:
            raise _SinSesion()
        return {"usuario": usuario}

    @asynccontextmanager
    async def ciclo_de_vida(_app):
        db.inicializar(config.db_path)
        yield

    # Sin /docs ni /openapi.json: nada de la app se publica sin querer.
    app = FastAPI(title="Soporte Audiocast", lifespan=ciclo_de_vida, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.config = config
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(config.hosts))
    app.mount("/estaticos", StaticFiles(directory=_CARPETA / "estaticos"), name="estaticos")

    @app.middleware("http")
    async def encabezados_de_seguridad(request: Request, call_next):
        respuesta = await call_next(request)
        for nombre, valor in _ENCABEZADOS.items():
            respuesta.headers.setdefault(nombre, valor)
        if not request.url.path.startswith("/estaticos/"):
            # Las páginas llevan datos personales: que no las guarde el navegador ni Cloudflare.
            respuesta.headers["Cache-Control"] = "no-store"
        return respuesta

    @app.exception_handler(_SinSesion)
    async def _sin_sesion(request: Request, _exc):
        # La galleta de la central es SameSite=Strict: el navegador no la manda cuando se llega desde otro sitio (el
        # enlace de un aviso, un correo). Pedida de nuevo desde esta misma página, sí la manda. Por eso la primera vez
        # la página se vuelve a pedir sola; si tampoco hay sesión, a la central, que muestra su entrada.
        if _SEGUNDA_VUELTA in request.query_params:
            return RedirectResponse(config.central_panel, status_code=303)
        consulta_url = request.url.query
        destino = base + quote(request.url.path) + "?" + (consulta_url + "&" if consulta_url else "") + _SEGUNDA_VUELTA + "=1"
        return _pagina("entrando.html", destino=destino)

    @app.exception_handler(_CentralCallada)
    async def _central_callada(_request, _exc):
        return _mensaje("No se pudo comprobar tu sesión", "La central no respondió. Vuelve a intentarlo en un momento.",
                        503)

    @app.exception_handler(StarletteHTTPException)
    async def _error_http(request: Request, exc):
        if request.url.path.startswith(_DE_MAQUINA):
            return Response(status_code=exc.status_code)
        titulo, texto = _TEXTOS_ERROR.get(exc.status_code, ("Error", "No se pudo completar la acción."))
        return _mensaje(titulo, texto, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _datos_no_validos(request: Request, _exc):
        if request.url.path.startswith(_DE_MAQUINA):
            return Response(status_code=400)
        return _mensaje("Datos no válidos", "Revisa el enlace e inténtalo de nuevo.", 400)

    @app.get("/salud")
    def salud(con=Depends(conexion)):
        """Para `curl` desde el servidor. Solo cuentas: ni nombres de tiendas ni datos de cajas ni de casos."""
        tiendas = directorio.todas(con)
        try:
            cajas = len(central.leer_cajas(config, transporte=transporte_central))
        except central.CentralNoDisponible:
            cajas = None
        return {"ok": True,
                "tiendas": len(tiendas),
                "tiendas_con_caja": sum(1 for tienda in tiendas if tienda.unit_id),
                "central": "archivo" if config.central_archivo else "http",
                "central_disponible": cajas is not None,
                "cajas_en_central": cajas,
                "herramienta": bool(config.herramienta_token),
                "webhook": bool(config.elevenlabs_webhook_secret),
                "avisos": bool(config.telegram_bot_token and config.telegram_chat_id)}

    # --- ElevenLabs: herramienta de la asistente (durante la llamada) ---

    @app.post("/herramientas/consultar_tienda")
    async def consultar_tienda(request: Request):
        if not config.herramienta_token:
            return Response(status_code=503)
        recibido = request.headers.get("x-soporte-token") or ""
        autorizacion = request.headers.get("authorization") or ""
        if not recibido and autorizacion.lower().startswith("bearer "):
            recibido = autorizacion[7:].strip()
        if not seguridad.token_valido(config.herramienta_token, recibido):
            return Response(status_code=401)
        cuerpo = await request.body()
        if len(cuerpo) > _CUERPO_MAXIMO_HERRAMIENTA:
            return Response(status_code=413)
        try:
            pedido = json.loads(cuerpo or b"{}")
            if not isinstance(pedido, dict):
                raise ValueError
        except ValueError:
            return JSONResponse({"error": "el cuerpo debe ser un objeto JSON"}, status_code=400)
        dicho = _cadena(pedido.get("tienda"))
        tienda_id = _cadena(pedido.get("tienda_id"))
        conversation_id = (_cadena(pedido.get("conversation_id"))
                           or _cadena(request.headers.get("x-conversation-id")))[:200]
        return JSONResponse(await run_in_threadpool(_consultar, dicho, tienda_id, conversation_id))

    def _consultar(dicho: str, tienda_id: str, conversation_id: str) -> dict:
        con = db.conectar(config.db_path)
        try:
            respuesta = consulta.consultar_tienda(con, config, dicho, tienda_id=tienda_id,
                                                  transporte=transporte_central)
            salida = consulta.para_la_asistente(respuesta)
            try:
                casos.anotar_consulta(con, conversation_id, dicho or tienda_id, respuesta, salida)
            except sqlite3.Error:
                # La persona está al teléfono: mejor contestarle sin anotar que fallarle por la base.
                pass
            return salida
        finally:
            con.close()

    # --- ElevenLabs: fin de la conversación ---

    @app.post("/webhooks/elevenlabs")
    async def webhook_elevenlabs(request: Request, tareas: BackgroundTasks):
        if not config.elevenlabs_webhook_secret:
            return Response(status_code=503)
        cuerpo = await request.body()
        if not elevenlabs.firma_valida(cuerpo, config.elevenlabs_webhook_secret,
                                       request.headers.get("elevenlabs-signature")):
            return Response(status_code=401)
        try:
            evento = json.loads(cuerpo)
            caso = (elevenlabs.caso_de_conversacion(evento["data"])
                    if evento["type"] == elevenlabs.EVENTO_GUARDADO else None)
        except (ValueError, KeyError, TypeError, AttributeError):
            return Response(status_code=400)
        # Un WhatsApp sin nada de la persona es la plantilla del caso que nadie contestó: no es un caso nuevo.
        if caso is not None and not (caso["canal"] == "whatsapp" and not casos.hablo_la_persona(caso)):
            await run_in_threadpool(_guardar_caso, config, caso)
            tareas.add_task(_avisar_si_es_urgente, config, caso["conversation_id"], enviar_aviso)
            tareas.add_task(_whatsapp_a_quien_llamo, config, caso["conversation_id"], transporte_whatsapp)
        return Response(status_code=204)

    # --- Panel: casos. Solo lectura. ---

    @app.get("/")
    def lista_de_casos(antes: int | None = None, urgentes: int = 0, sesion=Depends(sesion_de_la_central),
                       con=Depends(conexion)):
        filas = casos.lista(con, antes=antes, solo_urgentes=bool(urgentes))
        siguiente = filas[-1]["inicio"] if len(filas) == casos.LIMITE_PAGINA else None
        return _pagina("casos.html", sesion, casos=filas, cuenta=casos.contar(con), urgentes=bool(urgentes),
                       siguiente_antes=siguiente, pagina_siguiente=antes is not None)

    @app.get("/casos/{conversation_id}")
    def ver_caso(conversation_id: str, sesion=Depends(sesion_de_la_central), con=Depends(conexion)):
        caso = casos.leer(con, conversation_id)
        if caso is None:
            raise HTTPException(404)
        tienda = next((t for t in directorio.todas(con) if t.id == caso["tienda_id"]), None)
        ahora = consulta.revisar_equipo(config, tienda, transporte=transporte_central) if tienda else None
        return _pagina("caso.html", sesion, caso=caso, consultas=casos.consultas_de(con, conversation_id),
                       equipo_ahora=ahora["estado"] if ahora else None)

    return app


def _cadena(valor) -> str:
    return " ".join(valor.split())[:500] if isinstance(valor, str) else ""
