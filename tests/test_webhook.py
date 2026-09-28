"""POST /webhooks/elevenlabs: la conversación terminada se vuelve un caso."""

import json
import time

import pytest

from app import casos, elevenlabs

from ayudas import SECRETO, TOKEN_HERRAMIENTA, conversacion, firmado

RUTA = "/webhooks/elevenlabs"


def enviar(cliente, evento, **firma):
    cuerpo, encabezados = firmado(evento, **firma)
    return cliente.post(RUTA, content=cuerpo, headers=encabezados)


# ---- firma ----------------------------------------------------------------------------------------------------------------

def test_firma():
    cuerpo = b'{"type": "post_call_transcription"}'
    header = elevenlabs.firmar(cuerpo, SECRETO, 1000)
    assert elevenlabs.firma_valida(cuerpo, SECRETO, header, ahora_s=1000)
    assert elevenlabs.firma_valida(cuerpo, SECRETO, header, ahora_s=1000 + 29 * 60)
    assert not elevenlabs.firma_valida(cuerpo, SECRETO, header, ahora_s=1000 + 31 * 60)
    assert not elevenlabs.firma_valida(cuerpo + b" ", SECRETO, header, ahora_s=1000)
    assert not elevenlabs.firma_valida(cuerpo, "otro", header, ahora_s=1000)
    assert not elevenlabs.firma_valida(cuerpo, "", header, ahora_s=1000)
    for malo in (None, "", "t=1000", "v0=abc", "t=mil,v0=" + "a" * 64, "t=1000,v0=" + "A" * 64, "cualquier cosa"):
        assert not elevenlabs.firma_valida(cuerpo, SECRETO, malo, ahora_s=1000)


def test_sin_firma_con_otra_o_vieja_no_entra(cliente, con):
    evento = conversacion()
    cuerpo, _ = firmado(evento)
    assert cliente.post(RUTA, content=cuerpo).status_code == 401
    assert enviar(cliente, evento, secreto="otro").status_code == 401
    assert enviar(cliente, evento, momento=int(time.time()) - 3600).status_code == 401
    assert casos.contar(con)["total"] == 0


def test_se_firma_el_cuerpo_crudo(cliente):
    cuerpo, encabezados = firmado(conversacion())
    reordenado = json.dumps(json.loads(cuerpo), indent=2).encode()
    assert cliente.post(RUTA, content=reordenado, headers=encabezados).status_code == 401


def test_sin_secreto_configurado_responde_503(sin_configurar):
    cuerpo, encabezados = firmado(conversacion())
    assert sin_configurar.post(RUTA, content=cuerpo, headers=encabezados).status_code == 503


# ---- el caso --------------------------------------------------------------------------------------------------------------

def test_guarda_el_caso_con_su_ficha(cliente, con):
    assert enviar(cliente, conversacion("conv_1", inicio=1790000000)).status_code == 204
    caso = casos.leer(con, "conv_1")
    assert (caso["canal"], caso["telefono"], caso["inicio"], caso["duracion_s"]) == ("llamada", "+56911112222",
                                                                                      1790000000, 95)
    assert (caso["tienda_id"], caso["tienda_nombre"], caso["tienda"]) == ("recoleta", "Recoleta", "Recoleta")
    assert (caso["nombre_contacto"], caso["problema"], caso["motivo"]) == ("Marcela Soto", "sin_audio",
                                                                         "Tienda sin música")
    assert (caso["urgencia"], caso["resuelto_en_llamada"], caso["requiere_tecnico"]) == (1, 0, 1)
    assert caso["resumen"].startswith("La tienda Recoleta está sin música")
    assert caso["exitosa"] == 1
    assert json.loads(caso["transcripcion"]) == [
        {"rol": "asistente", "mensaje": "Aló, soporte Audiocast, ¿en qué le puedo ayudar?", "segundo": 0},
        {"rol": "persona", "mensaje": "Hola, llamo del Tottus de Recoleta, estamos sin música.", "segundo": 4},
        {"rol": "asistente", "mensaje": "No tenemos señal de su equipo desde las 9:40.", "segundo": 12},
    ]


def test_es_idempotente(cliente, con):
    enviar(cliente, conversacion("conv_1"))
    enviar(cliente, conversacion("conv_1", ficha={"motivo": "Corregido"}))
    assert casos.contar(con)["total"] == 1
    assert casos.leer(con, "conv_1")["motivo"] == "Corregido"


def test_otros_eventos_se_aceptan_y_se_ignoran(cliente, con):
    for tipo in ("post_call_audio", "call_initiation_failure"):
        assert enviar(cliente, {"type": tipo, "data": {"conversation_id": "x"}}).status_code == 204
    assert casos.contar(con)["total"] == 0


@pytest.mark.parametrize("evento", [[], {"type": "post_call_transcription"},
                                    {"type": "post_call_transcription", "data": {}},
                                    {"type": "post_call_transcription", "data": "texto"}, {"data": {}}])
def test_un_evento_mal_formado_da_400(cliente, evento):
    assert enviar(cliente, evento).status_code == 400


def test_una_prueba_del_navegador_tambien_es_un_caso(cliente, con):
    enviar(cliente, conversacion("conv_web", telefono=None))
    caso = casos.leer(con, "conv_web")
    assert (caso["canal"], caso["telefono"]) == ("prueba", None)


def test_la_tienda_del_caso_es_la_que_consulto_la_asistente(cliente, con):
    """La ficha dice "Talca", que son dos tiendas; la asistente consultó Talca Colín."""
    token = {"X-Soporte-Token": TOKEN_HERRAMIENTA}
    cliente.post("/herramientas/consultar_tienda", json={"tienda": "talca", "conversation_id": "conv_2"}, headers=token)
    cliente.post("/herramientas/consultar_tienda", headers=token,
                 json={"tienda": "talca", "tienda_id": "talca-colin", "conversation_id": "conv_2"})
    enviar(cliente, conversacion("conv_2", ficha={"tienda": "Talca", "urgencia": False}))
    caso = casos.leer(con, "conv_2")
    assert caso["tienda_id"] == "talca-colin"
    assert caso["equipo_frase"] == "Su equipo está funcionando y conectado."
    assert json.loads(caso["equipo_caja"])["site_id"] == "linares-47"
    assert caso["urgente"] == 0


def test_sin_consulta_y_con_una_tienda_dudosa_el_caso_queda_sin_tienda(cliente, con):
    enviar(cliente, conversacion("conv_3", ficha={"tienda": "Talca"}))
    caso = casos.leer(con, "conv_3")
    assert (caso["tienda_id"], caso["tienda"], caso["equipo_frase"]) == (None, "Talca", None)


def test_urgente_por_la_ficha_o_por_el_equipo(cliente, con):
    token = {"X-Soporte-Token": TOKEN_HERRAMIENTA}
    # El equipo de Recoleta no da señal: urgente aunque la ficha diga que no.
    cliente.post("/herramientas/consultar_tienda", json={"tienda": "recoleta", "conversation_id": "a"}, headers=token)
    enviar(cliente, conversacion("a", ficha={"urgencia": False}))
    enviar(cliente, conversacion("b", ficha={"tienda": "Providencia", "urgencia": True}))
    enviar(cliente, conversacion("c", ficha={"tienda": "Providencia", "urgencia": False}))
    assert {fila["conversation_id"]: fila["urgente"] for fila in casos.lista(con)} == {"a": 1, "b": 1, "c": 0}
    assert {fila["conversation_id"] for fila in casos.lista(con, solo_urgentes=True)} == {"a", "b"}
    assert casos.contar(con) == {"total": 3, "urgentes": 2}


def test_ficha_con_valores_raros(cliente, con):
    enviar(cliente, conversacion("conv_4", ficha={
        "problema": "se cortó la luz", "urgencia": "true", "resuelto_en_llamada": "no", "requiere_tecnico": None,
        "nombre_contacto": "None", "desde_cuando": "", "motivo": {"no": "es texto"}, "resumen": None}))
    caso = casos.leer(con, "conv_4")
    assert caso["problema"] == "otro"
    assert (caso["urgencia"], caso["resuelto_en_llamada"], caso["requiere_tecnico"]) == (1, 0, None)
    assert (caso["nombre_contacto"], caso["desde_cuando"], caso["motivo"]) == (None, None, None)
    assert caso["resumen"] == "Resumen de ElevenLabs."


def test_conversacion_sin_analisis_ni_transcripcion(cliente, con):
    evento = {"type": "post_call_transcription", "data": {"conversation_id": "conv_5"}}
    assert enviar(cliente, evento).status_code == 204
    caso = casos.leer(con, "conv_5")
    assert (caso["canal"], caso["transcripcion"], caso["problema"], caso["urgente"]) == ("prueba", "[]", None, 0)


# ---- aviso ----------------------------------------------------------------------------------------------------------------

def test_avisa_los_urgentes_una_sola_vez(cliente, con, avisos_enviados):
    enviar(cliente, conversacion("conv_1"))
    enviar(cliente, conversacion("conv_1"))
    enviar(cliente, conversacion("conv_2", ficha={"tienda": "Providencia", "urgencia": False}))
    assert len(avisos_enviados) == 1
    assert "caso urgente en Recoleta" in avisos_enviados[0]
    assert "sin audio" in avisos_enviados[0]
    assert casos.leer(con, "conv_1")["avisado"] == 1
    assert casos.leer(con, "conv_2")["avisado"] == 0
