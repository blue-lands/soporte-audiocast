#!/bin/bash
# Corre una tarea de app.cli con el mismo usuario, entorno y base que el servicio.
#   deploy/cli.sh cargar-tiendas
#   deploy/cli.sh consultar "la de nataniel"
# Hace falta porque la base vive en el StateDirectory de un DynamicUser: si root escribe ahí, el servicio
# después no puede. SIN PROBAR hasta que el servicio esté instalado.
set -euo pipefail
exec systemd-run --quiet --pipe --wait --collect \
    -p DynamicUser=yes -p User=soporte-audiocast \
    -p StateDirectory=soporte-audiocast -p StateDirectoryMode=0700 \
    -p WorkingDirectory=/var/www/soporte-audiocast \
    -p EnvironmentFile=/var/www/soporte-audiocast/.env \
    -p Environment=PYTHONDONTWRITEBYTECODE=1 \
    -p MemoryMax=150M \
    /var/www/soporte-audiocast/.venv/bin/python -m app.cli "$@"
