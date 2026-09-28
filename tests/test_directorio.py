import pytest

from app import central, directorio
from app.datos import tottus_tiendas as fuente


@pytest.fixture
def tiendas(con):
    return directorio.todas(con)


def nombres(busqueda):
    return [tienda.nombre for tienda in busqueda.tiendas]


# ---- los datos ----------------------------------------------------------------------------------------------------------

def test_son_las_71_tiendas_sin_repetidas():
    assert len(fuente.TIENDAS) == 71
    assert len({tienda[0] for tienda in fuente.TIENDAS}) == 71
    assert {tienda[3] for tienda in fuente.TIENDAS} == set(fuente.REGION_CORTA)


# ---- asociación ---------------------------------------------------------------------------------------------------------

def test_una_caja_por_tienda(tiendas):
    con_caja = [tienda.unit_id for tienda in tiendas if tienda.unit_id]
    assert len(tiendas) == 71
    assert len(con_caja) == len(set(con_caja)) == 70  # 69 simuladas + la real


def test_nataniel_cox_tiene_la_caja_real(tiendas):
    assert {t.id: t.unit_id for t in tiendas}["nataniel-cox"] == "minipc-lab-01"


def test_la_piloto_y_la_caja_fragil_no_se_asocian(tiendas):
    assert not {"nataniel-cox-01", "x98h-lab-02"} & {tienda.unit_id for tienda in tiendas}


def test_misma_comuna_primero_y_para_la_tienda_que_se_llama_igual(tiendas):
    por_id = {tienda.id: tienda for tienda in tiendas}
    assert por_id["recoleta"].site_id == "recoleta-07"
    assert por_id["la-cisterna"].site_id == "la-cisterna-22"
    assert por_id["puente-alto"].site_id == "puente-alto-05"
    assert por_id["catedral"].site_id == "santiago-06"  # "Santiago Centro" es "Santiago" en la central
    assert por_id["renaca"].site_id == "viña-del-mar-37"


def test_despues_la_misma_region(config, tiendas):
    cajas = central.leer_cajas(config)
    por_id = {tienda.id: tienda for tienda in tiendas}
    assert cajas[por_id["machali"].unit_id]["site"]["region"] == "VI"
    assert cajas[por_id["talca-colin"].unit_id]["site"]["region"] == "VII"


def test_cargar_dos_veces_da_lo_mismo(con, config, tiendas):
    directorio.guardar(con, directorio.asociar(central.leer_cajas(config)))
    assert directorio.todas(con) == tiendas


def test_sin_cajas_simuladas_quedan_las_tiendas_sin_caja():
    tiendas = directorio.asociar({})
    assert [t.unit_id for t in tiendas if t.unit_id] == ["minipc-lab-01"]


# ---- búsqueda -----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("dicho, tienda", [
    ("la de Nataniel", "Nataniel Cox"),
    ("Tottus Recoleta", "Recoleta"),
    ("RECOLETA", "Recoleta"),
    ("la cisterna", "La Cisterna"),
    ("nunoa", "Plaza Egaña"),
    ("plaza egaña", "Plaza Egaña"),
    ("Tobalaba", "Mall Plaza Tobalaba"),
    ("el trebol", "El trébol"),
    ("biobio", "Bío Bío"),
    ("bío-bío", "Bío Bío"),
    ("Concepción", "Bío Bío"),
    ("catedral, en santiago", "Catedral"),
    ("los angeles alemania", "Los Ángeles Alemania"),
    ("san vicente de tagua tagua", "San Vicente"),
    ("llamo desde el tottus de quilpué por favor", "Quilpué"),
    ("tengo un problema en talca colín", "Talca Colín"),
])
def test_encuentra_una(tiendas, dicho, tienda):
    busqueda = directorio.buscar(tiendas, dicho)
    assert (busqueda.tipo, nombres(busqueda)) == ("una", [tienda])


@pytest.mark.parametrize("dicho, tienda", [("natanael", "Nataniel Cox"), ("maipo", "Maipú"), ("quilicurá", "Quilicura"),
                                           ("bitacura", "Vitacura")])
def test_tolera_lo_que_entendio_mal_el_reconocimiento_de_voz(tiendas, dicho, tienda):
    assert nombres(directorio.buscar(tiendas, dicho)) == [tienda]


@pytest.mark.parametrize("dicho, opciones", [
    ("el de Viña", ["Reñaca", "Santa Julia"]),
    ("viña del mar", ["Reñaca", "Santa Julia"]),
    ("Talca", ["Talca", "Talca Colín"]),
    ("puente alto", ["Puente Alto", "Mall Plaza Tobalaba"]),
    ("santiago centro", ["Nataniel Cox", "Catedral", "Vicuña Mackenna"]),
    ("antofagasta", ["Antofagasta Norte", "Antofagasta Centro", "Antofagasta Mall"]),
    ("san bernardo", ["San Bernardo Estación", "San Bernardo Plaza"]),
])
def test_si_hay_varias_las_devuelve_para_preguntar(tiendas, dicho, opciones):
    busqueda = directorio.buscar(tiendas, dicho)
    assert (busqueda.tipo, nombres(busqueda)) == ("varias", opciones)
    assert busqueda.tienda is None


def test_varias_tiene_tope(tiendas):
    assert len(directorio.buscar(tiendas, "san").tiendas) == directorio.MAX_OPCIONES


@pytest.mark.parametrize("dicho", ["Temuco", "Puerto Montt", "tottus", "", "   ", "la tienda", "xyz",
                                   "llamo de la tienda de puerto varas"])
def test_ninguna(tiendas, dicho):
    assert directorio.buscar(tiendas, dicho).tipo == "ninguna"
