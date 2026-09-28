"""POST /herramientas/consultar_tienda: lo que usa la asistente durante la llamada."""

import json

import httpx
from fastapi.testclient import TestClient

from app import casos
from app.principal import crear_app

from ayudas import TOKEN_HERRAMIENTA
from conftest import con_http

RUTA = "/herramientas/consultar_tienda"
CON_TOKEN = {"X-Soporte-Token": TOKEN_HERRAMIENTA}


def test_sin_token_o_con_otro_no_entra(cliente):
    assert cliente.post(RUTA, json={"tienda": "recoleta"}).status_code == 401
    assert cliente.post(RUTA, json={"tienda": "recoleta"}, headers={"X-Soporte-Token": "otro"}).status_code == 401
    assert cliente.post(RUTA, json={"tienda": "recoleta"}, headers={"X-Soporte-Token": ""}).status_code == 401


def test_sin_token_configurado_la_herramienta_no_existe(sin_configurar):
    respuesta = sin_configurar.post(RUTA, json={"tienda": "recoleta"}, headers={"X-Soporte-Token": ""})
    assert respuesta.status_code == 503


def test_tambien_acepta_bearer(cliente):
    respuesta = cliente.post(RUTA, json={"tienda": "recoleta"},
                             headers={"Authorization": f"Bearer {TOKEN_HERRAMIENTA}"})
    assert respuesta.status_code == 200


def test_encuentra_la_tienda_y_dice_como_esta(cliente):
    respuesta = cliente.post(RUTA, json={"tienda": "la de Nataniel", "conversation_id": "conv_1"}, headers=CON_TOKEN)
    assert respuesta.status_code == 200
    assert respuesta.headers["cache-control"] == "no-store"
    salida = respuesta.json()
    assert salida["resultado"] == "encontrada"
    assert (salida["tienda_id"], salida["tienda"], salida["comuna"]) == ("nataniel-cox", "Nataniel Cox",
                                                                           "Santiago Centro")
    assert salida["estado_del_equipo"] == "Su equipo está funcionando normal."
    assert salida["urgente"] is False
    assert "caja" not in salida


def test_varias_y_despues_la_elegida(cliente):
    primera = cliente.post(RUTA, json={"tienda": "talca"}, headers=CON_TOKEN).json()
    assert primera["resultado"] == "varias"
    elegida = primera["opciones"][1]["tienda_id"]
    segunda = cliente.post(RUTA, json={"tienda": "talca", "tienda_id": elegida}, headers=CON_TOKEN).json()
    assert (segunda["resultado"], segunda["tienda"]) == ("encontrada", "Talca Colín")


def test_ninguna(cliente):
    salida = cliente.post(RUTA, json={"tienda": "Temuco"}, headers=CON_TOKEN).json()
    assert salida["resultado"] == "ninguna"
    assert "comuna" in salida["indicacion"]


def test_pedidos_raros_no_rompen(cliente):
    assert cliente.post(RUTA, json={}, headers=CON_TOKEN).json()["resultado"] == "ninguna"
    assert cliente.post(RUTA, json={"tienda": None, "tienda_id": 7}, headers=CON_TOKEN).json()["resultado"] == "ninguna"
    assert cliente.post(RUTA, json={"tienda": ["recoleta"]}, headers=CON_TOKEN).json()["resultado"] == "ninguna"
    assert cliente.post(RUTA, content=b"", headers=CON_TOKEN).json()["resultado"] == "ninguna"
    assert cliente.post(RUTA, content=b"no es json", headers=CON_TOKEN).status_code == 400
    assert cliente.post(RUTA, json=["recoleta"], headers=CON_TOKEN).status_code == 400
    assert cliente.post(RUTA, json={"tienda": "x" * 5000}, headers=CON_TOKEN).status_code == 413


def test_solo_post(cliente):
    assert cliente.get(RUTA, headers=CON_TOKEN).status_code == 405


def test_cada_consulta_queda_anotada_con_la_caja_cruda(cliente, con):
    cliente.post(RUTA, json={"tienda": "talca", "conversation_id": "conv_7"}, headers=CON_TOKEN)
    cliente.post(RUTA, json={"tienda": "talca", "tienda_id": "talca", "conversation_id": "conv_7"}, headers=CON_TOKEN)
    cliente.post(RUTA, json={"tienda": "recoleta", "conversation_id": "otra"}, headers=CON_TOKEN)
    anotadas = casos.consultas_de(con, "conv_7")
    assert [(c["dicho"], c["resultado"], c["tienda_id"]) for c in anotadas] == [("talca", "varias", None),
                                                                               ("talca", "una", "talca")]
    assert anotadas[0]["caja"] is None
    assert json.loads(anotadas[1]["caja"])["site_id"] == "talca-45"
    assert json.loads(anotadas[1]["respuesta"])["estado_del_equipo"] == anotadas[1]["frase"]


def test_el_conversation_id_tambien_llega_por_encabezado(cliente, con):
    cliente.post(RUTA, json={"tienda": "recoleta"}, headers={**CON_TOKEN, "X-Conversation-Id": "conv_9"})
    assert len(casos.consultas_de(con, "conv_9")) == 1


def test_si_la_central_no_responde_la_asistente_igual_recibe_respuesta(con, config):
    def caida(_request):
        raise httpx.ReadTimeout("sin respuesta")
    app = crear_app(con_http(config), transporte_central=httpx.MockTransport(caida))
    with TestClient(app) as cliente:
        salida = cliente.post(RUTA, json={"tienda": "recoleta"}, headers=CON_TOKEN).json()
    assert salida["resultado"] == "encontrada"
    assert salida["estado_del_equipo"] == "No pude revisar su equipo en este momento."
    assert "urgente" not in salida


def test_la_app_solo_le_hace_get_a_la_central(con, config):
    vistos = []

    def central_falsa(request):
        vistos.append((request.method, request.url.path))
        return httpx.Response(200, json={"units": []})
    app = crear_app(con_http(config), transporte_central=httpx.MockTransport(central_falsa))
    with TestClient(app) as cliente:
        cliente.post(RUTA, json={"tienda": "recoleta"}, headers=CON_TOKEN)
        cliente.get("/salud")
        cliente.cookies.set("ac_session", "una-sesion")
        cliente.get("/")
    assert set(vistos) == {("GET", "/api/units"), ("GET", "/api/me")}
