import dataclasses
from datetime import datetime, timezone

import httpx

from app import consulta

AHORA = datetime(2026, 9, 28, 13, 23, 9, tzinfo=timezone.utc)


def test_una_tienda_con_su_estado_y_la_caja_cruda(con, config):
    respuesta = consulta.consultar_tienda(con, config, "la de nataniel", ahora=AHORA)
    assert respuesta["resultado"] == "una"
    assert respuesta["tienda"] == {"id": "nataniel-cox", "nombre": "Nataniel Cox", "comuna": "Santiago Centro",
                                   "region": "Región Metropolitana", "direccion": "Nataniel Cox 620"}
    # La piloto, asignada a Nataniel Cox en la central y desenchufada (hrm 2026-09-30: se puede mencionar).
    assert respuesta["estado"]["frase"].startswith("No tenemos señal de su equipo desde hace 9 días")
    assert respuesta["caja"]["unit_id"] == "96adc18211af42c1ba49ef5c0574da54"
    assert respuesta["central_disponible"] is True


def test_los_tres_casos_del_guion_con_el_plan_mixto(con, config):
    def frase(tienda):
        return consulta.consultar_tienda(con, config, tienda, ahora=AHORA)["estado"]["frase"]
    assert frase("providencia") == "Su equipo está funcionando y conectado."
    assert frase("buin").startswith("Su equipo perdió la conexión hace")
    assert frase("vitacura").startswith("No tenemos señal de su equipo desde las")


def test_varias_y_ninguna_no_consultan_el_equipo(con, config):
    varias = consulta.consultar_tienda(con, config, "talca")
    assert varias["resultado"] == "varias"
    assert [opcion["nombre"] for opcion in varias["opciones"]] == ["Talca", "Talca Colín"]
    assert "estado" not in varias
    assert consulta.consultar_tienda(con, config, "temuco")["resultado"] == "ninguna"


def test_con_tienda_id_se_sale_de_la_duda(con, config):
    assert consulta.consultar_tienda(con, config, "talca", tienda_id="talca")["tienda"]["nombre"] == "Talca"
    assert consulta.consultar_tienda(con, config, "", tienda_id="Talca-Colin ")["tienda"]["nombre"] == "Talca Colín"


def test_un_tienda_id_inventado_cae_en_la_busqueda_por_texto(con, config):
    assert consulta.consultar_tienda(con, config, "recoleta", tienda_id="no-existe")["tienda"]["id"] == "recoleta"
    assert consulta.consultar_tienda(con, config, "", tienda_id="no-existe")["resultado"] == "ninguna"


def test_tienda_sin_caja(con, config):
    # Hoy las 71 tienen caja en la central; se le quita a una para probar el caso.
    con.execute("UPDATE tiendas SET unit_id = NULL, site_id = NULL WHERE id = 'san-vicente'")
    con.commit()
    respuesta = consulta.consultar_tienda(con, config, "san vicente")
    assert respuesta["estado"]["frase"] == "No tengo registrado un equipo en esa tienda."
    assert respuesta["caja"] is None


def test_si_la_central_no_responde_la_llamada_sigue(con, config):
    def caida(_request):
        raise httpx.ConnectTimeout("sin respuesta")
    con_http = dataclasses.replace(config, central_archivo="", central_token="token-de-prueba")
    respuesta = consulta.consultar_tienda(con, con_http, "recoleta", transporte=httpx.MockTransport(caida))
    assert respuesta["resultado"] == "una"
    assert respuesta["central_disponible"] is False
    assert respuesta["estado"]["frase"] == consulta.SIN_REVISAR
    assert respuesta["caja"] is None


def test_caja_asociada_que_la_central_no_conoce(con, config):
    vacia = httpx.MockTransport(lambda _request: httpx.Response(200, json={"units": []}))
    con_http = dataclasses.replace(config, central_archivo="", central_token="token-de-prueba")
    respuesta = consulta.consultar_tienda(con, con_http, "recoleta", transporte=vacia)
    assert respuesta["central_disponible"] is True
    assert respuesta["estado"]["frase"] == consulta.SIN_REVISAR


# ---- lo que recibe la asistente -------------------------------------------------------------------------------------------

def test_a_la_asistente_le_llegan_frases_y_nada_tecnico(con, config, unidades):
    import json
    for tienda in ("recoleta", "maipú", "la de nataniel", "providencia", "vicuña mackenna", "san vicente"):
        salida = consulta.para_la_asistente(consulta.consultar_tienda(con, config, tienda, ahora=AHORA))
        assert salida["resultado"] == "encontrada"
        texto = json.dumps(salida, ensure_ascii=False)
        for prohibido in ("unit_id", "sim-", "minipc", "rms", "dbm", "STREAMING", "FALLBACK", "regla", "site_id"):
            assert prohibido not in texto, (tienda, prohibido)


def test_a_la_asistente_varias_le_llegan_con_su_tienda_id(con, config):
    salida = consulta.para_la_asistente(consulta.consultar_tienda(con, config, "puente alto"))
    assert salida["resultado"] == "varias"
    assert salida["opciones"] == [{"tienda_id": "puente-alto", "nombre": "Puente Alto", "comuna": "Puente Alto"},
                                  {"tienda_id": "mall-plaza-tobalaba", "nombre": "Mall Plaza Tobalaba",
                                   "comuna": "Puente Alto"}]
    assert "tienda_id" in salida["indicacion"]


def test_a_la_asistente_la_senal_debil_y_lo_urgente(con, config):
    salida = consulta.para_la_asistente(consulta.consultar_tienda(con, config, "vitacura", ahora=AHORA))
    assert salida["urgente"] is True
    assert "senal_de_celular" not in salida  # sin latido: la señal es del último latido, no de ahora
    con.execute("UPDATE tiendas SET unit_id = NULL, site_id = NULL WHERE id = 'san-vicente'")
    con.commit()
    sin_caja = consulta.para_la_asistente(consulta.consultar_tienda(con, config, "san vicente"))
    assert "urgente" not in sin_caja
