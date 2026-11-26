from datetime import datetime, timezone

from django.urls import reverse
from rest_framework.test import APITestCase

from ecommerce.infrastructure.usuarios.tests.factories import create_user
from ecommerce.infrastructure.ventas.models import ConfiguracionGlobal, PlanSuscripcion

from .documents import Producto, Variante
from .tests import usar_mongo_de_prueba


class RenombrarCategoriaApiTests(APITestCase):
    """RF-03.2: el admin renombra o une categorías; cambian sus productos, el orden del catálogo y los planes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Base Mongo temporal: el catálogo de la base real nunca se toca (AGENTS.md §11)
        usar_mongo_de_prueba(cls)

    def setUp(self):
        Producto._get_collection().delete_many({})
        self.admin = create_user(email='admin-categorias@example.test', rol='ADMIN')
        self.client.force_authenticate(self.admin)
        self.contador = 0
        for categoria, publicado in (('Cafes', True), ('Cafes', False), ('Packs', True), ('Promos', True)):
            self.producto(categoria, publicado)
        ConfiguracionGlobal.objects.update_or_create(pk=1, defaults={'orden_categorias': ['Promos', 'Cafes']})
        self.plan = PlanSuscripcion.objects.create(nombre='Café del mes', precio=14990, frecuencia_semanas=4,
                                                   categorias=['cafes'])

    def tearDown(self):
        Producto._get_collection().delete_many({})

    def producto(self, categoria, publicado=True, activo=True):
        self.contador += 1
        Producto(nombre=f'Producto {self.contador}', categoria=categoria, publicado=publicado, activo=activo,
                 fecha_creacion=datetime.now(timezone.utc),
                 variantes=[Variante(sku=f'CAT-{self.contador}', precio=1000, stock=1)]).save()

    def categorias_de_productos(self):
        return sorted(Producto._get_collection().distinct('categoria'))

    def test_lista_las_categorias_con_sus_productos(self):
        respuesta = self.client.get(reverse('categorias_catalogo'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['categorias'], [
            {'nombre': 'Cafes', 'productos': 2, 'publicados': 1},
            {'nombre': 'Packs', 'productos': 1, 'publicados': 1},
            {'nombre': 'Promos', 'productos': 1, 'publicados': 1},
        ])

    def test_renombra_en_productos_orden_y_planes(self):
        respuesta = self.client.post(reverse('renombrar_categoria'), {'desde': 'Cafes', 'hacia': ' Cafés '}, format='json')

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual((respuesta.data['hacia'], respuesta.data['une'], respuesta.data['productos']), ('Cafés', False, 2))
        self.assertEqual(self.categorias_de_productos(), ['Cafés', 'Packs', 'Promos'])
        self.assertEqual(ConfiguracionGlobal.objects.get(pk=1).orden_categorias, ['Promos', 'Cafés'])
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.categorias, ['Cafés'])
        self.assertIn({'nombre': 'Cafés', 'productos': 2, 'publicados': 1}, respuesta.data['categorias'])

    def test_unir_con_otra_existente(self):
        # Un producto inactivo también cambia, para que la categoría no reaparezca
        self.producto('Promos', activo=False)
        respuesta = self.client.post(reverse('renombrar_categoria'), {'desde': 'Promos', 'hacia': 'packs'}, format='json')

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual((respuesta.data['hacia'], respuesta.data['une'], respuesta.data['productos']), ('Packs', True, 2))
        self.assertEqual(self.categorias_de_productos(), ['Cafes', 'Packs'])
        self.assertEqual(ConfiguracionGlobal.objects.get(pk=1).orden_categorias, ['Packs', 'Cafes'])

    def test_errores_que_ve_el_admin(self):
        url = reverse('renombrar_categoria')
        casos = (({'desde': 'Cafes', 'hacia': ''}, 'Escribe el nombre nuevo'),
                 ({'desde': 'Cafes', 'hacia': 'Cafes'}, 'distinto al actual'),
                 ({'desde': 'Té', 'hacia': 'Tés'}, 'ya no existe'),
                 ({'hacia': 'Tés'}, 'Elige la categoría'))
        for datos, mensaje in casos:
            with self.subTest(datos=datos):
                respuesta = self.client.post(url, datos, format='json')
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn(mensaje, respuesta.data['detail'])
        self.assertEqual(self.categorias_de_productos(), ['Cafes', 'Packs', 'Promos'])

    def test_solo_el_admin(self):
        comprador = create_user(email='comprador-categorias@example.test', rol='COMPRADOR')
        self.client.force_authenticate(comprador)
        self.assertEqual(self.client.get(reverse('categorias_catalogo')).status_code, 403)
        respuesta = self.client.post(reverse('renombrar_categoria'), {'desde': 'Cafes', 'hacia': 'X'}, format='json')
        self.assertEqual(respuesta.status_code, 403)
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(reverse('categorias_catalogo')).status_code, (401, 403))
        self.assertEqual(self.categorias_de_productos(), ['Cafes', 'Packs', 'Promos'])
