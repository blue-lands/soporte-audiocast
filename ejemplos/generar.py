"""Genera ejemplos/units-mixto.json: lo que respondería GET /api/units de la central con el simulador en plan `mixto`.

Sirve para desarrollar y probar mientras no exista el token `soporte` de la central. No habla con la central: importa el
simulador (solo lectura) y arma la misma flota, que tiene semilla fija (los `unit_id` y `site_id` son los de verdad).

    python3 ejemplos/generar.py > ejemplos/units-mixto.json

Las tres cajas reales del final son INVENTADAS a partir de la descripción de la guía (§4 y §5), no copiadas de la central.
"""

import json
import random
import sys
import time

sys.dont_write_bytecode = True  # la carpeta de la central no es nuestra: ni un .pyc
sys.path.insert(0, "/var/www/central-audiocast/app/central")
import simulator  # noqa: E402

PLAN = "mixto"
AHORA = time.time()


def derivados(payload: dict, seconds_since: float, offline: bool) -> dict:
    """Los campos que agrega la central (server.unit_view) y que esta app usa."""
    return {**payload, "seconds_since": seconds_since, "expected_interval_s": 10.0, "offline": offline,
            "silent_streak": 0, "fallback_s_24h": payload.get("time_in_fallback_s", 0)}


def flota() -> list[dict]:
    rng = random.Random(20260724)  # la semilla de simulator.main()
    plan = simulator.PLANES[PLAN]
    cajas = []
    for n in range(69):
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
        derivados({**base, "unit_id": "minipc-lab-01", "site_id": "lab-01", "mode": "local_first", "source": "local",
                   "state": "FALLBACK", "state_since": iso(86000), "time_in_fallback_s": 86000, "ts": iso(6),
                   "stream_s_24h": 0}, 6.0, False),
        derivados({**base, "unit_id": "x98h-lab-02", "site_id": "lab-02", "state": "STREAMING",
                   "state_since": iso(5000), "time_in_fallback_s": 0, "ts": iso(8)}, 8.0, False),
        # La piloto: está para probar que la app NO la muestra.
        derivados({**base, "unit_id": "nataniel-cox-01", "site_id": "nataniel-cox", "state": "STREAMING",
                   "state_since": iso(900000), "time_in_fallback_s": 0, "ts": iso(800000)}, 800000.0, True),
    ]


if __name__ == "__main__":
    unidades = sorted(flota() + reales(), key=lambda caja: str(caja.get("site_id", "")))
    json.dump({"generated_at": AHORA, "units": unidades}, sys.stdout, ensure_ascii=False, indent=1)
