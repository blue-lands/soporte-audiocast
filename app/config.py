"""Configuración leída del entorno. El servicio de systemd la carga desde /var/www/soporte-audiocast/.env."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    db_path: str
    # Central de Audiocast (app/central.py). Solo se le hace GET /api/units.
    central_url: str = "http://127.0.0.1:9000"
    central_token: str = ""
    # Mientras no exista el token de operador `soporte`: un JSON con la forma de /api/units que reemplaza a la central.
    # Si tiene valor, manda sobre central_url (es para desarrollo; en producción va vacío).
    central_archivo: str = ""
    central_timeout_s: float = 2.0
    central_cache_s: float = 10.0
    # Cajas que la app no ve nunca, aunque la central las entregue (la piloto).
    cajas_ocultas: tuple[str, ...] = ("nataniel-cox-01",)
    zona_horaria: str = "America/Santiago"
    # Panel.
    hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "testserver")
    # Dónde se publica dentro del dominio: "/soporte" en central.mediaflow.cl/soporte; "" si tiene dominio propio.
    prefijo: str = ""
    # El panel no tiene entrada propia: vale la sesión de la central. Nombre de su galleta y adónde mandar a quien no
    # tiene sesión (la central muestra su propia entrada).
    central_galleta: str = "ac_session"
    central_panel: str = "/"
    # Lo que manda ElevenLabs en `X-Soporte-Token` al usar la herramienta consultar_tienda. Vacío: la herramienta responde 503.
    herramienta_token: str = ""
    # Secreto HMAC del webhook de fin de conversación (lo entrega ElevenLabs al crear el webhook). Vacío: responde 503.
    elevenlabs_webhook_secret: str = ""
    # WhatsApp a quien llamó, con el número de su caso (app/whatsapp.py). Sale del WhatsApp oficial de Audiocast por
    # ElevenLabs con una plantilla aprobada por Meta. Sin clave o sin número no se envía nada.
    elevenlabs_api_key: str = ""
    whatsapp_numero_id: str = ""     # phone_number_id de Meta del número que envía
    whatsapp_plantilla: str = "caso_registrado"
    whatsapp_idioma: str = "es"
    # Aviso a hrm cuando llega un caso urgente. Sin token o sin chat no se envía nada.
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    base_url: str = ""  # para el enlace al caso en el aviso; vacío: el aviso va sin enlace


def _lista(nombre: str, por_defecto: str) -> tuple[str, ...]:
    return tuple(parte.strip() for parte in os.environ.get(nombre, por_defecto).split(",") if parte.strip())


def _prefijo(valor: str) -> str:
    """'soporte/', '/soporte' y '/soporte/' son '/soporte'; '' y '/' son ''."""
    valor = valor.strip().strip("/")
    return f"/{valor}" if valor else ""


def cargar() -> Config:
    return Config(
        prefijo=_prefijo(os.environ.get("SOPORTE_PREFIJO", "")),
        db_path=os.environ.get("SOPORTE_DB", "/var/lib/soporte-audiocast/soporte.db"),
        central_url=os.environ.get("CENTRAL_URL", "http://127.0.0.1:9000").rstrip("/"),
        central_token=os.environ.get("CENTRAL_TOKEN", "").strip(),
        central_archivo=os.environ.get("CENTRAL_ARCHIVO", "").strip(),
        central_timeout_s=float(os.environ.get("CENTRAL_TIMEOUT_S", "2")),
        central_cache_s=float(os.environ.get("CENTRAL_CACHE_S", "10")),
        cajas_ocultas=_lista("SOPORTE_CAJAS_OCULTAS", "nataniel-cox-01"),
        zona_horaria=os.environ.get("SOPORTE_ZONA_HORARIA", "America/Santiago"),
        hosts=_lista("SOPORTE_HOSTS", "127.0.0.1,localhost"),
        central_galleta=os.environ.get("CENTRAL_GALLETA", "ac_session").strip(),
        central_panel=os.environ.get("CENTRAL_PANEL", "/").strip() or "/",
        herramienta_token=os.environ.get("SOPORTE_HERRAMIENTA_TOKEN", "").strip(),
        elevenlabs_webhook_secret=os.environ.get("ELEVENLABS_WEBHOOK_SECRET", "").strip(),
        elevenlabs_api_key=os.environ.get("ELEVENLABS_API_KEY", "").strip(),
        whatsapp_numero_id=os.environ.get("WHATSAPP_NUMERO_ID", "").strip(),
        whatsapp_plantilla=os.environ.get("WHATSAPP_PLANTILLA", "caso_registrado").strip(),
        whatsapp_idioma=os.environ.get("WHATSAPP_IDIOMA", "es").strip(),
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", "").strip(),
        base_url=os.environ.get("SOPORTE_BASE_URL", "").strip().rstrip("/"),
    )
