"""El panel: entra quien tiene sesión en la central; lista de casos y caso."""

import re

import httpx
from fastapi.testclient import TestClient

from app import avisos, central
from app.config import Config
from app.principal import crear_app

from ayudas import TOKEN_HERRAMIENTA, conversacion, firmado
from conftest import SESION, USUARIO


def llega_un_caso(cliente, conversation_id="conv_1", consultar: str | None = "recoleta", **ficha):
    if consultar:
        cliente.post("/herramientas/consultar_tienda", headers={"X-Soporte-Token": TOKEN_HERRAMIENTA},
                     json={"tienda": consultar, "conversation_id": conversation_id})
    cuerpo, encabezados = firmado(conversacion(conversation_id, ficha=ficha))
    assert cliente.post("/webhooks/elevenlabs", content=cuerpo, headers=encabezados).status_code == 204


# ---- salud y encabezados --------------------------------------------------------------------------------------------------

def test_salud(cliente):
    respuesta = cliente.get("/salud")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"ok": True, "tiendas": 71, "tiendas_con_caja": 70, "central": "archivo",
                                "central_disponible": True, "cajas_en_central": 71, "herramienta": True,
                                "webhook": True, "avisos": False}


def test_salud_sin_configurar(sin_configurar):
    assert sin_configurar.get("/salud").json() == {
        "ok": True, "tiendas": 0, "tiendas_con_caja": 0, "central": "http", "central_disponible": False,
        "cajas_en_central": None, "herramienta": False, "webhook": False, "avisos": False}


def test_no_hay_documentacion_publica(cliente):
    for ruta in ("/docs", "/redoc", "/openapi.json"):
        assert cliente.get(ruta).status_code == 404


def test_encabezados_de_seguridad(panel):
    respuesta = panel.get("/")
    assert "default-src 'none'" in respuesta.headers["content-security-policy"]
    assert "form-action 'none'" in respuesta.headers["content-security-policy"]
    assert respuesta.headers["x-frame-options"] == "DENY"
    assert respuesta.headers["cache-control"] == "no-store"
    assert panel.get("/estaticos/estilo.css").headers.get("cache-control") != "no-store"


def test_otro_host_no_entra(panel):
    assert panel.get("/", headers={"Host": "otro.ejemplo.cl"}).status_code == 400


# ---- entrada: la sesión de la central -------------------------------------------------------------------------------------

def test_no_hay_entrada_propia(panel):
    """Ni página de ingreso, ni claves, ni galleta propia: decisión de hrm del 2026-09-28."""
    for ruta in ("/entrar", "/salir", "/login"):
        assert panel.get(ruta).status_code == 404
        assert panel.post(ruta).status_code in (404, 405)
    respuesta = panel.get("/")
    assert "set-cookie" not in respuesta.headers
    assert "<form" not in respuesta.text and 'type="password"' not in respuesta.text


def test_con_sesion_en_la_central_entra_directo(panel, pedidos_a_la_central):
    respuesta = panel.get("/")
    assert respuesta.status_code == 200
    assert USUARIO in respuesta.text
    assert 'href="/">Central de flota</a>' in respuesta.text
    assert [(p.method, p.url.path) for p in pedidos_a_la_central] == [("GET", "/api/me")]


def test_sin_sesion_la_pagina_se_pide_de_nuevo_y_despues_va_a_la_central(cliente):
    """La galleta de la central es SameSite=Strict: llegando desde otro sitio, el navegador no la manda la primera vez."""
    llega_un_caso(cliente)
    primera = cliente.get("/casos/conv_1")
    assert primera.status_code == 200
    assert '<meta http-equiv="refresh" content="0; url=/casos/conv_1?v=1">' in primera.text
    assert "Recoleta" not in primera.text and "Marcela" not in primera.text
    segunda = cliente.get("/casos/conv_1?v=1")
    assert (segunda.status_code, segunda.headers["location"]) == (303, "/")
    assert "Recoleta" not in segunda.text
    con_filtro = cliente.get("/?urgentes=1")
    assert 'url=/?urgentes=1&amp;v=1"' in con_filtro.text


def test_la_segunda_vuelta_con_sesion_muestra_la_pagina(panel):
    llega_un_caso(panel)
    assert "Marcela Soto" in panel.get("/casos/conv_1?v=1").text


def test_una_sesion_que_la_central_no_conoce_no_entra(cliente):
    llega_un_caso(cliente)
    for galleta in ("inventada", "", "a" * 600, "con;punto-y-coma"):
        cliente.cookies.clear()
        if galleta:
            cliente.cookies.set("ac_session", galleta)
        respuesta = cliente.get("/?v=1")
        assert (respuesta.status_code, respuesta.headers["location"]) == (303, "/"), galleta
        assert "Recoleta" not in respuesta.text


def test_la_galleta_vieja_del_soporte_ya_no_abre_nada(cliente):
    cliente.cookies.set("soporte_sesion", "lo-que-sea")
    assert cliente.get("/?v=1").status_code == 303


def test_la_sesion_se_vuelve_a_comprobar_pasado_un_rato(panel, pedidos_a_la_central, monkeypatch):
    panel.get("/")
    panel.get("/")
    assert len(pedidos_a_la_central) == 1  # se le cree por 30 s
    monkeypatch.setattr(central, "SESION_CACHE_S", 0)
    panel.get("/")
    assert len(pedidos_a_la_central) == 2


def test_si_la_central_no_responde_no_se_entra(con, config):
    def caida(_request):
        raise httpx.ConnectError("conexión rechazada")
    with TestClient(crear_app(config, transporte_central=httpx.MockTransport(caida)), follow_redirects=False) as cliente:
        cliente.cookies.set("ac_session", SESION)
        respuesta = cliente.get("/")
    assert respuesta.status_code == 503
    assert "No se pudo comprobar tu sesión" in respuesta.text


def test_quien_entra_a_la_central_con_token_no_tiene_usuario(con, config):
    """La central responde 200 con user: null a un token de operador. Eso no es una sesión de persona."""
    sin_usuario = httpx.MockTransport(lambda _request: httpx.Response(200, json={"user": None, "login": True}))
    with TestClient(crear_app(config, transporte_central=sin_usuario), follow_redirects=False) as cliente:
        cliente.cookies.set("ac_session", SESION)
        assert cliente.get("/?v=1").status_code == 303


def test_a_la_central_solo_se_le_muestra_la_galleta(panel, pedidos_a_la_central):
    panel.get("/")
    pedido = pedidos_a_la_central[0]
    assert pedido.headers["cookie"] == f"ac_session={SESION}"
    assert "authorization" not in pedido.headers


# ---- casos ----------------------------------------------------------------------------------------------------------------

def test_lista_vacia(panel):
    respuesta = panel.get("/")
    assert "Todavía no hay casos." in respuesta.text
    assert "No hay casos urgentes." in panel.get("/?urgentes=1").text


def test_lista_con_casos(panel):
    llega_un_caso(panel, "conv_1")
    llega_un_caso(panel, "conv_2", consultar="providencia", tienda="Providencia", urgencia=False,
                  requiere_tecnico=False, problema="volumen", motivo="Música muy baja")
    pagina = panel.get("/").text
    assert "2 casos" in pagina and "1 urgente" in pagina
    assert pagina.count("caso caso-urgente") == 1
    for texto in ("Recoleta", "Tienda sin música", "Sin audio", "Requiere técnico", "Urgente", "Providencia",
                  "Música muy baja", "Volumen", "Su equipo está funcionando y conectado.", 'href="/casos/conv_2"'):
        assert texto in pagina, texto
    urgentes = panel.get("/?urgentes=1").text
    assert "Tienda sin música" in urgentes and "Música muy baja" not in urgentes


def test_caso(panel):
    llega_un_caso(panel, "conv_1")
    pagina = panel.get("/casos/conv_1").text
    for texto in ("Recoleta", "Región Metropolitana", "Llamada", "1 min 35 s", "Marcela Soto", "+56911112222",
                  "desde las diez de la mañana", "Durante la llamada", "No tenemos señal de su equipo", "Ahora",
                  "Buscó «recoleta»", "Aló, soporte Audiocast", "estamos sin música", "recoleta-07", "conv_1"):
        assert texto in pagina, texto


def test_caso_sin_tienda_ni_consulta(panel):
    llega_un_caso(panel, "conv_1", consultar=None, tienda="no dijo")
    pagina = panel.get("/casos/conv_1").text
    assert "La asistente no consultó el equipo" in pagina
    assert "no quedó asociado a una tienda" in pagina


def test_caso_que_no_existe(panel):
    respuesta = panel.get("/casos/no-existe")
    assert respuesta.status_code == 404
    assert "No encontrado" in respuesta.text


def test_lo_que_dijo_la_persona_no_se_ejecuta(panel):
    malo = '<script>alert(1)</script><img src=x onerror=alert(2)>'
    cuerpo, encabezados = firmado(conversacion(
        "conv_<b>", ficha={"motivo": malo, "resumen": malo, "nombre_contacto": malo, "tienda": malo},
        transcript=[{"role": "user", "message": malo, "time_in_call_secs": 1}]))
    assert panel.post("/webhooks/elevenlabs", content=cuerpo, headers=encabezados).status_code == 204
    for pagina in (panel.get("/").text, panel.get("/casos/conv_%3Cb%3E").text):
        assert "<script>" not in pagina and "<img" not in pagina and "conv_<b>" not in pagina
        assert "&lt;script&gt;" in pagina


def test_el_panel_nunca_muestra_la_piloto(panel):
    llega_un_caso(panel, "conv_1", consultar="la de nataniel", tienda="Nataniel Cox")
    assert "nataniel-cox-01" not in panel.get("/casos/conv_1").text


# ---- avisos ---------------------------------------------------------------------------------------------------------------

def test_telegram(con, config, panel):
    import dataclasses
    from app import casos
    llega_un_caso(panel, "conv_1")
    caso = casos.leer(con, "conv_1")
    texto = avisos.texto_de_caso(caso, "https://soporte.ejemplo.cl")
    assert texto.splitlines()[0] == "🔴 Soporte Audiocast: caso urgente en Recoleta"
    assert texto.splitlines()[-1] == "https://soporte.ejemplo.cl/casos/conv_1"
    assert "sim-" not in texto

    vistos = []

    def telegram(request):
        vistos.append(request)
        return httpx.Response(200, json={"ok": True})
    assert avisos.enviar(config, texto, transporte=httpx.MockTransport(telegram)) is False  # sin configurar
    assert vistos == []
    configurado = dataclasses.replace(config, telegram_bot_token="123:abc", telegram_chat_id="42")
    assert avisos.enviar(configurado, texto, transporte=httpx.MockTransport(telegram)) is True
    assert str(vistos[0].url) == "https://api.telegram.org/bot123:abc/sendMessage"
    caido = httpx.MockTransport(lambda _request: httpx.Response(500))
    assert avisos.enviar(configurado, texto, transporte=caido) is False


def test_config_por_defecto_no_acepta_testserver(monkeypatch):
    from app.config import cargar
    for nombre in ("SOPORTE_HOSTS", "SOPORTE_HERRAMIENTA_TOKEN", "CENTRAL_GALLETA", "CENTRAL_PANEL"):
        monkeypatch.delenv(nombre, raising=False)
    config = cargar()
    assert config.hosts == ("127.0.0.1", "localhost")
    assert config.herramienta_token == ""
    assert (config.central_galleta, config.central_panel) == ("ac_session", "/")
    assert isinstance(config, Config)


# ---- publicado bajo un prefijo (central.mediaflow.cl/soporte) -------------------------------------------------------------

def test_con_prefijo_todo_lo_que_sale_lo_lleva(con, config, central_falsa):
    """nginx le quita /soporte a lo que entra: la app atiende en /casos/x y contesta con /soporte/casos/x."""
    import dataclasses
    app = crear_app(dataclasses.replace(config, prefijo="/soporte"), transporte_central=central_falsa)
    with TestClient(app, follow_redirects=False) as cliente:
        assert 'url=/soporte/?v=1"' in cliente.get("/").text
        assert cliente.get("/?v=1").headers["location"] == "/"  # a la central, que no lleva prefijo
        cliente.cookies.set("ac_session", SESION)
        llega_un_caso(cliente, "conv_1")
        for pagina in (cliente.get("/").text, cliente.get("/casos/conv_1").text, cliente.get("/casos/no").text):
            enlaces = re.findall(r'href="([^"]+)"', pagina)
            assert enlaces and all(e == "/" or e.startswith("/soporte/") for e in enlaces), enlaces
        assert 'href="/soporte/casos/conv_1"' in cliente.get("/").text


def test_prefijo_se_normaliza(monkeypatch):
    from app.config import cargar
    for escrito, queda in (("", ""), ("/", ""), ("soporte", "/soporte"), ("/soporte/", "/soporte"),
                           (" /soporte ", "/soporte")):
        monkeypatch.setenv("SOPORTE_PREFIJO", escrito)
        assert cargar().prefijo == queda
