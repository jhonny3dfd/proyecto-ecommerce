from datetime import datetime, timezone

from bson import ObjectId
from django.urls import reverse
from rest_framework.test import APITestCase

from ecommerce.infrastructure.catalogo.documents import Producto, Variante
from ecommerce.infrastructure.catalogo.tests import usar_mongo_de_prueba
from ecommerce.infrastructure.usuarios.tests.factories import create_user

from .models import DetalleOrden, OrdenCompra


class FotosMisPedidosTests(APITestCase):
    """"Mis pedidos" muestra la foto que tiene hoy en el catálogo cada producto comprado."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        usar_mongo_de_prueba(cls)

    def setUp(self):
        Producto._get_collection().delete_many({})
        self.comprador = create_user('ana@example.test')
        self.client.force_authenticate(self.comprador)
        portada = f'catalogo/productos/{"a" * 24}/{"1" * 32}.webp'
        self.poleron = Producto(
            id=ObjectId('a' * 24), nombre='Polerón', categoria='Ropa', fecha_creacion=datetime.now(timezone.utc),
            imagenes=[portada, 'https://cdn.example.test/otra.jpg'], variantes=[
                Variante(sku='POL-S', precio=10000, stock=3, atributos_variables={'Talla': 'S'},
                         imagen_especifica='https://cdn.example.test/polerón-s.jpg'),
                Variante(sku='POL-M', precio=10000, stock=3, atributos_variables={'Talla': 'M', 'Color': 'Negro'}),
            ]).save()
        self.taza = Producto(nombre='Taza', categoria='Hogar', fecha_creacion=datetime.now(timezone.utc),
                             variantes=[Variante(sku='TAZA-1', precio=5000, stock=3)]).save()

    def pedido(self, *lineas, usuario=None):
        orden = OrdenCompra.objects.create(
            usuario=usuario or self.comprador, metodo_pago='TRANSBANK', estado='ENTREGADO',
            direccion_envio_snapshot={'comuna': 'SANTIAGO'}, subtotal=10000, costo_envio=0, total_final=10000)
        for producto_id, sku, nombre in lineas:
            DetalleOrden.objects.create(orden=orden, producto_mongo_id=producto_id, variante_sku=sku,
                                        nombre_producto_snapshot=nombre, precio_unitario_snapshot=10000, cantidad=1)
        return orden

    def lineas(self):
        response = self.client.get(reverse('mis-pedidos'))
        self.assertEqual(response.status_code, 200)
        return {d['variante_sku']: d for pedido in response.data for d in pedido['detalles']}

    def test_la_foto_de_la_variante_y_si_no_tiene_la_del_producto(self):
        poleron = str(self.poleron.id)
        self.pedido((poleron, 'POL-S', 'Polerón'), (poleron, 'POL-M', 'Polerón'))

        lineas = self.lineas()

        self.assertEqual(lineas['POL-S']['imagen'], 'https://cdn.example.test/polerón-s.jpg')
        self.assertEqual(lineas['POL-S']['variante'], 'Talla: S')
        # La imagen gestionada se entrega como URL absoluta, igual que en el catálogo
        self.assertTrue(lineas['POL-M']['imagen'].startswith('http://testserver/'))
        self.assertTrue(lineas['POL-M']['imagen'].endswith(f'{"1" * 32}.webp'))
        self.assertEqual(lineas['POL-M']['variante'], 'Talla: M · Color: Negro')

    def test_sin_foto_o_borrado_queda_sin_imagen(self):
        self.pedido((str(self.taza.id), 'TAZA-1', 'Taza'), ('b' * 24, 'BORRADO-1', 'Producto borrado'),
                    ('no-es-un-id', 'RARO-1', 'Id inválido'))

        lineas = self.lineas()

        for sku in ('TAZA-1', 'BORRADO-1', 'RARO-1'):
            with self.subTest(sku=sku):
                self.assertIsNone(lineas[sku]['imagen'])
        self.assertEqual(lineas['BORRADO-1']['nombre_producto'], 'Producto borrado')

    def test_solo_los_pedidos_del_comprador(self):
        self.pedido((str(self.taza.id), 'TAZA-1', 'Taza'), usuario=create_user('beto@example.test'))

        self.assertEqual(self.client.get(reverse('mis-pedidos')).data, [])
