"""Persistencia y contrato público de las etiquetas de productos (SCRUM-198)."""

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from ecommerce.domain.catalogo import COLORES_ETIQUETA_PRODUCTO
from ecommerce.infrastructure.usuarios.tests.factories import create_user
from ecommerce.infrastructure.ventas.models import ConfiguracionGlobal
from .documents import Producto
from .tests import usar_mongo_de_prueba


class EtiquetasProductoTests(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Producto en una base Mongo temporal: el catálogo de la base real nunca se toca (AGENTS.md §11)
        usar_mongo_de_prueba(cls)

    def setUp(self):
        # Sin drop_collection(): borra la colección de la base real aunque Producto esté ligado a la temporal
        Producto._get_collection().delete_many({})
        self.admin = create_user(email='admin198@example.test', rol='ADMIN')
        self.client.force_authenticate(self.admin)
        self.lista = reverse('lista_productos')
        self.contador = 0

    def tearDown(self):
        Producto._get_collection().delete_many({})

    def crear(self, **cambios):
        self.contador += 1
        datos = {'nombre': 'Obra de prueba', 'categoria': 'Arte', 'publicado': True,
                 'variantes': [{'sku': f'ETIQUETA-{self.contador}', 'precio': 10000, 'stock': 2}]}
        respuesta = self.client.post(self.lista, {**datos, **cambios}, format='json')
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        return respuesta.data

    def detalle(self, producto):
        return reverse('detalle_producto', args=[producto['id']])

    def test_producto_nuevo_y_documento_antiguo_no_tienen_etiqueta(self):
        nuevo = self.crear()
        self.assertEqual(nuevo['etiqueta'], '')
        self.assertEqual(nuevo['etiqueta_color'], 'primary')
        # Documento anterior al cambio: no necesita un backfill ni una migración SQL.
        antiguo = Producto._get_collection().insert_one({
            'nombre': 'Producto antiguo', 'categoria': 'Arte', 'fecha_creacion': timezone.now(),
            'activo': True, 'publicado': True, 'variantes': [],
        })
        self.client.force_authenticate(None)
        respuesta = self.client.get(reverse('detalle_producto', args=[str(antiguo.inserted_id)]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['etiqueta'], '')
        self.assertEqual(respuesta.data['etiqueta_color'], 'primary')

    def test_crear_editar_y_quitar_etiqueta_conserva_los_demas_datos(self):
        producto = self.crear(etiqueta='  Edición limitada  ', etiqueta_color='accent')
        guardado = Producto.objects.get(id=producto['id'])
        self.assertEqual(guardado.etiqueta, 'Edición limitada')
        self.assertEqual(guardado.etiqueta_color, 'accent')
        anteriores = guardado.to_mongo().to_dict()
        for texto, color in [('Últimas unidades', 'secondary'), ('', 'text')]:
            respuesta = self.client.patch(self.detalle(producto),
                                          {'etiqueta': texto, 'etiqueta_color': color}, format='json')
            self.assertEqual(respuesta.status_code, 200, respuesta.data)
            actual = Producto.objects.get(id=producto['id']).to_mongo().to_dict()
            self.assertEqual(actual['etiqueta'], texto)
            self.assertEqual(actual['etiqueta_color'], color)
            for campo in ('nombre', 'variantes', 'publicado', 'coleccion_privada'):
                self.assertEqual(actual[campo], anteriores[campo])

    def test_acepta_20_caracteres_y_todos_los_roles_de_color(self):
        for color in COLORES_ETIQUETA_PRODUCTO:
            with self.subTest(color=color):
                producto = self.crear(etiqueta='x' * 20, etiqueta_color=color)
                self.assertEqual(producto['etiqueta'], 'x' * 20)
                self.assertEqual(producto['etiqueta_color'], color)

    def test_rechaza_texto_largo_y_colores_libres_sin_alterar_el_producto(self):
        producto = self.crear(etiqueta='Nuevo')
        for cambios, campo in [({'etiqueta': 'x' * 21}, 'etiqueta'),
                                ({'etiqueta_color': '#ff0000'}, 'etiqueta_color'),
                                ({'etiqueta_color': 'var(--otro)'}, 'etiqueta_color')]:
            with self.subTest(cambios=cambios):
                respuesta = self.client.patch(self.detalle(producto), cambios, format='json')
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn(campo, respuesta.data)
        guardado = Producto.objects.get(id=producto['id'])
        self.assertEqual(guardado.etiqueta, 'Nuevo')
        self.assertEqual(guardado.etiqueta_color, 'primary')

    def test_actualizar_otro_campo_no_borra_etiqueta_y_admite_solo_espacios_para_quitarla(self):
        producto = self.crear(etiqueta='Único', etiqueta_color='text')
        respuesta = self.client.patch(self.detalle(producto), {'nombre': 'Nuevo nombre'}, format='json')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['etiqueta'], 'Único')
        self.assertEqual(respuesta.data['etiqueta_color'], 'text')
        respuesta = self.client.patch(self.detalle(producto), {'etiqueta': '   '}, format='json')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['etiqueta'], '')

    def test_etiqueta_se_publica_en_detalle_catalogo_vitrina_y_destacados(self):
        producto = self.crear(etiqueta='Obra única', etiqueta_color='secondary', coleccion_privada=True)
        ConfiguracionGlobal.objects.create(pk=1, vitrina_modo='DESTACADOS',
                                          destacados=[{'tipo': 'PRODUCTO', 'id': producto['id']}])
        self.client.force_authenticate(None)
        detalle = self.client.get(self.detalle(producto))
        listado = self.client.get(self.lista, {'page': 1, 'page_size': 24})
        vitrina = self.client.get('/api/catalogo/vitrina/')
        self.assertEqual(vitrina.status_code, 200, vitrina.data)
        for datos in [detalle.data, listado.data['results'][0],
                      vitrina.data['recientes'][0], vitrina.data['destacados'][0]]:
            self.assertEqual(datos['etiqueta'], 'Obra única')
            self.assertEqual(datos['etiqueta_color'], 'secondary')
            self.assertTrue(datos['coleccion_privada'])

    def test_solo_el_administrador_puede_cambiar_la_etiqueta(self):
        producto = self.crear(etiqueta='Original')
        comprador = create_user()
        for usuario in (None, comprador):
            self.client.force_authenticate(usuario)
            respuesta = self.client.patch(self.detalle(producto), {'etiqueta': 'Alterada'}, format='json')
            self.assertIn(respuesta.status_code, (401, 403))
        self.assertEqual(Producto.objects.get(id=producto['id']).etiqueta, 'Original')
