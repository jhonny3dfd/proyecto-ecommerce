from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.urls import reverse
from pymongo import MongoClient
from rest_framework.test import APITestCase

from ecommerce.infrastructure.usuarios.tests.factories import create_user
from ecommerce.infrastructure.ventas.models import ConfiguracionGlobal
from .documents import Producto, Variante


class OrdenCatalogoTests(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mongo = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
        cls.addClassCleanup(mongo.close)
        database = 'test_orden_catalogo_' + uuid4().hex
        cls.addClassCleanup(mongo.drop_database, database)
        cls.collection = mongo[database]['productos']
        binding = patch.object(Producto, '_get_collection', return_value=cls.collection)
        binding.start()
        cls.addClassCleanup(binding.stop)
        Producto.ensure_indexes()

    def setUp(self):
        self.collection.delete_many({})
        self.config = ConfiguracionGlobal.objects.create(pk=1, nombre_tienda='Tienda')
        self.admin = create_user('orden-admin@example.test', rol='ADMIN')
        for i in range(30):
            Producto(nombre='Empate', categoria='Zeta' if i % 2 else 'Beta',
                     fecha_creacion=datetime(2026, 1, 1, tzinfo=timezone.utc),
                     activo=True, publicado=True,
                     variantes=[Variante(sku=f'ORD-{i}', precio=1000 if i < 15 else 2000)]).save()

    def get(self, **params):
        respuesta = self.client.get(reverse('lista_productos'), params)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.data

    def test_orden_estable_antes_de_paginar_y_eleccion_explicita(self):
        self.config.orden_catalogo = 'precio-desc'
        self.config.save()
        self.assertEqual(self.get()['orden'], 'precio-desc')
        for orden in ['destacados', 'recientes', 'precio-asc', 'precio-desc', 'nombre']:
            with self.subTest(orden=orden):
                paginas = [self.get(orden=orden, page=pagina, page_size=7)['results'] for pagina in range(1, 6)]
                ids = [p['id'] for pagina in paginas for p in pagina]
                direccion = -1 if orden == 'precio-desc' else 1
                campo = 'precio_minimo_vigente' if orden.startswith('precio') else 'nombre' if orden == 'nombre' else 'fecha_creacion'
                if campo == 'fecha_creacion': direccion = -1
                esperados = [str(p['_id']) for p in self.collection.find().sort([(campo, direccion), ('_id', 1)])]
                self.assertEqual(ids, esperados)
                self.assertEqual(len(set(ids)), 30)

    def test_ofertas_y_variantes(self):
        producto = Producto.objects.first()
        producto.variantes = [Variante(sku='OFERTA', precio=9000, precio_oferta=100), Variante(sku='OTRA', precio=12000)]
        producto.save()
        self.assertEqual(self.get(orden='precio-asc')['results'][0]['id'], str(producto.id))
        self.assertNotEqual(self.get(orden='precio-desc')['results'][0]['id'], str(producto.id))

    def test_categoria_de_mas_de_24_productos_continua_en_segunda_pagina(self):
        self.config.orden_categorias = ['Calzado', 'Ropa', 'Accesorios']
        self.config.save()
        self.collection.update_many({}, {'$set': {'categoria': 'Ropa'}})
        for categoria, cantidad in [('Calzado', 30), ('Accesorios', 2), ('Omega', 1), ('Alfa', 1)]:
            for i in range(cantidad):
                Producto(nombre=f'{categoria} {i}', categoria=categoria,
                         fecha_creacion=datetime(2026, 2, 1 + i % 3, tzinfo=timezone.utc),
                         publicado=True, atributos_globales={'color': 'Azul'},
                         variantes=[Variante(sku=f'{categoria}-{i}', precio=1000)]).save()
        with patch.object(self.collection, 'aggregate', wraps=self.collection.aggregate) as agregaciones:
            paginas = [self.get(page=pagina) for pagina in range(1, 4)]
        self.assertEqual(agregaciones.call_count, 3)
        self.assertEqual(paginas[0]['count'], 64)
        self.assertEqual(paginas[0]['total_pages'], 3)
        self.assertEqual([p['categoria'] for p in paginas[0]['results']], ['Calzado'] * 24)
        self.assertEqual([p['categoria'] for p in paginas[1]['results']], ['Calzado'] * 6 + ['Ropa'] * 18)
        self.assertEqual([p['categoria'] for p in paginas[2]['results']], ['Ropa'] * 12 + ['Accesorios'] * 2 + ['Alfa', 'Omega'])
        documentos = list(self.collection.find().sort([('fecha_creacion', -1), ('_id', 1)]))
        prioridades = self.config.orden_categorias
        esperados = sorted(documentos, key=lambda p: (prioridades.index(p['categoria']) if p['categoria'] in prioridades else len(prioridades), p['categoria']))
        ids = [p['id'] for pagina in paginas for p in pagina['results']]
        self.assertEqual(ids, [str(p['_id']) for p in esperados])
        self.assertEqual(len(set(ids)), 64)
        self.assertEqual(self.get(page=4)['results'], [])
        filtrados = self.get(categoria='Calzado', atributo_color='Azul', page=2)
        self.assertEqual(filtrados['count'], 30)
        self.assertEqual(len(filtrados['results']), 6)
        vacio = self.get(categoria='No existe')
        self.assertEqual(vacio['count'], 0)
        self.assertEqual(vacio['results'], [])
        self.assertEqual(vacio['total_pages'], 1)

    def test_ordenes_explicitos_siguen_siendo_globales_con_prioridades(self):
        self.config.orden_categorias = ['Zeta']
        self.config.save()
        for orden, campo, direccion in [('recientes', 'fecha_creacion', -1), ('nombre', 'nombre', 1),
                                         ('precio-asc', 'precio_minimo_vigente', 1), ('precio-desc', 'precio_minimo_vigente', -1)]:
            with self.subTest(orden=orden):
                ids = [p['id'] for pagina in [1, 2] for p in self.get(orden=orden, page=pagina)['results']]
                esperados = [str(p['_id']) for p in self.collection.find().sort([(campo, direccion), ('_id', 1)])]
                self.assertEqual(ids, esperados)

    def test_categorias_priorizadas_nuevas_borradores_y_restauracion(self):
        self.config.orden_categorias = ['Zeta', 'Desaparecida']
        self.config.save()
        nuevo = Producto(nombre='Nuevo', categoria='Alfa', fecha_creacion=datetime.now(timezone.utc), publicado=True,
                         variantes=[Variante(sku='NUEVO', precio=1000)])
        nuevo.save()
        borrador = Producto(nombre='Borrador', categoria='Borradores', fecha_creacion=datetime.now(timezone.utc), publicado=False,
                            variantes=[Variante(sku='BORRADOR', precio=1000)])
        borrador.save()
        Producto(nombre='Inactivo', categoria='Oculta', fecha_creacion=datetime.now(timezone.utc), activo=False, publicado=True,
                 variantes=[Variante(sku='INACTIVO', precio=1000)]).save()
        esperado = ['Zeta', 'Alfa', 'Beta']
        catalogo = self.get()
        self.assertEqual(catalogo['filtros']['categorias'], esperado)
        self.assertNotIn('Borradores', [p['categoria'] for p in catalogo['results']])
        self.assertNotIn('Oculta', [p['categoria'] for p in catalogo['results']])
        self.assertEqual(self.client.get(reverse('filtros_catalogo')).data['categorias'], esperado)
        self.client.force_authenticate(self.admin)
        lista = self.get(todos='true')
        self.assertIn('Borradores', [p['categoria'] for p in lista])
        self.assertNotIn('Oculta', [p['categoria'] for p in lista])
        self.config.orden_categorias = []
        self.config.save()
        self.client.force_authenticate(None)
        self.assertEqual(self.get()['filtros']['categorias'], ['Alfa', 'Beta', 'Zeta'])

    def test_validaciones_permisos_persistencia_y_defaults(self):
        url = reverse('configuracion-negocio')
        datos = {'orden_catalogo': 'precio-asc', 'orden_categorias': ['Zeta', 'Beta']}
        self.assertEqual(self.client.patch(url, datos, format='json').status_code, 401)
        self.client.force_authenticate(create_user('orden-cliente@example.test'))
        self.assertEqual(self.client.patch(url, datos, format='json').status_code, 403)
        self.client.force_authenticate(self.admin)
        for valor in [None, {}, [''], ['Beta', ' Beta '], [1], ['x' * 101]]:
            with self.subTest(valor=valor):
                self.assertEqual(self.client.patch(url, {'orden_categorias': valor}, format='json').status_code, 400)
        for valor in ['nombre', 'otro', '', None]:
            self.assertEqual(self.client.patch(url, {'orden_catalogo': valor}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(url, datos, format='json').status_code, 200)
        self.config.refresh_from_db()
        self.assertEqual(self.config.orden_catalogo, 'precio-asc')
        self.assertEqual(self.config.orden_categorias, ['Zeta', 'Beta'])
        self.assertEqual(self.client.get(reverse('configuracion-global')).data['orden_catalogo'], 'precio-asc')
        self.assertEqual(self.client.patch(url, {'orden_catalogo': 'destacados', 'orden_categorias': []}, format='json').status_code, 200)
