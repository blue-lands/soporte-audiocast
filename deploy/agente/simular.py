"""Batería de llamadas simuladas contra la COPIA de pruebas del agente (nunca contra el que atiende el teléfono).

Mide, por escenario, cuántas veces la asistente consulta la tienda apenas la persona nombra la comuna (sin pedirle más
datos antes), y si después confirma con la dirección o nombra las opciones. La herramienta va simulada
(`tool_mock_config`): no toca esta app ni la central, y la copia no tiene teléfono ni webhook de fin.

    set -a; . ./.env; set +a
    python3 deploy/agente/simular.py <agent_id_copia> [veces=10] [llm] [temperatura]

llm/temperatura: si vienen, se aplican a la COPIA antes de correr (el prompt no se toca).
"""

import json
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

API = "https://api.elevenlabs.io"
INDICACION_UNA = ("Al confirmar la tienda, diga también su dirección: en una llamada, con las palabras de "
                  "direccion_para_decir; por escrito, como viene en direccion. Diga el estado del equipo con esas "
                  "palabras. El volumen y la señal, solo si la persona pregunta o si tienen que ver con su problema.")


def una(tienda_id, nombre, comuna, direccion, para_decir):
    return {"resultado": "encontrada", "tienda_id": tienda_id, "tienda": nombre, "comuna": comuna,
            "estado_del_equipo": "Su equipo está funcionando y conectado.", "direccion": direccion,
            "direccion_para_decir": para_decir, "urgente": False, "indicacion": INDICACION_UNA}


ESCENARIOS = {
    "concepcion": {
        "primera": "Hola, buenas tardes. Tengo un problema con la radio en el local de Concepción.",
        "persona": ("Trabajas en la tienda Tóttus de Concepción. La radio no suena desde la mañana. No sabes el nombre "
                    "oficial de la tienda: si te lo preguntan, di 'la de Concepción, no hay otra'. Respuestas cortas. "
                    "Si te leen una dirección, di que sí."),
        "comuna": "concepci",
        "respuesta": una("bio-bio", "Bío Bío", "Concepción", "Avenida Los Carrera 301",
                         "Avenida Los Carrera trescientos uno"),
        "despues": ["los carrera"],
    },
    "valparaiso": {
        "primera": "Hola, tengo un problema con el sistema de audio.",
        "persona": ("Trabajas en la tienda Tóttus del centro de Valparaíso; los avisos no suenan. Cuando te pregunten "
                    "desde qué tienda llamas, di solo 'De Valparaíso'. Si te piden el nombre o la comuna exacta, di "
                    "'usted debería saberlo'. Si te nombran opciones, elige la de Valparaíso centro. Respuestas cortas."),
        "comuna": "valpara",
        "respuesta": {"resultado": "varias", "opciones": [
            {"tienda_id": "valparaiso", "nombre": "Valparaíso", "comuna": "Valparaíso"},
            {"tienda_id": "curauma", "nombre": "Curauma", "comuna": "Valparaíso"}],
            "indicacion": ("Hay más de una tienda que calza. Pregunte cuál de estas es, nombrándolas, y vuelva a "
                           "consultar con el tienda_id de la que elija la persona.")},
        "despues": ["curauma"],
    },
    "providencia": {
        "primera": "Eh, tengo un pequeño problema con la tienda en Providencia.",
        "persona": ("Trabajas en la tienda Tóttus de Providencia; la música suena muy baja. Respuestas cortas. Si te "
                    "preguntan el nombre, di 'Hernán'. Si te leen una dirección, di que sí."),
        "comuna": "providencia",
        "respuesta": una("providencia", "Providencia", "Providencia", "Avenida Bilbao 451",
                         "Avenida Bilbao cuatrocientos cincuenta y uno"),
        "despues": ["bilbao"],
    },
}


def pedir(metodo, ruta, cuerpo=None, timeout=180):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    request = urllib.request.Request(API + ruta, data=datos, method=metodo,
                                     headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"],
                                              "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as respuesta:
            return json.load(respuesta)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"{error.code}: {error.read().decode()[:800]}") from None


def simular(agente, nombre):
    esc = ESCENARIOS[nombre]
    cuerpo = {"simulation_specification": {
        "simulated_user_config": {"first_message": esc["primera"], "language": "es",
                                  "prompt": {"prompt": esc["persona"], "temperature": 0.7}},
        "tool_mock_config": {"consultar_tienda": {"default_return_value": json.dumps(esc["respuesta"],
                                                                                     ensure_ascii=False)}},
        # Las que el agente espera de una llamada real; fijo que no es celular (+569): no promete WhatsApp.
        "dynamic_variables": {"system__conversation_id": "simulacion", "system__caller_id": "+56225550000"}},
        "new_turns_limit": 10}
    turnos = pedir("POST", f"/v1/convai/agents/{agente}/simulate-conversation", cuerpo)["simulated_conversation"]
    return medir(esc, turnos), turnos


def medir(esc, turnos):
    """consulta_directa: entre que la persona nombra la comuna y la primera consulta, la asistente no habló (o solo
    dijo algo sin preguntar). despues: tras la consulta menciona la dirección (o las dos opciones)."""
    nombrada = consulta = None
    preguntas_antes = 0
    for i, turno in enumerate(turnos):
        texto = (turno.get("message") or "").lower()
        if nombrada is None and turno.get("role") == "user" and esc["comuna"] in texto:
            nombrada = i
            continue
        if nombrada is not None and consulta is None and turno.get("role") == "agent":
            if any(llamada.get("tool_name") == "consultar_tienda" for llamada in turno.get("tool_calls") or []):
                consulta = i
            elif "?" in texto:
                preguntas_antes += 1
    dijo = " ".join((t.get("message") or "").lower() for t in turnos[(consulta or 0):] if t.get("role") == "agent")
    return {"consulta_directa": nombrada is not None and consulta is not None and preguntas_antes == 0,
            "consulto": consulta is not None, "preguntas_antes": preguntas_antes,
            "despues": consulta is not None and all(p in dijo for p in esc["despues"])}


def main():
    agente = sys.argv[1]
    veces = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    if len(sys.argv) > 3:
        cambio = {"llm": sys.argv[3]}
        if len(sys.argv) > 4:
            cambio["temperature"] = float(sys.argv[4])
        pedir("PATCH", f"/v1/convai/agents/{agente}", {"conversation_config": {"agent": {"prompt": cambio}}})
    prompt = pedir("GET", f"/v1/convai/agents/{agente}")["conversation_config"]["agent"]["prompt"]
    print(f"agente {agente} · llm {prompt['llm']} · temperatura {prompt['temperature']} · {veces} por escenario")
    trabajos = [(nombre, n) for nombre in ESCENARIOS for n in range(veces)]
    with ThreadPoolExecutor(max_workers=5) as grupo:
        resultados = list(grupo.map(lambda t: (t[0], *simular(agente, t[0])), trabajos))
    salida = {}
    for nombre in ESCENARIOS:
        de_este = [(m, turnos) for n, m, turnos in resultados if n == nombre]
        directa = sum(m["consulta_directa"] for m, _ in de_este)
        despues = sum(m["despues"] for m, _ in de_este)
        print(f"  {nombre:12} consulta directa {directa}/{len(de_este)} · "
              f"{'nombra opciones' if nombre == 'valparaiso' else 'dice dirección'} {despues}/{len(de_este)}")
        salida[nombre] = [{"medida": m, "turnos": [{"rol": t.get("role"), "mensaje": t.get("message"),
                                                    "herramientas": [c.get("tool_name") for c in t.get("tool_calls") or []]}
                                                   for t in turnos]} for m, turnos in de_este]
    archivo = f"/var/tmp/simulacion-{prompt['llm'].replace('/', '_')}-{prompt['temperature']}.json"
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)
    print(f"  detalle: {archivo}")


if __name__ == "__main__":
    main()
