"""Aviso a hrm por Telegram cuando llega un caso urgente. Sin configuración no hace nada."""

import logging

import httpx

from .config import Config

_log = logging.getLogger("uvicorn.error")

_PROBLEMA = {"sin_audio": "sin audio", "volumen": "volumen", "aviso_no_salio": "un aviso no salió", "musica": "música",
             "otro": "otro"}


def texto_de_caso(caso, base_url: str = "") -> str:
    tienda = caso["tienda_nombre"] or caso["tienda"] or "tienda sin identificar"
    lineas = [f"🔴 Soporte Audiocast: caso urgente en {tienda}"]
    if caso["problema"]:
        lineas.append(f"Problema: {_PROBLEMA.get(caso['problema'], caso['problema'])}")
    if caso["equipo_frase"]:
        lineas.append(f"Equipo: {caso['equipo_frase']}")
    if caso["resumen"]:
        lineas.append(caso["resumen"])
    if caso["nombre_contacto"]:
        lineas.append(f"Llamó: {caso['nombre_contacto']}")
    if base_url:
        lineas.append(f"{base_url}/casos/{caso['conversation_id']}")
    return "\n".join(lineas)


def enviar(config: Config, texto: str, *, transporte: httpx.BaseTransport | None = None) -> bool:
    if not (config.telegram_bot_token and config.telegram_chat_id):
        return False
    try:
        with httpx.Client(timeout=5, transport=transporte) as cliente:
            respuesta = cliente.post(f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage",
                                     json={"chat_id": config.telegram_chat_id, "text": texto[:4000],
                                           "disable_web_page_preview": True})
        respuesta.raise_for_status()
        return True
    except httpx.HTTPError as error:
        # Sin el mensaje de httpx: trae la URL, y la URL trae el token del bot.
        _log.warning("aviso por Telegram no enviado: %s", type(error).__name__)
        return False
