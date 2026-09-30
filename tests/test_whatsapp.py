"""Número de caso y WhatsApp a quien llamó (plantilla caso_registrado por ElevenLabs)."""

import dataclasses
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import casos, db, whatsapp
from app.principal import crear_app

from ayudas import conversacion, firmado

CLAVE = "xi-clave-de-prueba"
NUMERO_ID = "1366498186551130"


@pytest.fixture
def pedidos() -> list[httpx.Request]:
    return []


@pytest.fixture
def respuesta_elevenlabs() -> list[httpx.Response]:
    """La respuesta que dará ElevenLabs; las pruebas pueden cambiarla."""
    return [httpx.Response(200, json={"conversation_id": "conv_wa_1"})]


@pytest.fixture
def con_whatsapp(con, config, central_falsa, pedidos, respuesta_elevenlabs):
    def atender(request: httpx.Request) -> httpx.Response:
        pedidos.append(request)
        return respuesta_elevenlabs[0]
    configurado = dataclasses.replace(config, elevenlabs_api_key=CLAVE, whatsapp_numero_id=NUMERO_ID)
    app = crear_app(configurado, enviar_aviso=lambda *_: True, transporte_central=central_falsa,
                    transporte_whatsapp=httpx.MockTransport(atender))
    with TestClient(app, follow_redirects=False) as c:
        yield c


def enviar(cliente, evento):
    cuerpo, encabezados = firmado(evento)
    assert cliente.post("/webhooks/elevenlabs", content=cuerpo, headers=encabezados).status_code == 204


SOLO_LA_ASISTENTE = [{"role": "agent", "message": "Aló, soporte Audiocast, ¿en qué le puedo ayudar?",
                      "time_in_call_secs": 0}]


# ---- número de caso ------------------------------------------------------------------------------------------------------

def test_cada_caso_recibe_el_siguiente_numero_y_un_reintento_no_lo_cambia(cliente, con):
    enviar(cliente, conversacion("conv_1"))
    enviar(cliente, conversacion("conv_2"))
    enviar(cliente, conversacion("conv_1", ficha={"motivo": "Otro motivo"}))
    assert casos.leer(con, "conv_1")["numero"] == 1
    assert casos.leer(con, "conv_2")["numero"] == 2
    assert casos.leer(con, "conv_1")["motivo"] == "Otro motivo"


def test_los_casos_anteriores_al_numero_lo_reciben_en_orden(cliente, con, config):
    enviar(cliente, conversacion("conv_tarde", inicio=1790000500))
    enviar(cliente, conversacion("conv_temprano", inicio=1790000100))
    # Una base de antes del número de caso.
    antiguas = ", ".join(casos._COLUMNAS + ("avisado",))
    con.execute(f"CREATE TABLE casos_antes AS SELECT {antiguas} FROM casos")
    con.execute("DROP TABLE casos")
    con.execute("ALTER TABLE casos_antes RENAME TO casos")
    db.inicializar(config.db_path)
    assert casos.leer(con, "conv_temprano")["numero"] == 1
    assert casos.leer(con, "conv_tarde")["numero"] == 2
    db.inicializar(config.db_path)  # se puede repetir
    assert casos.leer(con, "conv_tarde")["numero"] == 2


# ---- el WhatsApp ---------------------------------------------------------------------------------------------------------

def test_manda_la_plantilla_a_quien_llamo(con_whatsapp, con, pedidos):
    enviar(con_whatsapp, conversacion("conv_1", telefono="+56911112222"))
    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert str(pedido.url) == whatsapp.URL
    assert pedido.headers["xi-api-key"] == CLAVE
    assert json.loads(pedido.content) == {
        "whatsapp_phone_number_id": NUMERO_ID,
        "whatsapp_user_id": "56911112222",
        "template_name": "caso_registrado",
        "template_language_code": "es",
        "template_params": [{"type": "body", "parameters": [
            {"type": "text", "text": "Marcela"}, {"type": "text", "text": "0001"},
            {"type": "text", "text": "Tottus Recoleta"}, {"type": "text", "text": "Tienda sin música"}]}],
        "agent_id": "agent_de_prueba",
    }
    caso = casos.leer(con, "conv_1")
    assert caso["whatsapp_estado"] == "enviado"


def test_un_reintento_del_webhook_no_lo_repite(con_whatsapp, pedidos):
    enviar(con_whatsapp, conversacion("conv_1"))
    enviar(con_whatsapp, conversacion("conv_1"))
    assert len(pedidos) == 1


@pytest.mark.parametrize("evento, motivo", [
    (conversacion("conv_1", telefono="+56223334444"), "No llamó desde un celular."),
    (conversacion("conv_1", telefono=None), None),  # prueba desde el navegador: no es una llamada
    (conversacion("conv_1", ficha={"resuelto_en_llamada": True}), "El problema se resolvió en la llamada."),
    (conversacion("conv_1", transcript=SOLO_LA_ASISTENTE), "La persona cortó sin hablar."),
])
def test_casos_que_no_llevan_whatsapp(con_whatsapp, con, pedidos, evento, motivo):
    enviar(con_whatsapp, evento)
    assert pedidos == []
    caso = casos.leer(con, "conv_1")
    assert caso["whatsapp_estado"] == ("omitido" if motivo else None)
    assert caso["whatsapp_detalle"] == motivo


def test_sin_configurar_no_manda_nada(cliente, con):
    enviar(cliente, conversacion("conv_1"))
    caso = casos.leer(con, "conv_1")
    assert (caso["whatsapp_estado"], caso["whatsapp_detalle"]) == ("omitido", "El envío de WhatsApp no está configurado.")


def test_si_elevenlabs_falla_queda_anotado_sin_la_clave(con_whatsapp, con, respuesta_elevenlabs):
    respuesta_elevenlabs[0] = httpx.Response(400, json={"detail": "template not approved"})
    enviar(con_whatsapp, conversacion("conv_1"))
    caso = casos.leer(con, "conv_1")
    assert caso["whatsapp_estado"] == "error"
    assert "400" in caso["whatsapp_detalle"] and "template not approved" in caso["whatsapp_detalle"]
    assert CLAVE not in caso["whatsapp_detalle"]


def test_un_whatsapp_que_nadie_contesto_no_es_un_caso(con_whatsapp, con, pedidos):
    evento = conversacion("conv_wa_1", telefono=None, transcript=SOLO_LA_ASISTENTE)
    evento["data"]["metadata"]["whatsapp"] = {"direction": "outbound", "whatsapp_user_id": "56911112222"}
    enviar(con_whatsapp, evento)
    assert casos.leer(con, "conv_wa_1") is None
    # Si la persona contestó, sí es un caso; no se le vuelve a mandar la plantilla.
    evento = conversacion("conv_wa_2", telefono=None)
    evento["data"]["metadata"]["whatsapp"] = {"direction": "outbound", "whatsapp_user_id": "56911112222"}
    enviar(con_whatsapp, evento)
    assert casos.leer(con, "conv_wa_2")["canal"] == "whatsapp"
    assert pedidos == []


# ---- los valores de la plantilla -----------------------------------------------------------------------------------------

def _caso(**cambios) -> dict:
    caso = {"nombre_contacto": "Fernán Rodríguez", "numero": 3, "tienda_nombre": "Rancagua Centro", "tienda": "Rancagua",
            "motivo": "Avisos no suenan", "problema": "aviso_no_salio"}
    caso.update(cambios)
    return caso


def test_valores_de_la_plantilla():
    assert whatsapp.valores_de_plantilla(_caso()) == ["Fernán", "0003", "Tottus Rancagua Centro", "Avisos no suenan"]
    assert whatsapp.valores_de_plantilla(_caso(nombre_contacto=None, tienda_nombre=None, tienda=None, motivo=None,
                                               problema=None)) == ["estimado/a", "0003", "por confirmar", "por revisar"]
    # Sin tienda del directorio, la que dijo la persona; la marca no se repite.
    assert whatsapp.valores_de_plantilla(_caso(tienda_nombre=None, tienda="Tóttus de Viña"))[2] == "Tóttus de Viña"
    # Sin motivo, el tipo de problema.
    assert whatsapp.valores_de_plantilla(_caso(motivo=""))[3] == "Un aviso no salió"
    # Meta no acepta saltos de línea; lo largo se corta.
    motivo = whatsapp.valores_de_plantilla(_caso(motivo="Se corta\nla música " + "x" * 100))[3]
    assert "\n" not in motivo and len(motivo) == 60 and motivo.endswith("…")


def test_celular():
    assert whatsapp.celular("+56911112222") == "56911112222"
    for otro in ("+56223334444", "", None, "+5491122223333", "anonymous"):
        assert whatsapp.celular(otro) is None


# ---- panel ---------------------------------------------------------------------------------------------------------------

def test_el_panel_muestra_el_numero_y_el_whatsapp(con_whatsapp, pedidos):
    enviar(con_whatsapp, conversacion("conv_1"))
    con_whatsapp.cookies.set("ac_session", "sesion-abierta-en-la-central")
    assert "N° 0001" in con_whatsapp.get("/").text
    pagina = con_whatsapp.get("/casos/conv_1").text
    assert "N° 0001" in pagina and "Enviado" in pagina


def test_reintentar_un_envio_que_fallo(con_whatsapp, con, config, pedidos, respuesta_elevenlabs):
    respuesta_elevenlabs[0] = httpx.Response(400, json={"detail": "template does not exist"})
    enviar(con_whatsapp, conversacion("conv_1"))
    assert casos.leer(con, "conv_1")["whatsapp_estado"] == "error"
    respuesta_elevenlabs[0] = httpx.Response(200, json={})
    configurado = dataclasses.replace(config, elevenlabs_api_key=CLAVE, whatsapp_numero_id=NUMERO_ID)
    transporte = httpx.MockTransport(lambda request: (pedidos.append(request), respuesta_elevenlabs[0])[1])
    assert whatsapp.reintentar(configurado, con, 1, transporte=transporte) == "enviado"
    assert casos.leer(con, "conv_1")["whatsapp_estado"] == "enviado"
    assert len(pedidos) == 2
    # Uno ya enviado no se repite; un número que no existe tampoco hace nada.
    assert whatsapp.reintentar(configurado, con, 1, transporte=transporte) == "no se reintenta: está enviado"
    assert whatsapp.reintentar(configurado, con, 99, transporte=transporte) == "no existe"
    assert len(pedidos) == 2
