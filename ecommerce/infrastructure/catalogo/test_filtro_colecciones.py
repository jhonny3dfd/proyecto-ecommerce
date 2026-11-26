import re
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from .views import ProductoListCreateView


class FiltroColeccionesLiteralTests(SimpleTestCase):
    """Ejercita la vista sin conexiones ni escrituras en bases de datos."""

    def comprobar_filtro_literal(self, nombre, patron_esperado, no_coinciden):
        queryset = MagicMock()
        queryset.filter.return_value = queryset
        queryset.order_by.return_value = queryset
        queryset.count.return_value = 3
        queryset.__getitem__.return_value = []

        with (
            patch('ecommerce.infrastructure.catalogo.views.Producto.objects') as productos,
            patch('ecommerce.infrastructure.catalogo.views.Producto._get_collection',
                  side_effect=AssertionError('No debe acceder a MongoDB')),
            patch('ecommerce.infrastructure.catalogo.views.ConfiguracionGlobal.objects') as config,
            patch('ecommerce.infrastructure.catalogo.views.obtener_filtros_catalogo', return_value={}),
            patch('ecommerce.infrastructure.catalogo.views.obtener_versiones_publicadas', return_value={}),
            patch('ecommerce.infrastructure.catalogo.views.ProductoSerializer') as serializer,
        ):
            productos.filter.return_value = queryset
            config.filter.return_value.values.return_value.first.return_value = {}
            serializer.return_value.data = []
            request = APIRequestFactory().get('/api/catalogo/productos/', {
                'coleccion': nombre,
                'categoria': 'Electronica',
                'atributo_color': 'Azul',
                'page': 2,
                'page_size': 2,
                'orden': 'nombre',
            })
            response = ProductoListCreateView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        queryset.filter.assert_any_call(publicado=True)
        queryset.filter.assert_any_call(categoria='Electronica')
        queryset.filter.assert_any_call(atributos_globales__color='Azul')
        queryset.filter.assert_any_call(colecciones__iregex=patron_esperado)
        queryset.order_by.assert_called_once_with('nombre', 'id')
        queryset.__getitem__.assert_called_once_with(slice(2, 4))
        self.assertEqual(response.data['current_page'], 2)
        self.assertEqual(response.data['count'], 3)
        patron = next(
            llamada.kwargs['colecciones__iregex']
            for llamada in queryset.filter.call_args_list
            if 'colecciones__iregex' in llamada.kwargs
        )
        regex = re.compile(patron, re.IGNORECASE)
        self.assertIsNotNone(regex.search(nombre.swapcase()))
        for otro_nombre in no_coinciden:
            with self.subTest(otro_nombre=otro_nombre):
                self.assertIsNone(regex.search(otro_nombre))

    def test_cyber_mas_es_literal(self):
        self.comprobar_filtro_literal('Cyber+', r'^Cyber\+$', ['Cyber', 'Cyberrr', 'Otra'])

    def test_punto_asterisco_no_es_comodin(self):
        self.comprobar_filtro_literal('.*', r'^\.\*$', ['Cyber', 'Verano', ''])

    def test_corchete_es_literal_y_no_rompe_la_regex(self):
        self.comprobar_filtro_literal('[', r'^\[$', ['Cyber', '[]', ''])
