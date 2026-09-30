"""Directorio de tiendas: qué caja tiene cada tienda y cómo encontrar la tienda que nombra quien llama."""

import sqlite3
import unicodedata
from dataclasses import dataclass
from difflib import get_close_matches

from .datos import tottus_tiendas as fuente
from .db import transaccion

MAX_OPCIONES = 6
# Palabras que no distinguen una tienda de otra. Se quitan de lo que dice la persona Y de los nombres
# ("La Florida" se compara como "florida"), así que un artículo aquí no rompe ningún nombre.
_VACIAS = frozenset("""
    tottus tienda sucursal local supermercado super hipermercado
    el la los las lo un una de del al a en y o que es por para con
    desde llamo llamando soy estoy estamos trabajo favor mi nuestra nuestro aca aqui
""".split())


@dataclass(frozen=True)
class Tienda:
    id: str
    nombre: str
    comuna: str
    region: str
    unit_id: str | None = None
    site_id: str | None = None
    alias: str = ""

    def como_dict(self) -> dict:
        return {"id": self.id, "nombre": self.nombre, "comuna": self.comuna, "region": self.region,
                "direccion": fuente.DIRECCIONES.get(self.id, "")}


@dataclass(frozen=True)
class Busqueda:
    tipo: str  # 'una' | 'varias' | 'ninguna'
    tiendas: tuple[Tienda, ...] = ()

    @property
    def tienda(self) -> Tienda | None:
        return self.tiendas[0] if self.tipo == "una" else None


# ---- asociación tienda → caja -------------------------------------------------------------------------------------------

def asociar(cajas: dict[str, dict]) -> list[Tienda]:
    """Las 71 tiendas, cada una con su caja. Una caja por tienda.

    1. Las tiendas con caja real (fuente.CAJAS_REALES).
    2. El resto, con una caja simulada: de la misma comuna; si no queda, de la misma región; si no, cualquiera libre.
    Cada paso recorre todas las tiendas antes del siguiente, para que una tienda no le quite a otra la caja de su comuna.
    """
    libres = sorted((caja for unit_id, caja in cajas.items() if unit_id.startswith("sim-")), key=_orden_caja)
    asignada: dict[str, tuple[str, str | None]] = {
        tienda_id: (unit_id, (cajas.get(unit_id) or {}).get("site_id"))
        for tienda_id, unit_id in fuente.CAJAS_REALES.items()
    }

    def repartir(calza, solo=lambda nombre, comuna: True):
        for tienda_id, nombre, comuna, region, _alias in fuente.TIENDAS:
            if tienda_id in asignada or not solo(nombre, comuna):
                continue
            caja = next((c for c in libres if calza(c.get("site") or {}, comuna, region)), None)
            if caja:
                libres.remove(caja)
                asignada[tienda_id] = (caja["unit_id"], caja.get("site_id"))

    def misma_comuna(sitio, comuna, _region):
        return _plano(sitio.get("comuna")) == _plano(fuente.COMUNA_EN_CENTRAL.get(comuna, comuna))

    # La caja de Puente Alto es para la tienda Puente Alto antes que para Mall Plaza Tobalaba.
    repartir(misma_comuna, solo=lambda nombre, comuna: _plano(nombre) == _plano(comuna))
    repartir(misma_comuna)
    repartir(lambda sitio, _comuna, region: sitio.get("region") == fuente.REGION_CORTA.get(region))
    repartir(lambda _sitio, _comuna, _region: True)

    return [Tienda(tienda_id, nombre, comuna, region, *asignada.get(tienda_id, (None, None)), alias)
            for tienda_id, nombre, comuna, region, alias in fuente.TIENDAS]


def _orden_caja(caja: dict):
    return (str((caja.get("site") or {}).get("short_id") or ""), caja["unit_id"])


# ---- base de datos --------------------------------------------------------------------------------------------------------

def guardar(con: sqlite3.Connection, tiendas: list[Tienda]) -> None:
    """Deja la tabla igual a `tiendas`. Se puede repetir cuantas veces haga falta."""
    with transaccion(con):
        # unit_id es UNIQUE: se sueltan todas las cajas antes de repartirlas de nuevo.
        con.execute("UPDATE tiendas SET unit_id = NULL, site_id = NULL")
        ids = [t.id for t in tiendas]
        con.execute(f"DELETE FROM tiendas WHERE id NOT IN ({','.join('?' * len(ids))})", ids)
        con.executemany(
            "INSERT INTO tiendas (id, nombre, comuna, region, unit_id, site_id, alias) VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (id) DO UPDATE SET nombre = excluded.nombre, comuna = excluded.comuna, "
            "region = excluded.region, unit_id = excluded.unit_id, site_id = excluded.site_id, alias = excluded.alias",
            [(t.id, t.nombre, t.comuna, t.region, t.unit_id, t.site_id, t.alias) for t in tiendas])


def todas(con: sqlite3.Connection) -> list[Tienda]:
    filas = con.execute("SELECT id, nombre, comuna, region, unit_id, site_id, alias FROM tiendas ORDER BY rowid")
    return [Tienda(**dict(fila)) for fila in filas]


# ---- búsqueda -------------------------------------------------------------------------------------------------------------

def buscar(tiendas: list[Tienda], texto: str) -> Busqueda:
    """La tienda que nombra quien llama: "la de Nataniel", "Tottus Recoleta", "el de Viña".

    Si lo dicho calza con varias ("Talca": Talca y Talca Colín; "Puente Alto": la tienda y Mall Plaza Tobalaba, que está
    en esa comuna), se devuelven todas y la asistente pregunta cuál. Equivocarse de tienda es peor que preguntar.
    """
    dicho = _palabras(texto)
    if not dicho:
        return Busqueda("ninguna")
    fichas = [_Ficha(tienda) for tienda in tiendas]
    encontradas = _directas(fichas, dicho) or _en_frase(fichas, dicho)
    if not encontradas:
        # Lo que entendió mal el reconocimiento de voz ("natanael", "maipo"): cada palabra desconocida, a la más parecida.
        # Solo vale si después TODO lo dicho es de la tienda: dentro de una frase, "Puerto Montt" terminaba en El Monte.
        vocabulario = sorted(set().union(*(ficha.todo for ficha in fichas))) if fichas else []
        corregido = frozenset(
            palabra if palabra in vocabulario else next(iter(get_close_matches(palabra, vocabulario, 1, 0.75)), palabra)
            for palabra in dicho)
        if corregido != dicho:
            encontradas = _directas(fichas, corregido)
    if not encontradas:
        return Busqueda("ninguna")
    if len(encontradas) == 1:
        return Busqueda("una", (encontradas[0],))
    return Busqueda("varias", tuple(encontradas[:MAX_OPCIONES]))


class _Ficha:
    def __init__(self, tienda: Tienda):
        self.tienda = tienda
        self.nombre = _palabras(tienda.nombre)
        self.comuna = _palabras(tienda.comuna)
        self.alias = [palabras for palabras in map(_palabras, tienda.alias.split("|")) if palabras]
        self.todo = self.nombre.union(self.comuna, *self.alias)


def _directas(fichas: list[_Ficha], dicho: frozenset[str]) -> list[Tienda]:
    """Todo lo dicho es de la tienda: su nombre, su comuna o un alias, completos o en parte."""
    puntos = []
    for ficha in fichas:
        if dicho == ficha.nombre:
            puntos.append((100, ficha))
        elif dicho in ficha.alias:
            puntos.append((95, ficha))
        elif dicho == ficha.comuna:
            puntos.append((90, ficha))
        elif dicho <= ficha.todo:
            puntos.append((70, ficha))
    puntos.sort(key=lambda par: -par[0])  # estable: a igual puntaje, el orden del directorio
    return [ficha.tienda for _, ficha in puntos]


def _en_frase(fichas: list[_Ficha], dicho: frozenset[str]) -> list[Tienda]:
    """Dijo una frase más larga ("tengo un problema en talca colín"): la tienda cuyo nombre, alias o comuna aparece
    entero. Gana el que ocupa más palabras (Talca Colín antes que Talca)."""
    puntos = []
    for ficha in fichas:
        enteros = [len(clave) for clave in (ficha.nombre, ficha.comuna, *ficha.alias) if clave and clave <= dicho]
        if enteros:
            puntos.append((max(enteros), ficha))
    mejor = max((p for p, _ in puntos), default=0)
    return [ficha.tienda for p, ficha in puntos if p == mejor]


def _plano(texto) -> str:
    """Sin tildes ni mayúsculas ('Ñuñoa' → 'nunoa'), solo letras, números y espacios."""
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", str(texto or "")) if not unicodedata.combining(c))
    return " ".join("".join(c if c.isalnum() else " " for c in sin_tildes.lower()).split())


def _palabras(texto) -> frozenset[str]:
    return frozenset(palabra for palabra in _plano(texto).split() if palabra not in _VACIAS)
