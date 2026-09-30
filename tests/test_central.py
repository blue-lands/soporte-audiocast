import dataclasses
import json

import httpx
import pytest

from app import central
from app.config import Config

CONFIG = Config(db_path=":memory:", central_url="http://central.prueba", central_token="token-de-prueba")
UNIDADES = [{"unit_id": "sim-07-e37e0c", "site_id": "recoleta-07", "state": "STREAMING"},
            {"unit_id": "minipc-lab-01", "state": "FALLBACK", "mode": "local_first"},
            {"unit_id": "nataniel-cox-01", "state": "STREAMING"}]


def central_falsa(respuesta, vistos: list | None = None) -> httpx.MockTransport:
    def atender(request: httpx.Request) -> httpx.Response:
        if vistos is not None:
            vistos.append(request)
        return respuesta(request) if callable(respuesta) else respuesta
    return httpx.MockTransport(atender)


def test_pide_con_get_y_bearer():
    vistos = []
    transporte = central_falsa(httpx.Response(200, json={"generated_at": 1.0, "units": UNIDADES}), vistos)
    cajas = central.leer_cajas(CONFIG, transporte=transporte)
    assert [(r.method, str(r.url)) for r in vistos] == [("GET", "http://central.prueba/api/units")]
    assert vistos[0].headers["authorization"] == "Bearer token-de-prueba"
    assert cajas["sim-07-e37e0c"]["site_id"] == "recoleta-07"


def test_acepta_la_lista_suelta():
    cajas = central.leer_cajas(CONFIG, transporte=central_falsa(httpx.Response(200, json=UNIDADES)))
    assert set(cajas) == {"sim-07-e37e0c", "minipc-lab-01", "nataniel-cox-01"}


def test_una_caja_oculta_no_existe_para_la_app():
    # Desde 2026-09-30 no se oculta ninguna por defecto (hrm: la asistente puede mencionar Nataniel Cox); el
    # mecanismo queda por si hace falta (SOPORTE_CAJAS_OCULTAS).
    con_oculta = dataclasses.replace(CONFIG, cajas_ocultas=("nataniel-cox-01",))
    cajas = central.leer_cajas(con_oculta, transporte=central_falsa(httpx.Response(200, json={"units": UNIDADES})))
    assert "nataniel-cox-01" not in cajas
    assert central.buscar_caja(cajas, "nataniel-cox-01") is None


def lenta(_request):
    raise httpx.ReadTimeout("la central no respondió")


def caida(_request):
    raise httpx.ConnectError("conexión rechazada")


@pytest.mark.parametrize("respuesta", [
    httpx.Response(401, json={"error": "token"}),
    httpx.Response(500, text="error"),
    httpx.Response(200, text="<html>no es json</html>"),
    httpx.Response(200, json={"units": "no es lista"}),
    httpx.Response(200, json={"otra": "cosa"}),
    lenta,
    caida,
])
def test_si_la_central_falla_avisa_con_una_sola_excepcion(respuesta):
    with pytest.raises(central.CentralNoDisponible):
        central.leer_cajas(CONFIG, transporte=central_falsa(respuesta))


def test_el_error_no_lleva_el_token():
    with pytest.raises(central.CentralNoDisponible) as error:
        central.leer_cajas(CONFIG, transporte=central_falsa(httpx.Response(401)))
    assert "token-de-prueba" not in str(error.value)


def test_sin_token_no_llama_a_la_central():
    vistos = []
    sin_token = dataclasses.replace(CONFIG, central_token="")
    with pytest.raises(central.CentralNoDisponible):
        central.leer_cajas(sin_token, transporte=central_falsa(httpx.Response(200, json=UNIDADES), vistos))
    assert vistos == []


def test_ignora_entradas_sin_unit_id():
    revueltas = [*UNIDADES, {"state": "STREAMING"}, "texto", None, {"unit_id": 7}]
    cajas = central.leer_cajas(CONFIG, transporte=central_falsa(httpx.Response(200, json=revueltas)))
    assert set(cajas) == {"sim-07-e37e0c", "minipc-lab-01", "nataniel-cox-01"}


def test_busca_por_site_id_si_cambio_el_unit_id():
    cajas = {"sim-07-nuevo": {"unit_id": "sim-07-nuevo", "site_id": "recoleta-07"}}
    assert central.buscar_caja(cajas, "sim-07-e37e0c", "recoleta-07")["unit_id"] == "sim-07-nuevo"
    assert central.buscar_caja(cajas, "sim-07-e37e0c", None) is None


def test_archivo_de_ejemplo_y_cache(tmp_path):
    archivo = tmp_path / "units.json"
    archivo.write_text(json.dumps({"units": UNIDADES}), encoding="utf-8")
    config = Config(db_path=":memory:", central_archivo=str(archivo))
    assert set(central.leer_cajas(config)) == {"sim-07-e37e0c", "minipc-lab-01", "nataniel-cox-01"}
    archivo.write_text(json.dumps({"units": []}), encoding="utf-8")
    assert len(central.leer_cajas(config)) == 3  # 10 s de caché
    assert central.leer_cajas(config, usar_cache=False) == {}


def test_archivo_que_no_existe(tmp_path):
    with pytest.raises(central.CentralNoDisponible):
        central.leer_cajas(Config(db_path=":memory:", central_archivo=str(tmp_path / "no-esta.json")))


def test_de_quien_es_la_sesion():
    def atender(request):
        assert (request.method, request.url.path) == ("GET", "/api/me")
        if request.headers.get("cookie") == "ac_session=buena":
            return httpx.Response(200, json={"user": "hrm", "login": True})
        return httpx.Response(401)
    transporte = httpx.MockTransport(atender)
    assert central.usuario_de_sesion(CONFIG, "buena", transporte=transporte) == "hrm"
    assert central.usuario_de_sesion(CONFIG, "mala", transporte=transporte) is None
    assert central.usuario_de_sesion(CONFIG, None, transporte=transporte) is None
    # No hace falta el token de operador: la sesión se comprueba aunque las cajas se lean de un archivo.
    sin_token = dataclasses.replace(CONFIG, central_token="", central_archivo="/no/importa.json")
    central.olvidar_cache()
    assert central.usuario_de_sesion(sin_token, "buena", transporte=transporte) == "hrm"


@pytest.mark.parametrize("respuesta", [httpx.Response(500), httpx.Response(200, text="no es json"),
                                       httpx.Response(200, json=["lista"])])
def test_si_la_central_falla_al_comprobar_la_sesion_avisa(respuesta):
    with pytest.raises(central.CentralNoDisponible):
        central.usuario_de_sesion(CONFIG, "buena", transporte=central_falsa(respuesta))


def test_el_modulo_no_sabe_hacer_post():
    """La central no tiene rol de solo lectura: el límite lo pone esta app."""
    import inspect
    codigo = inspect.getsource(central)
    assert ".post(" not in codigo and ".put(" not in codigo and ".delete(" not in codigo and ".request(" not in codigo
