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
    assert len(con_caja) == len(set(con_caja)) == 71  # 70 simuladas + la real


def test_nataniel_cox_tiene_la_caja_real(tiendas):
    por_id = {tienda.id: tienda for tienda in tiendas}
    assert por_id["nataniel-cox"].unit_id == "96adc18211af42c1ba49ef5c0574da54"
    assert por_id["nataniel-cox"].site_id == "nataniel-cox-01"


def test_las_cajas_sin_tienda_no_se_asocian(tiendas):
    assert not {"ea4162f64b014c2fac77305255dad08c", "fdbaaaf2520183b5debe89746a6dc304"} & {
        tienda.unit_id for tienda in tiendas}


def test_la_central_dice_la_tienda(tiendas):
    por_id = {tienda.id: tienda for tienda in tiendas}
    for tienda_id in ("recoleta", "la-cisterna", "puente-alto", "catedral", "renaca", "piedra-roja"):
        assert por_id[tienda_id].site_id == tienda_id


def test_sin_site_tienda_misma_comuna_primero_y_para_la_tienda_que_se_llama_igual():
    # El respaldo para cajas que no traen site.tienda (flotas viejas): se reparte por comuna.
    cajas = {
        "sim-01": {"unit_id": "sim-01", "site_id": "a", "site": {"comuna": "Puente Alto", "region": "RM", "short_id": "AC-01"}},
        "sim-02": {"unit_id": "sim-02", "site_id": "b", "site": {"comuna": "Santiago", "region": "RM", "short_id": "AC-02"}},
    }
    por_id = {tienda.id: tienda for tienda in directorio.asociar(cajas)}
    assert por_id["puente-alto"].site_id == "a"  # antes que Mall Plaza Tobalaba, de la misma comuna
    assert por_id["nataniel-cox"].site_id == "b"  # "Santiago Centro" es "Santiago" en la central


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
    assert [t.unit_id for t in tiendas if t.unit_id] == []


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
