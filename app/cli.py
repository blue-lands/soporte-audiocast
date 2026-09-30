"""Tareas de consola.

    .venv/bin/python -m app.cli cargar-tiendas [--cajas ejemplos/units-mixto.json]
    .venv/bin/python -m app.cli tiendas
    .venv/bin/python -m app.cli consultar "la de nataniel"
    .venv/bin/python -m app.cli reenviar-whatsapp 5     # el WhatsApp del caso N° 0005, si falló

Leen la misma configuración que el servicio (variables de entorno; ver .env.ejemplo).
"""

import argparse
import dataclasses
import json
import sys

from . import central, consulta, db, directorio, whatsapp
from .config import cargar


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli", description="Soporte Audiocast")
    tareas = parser.add_subparsers(dest="tarea", required=True)
    cargar_tiendas = tareas.add_parser("cargar-tiendas", help="llena la tabla tiendas y asocia cada una con su caja")
    cargar_tiendas.add_argument("--cajas", help="JSON con la forma de /api/units; por defecto, la central configurada")
    tareas.add_parser("tiendas", help="lista el directorio")
    consultar = tareas.add_parser("consultar", help="lo que respondería la herramienta consultar_tienda")
    consultar.add_argument("texto")
    reenviar = tareas.add_parser("reenviar-whatsapp", help="vuelve a mandar el WhatsApp de un caso que falló")
    reenviar.add_argument("numero", type=int, help="N° del caso")
    args = parser.parse_args(argv)

    config = cargar()
    if args.tarea == "cargar-tiendas" and args.cajas:
        config = dataclasses.replace(config, central_archivo=args.cajas)
    db.inicializar(config.db_path)
    con = db.conectar(config.db_path)
    try:
        if args.tarea == "cargar-tiendas":
            return _cargar_tiendas(con, config)
        if args.tarea == "tiendas":
            _listar(directorio.todas(con))
            return 0
        if args.tarea == "reenviar-whatsapp":
            resultado = whatsapp.reintentar(config, con, args.numero)
            print(f"Caso N° {args.numero:04d}: {resultado}")
            return 0 if resultado == "enviado" else 1
        print(json.dumps(consulta.consultar_tienda(con, config, args.texto), ensure_ascii=False, indent=2))
        return 0
    finally:
        con.close()


def _cargar_tiendas(con, config) -> int:
    try:
        cajas = central.leer_cajas(config, usar_cache=False)
    except central.CentralNoDisponible as error:
        print(f"No se pudo leer la lista de cajas ({error}). No se cambió nada.", file=sys.stderr)
        return 1
    tiendas = directorio.asociar(cajas)
    directorio.guardar(con, tiendas)
    _listar(tiendas)
    sin_caja = [tienda.nombre for tienda in tiendas if not tienda.unit_id]
    print(f"\n{len(tiendas)} tiendas, {len(tiendas) - len(sin_caja)} con caja."
          + (f" Sin caja: {', '.join(sin_caja)}." if sin_caja else ""))
    return 0


def _listar(tiendas) -> None:
    for tienda in tiendas:
        print(f"{tienda.id:24} {tienda.comuna:28} {tienda.region:24} {tienda.unit_id or '—':16} {tienda.site_id or ''}")


if __name__ == "__main__":
    sys.exit(main())
