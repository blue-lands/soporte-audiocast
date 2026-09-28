import dataclasses
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app import central, db, directorio
from app.config import Config
from app.principal import crear_app

from ayudas import SECRETO, TOKEN_HERRAMIENTA

EJEMPLO = Path(__file__).resolve().parent.parent / "ejemplos" / "units-mixto.json"
USUARIO, SESION = "hrm", "sesion-abierta-en-la-central"


@pytest.fixture(autouse=True)
def sin_cache():
    central.olvidar_cache()
    yield
    central.olvidar_cache()


@pytest.fixture
def unidades() -> list[dict]:
    return json.loads(EJEMPLO.read_text(encoding="utf-8"))["units"]


@pytest.fixture
def config(tmp_path) -> Config:
    return Config(db_path=str(tmp_path / "soporte.db"), central_archivo=str(EJEMPLO),
                  herramienta_token=TOKEN_HERRAMIENTA, elevenlabs_webhook_secret=SECRETO)


@pytest.fixture
def con(config):
    db.inicializar(config.db_path)
    conexion = db.conectar(config.db_path)
    directorio.guardar(conexion, directorio.asociar(central.leer_cajas(config)))
    yield conexion
    conexion.close()


@pytest.fixture
def avisos_enviados() -> list[str]:
    return []


@pytest.fixture
def pedidos_a_la_central() -> list[httpx.Request]:
    return []


@pytest.fixture
def central_falsa(pedidos_a_la_central):
    """La central: conoce una sola sesión abierta, la de hrm."""
    def atender(request: httpx.Request) -> httpx.Response:
        pedidos_a_la_central.append(request)
        if request.url.path == "/api/me":
            if request.headers.get("cookie") == f"ac_session={SESION}":
                return httpx.Response(200, json={"user": USUARIO, "login": True})
            return httpx.Response(401, text="token requerido")
        return httpx.Response(404)
    return httpx.MockTransport(atender)


@pytest.fixture
def cliente(con, config, avisos_enviados, central_falsa):
    """Sin sesión en la central: es ElevenLabs o un visitante."""
    def enviar(_config, texto):
        avisos_enviados.append(texto)
        return True
    app = crear_app(config, enviar_aviso=enviar, transporte_central=central_falsa)
    with TestClient(app, follow_redirects=False) as c:
        yield c


@pytest.fixture
def panel(cliente):
    """Con la sesión de hrm abierta en la central."""
    cliente.cookies.set("ac_session", SESION)
    return cliente


@pytest.fixture
def sin_configurar(tmp_path):
    config = Config(db_path=str(tmp_path / "vacia.db"))
    with TestClient(crear_app(config), follow_redirects=False) as c:
        yield c


def con_http(config: Config) -> Config:
    return dataclasses.replace(config, central_archivo="", central_token="token-de-prueba")
