"""Números en palabras, para que la voz diga una dirección sin leer cifras ("Recoleta 806" → "Recoleta ochocientos seis").

La asistente no lee números: una vez inventó dígitos de un celular. Por eso la dirección le llega ya escrita en palabras.
"""

import re

_UNIDADES = ("cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince dieciséis "
             "diecisiete dieciocho diecinueve veinte veintiuno veintidós veintitrés veinticuatro veinticinco veintiséis "
             "veintisiete veintiocho veintinueve").split()
_DECENAS = {3: "treinta", 4: "cuarenta", 5: "cincuenta", 6: "sesenta", 7: "setenta", 8: "ochenta", 9: "noventa"}
_CENTENAS = {1: "ciento", 2: "doscientos", 3: "trescientos", 4: "cuatrocientos", 5: "quinientos", 6: "seiscientos",
             7: "setecientos", 8: "ochocientos", 9: "novecientos"}


def numero(n: int) -> str:
    """De 0 a 999.999: 806 → 'ochocientos seis', 12400 → 'doce mil cuatrocientos'."""
    if not 0 <= n < 1_000_000:
        raise ValueError(n)
    if n < 30:
        return _UNIDADES[n]
    if n < 100:
        decena, unidad = divmod(n, 10)
        return _DECENAS[decena] + (f" y {_UNIDADES[unidad]}" if unidad else "")
    if n < 1000:
        centena, resto = divmod(n, 100)
        if n == 100:
            return "cien"
        return _CENTENAS[centena] + (f" {numero(resto)}" if resto else "")
    miles, resto = divmod(n, 1000)
    # "veintiún mil", "treinta y un mil": delante de "mil", uno pierde la o.
    delante = "" if miles == 1 else re.sub(r"uno$", "ún" if miles < 30 else "un", numero(miles)) + " "
    return f"{delante}mil" + (f" {numero(resto)}" if resto else "")


def para_decir(texto: str) -> str:
    """Cambia cada número por palabras. Un 0 inicial se dice: 'Diego Portales 081' → '... cero ochenta y uno'."""
    def cambiar(cifras: re.Match) -> str:
        digitos = cifras.group()
        ceros = len(digitos) - len(digitos.lstrip("0"))
        if ceros == len(digitos):
            return " ".join(["cero"] * ceros)
        return " ".join(["cero"] * ceros + [numero(int(digitos))])
    return re.sub(r"\d+", cambiar, texto)
