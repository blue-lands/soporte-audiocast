"""Webhook de fin de conversación de ElevenLabs Agents: firma y traducción de la conversación a un caso.

Firma, según el SDK oficial: header `ElevenLabs-Signature` = "t=<segundos>,v0=<64 hex>", donde hex = HMAC-SHA256 con el
secreto del webhook de "<t>.<cuerpo crudo>". Se rechazan timestamps de más de 30 minutos. Ver la guía §7.2.
"""

import hashlib
import hmac
import json
import re
import time

# Solo post_call_transcription trae la conversación; post_call_audio y call_initiation_failure se ignoran.
EVENTO_GUARDADO = "post_call_transcription"
PROBLEMAS = ("sin_audio", "volumen", "aviso_no_salio", "musica", "otro")

_VENTANA_S = 30 * 60
_EXITOSA = {"success": 1, "failure": 0}
_SI = {"true", "si", "sí", "yes", "1", "verdadero"}
_NO = {"false", "no", "0", "falso"}
_LARGO_MAXIMO = 2000


def firmar(cuerpo: bytes, secreto: str, momento_s: int) -> str:
    """Arma el header igual que ElevenLabs. Lo usan las pruebas."""
    digest = hmac.new(secreto.encode(), f"{momento_s}.".encode() + cuerpo, hashlib.sha256).hexdigest()
    return f"t={momento_s},v0={digest}"


def firma_valida(cuerpo: bytes, secreto: str, header: str | None, ahora_s: int | None = None) -> bool:
    if not secreto or not header:
        return False
    partes = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    momento, recibida = partes.get("t", "").strip(), partes.get("v0", "").strip()
    if not momento.isdigit() or not re.fullmatch(r"[0-9a-f]{64}", recibida):
        return False
    if ahora_s is None:
        ahora_s = int(time.time())
    if abs(ahora_s - int(momento)) > _VENTANA_S:
        return False
    esperada = firmar(cuerpo, secreto, int(momento)).rsplit("v0=", 1)[1]
    return hmac.compare_digest(esperada, recibida)


def caso_de_conversacion(data: dict, ahora_s: int | None = None) -> dict:
    """Las columnas de `casos` que salen de la conversación. `tienda_id` lo resuelve app/casos.py."""
    ahora_s = int(time.time()) if ahora_s is None else ahora_s
    metadata = data.get("metadata") or {}
    analisis = data.get("analysis") or {}
    telefono = metadata.get("phone_call") or {}
    whatsapp = metadata.get("whatsapp") or {}
    if telefono:
        canal, numero = "llamada", _numero(telefono.get("external_number"))
    elif whatsapp:
        canal, numero = "whatsapp", _numero(whatsapp.get("whatsapp_user_id"))
    else:
        canal, numero = "prueba", None  # desde el navegador de ElevenLabs: en el demo sin número, son los casos
    ficha = {
        nombre: resultado.get("value")
        for nombre, resultado in (analisis.get("data_collection_results") or {}).items()
        if isinstance(resultado, dict)
    }
    problema = _texto(ficha.get("problema"))
    costo = {k: metadata[k] for k in ("cost", "cost_fiat") if metadata.get(k) is not None}
    inicio, duracion = metadata.get("start_time_unix_secs"), metadata.get("call_duration_secs")
    return {
        "conversation_id": str(data["conversation_id"]),
        "agent_id": _texto(data.get("agent_id")),
        "canal": canal,
        "telefono": numero,
        "inicio": int(inicio) if _es_numero(inicio) and inicio > 0 else ahora_s,
        "duracion_s": int(duracion) if _es_numero(duracion) else None,
        "tienda": _texto(ficha.get("tienda")),
        "nombre_contacto": _texto(ficha.get("nombre_contacto")),
        # Un valor fuera de la lista no se pierde: queda como 'otro' y el motivo y el resumen dicen qué fue.
        "problema": (problema if problema in PROBLEMAS else "otro") if problema else None,
        "desde_cuando": _texto(ficha.get("desde_cuando")),
        "motivo": _texto(ficha.get("motivo")),
        "resumen": _texto(ficha.get("resumen")) or _texto(analisis.get("transcript_summary")),
        "urgencia": _si_o_no(ficha.get("urgencia")),
        "resuelto_en_llamada": _si_o_no(ficha.get("resuelto_en_llamada")),
        "requiere_tecnico": _si_o_no(ficha.get("requiere_tecnico")),
        "exitosa": _EXITOSA.get(analisis.get("call_successful")),
        "motivo_corte": _texto(metadata.get("termination_reason")),
        "transcripcion": json.dumps(_turnos(data.get("transcript")), ensure_ascii=False),
        "costo": json.dumps(costo) if costo else None,
        "recibido": ahora_s,
    }


def _turnos(transcript) -> list[dict]:
    turnos = []
    for turno in transcript or []:
        if not isinstance(turno, dict):
            continue
        # Los turnos en que la asistente solo usó una herramienta vienen sin mensaje.
        mensaje = " ".join(str(turno.get("message") or "").split())
        if mensaje:
            segundo = turno.get("time_in_call_secs")
            turnos.append({"rol": "asistente" if turno.get("role") == "agent" else "persona", "mensaje": mensaje,
                           "segundo": int(segundo) if _es_numero(segundo) else None})
    return turnos


def _numero(valor) -> str | None:
    """E.164 con +. WhatsApp entrega el número sin + ("56992406777")."""
    valor = str(valor or "").strip()
    if re.fullmatch(r"\d{8,15}", valor):
        return "+" + valor
    return valor or None


def _texto(valor) -> str | None:
    if valor is None or isinstance(valor, (dict, list)):
        return None
    texto = " ".join(str(valor).split())[:_LARGO_MAXIMO]
    # El analizador a veces escribe que no supo en vez de dejar el campo vacío.
    return None if texto.lower() in ("", "none", "null", "n/a", "desconocido", "no especificado") else texto


def _si_o_no(valor) -> int | None:
    if isinstance(valor, bool):
        return int(valor)
    texto = str(valor or "").strip().lower()
    return 1 if texto in _SI else 0 if texto in _NO else None


def _es_numero(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)
