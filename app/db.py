"""Conexión a SQLite y esquema."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

_ESQUEMA = Path(__file__).with_name("esquema.sql")


def conectar(ruta: str) -> sqlite3.Connection:
    # isolation_level=None: cada sentencia se confirma sola; las escrituras de varias sentencias usan transaccion().
    # check_same_thread=False: FastAPI puede abrir la conexión en un hilo y usarla en otro dentro del mismo request.
    con = sqlite3.connect(ruta, timeout=5, isolation_level=None, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def inicializar(ruta: str) -> None:
    if ruta != ":memory:":
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    con = conectar(ruta)
    try:
        con.executescript(_ESQUEMA.read_text(encoding="utf-8"))
        _migrar(con)
    finally:
        con.close()


def _migrar(con: sqlite3.Connection) -> None:
    # 2026-09-28: el panel tuvo entrada propia unas horas. Ahora vale la sesión de la central.
    for tabla in ("sesiones", "intentos_fallidos", "usuarios"):
        con.execute(f"DROP TABLE IF EXISTS {tabla}")
    # 2026-09-28: número de caso y WhatsApp a quien llamó.
    columnas = {fila["name"] for fila in con.execute("PRAGMA table_info(casos)")}
    for columna, tipo in (("numero", "INTEGER"), ("whatsapp_estado", "TEXT"), ("whatsapp_detalle", "TEXT"),
                          ("whatsapp_momento", "INTEGER")):
        if columna not in columnas:
            con.execute(f"ALTER TABLE casos ADD COLUMN {columna} {tipo}")
    # Los casos que llegaron antes del número lo reciben en el orden en que ocurrieron.
    for fila in con.execute("SELECT conversation_id FROM casos WHERE numero IS NULL ORDER BY inicio, recibido").fetchall():
        con.execute("UPDATE casos SET numero = (SELECT COALESCE(MAX(numero), 0) + 1 FROM casos) WHERE conversation_id = ?",
                    (fila["conversation_id"],))
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS casos_numero ON casos (numero)")


@contextmanager
def transaccion(con: sqlite3.Connection):
    con.execute("BEGIN IMMEDIATE")
    try:
        yield con
    except BaseException:
        con.execute("ROLLBACK")
        raise
    con.execute("COMMIT")
