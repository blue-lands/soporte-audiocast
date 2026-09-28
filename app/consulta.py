"""Lo que responde `consultar_tienda`: la tienda que nombró quien llama y cómo está su equipo, en frases listas."""

import sqlite3
from datetime import datetime

from . import central, directorio, estado
from .config import Config

SIN_REVISAR = "No pude revisar su equipo en este momento."


def consultar_tienda(con: sqlite3.Connection, config: Config, texto: str, *, tienda_id: str | None = None,
                     ahora: datetime | None = None, transporte=None) -> dict:
    """Devuelve siempre un dict con `resultado`: 'una', 'varias' o 'ninguna'. Nunca lanza por culpa de la central.

    `tienda_id` es para la segunda vuelta: la persona ya eligió una de las opciones. Sin él, "Talca" daría otra vez
    Talca y Talca Colín. Si el id no existe, se busca por el texto.
    """
    tiendas = directorio.todas(con)
    elegida = next((tienda for tienda in tiendas if tienda.id == (tienda_id or "").strip().lower()), None)
    busqueda = directorio.Busqueda("una", (elegida,)) if elegida else directorio.buscar(tiendas, texto)
    if busqueda.tipo == "ninguna":
        return {"resultado": "ninguna"}
    if busqueda.tipo == "varias":
        return {"resultado": "varias", "opciones": [tienda.como_dict() for tienda in busqueda.tiendas]}
    tienda = busqueda.tienda
    return {"resultado": "una", "tienda": tienda.como_dict(), **revisar_equipo(config, tienda, ahora=ahora,
                                                                                transporte=transporte)}


def revisar_equipo(config: Config, tienda: directorio.Tienda, *, ahora: datetime | None = None, transporte=None) -> dict:
    """`estado` es lo que dice la asistente; `caja` es el JSON crudo, para guardarlo en la ficha del caso (no se lee)."""
    if not tienda.unit_id:
        return {"central_disponible": True, "estado": estado.describir(None).como_dict(), "caja": None}
    try:
        cajas = central.leer_cajas(config, transporte=transporte)
    except central.CentralNoDisponible:
        return {"central_disponible": False, "estado": _sin_revisar(), "caja": None}
    caja = central.buscar_caja(cajas, tienda.unit_id, tienda.site_id)
    if caja is None:
        # La tienda tiene caja, pero la central no la conoce (recién reiniciada, o la caja nunca ha reportado).
        return {"central_disponible": True, "estado": _sin_revisar(), "caja": None}
    return {"central_disponible": True,
            "estado": estado.describir(caja, ahora, config.zona_horaria).como_dict(),
            "caja": caja}


def para_la_asistente(respuesta: dict) -> dict:
    """Lo que recibe el agente de ElevenLabs: frases e indicaciones. Ni la caja cruda ni ningún dato técnico."""
    if respuesta["resultado"] == "ninguna":
        return {"resultado": "ninguna",
                "indicacion": "No encontré esa tienda. Pregunte en qué comuna está y vuelva a consultar."}
    if respuesta["resultado"] == "varias":
        return {"resultado": "varias",
                "opciones": [{"tienda_id": o["id"], "nombre": o["nombre"], "comuna": o["comuna"]}
                             for o in respuesta["opciones"]],
                "indicacion": "Hay más de una tienda que calza. Pregunte cuál de estas es, nombrándolas, y vuelva a "
                              "consultar con el tienda_id de la que elija la persona."}
    tienda, est = respuesta["tienda"], respuesta["estado"]
    salida = {"resultado": "encontrada", "tienda_id": tienda["id"], "tienda": tienda["nombre"], "comuna": tienda["comuna"],
              "estado_del_equipo": est["frase"]}
    if est["urgente"] is not None:
        salida["urgente"] = est["urgente"]
    if est["volumen"]:
        salida["volumen"] = est["volumen"]
    if est["senal"]:
        salida["senal_de_celular"] = est["senal"]
    salida["indicacion"] = ("Diga el estado del equipo con esas palabras. El volumen y la señal, solo si la persona "
                            "pregunta o si tienen que ver con su problema.")
    return salida


def _sin_revisar() -> dict:
    return estado.Estado(0, SIN_REVISAR, None).como_dict()
