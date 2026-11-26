from unittest.mock import patch

from django.test import SimpleTestCase

from .views import obtener_filtros_catalogo


class OpcionesColeccionesTests(SimpleTestCase):
    def obtener_opciones(self, productos):
        with (
            patch('ecommerce.infrastructure.catalogo.views.Producto.objects') as manager,
            patch('ecommerce.infrastructure.catalogo.views.Producto._get_collection',
                  side_effect=AssertionError('No debe acceder a MongoDB')),
        ):
            # Simula el predicado aplicado por Mongo, sin tocar bases de datos.
            manager.filter.side_effect = lambda **criterios: self.consulta_filtrada(
                productos, criterios, manager)
            resultado = obtener_filtros_catalogo([])
            manager.filter.assert_called_once_with(activo=True, publicado=True)
            return resultado

    def consulta_filtrada(self, productos, criterios, manager):
        consulta = manager.filter.return_value
        consulta.only.return_value.as_pymongo.return_value = [
            producto for producto in productos
            if all(producto.get(campo) == valor for campo, valor in criterios.items())
        ]
        return consulta

    def producto(self, colecciones):
        return dict(activo=True, publicado=True, categoria='Tecnologia',
                    atributos_globales={'color': 'Azul'}, colecciones=colecciones)

    def test_deduplica_entre_productos_y_conserva_nombres_de_forma_determinista(self):
        productos = [self.producto(['cyber', 'iphone']),
                     self.producto([' Cyber ', 'iPhone']), self.producto(['Cyber'])]
        for lista in (productos, list(reversed(productos))):
            with self.subTest(orden=lista):
                resultado = self.obtener_opciones(lista)
                self.assertEqual(resultado['colecciones'], ['Cyber', 'iPhone'])
                self.assertEqual(resultado['categorias'], ['Tecnologia'])
                self.assertEqual(resultado['atributos'], {'Tecnologia': {'color': ['Azul']}})
        self.assertEqual(productos[0]['colecciones'], ['cyber', 'iphone'])

    def test_excluye_colecciones_de_inactivos_y_despublicados(self):
        publicados = self.producto(['Cyber'])
        borrador = {**self.producto(['Solo borrador']), 'publicado': False}
        inactivo = {**self.producto(['Solo inactivo']), 'activo': False}
        self.assertEqual(self.obtener_opciones([publicados, borrador, inactivo])['colecciones'], ['Cyber'])

    def test_sin_productos_publicados_no_hay_opciones(self):
        self.assertEqual(self.obtener_opciones([])['colecciones'], [])
