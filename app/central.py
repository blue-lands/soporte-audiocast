"""Lectura de la central de Audiocast. SOLO `GET /api/units` (las cajas) y `GET /api/me` (quién tiene la sesión).

La central no tiene rol de solo lectura: el token de esta app es de operador. Por eso aquí no hay, ni debe haber, ningún
POST (comandos a cajas, avisos, silenciar alertas). Ver `soporte-audiocast-central-y-tiendas.md` §1 y §2.

El panel no tiene entrada propia: quien entró a la central ya entró al soporte. Comparten dominio, así que la galleta de
sesión de la central llega también aquí; esta app no la entiende, se la muestra a la central y le pregunta de quién es.
"""

import hashlib
import json
import threading
import time
from pathlib import Path

import httpx

from .config import Config


class CentralNoDisponible(Exception):
    """La central no respondió a tiempo, respondió mal o no está configurada. La llamada sigue sin el estado del equipo."""


_cache_lock = threading.Lock()
_cache: dict[tuple, tuple[float, dict[str, dict]]] = {}


def leer_cajas(config: Config, *, transporte: httpx.BaseTransport | None = None, usar_cache: bool = True) -> dict[str, dict]:
    """Todas las cajas que entrega la central, por `unit_id`, sin las ocultas."""
    clave = (config.central_archivo, config.central_url, config.central_token)
    if usar_cache and transporte is None:
        with _cache_lock:
            guardado = _cache.get(clave)
        if guardado and time.monotonic() - guardado[0] < config.central_cache_s:
            return guardado[1]
    crudo = _leer_archivo(config.central_archivo) if config.central_archivo else _pedir(config, transporte)
    cajas = _ordenar(crudo, config.cajas_ocultas)
    if usar_cache and transporte is None:
        with _cache_lock:
            _cache[clave] = (time.monotonic(), cajas)
    return cajas


def olvidar_cache() -> None:
    with _cache_lock:
        _cache.clear()
        _sesiones.clear()


# Cuánto se le cree a una sesión ya comprobada sin volver a preguntar. Quien sale de la central sigue viendo el
# soporte, a lo más, este rato.
SESION_CACHE_S = 30.0
_sesiones: dict[str, tuple[float, str]] = {}


def usuario_de_sesion(config: Config, galleta: str | None, *, transporte: httpx.BaseTransport | None = None) -> str | None:
    """El usuario de la central dueño de esa galleta de sesión, o None si no vale. Siempre contra la central de verdad,
    aunque las cajas se lean de un archivo de ejemplo."""
    if not galleta or len(galleta) > 512 or any(c in galleta for c in ";, \t\r\n"):
        return None
    huella = hashlib.sha256(galleta.encode()).hexdigest()
    with _cache_lock:
        guardada = _sesiones.get(huella)
    if guardada and time.monotonic() - guardada[0] < SESION_CACHE_S:
        return guardada[1]
    try:
        with httpx.Client(timeout=config.central_timeout_s, transport=transporte) as cliente:
            respuesta = cliente.get(config.central_url + "/api/me",
                                    headers={"Cookie": f"{config.central_galleta}={galleta}"})
        if respuesta.status_code in (401, 403):
            return None
        respuesta.raise_for_status()
        usuario = respuesta.json().get("user")
    except (httpx.HTTPError, ValueError, AttributeError) as error:
        raise CentralNoDisponible(type(error).__name__) from error
    if not isinstance(usuario, str) or not usuario:
        return None
    with _cache_lock:
        if len(_sesiones) > 200:
            _sesiones.clear()
        _sesiones[huella] = (time.monotonic(), usuario)
    return usuario


def buscar_caja(cajas: dict[str, dict], unit_id: str | None, site_id: str | None = None) -> dict | None:
    """La caja de una tienda: por `unit_id` y, si cambió, por `site_id` (estable entre reinicios del simulador)."""
    if unit_id and unit_id in cajas:
        return cajas[unit_id]
    if site_id:
        for caja in cajas.values():
            if caja.get("site_id") == site_id:
                return caja
    return None


def _pedir(config: Config, transporte: httpx.BaseTransport | None):
    if not config.central_token:
        raise CentralNoDisponible("falta CENTRAL_TOKEN")
    try:
        with httpx.Client(timeout=config.central_timeout_s, transport=transporte) as cliente:
            respuesta = cliente.get(config.central_url + "/api/units",
                                    headers={"Authorization": f"Bearer {config.central_token}"})
        respuesta.raise_for_status()
        return respuesta.json()
    except (httpx.HTTPError, ValueError) as error:
        # Sin el mensaje de httpx: puede traer la URL completa y no aporta a quien atiende.
        raise CentralNoDisponible(type(error).__name__) from error


def _leer_archivo(ruta: str):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise CentralNoDisponible(f"archivo de ejemplo: {type(error).__name__}") from error


def _ordenar(crudo, ocultas: tuple[str, ...]) -> dict[str, dict]:
    # La central responde {"generated_at": …, "units": […]}; se acepta también la lista suelta.
    lista = crudo.get("units") if isinstance(crudo, dict) else crudo
    if not isinstance(lista, list):
        raise CentralNoDisponible("respuesta sin lista de cajas")
    cajas = {}
    for caja in lista:
        if not isinstance(caja, dict):
            continue
        unit_id = caja.get("unit_id")
        if isinstance(unit_id, str) and unit_id and unit_id not in ocultas:
            cajas[unit_id] = caja
    return cajas
