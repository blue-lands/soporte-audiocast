"""Consultas de la asistente y casos: lo que el panel guarda y muestra."""

import json
import sqlite3
import time

from . import directorio
from .db import transaccion

LIMITE_PAGINA = 50
_COLUMNAS = ("conversation_id", "agent_id", "canal", "telefono", "inicio", "duracion_s", "tienda_id", "tienda",
             "nombre_contacto", "problema", "desde_cuando", "motivo", "resumen", "urgencia", "resuelto_en_llamada",
             "requiere_tecnico", "exitosa", "motivo_corte", "transcripcion", "costo", "recibido")


# ---- consultas ------------------------------------------------------------------------------------------------------------

def anotar_consulta(con: sqlite3.Connection, conversation_id: str | None, dicho: str, respuesta: dict,
                    para_la_asistente: dict, momento: int | None = None) -> None:
    estado = respuesta.get("estado") or {}
    urgente = estado.get("urgente")
    con.execute(
        "INSERT INTO consultas (conversation_id, momento, dicho, resultado, tienda_id, frase, urgente, respuesta, caja) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (conversation_id or None, int(time.time()) if momento is None else momento, dicho[:500], respuesta["resultado"],
         (respuesta.get("tienda") or {}).get("id"), estado.get("frase"), None if urgente is None else int(urgente),
         json.dumps(para_la_asistente, ensure_ascii=False),
         json.dumps(respuesta["caja"], ensure_ascii=False) if respuesta.get("caja") else None))


def consultas_de(con: sqlite3.Connection, conversation_id: str) -> list[sqlite3.Row]:
    return con.execute("SELECT * FROM consultas WHERE conversation_id = ? ORDER BY id", (conversation_id,)).fetchall()


def _ultima_con_tienda(con: sqlite3.Connection, conversation_id: str) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM consultas WHERE conversation_id = ? AND resultado = 'una' ORDER BY id DESC LIMIT 1",
                       (conversation_id,)).fetchone()


# ---- casos ----------------------------------------------------------------------------------------------------------------

def guardar(con: sqlite3.Connection, caso: dict) -> bool:
    """Guarda el caso; si ya estaba (ElevenLabs reintenta), lo reemplaza. Devuelve si el caso es nuevo.

    La tienda del caso es la que la asistente consultó; si no consultó ninguna, la que se entienda de la ficha.
    """
    caso = dict(caso)
    consulta = _ultima_con_tienda(con, caso["conversation_id"])
    if consulta is not None:
        caso["tienda_id"] = consulta["tienda_id"]
    else:
        tienda = directorio.buscar(directorio.todas(con), caso.get("tienda") or "").tienda
        caso["tienda_id"] = tienda.id if tienda else None
    with transaccion(con):
        nuevo = con.execute("SELECT 1 FROM casos WHERE conversation_id = ?", (caso["conversation_id"],)).fetchone() is None
        # El número se asigna una sola vez: un reintento de ElevenLabs no lo cambia.
        caso["numero"] = con.execute("SELECT COALESCE(MAX(numero), 0) + 1 FROM casos").fetchone()[0]
        columnas = _COLUMNAS + ("numero",)
        con.execute(
            f"INSERT INTO casos ({', '.join(columnas)}) VALUES ({', '.join('?' * len(columnas))}) "
            "ON CONFLICT (conversation_id) DO UPDATE SET "
            + ", ".join(f"{c} = excluded.{c}" for c in _COLUMNAS if c not in ("conversation_id", "recibido")),
            [caso.get(columna) for columna in columnas])
    return nuevo


def hablo_la_persona(caso: dict) -> bool:
    """Si la persona dijo o escribió algo. Un corte antes de hablar, o la plantilla de WhatsApp sin respuesta, no."""
    return any(turno.get("rol") == "persona" for turno in json.loads(caso.get("transcripcion") or "[]"))


def marcar_whatsapp(con: sqlite3.Connection, conversation_id: str, estado: str | None, detalle: str | None = None,
                    *, solo_si_estaba: str | None = None, momento: int | None = None) -> bool:
    """Anota el WhatsApp del caso. Con `solo_si_estaba=''`, solo si nunca se procesó: así se envía una sola vez."""
    condicion, valores = "", []
    if solo_si_estaba == "":
        condicion = " AND whatsapp_estado IS NULL"
    elif solo_si_estaba is not None:
        condicion, valores = " AND whatsapp_estado = ?", [solo_si_estaba]
    return con.execute(
        f"UPDATE casos SET whatsapp_estado = ?, whatsapp_detalle = ?, whatsapp_momento = ? "
        f"WHERE conversation_id = ?{condicion}",
        [estado, detalle, int(time.time()) if momento is None else momento, conversation_id, *valores]).rowcount == 1


_SELECT = """
    SELECT c.*, t.nombre AS tienda_nombre, t.comuna AS tienda_comuna, t.region AS tienda_region,
           q.frase AS equipo_frase, q.urgente AS equipo_urgente, q.momento AS equipo_momento, q.caja AS equipo_caja,
           -- Urgente si lo dijo la ficha o si el equipo estaba en un estado urgente cuando se consultó.
           (COALESCE(c.urgencia, 0) = 1 OR COALESCE(q.urgente, 0) = 1) AS urgente
    FROM casos c
    LEFT JOIN tiendas t ON t.id = c.tienda_id
    LEFT JOIN consultas q ON q.id = (SELECT MAX(id) FROM consultas
                                     WHERE conversation_id = c.conversation_id AND resultado = 'una')
"""


def lista(con: sqlite3.Connection, antes: int | None = None, solo_urgentes: bool = False) -> list[sqlite3.Row]:
    condiciones, valores = [], []
    if antes is not None:
        condiciones.append("c.inicio < ?")
        valores.append(antes)
    if solo_urgentes:
        condiciones.append("(COALESCE(c.urgencia, 0) = 1 OR COALESCE(q.urgente, 0) = 1)")
    donde = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    return con.execute(f"{_SELECT} {donde} ORDER BY c.inicio DESC, c.conversation_id LIMIT {LIMITE_PAGINA}",
                       valores).fetchall()


def leer(con: sqlite3.Connection, conversation_id: str) -> sqlite3.Row | None:
    return con.execute(f"{_SELECT} WHERE c.conversation_id = ?", (conversation_id,)).fetchone()


def contar(con: sqlite3.Connection) -> dict:
    fila = con.execute(f"SELECT COUNT(*) AS total, COALESCE(SUM(urgente), 0) AS urgentes FROM ({_SELECT})").fetchone()
    return {"total": fila["total"], "urgentes": fila["urgentes"]}


def marcar_avisado(con: sqlite3.Connection, conversation_id: str) -> bool:
    """True solo la primera vez: un reintento del webhook no repite el aviso."""
    return con.execute("UPDATE casos SET avisado = 1 WHERE conversation_id = ? AND avisado = 0",
                       (conversation_id,)).rowcount == 1
