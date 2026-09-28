"""La tabla de `soporte-audiocast-central-y-tiendas.md` §3, fila por fila."""

from datetime import datetime, timezone

import pytest

from app.estado import describir

# 2026-09-28 13:23:09 UTC = 10:23 en Santiago (UTC-3, horario de verano desde el 6 de septiembre).
AHORA = datetime(2026, 9, 28, 13, 23, 9, tzinfo=timezone.utc)


def caja(**campos) -> dict:
    base = {"unit_id": "sim-12-3fa9c1", "site_id": "recoleta-12", "state": "STREAMING",
            "state_since": "2026-09-28T13:02:11Z", "time_in_fallback_s": 0, "forced_fallback": False,
            "audio": {"rms_dbfs": -21.4, "silent": False},
            "volume": {"mpv_pct": 70, "hw_pct": 80, "hw_control": "Master", "hw_on": True},
            "net": {"lte": {"rsrp_dbm": -90.0, "quality_pct": 60}},
            "ts": "2026-09-28T13:23:05Z", "seconds_since": 4.1, "offline": False, "silent_streak": 0}
    return {**base, **campos}


def test_1_tienda_sin_caja():
    estado = describir(None, AHORA)
    assert (estado.regla, estado.urgente) == (1, None)
    assert estado.frase == "No tengo registrado un equipo en esa tienda."


def test_2_sin_latido_dice_la_hora_de_santiago():
    estado = describir(caja(offline=True, seconds_since=43 * 60 + 9), AHORA)
    assert (estado.regla, estado.urgente) == (2, True)
    assert estado.frase == ("No tenemos señal de su equipo desde las 9:40, hace 43 minutos. "
                            "Puede estar apagado o sin conexión.")


def test_2_sin_latido_gana_a_cualquier_estado():
    assert describir(caja(offline=True, state="PAUSED"), AHORA).regla == 2


def test_2_sin_latido_pasada_la_medianoche_no_dice_ayer():
    medianoche = datetime(2026, 9, 28, 3, 13, tzinfo=timezone.utc)  # 00:13 en Santiago
    estado = describir(caja(offline=True, seconds_since=25 * 60), medianoche)
    assert "desde las 23:48, hace 25 minutos" in estado.frase


def test_2_sin_latido_de_ayer_y_de_hace_dias():
    assert "desde ayer a las 17:23" in describir(caja(offline=True, seconds_since=17 * 3600), AHORA).frase
    assert "desde hace 9 días" in describir(caja(offline=True, seconds_since=800000), AHORA).frase


def test_2_a_la_una_es_la_una():
    assert "desde la 1:05" in describir(caja(offline=True, seconds_since=9 * 3600 + 18 * 60 + 9), AHORA).frase


def test_2_sin_latido_y_sin_tiempos_no_inventa():
    sin_tiempos = caja(offline=True)
    del sin_tiempos["seconds_since"], sin_tiempos["ts"]
    assert describir(sin_tiempos, AHORA).frase == ("No tenemos señal de su equipo. "
                                                   "Puede estar apagado o sin conexión.")


@pytest.mark.parametrize("state, regla, urgente, trozo", [
    ("PAUSED", 3, False, "todavía no está activado"),
    ("NO_AUDIO_DEVICE", 4, True, "no detecta la salida de audio"),
    ("STARTING", 5, False, "se está reiniciando"),
    ("STREAMING", 10, False, "funcionando y conectado"),
    ("STREAM_SUSPECT", 10, False, "funcionando y conectado"),
    ("ALGO_NUEVO", 11, None, "no puedo confirmar su estado"),
])
def test_estados_simples(state, regla, urgente, trozo):
    estado = describir(caja(state=state), AHORA)
    assert (estado.regla, estado.urgente) == (regla, urgente)
    assert trozo in estado.frase


def test_6_silencio_sostenido():
    assert describir(caja(silent_streak=2), AHORA).regla == 10
    estado = describir(caja(silent_streak=3, state="FALLBACK", mode="local_first"), AHORA)
    assert (estado.regla, estado.urgente) == (6, True)


def test_7_local_first_en_fallback_es_lo_normal():
    estado = describir(caja(state="FALLBACK", mode="local_first", source="local", time_in_fallback_s=86000), AHORA)
    assert (estado.regla, estado.urgente) == (7, False)
    assert estado.frase == "Su equipo está funcionando normal."
    assert "conexión" not in estado.frase


def test_8_fallback_forzado():
    estado = describir(caja(state="FALLBACK", forced_fallback=True, time_in_fallback_s=7200), AHORA)
    assert (estado.regla, estado.urgente) == (8, False)


def test_9_fallback_urgente_pasados_15_minutos():
    corto = describir(caja(state="FALLBACK", time_in_fallback_s=12 * 60), AHORA)
    assert (corto.regla, corto.urgente) == (9, False)
    assert corto.frase.startswith("Su equipo perdió la conexión hace 12 minutos y está tocando música de respaldo.")
    largo = describir(caja(state="FALLBACK", time_in_fallback_s=1260), AHORA)
    assert largo.urgente is True
    assert "hace 21 minutos" in largo.frase


def test_9_sin_time_in_fallback_usa_state_since():
    sin_contador = caja(state="FALLBACK")
    del sin_contador["time_in_fallback_s"]
    assert "hace 20 minutos" in describir(sin_contador, AHORA).frase


def test_duraciones():
    def hace(segundos):
        return describir(caja(state="FALLBACK", time_in_fallback_s=segundos), AHORA).frase
    assert "hace menos de un minuto" in hace(40)
    assert "hace 1 minuto " in hace(61)
    assert "hace 1 hora " in hace(3600)
    assert "hace 2 horas y 5 minutos" in hace(2 * 3600 + 5 * 60)
    assert "hace 3 días" in hace(3 * 86400 + 50)


def test_volumen_solo_si_se_aleja_de_la_norma():
    assert describir(caja(), AHORA).volumen is None
    for volumen in ({"mpv_pct": 70, "hw_pct": 100}, {"mpv_pct": 40, "hw_pct": 80},
                    {"mpv_pct": 70, "hw_pct": 80, "hw_on": False}):
        assert describir(caja(volume=volumen), AHORA).volumen == "El volumen del equipo está distinto al normal."


def test_senal_debil():
    assert describir(caja(), AHORA).senal is None
    assert describir(caja(net={"lte": {"rsrp_dbm": -108.2, "quality_pct": 23}}), AHORA).senal
    assert describir(caja(net={"lte": {"quality_pct": 23}}), AHORA).senal
    assert describir(caja(net={"lte": {"rsrp_dbm": -104.9}}), AHORA).senal is None


def test_campos_que_faltan_o_vienen_raros_no_rompen():
    assert describir({"unit_id": "x", "state": "STREAMING"}, AHORA).regla == 10
    raro = caja(volume=None, net="nada", silent_streak="3", time_in_fallback_s=True, state="fallback",
                state_since="no es fecha")
    estado = describir(raro, AHORA)
    assert estado.regla == 9
    assert estado.frase.startswith("Su equipo perdió la conexión y está tocando")
    assert (estado.volumen, estado.senal, estado.urgente) == (None, None, False)


def test_ninguna_frase_lleva_datos_tecnicos(unidades):
    for unidad in unidades:
        estado = describir(unidad, AHORA)
        texto = " ".join(filter(None, (estado.frase, estado.volumen, estado.senal)))
        for prohibido in (unidad["unit_id"], unidad["state"], "dBm", "dBFS", "sim-", "run-", "T1", "Z"):
            assert prohibido not in texto, (prohibido, texto)
