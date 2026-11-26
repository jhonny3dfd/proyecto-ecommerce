import re
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from mongoengine.queryset import QuerySet
from rest_framework.test import APIRequestFactory
from rest_framework_simplejwt.tokens import RefreshToken

from ecommerce.infrastructure.usuarios.models import Usuario
from .documents import Producto
from .views import ProductoListCreateView


class ConsultaEnMemoria:
    """Sustituye la persistencia; registra cuándo filtra, ordena y pagina la vista."""

    _query = None  # El orden por precio utiliza la alternativa sin agregación.

    def __init__(self, productos, eventos):
        self.productos = productos
        self.eventos = eventos

    def filter(self, **criterios):
        self.eventos.append('filtrar')

        def coincide(producto, clave, valor):
            if clave == 'colecciones__iregex':
                return any(re.search(valor, nombre, re.I) for nombre in producto['colecciones'])
            partes = clave.split('__')
            esperado_en_lista = partes[-1] == 'in'
            if esperado_en_lista:
                partes.pop()
            actual = producto
            for parte in partes:
                actual = actual.get(parte)
            return actual in valor if esperado_en_lista else actual == valor

        return ConsultaEnMemoria([
            p for p in self.productos if all(coincide(p, k, v) for k, v in criterios.items())
        ], self.eventos)

    def order_by(self, *campos):
        self.eventos.append('ordenar')
        productos = self.productos[:]
        for campo in reversed(campos):
            productos.sort(key=lambda p: p[campo.lstrip('-')], reverse=campo.startswith('-'))
        return ConsultaEnMemoria(productos, self.eventos)

    def count(self):
        self.eventos.append('contar')
        return len(self.productos)

    def __getitem__(self, rango):
        self.eventos.append('paginar')
        return self.productos[rango]

    def __iter__(self):
        return iter(self.productos)


class FiltrosCombinadosSinBaseTests(SimpleTestCase):
    def setUp(self):
        self.productos = [self.producto(i, nombre) for i, nombre in (
            (5, 'Zeta'), (2, 'Alfa'), (4, 'Alfa'), (1, 'Beta'), (3, 'Gamma'))]
        self.productos += [
            self.producto(6, 'Otra categoria', categoria='Ropa'),
            self.producto(7, 'Otro color', atributos_globales={'color': 'Rojo', 'capacidad': 128}),
            self.producto(8, 'Otra coleccion', colecciones=['Navidad']),
            self.producto(9, 'Inactivo', activo=False),
            self.producto(10, 'Borrador', publicado=False),
        ]

    def producto(self, indice, nombre, **cambios):
        return dict({
            'id': indice, 'nombre': nombre, 'categoria': 'Electronica',
            'colecciones': ['cyber' if indice % 2 else 'Cyber'],
            'atributos_globales': {'color': 'Azul', 'capacidad': 128},
            'activo': True, 'publicado': True, 'fecha_creacion': indice,
            'precio_minimo_vigente': indice * 100,
        }, **cambios)

    def consultar(self, parametros, rol=None):
        self.eventos = []
        consulta = ConsultaEnMemoria(self.productos, self.eventos)
        with (
            patch('ecommerce.infrastructure.catalogo.views.Producto.objects') as manager,
            patch.object(Producto, '_get_collection', side_effect=AssertionError('MongoDB bloqueado')),
            patch('ecommerce.infrastructure.catalogo.views.ConfiguracionGlobal.objects') as config,
            patch('ecommerce.infrastructure.catalogo.views.obtener_filtros_catalogo', return_value={}),
            patch('ecommerce.infrastructure.catalogo.views.obtener_versiones_publicadas', return_value={}),
            patch('ecommerce.infrastructure.catalogo.views.ProductoSerializer',
                  side_effect=lambda datos, **kwargs: SimpleNamespace(data=list(datos))),
            patch.object(Usuario.objects, 'get') as obtener_usuario,
        ):
            manager.filter.side_effect = consulta.filter
            config.filter.return_value.values.return_value.first.return_value = {}
            headers = {}
            if rol:
                usuario = Usuario(pk=1, email='filtros@example.test', rol=rol, is_active=True)
                obtener_usuario.return_value = usuario
                headers['HTTP_AUTHORIZATION'] = f'Bearer {RefreshToken.for_user(usuario).access_token}'
            request = APIRequestFactory().get('/api/catalogo/productos/', parametros, **headers)
            response = ProductoListCreateView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        return response.data

    def ids(self, productos):
        return [p['id'] for p in productos]

    def test_todos_y_sin_paginar_respetan_coleccion_y_conservan_lista_y_orden(self):
        for bandera in ('todos', 'sin_paginar'):
            with self.subTest(bandera=bandera):
                datos = self.consultar({bandera: 'true', 'coleccion': 'CYBER',
                                        'orden': 'nombre', 'page': 2, 'page_size': 1})
                self.assertIsInstance(datos, list)
                self.assertEqual(self.ids(datos), [5, 2, 4, 1, 3, 6, 7])
                self.assertNotIn('ordenar', self.eventos)
                self.assertNotIn('paginar', self.eventos)

    def test_todos_sin_filtros_conserva_contrato_y_visibilidad_del_inventario(self):
        for rol in (None, 'COMPRADOR', 'ADMIN'):
            with self.subTest(rol=rol):
                datos = self.consultar({'todos': 'true'}, rol)
                esperado = [5, 2, 4, 1, 3, 6, 7, 8] + ([10] if rol == 'ADMIN' else [])
                self.assertEqual(self.ids(datos), esperado)

    def test_combinaciones_de_categoria_y_atributos_en_ambas_rutas(self):
        combinaciones = [
            ({'categoria': 'Electronica'}, [1, 2, 3, 4, 5, 7]),
            ({'atributo_color': 'Azul'}, [1, 2, 3, 4, 5, 6]),
            ({'categoria': 'Electronica', 'atributo_color': 'Azul', 'attr_capacidad': '128'},
             [1, 2, 3, 4, 5]),
        ]
        for extras, esperado in combinaciones:
            for todos in (False, True):
                with self.subTest(extras=extras, todos=todos):
                    parametros = {'coleccion': 'cyber', 'orden': 'nombre', **extras}
                    if todos:
                        parametros['todos'] = 'true'
                    datos = self.consultar(parametros)
                    productos = datos if todos else datos['results']
                    self.assertEqual(sorted(self.ids(productos)), esperado)
                    if not todos:
                        self.assertEqual(datos['count'], len(esperado))

    def test_orden_estable_y_paginacion_sobre_el_conjunto_filtrado(self):
        for orden, esperado in (
            ('nombre', [2, 4, 1, 3, 5]),
            ('recientes', [5, 4, 3, 2, 1]),
            ('precio-asc', [1, 2, 3, 4, 5]),
            ('precio-desc', [5, 4, 3, 2, 1]),
        ):
            encontrados = []
            for pagina in (1, 2, 3, 4):
                with self.subTest(orden=orden, pagina=pagina):
                    datos = self.consultar({
                        'coleccion': 'CYBER', 'categoria': 'Electronica', 'atributo_color': 'Azul',
                        'orden': orden, 'page': pagina, 'page_size': 2,
                    })
                    self.assertEqual(datos['count'], 5)
                    self.assertEqual(datos['total_pages'], 3)
                    self.assertEqual(datos['current_page'], pagina)
                    self.assertEqual(datos['page_size'], 2)
                    self.assertEqual(self.ids(datos['results']), esperado[(pagina - 1) * 2:pagina * 2])
                    encontrados.extend(self.ids(datos['results']))
                    self.assertLess(self.eventos.index('ordenar'), self.eventos.index('contar'))
                    self.assertLess(self.eventos.index('contar'), self.eventos.index('paginar'))
                    self.assertNotIn('filtrar', self.eventos[self.eventos.index('contar'):])
            self.assertEqual(encontrados, esperado)

    def test_publico_y_comprador_no_reciben_inactivos_ni_borradores(self):
        for rol in (None, 'COMPRADOR'):
            for todos in (False, True):
                with self.subTest(rol=rol, todos=todos):
                    parametros = {'coleccion': 'Cyber'}
                    if todos:
                        parametros['todos'] = 'true'
                    datos = self.consultar(parametros, rol)
                    self.assertEqual(sorted(self.ids(datos if todos else datos['results'])),
                                     [1, 2, 3, 4, 5, 6, 7])

    def test_caracteres_especiales_son_literales_en_ambas_rutas(self):
        for nombre in ('Cyber+', '.*', '['):
            self.productos = [self.producto(1, 'Literal', colecciones=[nombre]),
                              self.producto(2, 'No coincide', colecciones=['Cyber'])]
            for todos in (False, True):
                with self.subTest(nombre=nombre, todos=todos):
                    parametros = {'coleccion': nombre.swapcase()}
                    if todos:
                        parametros['todos'] = 'true'
                    datos = self.consultar(parametros)
                    self.assertEqual(self.ids(datos if todos else datos['results']), [1])

    def test_agregaciones_conservan_filtros_y_ordenan_antes_de_paginar(self):
        for orden in ('precio-asc', 'precio-desc', 'destacados'):
            with (
                self.subTest(orden=orden),
                patch('ecommerce.infrastructure.catalogo.views.Producto.objects') as manager,
                patch.object(Producto, '_get_collection') as obtener_coleccion,
                patch('ecommerce.infrastructure.catalogo.views.ConfiguracionGlobal.objects') as config,
                patch('ecommerce.infrastructure.catalogo.views.obtener_filtros_catalogo', return_value={}),
                patch('ecommerce.infrastructure.catalogo.views.obtener_versiones_publicadas', return_value={}),
            ):
                coleccion = obtener_coleccion.return_value
                # Compila el queryset real de MongoEngine; no ejecuta consultas.
                manager.filter.side_effect = QuerySet(Producto, coleccion).filter
                config.filter.return_value.values.return_value.first.return_value = {
                    'orden_categorias': ['Electronica'],
                }
                coleccion.aggregate.return_value = iter([{'total': [{'count': 5}], 'results': []}])
                request = APIRequestFactory().get('/api/catalogo/productos/', {
                    'coleccion': 'Cyber+', 'categoria': 'Electronica', 'atributo_color': 'Azul',
                    'orden': orden, 'page': 2, 'page_size': 2,
                })
                response = ProductoListCreateView.as_view()(request)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data['count'], 5)
                self.assertEqual(response.data['total_pages'], 3)
                coleccion.aggregate.assert_called_once()
                pipeline = coleccion.aggregate.call_args.args[0]
                filtro = pipeline[0]['$match']
                self.assertTrue(filtro['activo'])
                self.assertTrue(filtro['publicado'])
                self.assertEqual(filtro['categoria'], 'Electronica')
                self.assertEqual(filtro['atributos_globales.color'], 'Azul')
                self.assertEqual(filtro['colecciones'].pattern, r'^Cyber\+$')
                self.assertTrue(filtro['colecciones'].flags & re.I)
                self.assertEqual(pipeline[-1]['$facet'], {
                    'total': [{'$count': 'count'}],
                    'results': [{'$skip': 2}, {'$limit': 2}],
                })
                campo = '_orden_categoria' if orden == 'destacados' else '_precio_efectivo'
                direccion = -1 if orden == 'precio-desc' else 1
                self.assertEqual(pipeline[-2]['$sort'][campo], direccion)
                self.assertEqual(pipeline[-2]['$sort']['_id'], 1)
