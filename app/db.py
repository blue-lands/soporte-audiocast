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


@contextmanager
def transaccion(con: sqlite3.Connection):
    con.execute("BEGIN IMMEDIATE")
    try:
        yield con
    except BaseException:
        con.execute("ROLLBACK")
        raise
    con.execute("COMMIT")
