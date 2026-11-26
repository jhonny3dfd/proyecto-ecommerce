"""Catalogue regressions through real MongoDB and Django API endpoints."""
from datetime import datetime, timezone
import os
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.urls import reverse
from pymongo import MongoClient, monitoring
from rest_framework.test import APITestCase

from ecommerce.infrastructure.usuarios.tests.factories import create_user
from .documents import Producto, Variante


class CommandCounter(monitoring.CommandListener):
    def __init__(self):
        self.commands = []

    def started(self, event):
        self.commands.append(dict(event.command))

    def succeeded(self, event):
        pass

    def failed(self, event):
        pass


class CatalogoConsultasRealesTests(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.counter = CommandCounter()
        mongo = MongoClient(os.environ.get('MONGO_TEST_URI', settings.MONGO_URI),
                            event_listeners=[cls.counter], serverSelectionTimeoutMS=5000)
        cls.addClassCleanup(mongo.close)
        database = 'test_ecode_scrum149_' + uuid4().hex
        cls.addClassCleanup(mongo.drop_database, database)
        cls.collection = mongo[database]['productos']
        binding = patch.object(Producto, '_get_collection', return_value=cls.collection)
        binding.start()
        cls.addClassCleanup(binding.stop)
        Producto.ensure_indexes()

    @classmethod
    def setUpTestData(cls):
        cls.admin = create_user('consultas149@example.test', rol='ADMIN')

    def setUp(self):
        self.collection.delete_many({})
        for i in range(76):
            Producto(nombre=f'QA {i:03}', categoria=f'Categoria {i % 3}',
                     fecha_creacion=datetime(2026, 1, 1, tzinfo=timezone.utc),
                     activo=i != 75, publicado=i != 74,
                     atributos_globales={'color': 'Solo otra pagina' if i == 0 else 'Azul',
                                         'capacidad_gb': 128 if i % 2 else 64,
                                         'vacio': None, 'espacios': '  '},
                     variantes=[Variante(sku=f'QA149-{i}', precio=1000 + i,
                                         precio_oferta=500 if i == 0 else None, stock=5)]).save()
        self.counter.commands.clear()

    def get(self, **params):
        response = self.client.get(reverse('lista_productos'), params)
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_opciones_globales_con_una_lectura_proyectada(self):
        response = self.client.get(reverse('filtros_catalogo'))
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(data['categorias'], ['Categoria 0', 'Categoria 1', 'Categoria 2'])
        self.assertEqual(data['atributos']['Categoria 0']['capacidad_gb'], ['128', '64'])
        self.assertIn('Solo otra pagina', data['atributos']['Categoria 0']['color'])
        self.assertEqual(data['atributos']['Categoria 0']['vacio'], [])
        finds = [c for c in self.counter.commands if 'find' in c]
        self.assertEqual(len(finds), 1)
        self.assertFalse(any('distinct' in c for c in self.counter.commands))
        self.assertEqual(finds[0]['filter'], {'activo': True, 'publicado': True})
        self.assertEqual(finds[0]['projection']['categoria'], 1)
        self.assertEqual(finds[0]['projection']['atributos_globales'], 1)
        self.assertNotIn('variantes', finds[0]['projection'])

    def test_paginacion_opciones_y_visibilidad_publica(self):
        ids = []
        for page in range(1, 5):
            data = self.get(page=page)
            self.assertEqual(data['count'], 74)
            self.assertEqual(data['total_pages'], 4)
            self.assertIn('Solo otra pagina', data['filtros']['atributos']['Categoria 0']['color'])
            ids.extend(p['id'] for p in data['results'])
        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual(len(ids), 74)
        for document in self.collection.find({'$or': [{'activo': False}, {'publicado': False}]}):
            self.assertNotIn(str(document['_id']), ids)
            self.assertEqual(self.client.get(reverse('detalle_producto', args=[document['_id']])).status_code, 404)

    def test_filtros_numericos_texto_y_lista_completa_admin(self):
        self.assertEqual(self.get(atributo_capacidad_gb=128)['count'], 37)
        self.assertEqual(self.get(atributo_color='Solo otra pagina')['count'], 1)
        self.client.force_authenticate(self.admin)
        self.assertEqual(len(self.get(todos='true')), 75)

    def test_cambios_se_reflejan_sin_cache_de_opciones(self):
        product = Producto.objects.get(nombre='QA 000')
        self.client.force_authenticate(self.admin)
        response = self.client.patch(reverse('detalle_producto', args=[product.id]),
                                     {'atributos_globales': {'color': 'Cambio 149'}}, format='json')
        self.assertEqual(response.status_code, 200)
        self.client.force_authenticate(None)
        data = self.get()
        colors = data['filtros']['atributos']['Categoria 0']['color']
        self.assertIn('Cambio 149', colors)
        self.assertNotIn('Solo otra pagina', colors)
        product.reload()
        self.assertEqual(product.atributos_globales['color'], 'Cambio 149')
