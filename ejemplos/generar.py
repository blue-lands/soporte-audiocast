"""Genera ejemplos/units-mixto.json: lo que respondería GET /api/units de la central con el simulador en plan `mixto`.

Sirve para desarrollar y probar mientras no exista el token `soporte` de la central. No habla con la central: importa el
simulador (solo lectura) y arma la misma flota, que tiene semilla fija (los `unit_id` y `site_id` son los de verdad).

    python3 ejemplos/generar.py > ejemplos/units-mixto.json

Desde 2026-09-30 la central dice de qué tienda es cada caja (`site.tienda`, central/tiendas.py de audiocast-player):
70 simuladas, una por tienda sin caja real. Las tres cajas reales del final imitan a las de verdad (mismos `unit_id` y
`site_id`), pero su estado es inventado: Beta y x98h sin tienda, `nataniel-cox-01` asignada a Nataniel Cox y sin latido.

    CENTRAL_DIR=/root/audiocast-player/central EJEMPLO_AHORA=1790565192.1482623 \
        python3 ejemplos/generar.py > ejemplos/units-mixto.json   # en vps7; la hora de los tests
"""

import json
import os
import random
import sys
import time

sys.dont_write_bytecode = True  # la carpeta de la central no es nuestra: ni un .pyc
sys.path.insert(0, os.environ.get("CENTRAL_DIR", "/var/www/central-audiocast/app/central"))
import simulator  # noqa: E402
import tiendas  # noqa: E402

PLAN = "mixto"
# EJEMPLO_AHORA fija el reloj: los tests comparan frases con "hace N minutos" contra una hora fija.
AHORA = float(os.environ.get("EJEMPLO_AHORA") or time.time())


def derivados(payload: dict, seconds_since: float, offline: bool) -> dict:
    """Los campos que agrega la central (server.unit_view) y que esta app usa."""
    return {**payload, "seconds_since": seconds_since, "expected_interval_s": 10.0, "offline": offline,
            "silent_streak": 0, "fallback_s_24h": payload.get("time_in_fallback_s", 0)}


def flota() -> list[dict]:
    rng = random.Random(20260724)  # la semilla de simulator.main()
    plan = simulator.PLANES[PLAN]
    cajas = []
    for n in range(len(simulator.SIM_TIENDAS)):
        unidad = simulator.SimUnit(n, rng, 10.0, plan)
        caida = simulator._en(plan["caidas"], n)
        cajas.append(derivados(unidad.payload(), 1500.0 + n if caida else 4.0, caida))
    return cajas


def reales() -> list[dict]:
    def iso(hace_s):
        return simulator._iso(AHORA - hace_s)
    base = {"audio": {"rms_dbfs": -19.8, "silent": False}, "forced_fallback": False,
            "volume": {"mpv_pct": 70, "hw_pct": 80, "hw_control": "Master", "hw_on": True}}
    return [
        derivados({**base, "unit_id": "ea4162f64b014c2fac77305255dad08c", "site_id": "Beta", "mode": "local_first",
                   "source": "local", "state": "FALLBACK", "state_since": iso(86000), "time_in_fallback_s": 86000,
                   "ts": iso(6), "stream_s_24h": 0}, 6.0, False),
        derivados({**base, "unit_id": "fdbaaaf2520183b5debe89746a6dc304", "site_id": "x98h-lab-02",
                   "state": "STREAMING", "state_since": iso(5000), "time_in_fallback_s": 0, "ts": iso(8)}, 8.0, False),
        # La piloto, asignada a Nataniel Cox en la central y desenchufada.
        derivados({**base, "unit_id": "96adc18211af42c1ba49ef5c0574da54", "site_id": "nataniel-cox-01",
                   "site": tiendas.sitio("nataniel-cox"), "state": "STREAMING", "state_since": iso(900000),
                   "time_in_fallback_s": 0, "ts": iso(800000)}, 800000.0, True),
    ]


if __name__ == "__main__":
    unidades = sorted(flota() + reales(), key=lambda caja: str(caja.get("site_id", "")))
    json.dump({"generated_at": AHORA, "units": unidades}, sys.stdout, ensure_ascii=False, indent=1)
