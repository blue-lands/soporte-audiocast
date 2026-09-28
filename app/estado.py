"""Traduce el estado de una caja a frases que la asistente puede decir tal cual.

Las reglas y su orden son los de `soporte-audiocast-central-y-tiendas.md` §3: manda la primera que calza. La asistente
recibe frases, nunca campos: aquí no sale ningún `unit_id`, versión, dBFS, dBm ni nombre de estado en inglés.
Si un campo falta, no se menciona.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Norma de la flota.
VOLUMEN_MPV = 70
VOLUMEN_HW = 80
SENAL_DEBIL_DBM = -105
SENAL_DEBIL_PCT = 30  # equivale a -105 dBm en la escala de la central
SILENCIO_SOSTENIDO = 3  # latidos seguidos
FALLBACK_URGENTE_S = 15 * 60


@dataclass(frozen=True)
class Estado:
    regla: int  # número de fila de la tabla de §3; sirve para pruebas y para el panel
    frase: str
    urgente: bool | None  # None: no aplica (sin equipo o estado desconocido)
    volumen: str | None = None  # solo si el volumen se aleja de la norma
    senal: str | None = None  # solo si la señal de celular es débil

    def como_dict(self) -> dict:
        return {"regla": self.regla, "frase": self.frase, "urgente": self.urgente,
                "volumen": self.volumen, "senal": self.senal}


def describir(caja: dict | None, ahora: datetime | None = None, zona: str = "America/Santiago") -> Estado:
    if not caja:
        return Estado(1, "No tengo registrado un equipo en esa tienda.", None)
    ahora = ahora or datetime.now(timezone.utc)
    tz = ZoneInfo(zona)
    estado = str(caja.get("state") or "").upper()
    volumen, senal = _volumen(caja), _senal(caja)

    if caja.get("offline") is True:
        desde = _desde_ultimo_latido(caja, ahora)
        cuando = f" {_desde_cuando(desde, ahora, tz)}" if desde else ""
        # Sin volumen ni señal: son del último latido, no de ahora.
        return Estado(2, f"No tenemos señal de su equipo{cuando}. Puede estar apagado o sin conexión.", True)
    if estado == "PAUSED":
        return Estado(3, "Su equipo todavía no está activado.", False)
    if estado == "NO_AUDIO_DEVICE":
        return Estado(4, "Su equipo está encendido, pero no detecta la salida de audio. Hay que revisarlo.", True,
                      senal=senal)
    if estado == "STARTING":
        return Estado(5, "Su equipo se está reiniciando; debería volver a sonar en un minuto.", False, senal=senal)
    if _numero(caja.get("silent_streak"), 0) >= SILENCIO_SOSTENIDO:
        return Estado(6, "Su equipo está encendido, pero registra silencio.", True, volumen, senal)
    if estado == "FALLBACK":
        if caja.get("mode") == "local_first":
            return Estado(7, "Su equipo está funcionando normal.", False, volumen, senal)
        if caja.get("forced_fallback") is True:
            return Estado(8, "Su equipo está tocando música local por indicación del equipo técnico.", False,
                          volumen, senal)
        segundos = _segundos_en_fallback(caja, ahora)
        hace = f" {_hace(segundos)}" if segundos is not None else ""
        return Estado(9, f"Su equipo perdió la conexión{hace} y está tocando música de respaldo. "
                         "Los avisos nuevos pueden no llegar.",
                      segundos is not None and segundos > FALLBACK_URGENTE_S, volumen, senal)
    if estado in ("STREAMING", "STREAM_SUSPECT"):
        return Estado(10, "Su equipo está funcionando y conectado.", False, volumen, senal)
    return Estado(11, "Veo su equipo, pero no puedo confirmar su estado.", None)


# ---- datos extra ------------------------------------------------------------------------------------------------------

def _volumen(caja: dict) -> str | None:
    volumen = caja.get("volume")
    if not isinstance(volumen, dict):
        return None
    mpv, hw = _numero(volumen.get("mpv_pct")), _numero(volumen.get("hw_pct"))
    distinto = ((mpv is not None and mpv != VOLUMEN_MPV) or (hw is not None and hw != VOLUMEN_HW)
                or volumen.get("hw_on") is False)
    return "El volumen del equipo está distinto al normal." if distinto else None


def _senal(caja: dict) -> str | None:
    red = caja.get("net")
    lte = red.get("lte") if isinstance(red, dict) else None
    if not isinstance(lte, dict):
        return None
    dbm, pct = _numero(lte.get("rsrp_dbm")), _numero(lte.get("quality_pct"))
    debil = dbm < SENAL_DEBIL_DBM if dbm is not None else (pct is not None and pct < SENAL_DEBIL_PCT)
    return "La señal de celular en su tienda es débil." if debil else None


# ---- tiempos ----------------------------------------------------------------------------------------------------------

def _desde_ultimo_latido(caja: dict, ahora: datetime) -> datetime | None:
    segundos = _numero(caja.get("seconds_since"))
    if segundos is not None and segundos >= 0:
        return ahora - timedelta(seconds=segundos)
    return _fecha(caja.get("ts"))


def _segundos_en_fallback(caja: dict, ahora: datetime) -> float | None:
    segundos = _numero(caja.get("time_in_fallback_s"))
    if segundos is not None and segundos > 0:
        return segundos
    desde = _fecha(caja.get("state_since"))
    if desde and desde <= ahora:
        return (ahora - desde).total_seconds()
    return None


def _desde_cuando(desde: datetime, ahora: datetime, tz: ZoneInfo) -> str:
    """'desde las 10:40, hace 25 minutos' · 'desde ayer a las 22:10' · 'desde hace 3 días'."""
    local, hoy = desde.astimezone(tz), ahora.astimezone(tz).date()
    dias = (hoy - local.date()).days
    # Pasada la medianoche, lo de hace 25 minutos no es "ayer".
    if dias <= 0 or ahora - desde < timedelta(hours=12):
        return f"desde {_hora(local)}, {_hace((ahora - desde).total_seconds())}"
    if dias == 1:
        return f"desde ayer a {_hora(local)}"
    return f"desde hace {dias} días"


def _hora(momento: datetime) -> str:
    articulo = "la" if momento.hour == 1 else "las"
    return f"{articulo} {momento.hour}:{momento.minute:02d}"


def _hace(segundos: float) -> str:
    minutos = int(segundos // 60)
    if minutos < 1:
        return "hace menos de un minuto"
    if minutos < 60:
        return f"hace {_cantidad(minutos, 'minuto')}"
    horas, resto = divmod(minutos, 60)
    if horas < 24:
        return f"hace {_cantidad(horas, 'hora')}" + (f" y {_cantidad(resto, 'minuto')}" if resto else "")
    return f"hace {_cantidad(horas // 24, 'día')}"


def _cantidad(n: int, unidad: str) -> str:
    return f"{n} {unidad}" if n == 1 else f"{n} {unidad}s"


def _fecha(valor) -> datetime | None:
    if not isinstance(valor, str):
        return None
    try:
        fecha = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return None
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def _numero(valor, por_defecto=None):
    # bool es subclase de int: True no es un número aquí.
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return por_defecto
    return valor
