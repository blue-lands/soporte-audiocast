"""WhatsApp a quien llamó: el número de su caso y que el equipo técnico lo va a llamar.

Sale del WhatsApp oficial de Audiocast (+56 2 2583 1900) por ElevenLabs, con la plantilla de Meta `caso_registrado`
(categoría Utilidad, idioma `es`). La tienda llamó por teléfono y no escribió: sin plantilla, Meta no deja escribir primero.
Si la persona responde, le contesta la misma asistente en ese chat.

Cuerpo de la plantilla; el orden de `valores_de_plantilla` es el de {{1}}…{{4}}:

    Hola {{1}}, le escribimos de Soporte Audiocast por su llamada de recién.
    Su caso N° {{2}} quedó registrado.
    Tienda: {{3}}
    Problema: {{4}}
    El equipo técnico lo va a llamar para revisarlo. Si necesita agregar algo, responda este mensaje.
"""

import logging
import re
import sqlite3

import httpx

from . import casos, formato
from .config import Config

_log = logging.getLogger("uvicorn.error")

URL = "https://api.elevenlabs.io/v1/convai/whatsapp/outbound-message"
_LARGO_MAXIMO = 60


def celular(telefono: str | None) -> str | None:
    """Celular chileno como lo pide WhatsApp (56912345678), o None si no lo es (fijo, número oculto, vacío)."""
    digitos = re.sub(r"\D", "", telefono or "")
    return digitos if len(digitos) == 11 and digitos.startswith("569") else None


def _limpio(texto: str | None) -> str:
    # Meta rechaza valores vacíos, con saltos de línea o con muchos espacios seguidos.
    texto = " ".join((texto or "").split())
    return texto if len(texto) <= _LARGO_MAXIMO else texto[:_LARGO_MAXIMO - 1].rstrip() + "…"


def valores_de_plantilla(caso) -> list[str]:
    """Nombre, N° de caso, tienda y problema. Lo que falta va con un reemplazo: Meta no acepta valores vacíos."""
    nombre = (caso["nombre_contacto"] or "").split()
    tienda = caso["tienda_nombre"] or caso["tienda"]
    if tienda and "tottus" not in tienda.lower().replace("ó", "o"):
        tienda = f"Tottus {tienda}"
    problema = caso["motivo"] or (formato.problema(caso["problema"]) if caso["problema"] else "")
    return [
        _limpio(nombre[0] if nombre else "") or "estimado/a",
        f"{caso['numero']:04d}",
        _limpio(tienda) or "por confirmar",
        _limpio(problema) or "por revisar",
    ]


def _por_que_no(config: Config, caso) -> str | None:
    """Por qué este caso no lleva WhatsApp, o None si lo lleva."""
    if not (config.elevenlabs_api_key and config.whatsapp_numero_id):
        return "El envío de WhatsApp no está configurado."
    if not casos.hablo_la_persona(dict(caso)):
        return "La persona cortó sin hablar."
    if caso["resuelto_en_llamada"]:
        return "El problema se resolvió en la llamada."
    if celular(caso["telefono"]) is None:
        return "No llamó desde un celular."
    return None


def enviar(config: Config, caso, *, transporte: httpx.BaseTransport | None = None) -> None:
    """Manda la plantilla. Si falla, levanta ErrorWhatsApp con un texto para el panel (nunca la clave)."""
    cuerpo = {
        "whatsapp_phone_number_id": config.whatsapp_numero_id,
        "whatsapp_user_id": celular(caso["telefono"]),
        "template_name": config.whatsapp_plantilla,
        "template_language_code": config.whatsapp_idioma,
        "template_params": [{"type": "body", "parameters": [{"type": "text", "text": valor}
                                                             for valor in valores_de_plantilla(caso)]}],
        "agent_id": caso["agent_id"],
    }
    try:
        with httpx.Client(timeout=20, transport=transporte) as cliente:
            respuesta = cliente.post(URL, json=cuerpo, headers={"xi-api-key": config.elevenlabs_api_key})
    except httpx.HTTPError as error:
        raise ErrorWhatsApp(f"No se pudo conectar con ElevenLabs ({type(error).__name__}).") from None
    if respuesta.status_code >= 400:
        raise ErrorWhatsApp(f"ElevenLabs respondió {respuesta.status_code}: {respuesta.text[:300]}")


class ErrorWhatsApp(Exception):
    pass


def procesar(config: Config, con: sqlite3.Connection, conversation_id: str, *,
             transporte: httpx.BaseTransport | None = None) -> str | None:
    """Manda el WhatsApp del caso si corresponde, una sola vez. Devuelve el estado final, o None si no aplica."""
    caso = casos.leer(con, conversation_id)
    if caso is None or caso["canal"] != "llamada":
        return None
    if not casos.marcar_whatsapp(con, conversation_id, "enviando", solo_si_estaba=""):
        return None  # ya se procesó: ElevenLabs reintentó el webhook
    motivo = _por_que_no(config, caso)
    if motivo:
        casos.marcar_whatsapp(con, conversation_id, "omitido", motivo)
        return "omitido"
    try:
        enviar(config, caso, transporte=transporte)
    except ErrorWhatsApp as error:
        _log.warning("WhatsApp del caso %s no enviado: %s", caso["numero"], error)
        casos.marcar_whatsapp(con, conversation_id, "error", str(error))
        return "error"
    casos.marcar_whatsapp(con, conversation_id, "enviado")
    return "enviado"


def reintentar(config: Config, con: sqlite3.Connection, numero: int, *,
               transporte: httpx.BaseTransport | None = None) -> str:
    """Vuelve a mandar el WhatsApp de un caso que falló. Uno ya enviado u omitido no se toca."""
    fila = con.execute("SELECT conversation_id, whatsapp_estado FROM casos WHERE numero = ?", (numero,)).fetchone()
    if fila is None:
        return "no existe"
    if fila["whatsapp_estado"] not in ("error", None):
        return f"no se reintenta: está {fila['whatsapp_estado']}"
    casos.marcar_whatsapp(con, fila["conversation_id"], None, None, solo_si_estaba=fila["whatsapp_estado"] or "")
    return procesar(config, con, fila["conversation_id"], transporte=transporte) or "no aplica: no es una llamada"
