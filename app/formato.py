"""Cómo se muestran fechas, duraciones y datos de la ficha en el panel."""

import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ZONA = ZoneInfo("America/Santiago")
_MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")

PROBLEMAS = {"sin_audio": "Sin audio", "volumen": "Volumen", "aviso_no_salio": "Un aviso no salió", "musica": "Música",
             "otro": "Otro"}
CANALES = {"llamada": "Llamada", "whatsapp": "WhatsApp", "prueba": "Prueba web"}


def _local(segundos: int) -> datetime:
    return datetime.fromtimestamp(segundos, tz=timezone.utc).astimezone(ZONA)


def fecha_hora(segundos: int | None, ahora: datetime | None = None) -> str:
    """'hoy 10:40' · 'ayer 22:10' · '24 sep 09:15' · '3 dic 2025 18:00'."""
    if not segundos:
        return "—"
    momento, hoy = _local(segundos), (ahora or datetime.now(timezone.utc)).astimezone(ZONA)
    hora = f"{momento.hour}:{momento.minute:02d}"
    dias = (hoy.date() - momento.date()).days
    if dias == 0:
        return f"hoy {hora}"
    if dias == 1:
        return f"ayer {hora}"
    fecha = f"{momento.day} {_MESES[momento.month - 1]}"
    return f"{fecha} {hora}" if momento.year == hoy.year else f"{fecha} {momento.year} {hora}"


def hora(segundos: int | None) -> str:
    if not segundos:
        return "—"
    momento = _local(segundos)
    return f"{momento.hour}:{momento.minute:02d}"


def duracion(segundos: int | None) -> str:
    if segundos is None:
        return "—"
    minutos, resto = divmod(int(segundos), 60)
    return f"{minutos} min {resto:02d} s" if minutos else f"{resto} s"


def minuto(segundos: int | None) -> str:
    """Posición dentro de la llamada: '1:05'."""
    if segundos is None:
        return ""
    return f"{int(segundos) // 60}:{int(segundos) % 60:02d}"


def problema(valor: str | None) -> str:
    return PROBLEMAS.get(valor or "", "—")


def canal(valor: str | None) -> str:
    return CANALES.get(valor or "", valor or "—")


def numero_caso(valor: int | None) -> str:
    return f"N° {valor:04d}" if valor else ""


_WHATSAPP = {"enviado": "Enviado", "omitido": "No enviado", "error": "Error al enviar", "enviando": "Enviando…"}


def whatsapp(caso) -> str:
    """'Enviado 12:41' · 'No enviado: No llamó desde un celular.' · '—' si no se procesó."""
    estado = caso["whatsapp_estado"]
    if not estado:
        return "—"
    texto = _WHATSAPP.get(estado, estado)
    if estado == "enviado" and caso["whatsapp_momento"]:
        return f"{texto} {hora(caso['whatsapp_momento'])}"
    return f"{texto}: {caso['whatsapp_detalle']}" if caso["whatsapp_detalle"] else texto


def si_no(valor) -> str:
    return "—" if valor is None else "Sí" if valor else "No"


def turnos(transcripcion: str | None) -> list[dict]:
    try:
        lista = json.loads(transcripcion or "[]")
    except ValueError:
        return []
    return [turno for turno in lista if isinstance(turno, dict) and turno.get("mensaje")]


def json_legible(crudo: str | None) -> str:
    try:
        return json.dumps(json.loads(crudo), ensure_ascii=False, indent=2) if crudo else ""
    except ValueError:
        return crudo or ""
