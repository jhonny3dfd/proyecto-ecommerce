from django.test import SimpleTestCase

from ecommerce.domain.destacados import (
    MAX_DESTACADOS, TITULO_POR_DEFECTO, DestacadosInvalidos, TipoDestacado, TituloDestacadosInvalido,
    ids_por_tipo, normalizar_destacados, normalizar_titulo_destacados,
)

PRODUCTO = {'tipo': 'PRODUCTO', 'id': '6650f0a1b2c3d4e5f6a7b8c9'}
PUBLICACION = {'tipo': 'PUBLICACION', 'id': '7'}


class NormalizarDestacadosTests(SimpleTestCase):
    def test_mezcla_productos_y_publicaciones_en_el_orden_elegido(self):
        lista = [PUBLICACION, PRODUCTO]
        self.assertEqual(normalizar_destacados(lista), lista)

    def test_lista_vacia_es_valida(self):
        self.assertEqual(normalizar_destacados([]), [])

    def test_el_id_numerico_de_una_publicacion_se_guarda_como_texto(self):
        self.assertEqual(normalizar_destacados([{'tipo': 'PUBLICACION', 'id': 7}]), [PUBLICACION])

    def test_quita_los_espacios_del_id(self):
        self.assertEqual(normalizar_destacados([{'tipo': 'PUBLICACION', 'id': ' 7 '}]), [PUBLICACION])

    def test_como_maximo_ocho(self):
        lista = [{'tipo': 'PUBLICACION', 'id': str(numero)} for numero in range(MAX_DESTACADOS + 1)]
        with self.assertRaisesMessage(DestacadosInvalidos, 'hasta 8'):
            normalizar_destacados(lista)
        self.assertEqual(len(normalizar_destacados(lista[:MAX_DESTACADOS])), MAX_DESTACADOS)

    def test_no_se_repiten(self):
        with self.assertRaisesMessage(DestacadosInvalidos, 'dos veces'):
            normalizar_destacados([PUBLICACION, {'tipo': 'PUBLICACION', 'id': 7}])

    def test_el_mismo_id_en_tipos_distintos_no_es_repetido(self):
        lista = [{'tipo': 'PRODUCTO', 'id': '7'}, PUBLICACION]
        self.assertEqual(normalizar_destacados(lista), lista)

    def test_rechaza_formas_invalidas(self):
        for valor in (None, {}, 'PRODUCTO', [None], [{'tipo': 'PRODUCTO'}], [{'id': '1'}],
                      [{'tipo': 'CATEGORIA', 'id': '1'}], [{'tipo': 'PRODUCTO', 'id': ''}],
                      [{'tipo': 'PRODUCTO', 'id': '   '}], [{'tipo': 'PRODUCTO', 'id': True}],
                      [{'tipo': 'PRODUCTO', 'id': ['1']}], [{'tipo': 'PRODUCTO', 'id': 'x' * 41}],
                      [{**PRODUCTO, 'extra': 1}]):
            with self.subTest(valor=valor), self.assertRaises(DestacadosInvalidos):
                normalizar_destacados(valor)

    def test_ids_por_tipo_conserva_el_orden(self):
        lista = [{'tipo': 'PUBLICACION', 'id': '3'}, PRODUCTO, {'tipo': 'PUBLICACION', 'id': '1'}]
        self.assertEqual(ids_por_tipo(lista, TipoDestacado.PUBLICACION), ['3', '1'])
        self.assertEqual(ids_por_tipo(lista, TipoDestacado.PRODUCTO), [PRODUCTO['id']])


class TituloDestacadosTests(SimpleTestCase):
    def test_vacio_vuelve_a_destacados(self):
        for valor in ('', '   ', None):
            with self.subTest(valor=valor):
                self.assertEqual(normalizar_titulo_destacados(valor), TITULO_POR_DEFECTO)

    def test_junta_los_espacios(self):
        self.assertEqual(normalizar_titulo_destacados('  Obras   elegidas '), 'Obras elegidas')

    def test_como_maximo_60_caracteres(self):
        self.assertEqual(len(normalizar_titulo_destacados('a' * 60)), 60)
        with self.assertRaises(TituloDestacadosInvalido):
            normalizar_titulo_destacados('a' * 61)
