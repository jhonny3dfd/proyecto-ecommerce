from django.test import SimpleTestCase

from ecommerce.application.categorias import (
    CategoriaCatalogo, CategoriaNoEncontrada, CategoriasCatalogo, ReferenciasCategorias, RenombrarCategoria,
)
from ecommerce.domain.categorias import CategoriaInvalida


class CategoriasFalsas(CategoriasCatalogo):
    def __init__(self, productos):
        # {id_producto: categoria}
        self.productos = dict(productos)
        self.falla = False

    def listar(self):
        nombres = sorted(set(self.productos.values()))
        return [CategoriaCatalogo(n, sum(1 for c in self.productos.values() if c == n), 0) for n in nombres]

    def renombrar(self, desde, hacia):
        if self.falla:
            raise RuntimeError('Mongo no responde')
        cambiados = [pid for pid, categoria in self.productos.items() if categoria == desde]
        for pid in cambiados:
            self.productos[pid] = hacia
        return len(cambiados)


class ReferenciasFalsas(ReferenciasCategorias):
    def __init__(self, orden=(), planes=None):
        self._orden = list(orden)
        self.planes = {pid: list(c) for pid, c in (planes or {}).items()}
        self.guardados = 0

    def orden(self):
        return list(self._orden)

    def guardar_orden(self, orden):
        self._orden = list(orden)
        self.guardados += 1

    def categorias_de_planes(self):
        return {pid: list(c) for pid, c in self.planes.items()}

    def guardar_categorias_de_plan(self, plan_id, categorias):
        self.planes[plan_id] = list(categorias)
        self.guardados += 1


class RenombrarCategoriaTests(SimpleTestCase):
    def setUp(self):
        self.catalogo = CategoriasFalsas({1: 'Cafes', 2: 'Cafes', 3: 'Packs', 4: 'Promos'})
        self.referencias = ReferenciasFalsas(orden=['Promos', 'Cafes'], planes={7: ['cafes'], 8: ['Packs']})
        self.caso = RenombrarCategoria(self.catalogo, self.referencias)

    def test_renombra_productos_orden_y_planes(self):
        resultado = self.caso.ejecutar('Cafes', 'Cafés')

        self.assertEqual((resultado.hacia, resultado.une, resultado.productos), ('Cafés', False, 2))
        self.assertEqual(self.catalogo.productos, {1: 'Cafés', 2: 'Cafés', 3: 'Packs', 4: 'Promos'})
        self.assertEqual(self.referencias.orden(), ['Promos', 'Cafés'])
        self.assertEqual(self.referencias.planes, {7: ['Cafés'], 8: ['Packs']})

    def test_unir_con_otra_usa_su_escritura(self):
        resultado = self.caso.ejecutar('Promos', 'PACKS')

        self.assertEqual((resultado.hacia, resultado.une, resultado.productos), ('Packs', True, 1))
        self.assertEqual(sorted(c.nombre for c in self.catalogo.listar()), ['Cafes', 'Packs'])
        self.assertEqual(self.referencias.orden(), ['Packs', 'Cafes'])

    def test_rechaza_una_categoria_que_ya_no_existe_o_un_nombre_invalido(self):
        with self.assertRaises(CategoriaNoEncontrada):
            self.caso.ejecutar('Té', 'Tés')
        with self.assertRaises(CategoriaInvalida):
            self.caso.ejecutar('Cafes', ' ')
        self.assertEqual(self.referencias.guardados, 0)

    def test_si_fallan_los_productos_se_puede_reintentar(self):
        self.catalogo.falla = True
        with self.assertRaises(RuntimeError):
            self.caso.ejecutar('Cafes', 'Cafés')
        # Las referencias ya cambiaron, pero la categoría sigue en sus productos: reintentar termina el cambio
        self.catalogo.falla = False
        resultado = self.caso.ejecutar('Cafes', 'Cafés')
        self.assertEqual(resultado.productos, 2)
        self.assertEqual(self.referencias.orden(), ['Promos', 'Cafés'])
        self.assertEqual(self.referencias.planes[7], ['Cafés'])
