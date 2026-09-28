"""Una conversación de ElevenLabs como llega al webhook de fin (campos de la guía §7.2) y cómo firmarla."""

import json
import time

from app import elevenlabs

SECRETO = "wsec_de_prueba"
TOKEN_HERRAMIENTA = "token-de-la-herramienta"


def conversacion(conversation_id: str = "conv_0001", *, ficha: dict | None = None, telefono: str | None = "+56911112222",
                 transcript: list | None = None, inicio: int | None = None) -> dict:
    valores = {"tienda": "Recoleta", "nombre_contacto": "Marcela Soto", "problema": "sin_audio",
               "desde_cuando": "desde las diez de la mañana", "motivo": "Tienda sin música",
               "resumen": "La tienda Recoleta está sin música desde la mañana. El equipo no da señal.",
               "urgencia": True, "resuelto_en_llamada": False, "requiere_tecnico": True}
    valores.update(ficha or {})
    metadata = {"start_time_unix_secs": inicio or int(time.time()) - 120, "call_duration_secs": 95,
                "cost": 412, "termination_reason": "end_call tool was called"}
    if telefono:
        metadata["phone_call"] = {"direction": "inbound", "external_number": telefono, "agent_number": "+56233330000",
                                  "type": "sip_trunk"}
    return {
        "type": "post_call_transcription",
        "event_timestamp": int(time.time()),
        "data": {
            "agent_id": "agent_de_prueba",
            "conversation_id": conversation_id,
            "status": "done",
            "transcript": transcript if transcript is not None else [
                {"role": "agent", "message": "Aló, soporte Audiocast, ¿en qué le puedo ayudar?", "time_in_call_secs": 0},
                {"role": "user", "message": "Hola, llamo del Tottus de Recoleta, estamos sin música.",
                 "time_in_call_secs": 4},
                {"role": "agent", "message": None, "time_in_call_secs": 9,
                 "tool_calls": [{"tool_name": "consultar_tienda"}]},
                {"role": "agent", "message": "No tenemos señal de su equipo desde las 9:40.", "time_in_call_secs": 12},
            ],
            "metadata": metadata,
            "analysis": {
                "call_successful": "success",
                "transcript_summary": "Resumen de ElevenLabs.",
                "data_collection_results": {nombre: {"data_collection_id": nombre, "value": valor}
                                            for nombre, valor in valores.items()},
            },
        },
    }


def firmado(evento: dict, secreto: str = SECRETO, momento: int | None = None) -> tuple[bytes, dict]:
    cuerpo = json.dumps(evento, ensure_ascii=False).encode()
    momento = int(time.time()) if momento is None else momento
    return cuerpo, {"ElevenLabs-Signature": elevenlabs.firmar(cuerpo, secreto, momento),
                    "Content-Type": "application/json"}
