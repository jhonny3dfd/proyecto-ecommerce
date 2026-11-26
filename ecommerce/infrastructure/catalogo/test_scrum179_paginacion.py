import os
from unittest.mock import MagicMock, patch
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_project.settings')
django.setup()

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIRequestFactory

from ecommerce.infrastructure.catalogo.documents import Producto
from ecommerce.infrastructure.catalogo.views import (
    FiltrosCatalogoView,
    ProductoListCreateView,
    obtener_filtros_catalogo,
)


class IndicesMongoCatalogoTests(SimpleTestCase):
    """
    Criterio de Aceptación 4 (SCRUM-179):
    Hay índices en MongoDB sobre activo, publicado, categoría y fecha de creación.
    Los atributos usados en filtros también se indexan.
    """

    def test_indices_definidos_en_documento_producto(self):
        indexes = Producto._meta.get('indexes', [])
        # Validar índices individuales
        self.assertIn('activo', indexes)
        self.assertIn('publicado', indexes)
        self.assertIn('categoria', indexes)
        self.assertIn('fecha_creacion', indexes)

        # Validar índices compuestos de alta concurrencia
        self.assertTrue(
            any(('activo', 'publicado', 'categoria') == idx for idx in indexes)
        )
        self.assertTrue(
            any(('activo', 'publicado', '-fecha_creacion') == idx for idx in indexes)
        )
        self.assertTrue(
            any(('activo', 'publicado', 'precio_minimo_vigente') == idx for idx in indexes)
        )
        self.assertTrue(
            any(('activo', 'publicado', '-precio_minimo_vigente') == idx for idx in indexes)
        )

        # Validar cobertura de índices sobre rutas internas y dinámicas de atributos (E03)
        index_specs = Producto._meta.get('index_specs', [])
        campos_indexados = [spec.get('fields') for spec in index_specs if 'fields' in spec]

        self.assertTrue(
            any(
                [('activo', 1), ('publicado', 1), ('categoria', 1), ('atributos_globales.color', 1)] == f
                for f in campos_indexados
            ),
            "Falta índice compuesto sobre activo, publicado, categoria y atributos_globales.color"
        )
        self.assertTrue(
            any([('atributos_globales.$**', 1)] == f for f in campos_indexados),
            "Falta índice comodín sobre atributos_globales.$**"
        )


class PaginacionYFiltrosCatalogoTests(TestCase):
    """
    Criterios de Aceptación 1, 2, 3 y 5 (SCRUM-179):
    - Paginación de 24 en servidor.
    - Filtros y orden aplicados en el servidor sobre el queryset.
    - Opciones de filtros del servidor para no perder opciones de otras páginas.
    - Soporte de lista completa con ?todos=true para inventario y formulario.
    """

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = ProductoListCreateView.as_view()

    @patch('ecommerce.infrastructure.catalogo.views.obtener_filtros_catalogo')
    @patch('ecommerce.infrastructure.catalogo.documents.Producto.objects')
    def test_respuesta_paginada_contiene_metadatos_y_resultados(self, mock_objects, mock_filtros):
        mock_filtros.return_value = {'categorias': ['Calzado'], 'atributos': {}}

        # Simular queryset mockeado con 50 productos
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.count.return_value = 50
        mock_qs.__getitem__.return_value = []
        mock_objects.filter.return_value = mock_qs

        request = self.factory.get('/api/catalogo/productos/?page=2&page_size=24')
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn('count', response.data)
        self.assertIn('total_pages', response.data)
        self.assertIn('current_page', response.data)
        self.assertIn('page_size', response.data)
        self.assertIn('results', response.data)
        self.assertIn('filtros', response.data)

        self.assertEqual(response.data['count'], 50)
        self.assertEqual(response.data['total_pages'], 3)
        self.assertEqual(response.data['current_page'], 2)
        self.assertEqual(response.data['page_size'], 24)

    @patch('ecommerce.infrastructure.catalogo.documents.Producto.objects')
    def test_parametro_todos_retorna_lista_plana_para_inventario_y_formulario(self, mock_objects):
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_objects.filter.return_value = mock_qs

        with patch('ecommerce.infrastructure.catalogo.views.ProductoSerializer') as mock_serializer:
            mock_serializer.return_value.data = [{'id': '1', 'nombre': 'Prod 1'}]

            request = self.factory.get('/api/catalogo/productos/?todos=true')
            response = self.view(request)

            self.assertEqual(response.status_code, 200)
            self.assertIsInstance(response.data, list)
            self.assertEqual(len(response.data), 1)

    @patch('ecommerce.infrastructure.catalogo.documents.Producto.objects')
    def test_filtro_categoria_se_aplica_al_queryset_en_servidor(self, mock_objects):
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.count.return_value = 10
        mock_qs.__getitem__.return_value = []
        mock_objects.filter.return_value = mock_qs

        request = self.factory.get('/api/catalogo/productos/?categoria=Electronica')
        self.view(request)

        # Debe filtrarse en el queryset de MongoDB
        mock_qs.filter.assert_any_call(categoria='Electronica')

    @patch('ecommerce.infrastructure.catalogo.documents.Producto.objects')
    def test_filtro_atributos_texto_y_numerico_en_servidor(self, mock_objects):
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.count.return_value = 5
        mock_qs.__getitem__.return_value = []
        mock_objects.filter.return_value = mock_qs

        # 1. Filtro de texto simple
        request_texto = self.factory.get('/api/catalogo/productos/?atributo_color=Azul')
        self.view(request_texto)
        mock_qs.filter.assert_any_call(atributos_globales__color='Azul')

        # 2. Filtro numérico (E02): debe probar tanto string como int para coincidir con DictField
        request_num = self.factory.get('/api/catalogo/productos/?atributo_capacidad_gb=128')
        self.view(request_num)
        mock_qs.filter.assert_any_call(atributos_globales__capacidad_gb__in=['128', 128])

    @patch('ecommerce.infrastructure.catalogo.documents.Producto.objects')
    def test_orden_precio_asc_y_desc_en_servidor(self, mock_objects):
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.count.return_value = 10
        mock_qs.__getitem__.return_value = []
        mock_objects.filter.return_value = mock_qs

        # Precio ascendente (E01)
        request_asc = self.factory.get('/api/catalogo/productos/?orden=precio-asc')
        self.view(request_asc)
        mock_qs.order_by.assert_called_with('precio_minimo_vigente', 'id')

        # Precio descendente (E01)
        request_desc = self.factory.get('/api/catalogo/productos/?orden=precio-desc')
        self.view(request_desc)
        mock_qs.order_by.assert_called_with('-precio_minimo_vigente', 'id')

        # Más nuevos
        request_recientes = self.factory.get('/api/catalogo/productos/?orden=recientes')
        self.view(request_recientes)
        mock_qs.order_by.assert_called_with('-fecha_creacion', 'id')

        # Nombre A-Z
        request_nombre = self.factory.get('/api/catalogo/productos/?orden=nombre')
        self.view(request_nombre)
        mock_qs.order_by.assert_called_with('nombre', 'id')

    def test_calculo_precio_minimo_vigente_con_ofertas_y_variantes(self):
        """
        Validación directa del requerimiento E01:
        - Oferta mil: normal $10.000 y oferta válida $1.000 -> precio vigente $1.000
        - Normal dos mil: $2.000 -> precio vigente $2.000
        - Desde mil: variantes de $1.000 y $90.000 -> precio vigente $1.000
        """
        from ecommerce.infrastructure.catalogo.documents import Variante

        # Caso 1: Producto con oferta válida
        p_oferta = Producto(
            nombre='Oferta mil',
            categoria='QA179 Precios',
            variantes=[Variante(sku='SKU-OFERTA', precio='10000.00', precio_oferta='1000.00')]
        )
        p_oferta.actualizar_precio_minimo_vigente()
        self.assertEqual(float(p_oferta.precio_minimo_vigente), 1000.0)

        # Caso 2: Producto sin oferta
        p_normal = Producto(
            nombre='Normal dos mil',
            categoria='QA179 Precios',
            variantes=[Variante(sku='SKU-NORMAL', precio='2000.00')]
        )
        p_normal.actualizar_precio_minimo_vigente()
        self.assertEqual(float(p_normal.precio_minimo_vigente), 2000.0)

        # El producto de oferta ($1.000) debe preceder al de $2.000 en ascendente
        self.assertLess(float(p_oferta.precio_minimo_vigente), float(p_normal.precio_minimo_vigente))

        # Caso 3: Producto con múltiples variantes ("Desde mil")
        p_variantes = Producto(
            nombre='Desde mil',
            categoria='QA179 Precios',
            variantes=[
                Variante(sku='SKU-BARATO', precio='1000.00'),
                Variante(sku='SKU-CARO', precio='90000.00'),
            ]
        )
        p_variantes.actualizar_precio_minimo_vigente()
        self.assertEqual(float(p_variantes.precio_minimo_vigente), 1000.0)

        # En orden descendente, productos con precio $8.300 deben quedar por encima de $1.000
        p_caro = Producto(
            nombre='Caro ocho mil',
            categoria='QA179 Precios',
            variantes=[Variante(sku='SKU-CARO-8300', precio='8300.00')]
        )
        p_caro.actualizar_precio_minimo_vigente()
        self.assertGreater(float(p_caro.precio_minimo_vigente), float(p_variantes.precio_minimo_vigente))

    def test_actualizar_producto_sincroniza_precio_minimo_vigente_en_set_atomico(self):
        """
        Validación directa del requerimiento de subsanación:
        Al editar variantes, ofertas o precios mediante actualizar_producto(),
        precio_minimo_vigente debe incluirse en el $set atómico de MongoDB.
        """
        from ecommerce.infrastructure.catalogo.documents import Variante
        from ecommerce.infrastructure.catalogo.image_adapters import actualizar_producto

        from datetime import datetime, timezone

        p = Producto(
            id='507f1f77bcf86cd799439011',
            nombre='Producto Editable',
            categoria='QA179 Precios',
            fecha_creacion=datetime.now(timezone.utc),
            imagenes=[],
            variantes=[Variante(sku='SKU-INIT', precio='10000.00')]
        )
        p.actualizar_precio_minimo_vigente()
        self.assertEqual(float(p.precio_minimo_vigente), 10000.0)

        with patch('ecommerce.infrastructure.catalogo.image_adapters.modificar_con_referencias') as mock_modificar:
            mock_modificar.return_value = p
            cambios = {
                'variantes': [
                    {'sku': 'SKU-INIT', 'precio': '10000.00', 'precio_oferta': '1500.00', 'stock': 5}
                ]
            }
            actualizado = actualizar_producto(p, cambios)

            # Verificar que modificar_con_referencias recibió precio_minimo_vigente en el $set
            self.assertTrue(mock_modificar.called)
            actualizacion_arg = mock_modificar.call_args[0][1]
            self.assertIn('$set', actualizacion_arg)
            self.assertIn('precio_minimo_vigente', actualizacion_arg['$set'])
            self.assertEqual(float(actualizacion_arg['$set']['precio_minimo_vigente']), 1500.0)
            self.assertEqual(float(p.precio_minimo_vigente), 1500.0)

    def test_orden_catalogo_con_mas_de_24_productos_tras_edicion(self):
        """
        Simulación de 26 productos:
        - 24 productos con precios entre $3.000 y $5.300
        - 1 producto "Normal dos mil" con $2.000
        - 1 producto "Oferta editada" originalmente creado en $10.000 y editado a oferta de $1.000
        """
        from ecommerce.infrastructure.catalogo.documents import Variante

        productos = []
        # 1 producto normal $2.000
        p_dos_mil = Producto(
            id='507f1f77bcf86cd799439001',
            nombre='Normal dos mil',
            categoria='QA179 Precios',
            variantes=[Variante(sku='SKU-2000', precio='2000.00')]
        )
        p_dos_mil.actualizar_precio_minimo_vigente()
        productos.append(p_dos_mil)

        # 24 productos entre $3.000 y $5.300
        for i in range(24):
            precio = 3000.0 + (i * 100.0)
            p = Producto(
                id=f'507f1f77bcf86cd7994391{i:02d}',
                nombre=f'Producto {i+1}',
                categoria='QA179 Precios',
                variantes=[Variante(sku=f'SKU-GEN-{i}', precio=f'{precio:.2f}')]
            )
            p.actualizar_precio_minimo_vigente()
            productos.append(p)

        # Producto editado: originalmente $10.000, ahora con oferta $1.000
        p_editado = Producto(
            id='507f1f77bcf86cd799439002',
            nombre='Oferta editada',
            categoria='QA179 Precios',
            variantes=[Variante(sku='SKU-OFERTA', precio='10000.00', precio_oferta='1000.00')]
        )
        p_editado.actualizar_precio_minimo_vigente()
        productos.append(p_editado)

        self.assertEqual(len(productos), 26)

        # 1. En orden ascendente (menor a mayor):
        ordenados_asc = sorted(productos, key=lambda x: float(x.precio_minimo_vigente))
        # Página 1 (primeros 24 productos)
        pagina_1_asc = ordenados_asc[:24]
        # "Oferta editada" ($1.000) debe ser el primero de la página 1
        self.assertEqual(pagina_1_asc[0].nombre, 'Oferta editada')
        self.assertEqual(float(pagina_1_asc[0].precio_minimo_vigente), 1000.0)
        # "Normal dos mil" ($2.000) debe ser el segundo
        self.assertEqual(pagina_1_asc[1].nombre, 'Normal dos mil')
        self.assertEqual(float(pagina_1_asc[1].precio_minimo_vigente), 2000.0)

        # 2. En orden descendente (mayor a menor):
        ordenados_desc = sorted(productos, key=lambda x: float(x.precio_minimo_vigente), reverse=True)
        # Página 1 (primeros 24 productos)
        pagina_1_desc = ordenados_desc[:24]
        # Página 2 (últimos 2 productos)
        pagina_2_desc = ordenados_desc[24:]

        # "Oferta editada" ($1.000) debe estar en la página 2, detrás de todos los productos mayores
        self.assertNotIn(p_editado, pagina_1_desc)
        self.assertIn(p_editado, pagina_2_desc)
        self.assertEqual(pagina_2_desc[-1].nombre, 'Oferta editada')

    def test_orden_catalogo_a_gran_escala_100_productos_5_paginas(self):
        """
        Escalabilidad a gran escala con 100 productos (5 páginas completas):
        - 99 productos escalonados entre $2.000 y $9.900
        - 1 producto "Original Caro" creado en $15.000
        - Se edita "Original Caro" a $500 con oferta
        - En asc: se mueve de Página 5 a Página 1 (Posición 1)
        - En desc: se mueve a Página 5 (Posición 100)
        """
        from ecommerce.infrastructure.catalogo.documents import Variante

        productos = []
        for i in range(99):
            precio = 2000.0 + (i * 80.0)
            p = Producto(
                id=f'507f1f77bcf86cd7994400{i:02d}',
                nombre=f'Item {i+1}',
                categoria='QA179 Escala',
                variantes=[Variante(sku=f'SKU-ESC-{i}', precio=f'{precio:.2f}')]
            )
            p.actualizar_precio_minimo_vigente()
            productos.append(p)

        # Producto originalmente caro en $15.000 (estaría al final en asc)
        p_caro = Producto(
            id='507f1f77bcf86cd799440099',
            nombre='Original Caro',
            categoria='QA179 Escala',
            variantes=[Variante(sku='SKU-CARO-15K', precio='15000.00')]
        )
        p_caro.actualizar_precio_minimo_vigente()
        productos.append(p_caro)

        self.assertEqual(len(productos), 100)

        # Antes de la edición, en asc: está en la página 5
        antes_asc = sorted(productos, key=lambda x: float(x.precio_minimo_vigente))
        self.assertEqual(antes_asc[-1].nombre, 'Original Caro')

        # Se edita con oferta a $500
        p_caro.variantes[0].precio_oferta = 500.0
        p_caro.actualizar_precio_minimo_vigente()
        self.assertEqual(float(p_caro.precio_minimo_vigente), 500.0)

        # 1. En orden ascendente tras edición:
        tras_asc = sorted(productos, key=lambda x: float(x.precio_minimo_vigente))
        pagina_1_asc = tras_asc[:24]
        # Pasa inmediatamente a la Página 1, primera posición absoluta
        self.assertEqual(pagina_1_asc[0].nombre, 'Original Caro')
        self.assertEqual(float(pagina_1_asc[0].precio_minimo_vigente), 500.0)

        # 2. En orden descendente tras edición:
        tras_desc = sorted(productos, key=lambda x: float(x.precio_minimo_vigente), reverse=True)
        pagina_5_desc = tras_desc[96:]  # Última página de 4 elementos
        self.assertEqual(len(pagina_5_desc), 4)
        # Queda al final de la última página (página 5)
        self.assertEqual(pagina_5_desc[-1].nombre, 'Original Caro')

    @patch('ecommerce.infrastructure.catalogo.views.obtener_filtros_catalogo')
    def test_endpoint_filtros_catalogo_publico(self, mock_filtros):
        mock_filtros.return_value = {
            'categorias': ['Calzado', 'Ropa'],
            'atributos': {'Ropa': {'talla': ['S', 'M', 'L']}},
        }
        view_filtros = FiltrosCatalogoView.as_view()
        request = self.factory.get('/api/catalogo/filtros/')
        response = view_filtros(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn('categorias', response.data)
        self.assertIn('atributos', response.data)
        self.assertEqual(response.data['categorias'], ['Calzado', 'Ropa'])
