import pytest

from app import palabras
from app.datos import tottus_tiendas


@pytest.mark.parametrize("n, dicho", [
    (0, "cero"), (16, "dieciséis"), (21, "veintiuno"), (47, "cuarenta y siete"), (100, "cien"),
    (101, "ciento uno"), (500, "quinientos"), (806, "ochocientos seis"), (1000, "mil"), (1030, "mil treinta"),
    (3470, "tres mil cuatrocientos setenta"), (12400, "doce mil cuatrocientos"), (21000, "veintiún mil"),
    (31500, "treinta y un mil quinientos"), (100000, "cien mil"), (10811, "diez mil ochocientos once"),
])
def test_numero(n, dicho):
    assert palabras.numero(n) == dicho


def test_direccion_sin_cifras_y_con_el_cero_inicial():
    assert palabras.para_decir("Avenida Recoleta 806") == "Avenida Recoleta ochocientos seis"
    assert palabras.para_decir("Diego Portales 081") == "Diego Portales cero ochenta y uno"
    assert palabras.para_decir("Los Aromos 0441") == "Los Aromos cero cuatrocientos cuarenta y uno"


def test_todas_las_direcciones_se_pueden_decir_y_son_de_tiendas_que_existen():
    ids = {tienda[0] for tienda in tottus_tiendas.TIENDAS}
    assert set(tottus_tiendas.DIRECCIONES) <= ids
    assert ids - set(tottus_tiendas.DIRECCIONES) == {"piedra-roja", "el-bosque"}
    for direccion in tottus_tiendas.DIRECCIONES.values():
        assert not any(c.isdigit() for c in palabras.para_decir(direccion)), direccion
        assert "Av." not in direccion
