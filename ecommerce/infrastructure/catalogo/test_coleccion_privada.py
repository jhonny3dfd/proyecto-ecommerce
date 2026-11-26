from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ecommerce.infrastructure.catalogo.documents import Producto, Variante
from ecommerce.infrastructure.catalogo.repositorio_variantes import MongoCatalogoVariantes
from ecommerce.infrastructure.catalogo.tests import usar_mongo_de_prueba
from ecommerce.infrastructure.usuarios.models import Usuario
from ecommerce.infrastructure.ventas.models import ConfiguracionGlobal
from ecommerce.infrastructure.ventas.tests import habilitar_medios_pago


class ColeccionPrivadaTests(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Producto en una base Mongo temporal: el catálogo de la base real nunca se toca (AGENTS.md §11)
        usar_mongo_de_prueba(cls)

    def setUp(self):
        # Sin drop_collection(): borra la colección de la base real aunque Producto esté ligado a la temporal
        Producto._get_collection().delete_many({})
        habilitar_medios_pago('TRANSFERENCIA')
        ConfiguracionGlobal.objects.update_or_create(
            pk=1,
            defaults={
                'nombre_tienda': 'Tienda Arte',
                'modo_autenticacion': 'MIXTO',
                'retiro_en_local_activo': True,
            }
        )
        self.admin = Usuario.objects.create_user(
            email='admin@tienda.test', password='password123', rol='ADMIN'
        )
        self.comprador = Usuario.objects.create_user(
            email='comprador@tienda.test', password='password123', rol='CLIENTE'
        )

    def tearDown(self):
        Producto._get_collection().delete_many({})

    def autenticar_admin(self):
        self.client.force_authenticate(user=self.admin)

    def crear_producto(self, **kwargs):
        datos = {
            'nombre': 'Pintura Original',
            'categoria': 'Arte',
            'activo': True,
            'publicado': True,
            'variantes': [
                {'sku': kwargs.pop('sku', 'ORIGINAL-1'), 'precio': Decimal('150000.00'), 'stock': 1}
            ]
        }
        datos.update(kwargs)
        self.autenticar_admin()
        resp = self.client.post(reverse('lista_productos'), datos, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        return resp.data

    def test_por_defecto_interruptor_apagado_sin_version_y_con_texto_por_defecto(self):
        prod = self.crear_producto()
        self.assertFalse(prod['coleccion_privada'])
        self.assertIsNone(prod.get('version_a_la_venta'))
        self.assertEqual(prod.get('texto_boton_version'), 'Disponible en print')
        self.assertFalse(prod['version_a_la_venta_disponible'])

    def test_admin_activa_coleccion_privada_y_asigna_version_a_la_venta(self):
        print_obra = self.crear_producto(nombre='Lámina Print A3', sku='PRINT-A3')
        original = self.crear_producto(
            nombre='Pintura Al Óleo',
            sku='OLEO-1',
            coleccion_privada=True,
            version_a_la_venta=print_obra['id'],
            texto_boton_version='Comprar lámina',
        )

        self.assertTrue(original['coleccion_privada'])
        self.assertEqual(original['version_a_la_venta'], print_obra['id'])
        self.assertEqual(original['texto_boton_version'], 'Comprar lámina')
        self.assertTrue(original['version_a_la_venta_disponible'])

    def test_si_version_a_la_venta_se_despublica_disponible_es_falso(self):
        print_obra = self.crear_producto(nombre='Lámina Print A3', sku='PRINT-A3', publicado=True)
        original = self.crear_producto(
            nombre='Pintura Al Óleo',
            sku='OLEO-1',
            coleccion_privada=True,
            version_a_la_venta=print_obra['id'],
        )
        self.assertTrue(original['version_a_la_venta_disponible'])

        # Despublicar la versión
        self.client.patch(
            reverse('detalle_producto', args=[print_obra['id']]),
            {'publicado': False},
            format='json'
        )

        # Al consultar el original, disponible es falso
        resp = self.client.get(reverse('detalle_producto', args=[original['id']]))
        self.assertFalse(resp.data['version_a_la_venta_disponible'])

    def test_obra_no_puede_ser_su_propia_version_a_la_venta(self):
        original = self.crear_producto(nombre='Pintura Al Óleo', sku='OLEO-1')
        resp = self.client.patch(
            reverse('detalle_producto', args=[original['id']]),
            {'version_a_la_venta': original['id']},
            format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('version_a_la_venta', resp.data)

    def test_obra_no_puede_enlazarse_a_otra_obra_de_coleccion_privada(self):
        privada_1 = self.crear_producto(nombre='Obra 1', sku='OBRA-1', coleccion_privada=True)
        privada_2 = self.crear_producto(nombre='Obra 2', sku='OBRA-2', coleccion_privada=True)

        resp = self.client.patch(
            reverse('detalle_producto', args=[privada_1['id']]),
            {'version_a_la_venta': privada_2['id']},
            format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('version_a_la_venta', resp.data)

    def test_obra_asignada_como_version_no_puede_ser_coleccion_privada(self):
        print_obra = self.crear_producto(nombre='Lámina Print A3', sku='PRINT-A3')
        self.crear_producto(
            nombre='Pintura Al Óleo', sku='OLEO-1',
            coleccion_privada=True, version_a_la_venta=print_obra['id']
        )

        # Intentar transformar la lámina print en colección privada
        resp = self.client.patch(
            reverse('detalle_producto', args=[print_obra['id']]),
            {'coleccion_privada': True},
            format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('coleccion_privada', resp.data)

    def test_backend_rechaza_coleccion_privada_en_carrito_y_orden(self):
        privada = self.crear_producto(nombre='Obra Privada', sku='PRIV-1', coleccion_privada=True)
        repo = MongoCatalogoVariantes()
        variante = repo.obtener(privada['id'], 'PRIV-1')
        self.assertIsNotNone(variante)
        self.assertFalse(variante.disponible)

        # Validación del carrito (ValidarCarritoView)
        resp_validar = self.client.post(
            reverse('carrito-validar'),
            {'items': [{'producto_mongo_id': privada['id'], 'variante_sku': 'PRIV-1', 'cantidad': 1}]},
            format='json'
        )
        self.assertEqual(resp_validar.status_code, 200)
        self.assertFalse(resp_validar.data['valido'])
        self.assertEqual(resp_validar.data['items'][0]['problema'], 'NO_DISPONIBLE')

        # Guardado en carrito de usuario (CarritoAPIView)
        self.client.force_authenticate(user=self.comprador)
        resp_carrito = self.client.post(
            reverse('carrito-usuario'),
            {'items': [{'producto_mongo_id': privada['id'], 'variante_sku': 'PRIV-1', 'cantidad': 1}]},
            format='json'
        )
        self.assertEqual(resp_carrito.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reduccion_atomica_de_stock_bloquea_coleccion_privada(self):
        privada = self.crear_producto(nombre='Obra Privada', sku='PRIV-1', coleccion_privada=True)
        # Intento de reducir stock de producto privado
        self.assertFalse(Producto.reducir_stock_variante(privada['id'], 'PRIV-1', 1))

    def test_adversario_checkout_directo_rechazado_para_coleccion_privada(self):
        privada = self.crear_producto(nombre='Obra Privada', sku='PRIV-1', coleccion_privada=True)
        self.client.force_authenticate(user=self.comprador)
        payload = {
            'items': [{'producto_mongo_id': privada['id'], 'variante_sku': 'PRIV-1', 'cantidad': 1}],
            'email_invitado': 'hacker@test.com',
            'metodo_pago': 'TRANSFERENCIA',
            'direccion_envio_snapshot': {'calle': 'Av. 123', 'ciudad': 'Santiago', 'comuna': 'Santiago'},
            'subtotal': 150000,
            'proveedor_logistico': 'RETIRO_LOCAL',
            'acepta_terminos': True,
            'nombre_destinatario': 'Hacker Intento',
            'telefono_destinatario': '+56912345678',
        }
        resp = self.client.post(reverse('checkout'), payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('items', resp.data)

    def test_adversario_valores_maliciosos_o_invalidos_en_version_a_la_venta(self):
        original = self.crear_producto(nombre='Obra Original', sku='ORIG-1', coleccion_privada=True)
        self.autenticar_admin()

        maliciosos = [
            '<script>alert(1)</script>',
            '{"$gt": ""}',
            'invalid_hex_string',
            '0',
            'nonexistent0000000000000',
        ]
        for valor in maliciosos:
            resp = self.client.patch(
                reverse('detalle_producto', args=[original['id']]),
                {'version_a_la_venta': valor},
                format='json'
            )
            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn('version_a_la_venta', resp.data)
            self.assertNotIn('Traceback', str(resp.data))

    def test_adversario_no_admin_no_puede_modificar_coleccion_privada(self):
        privada = self.crear_producto(nombre='Obra Privada', sku='PRIV-1', coleccion_privada=True)
        # Intentar modificar sin autenticar
        self.client.logout()
        resp_anon = self.client.patch(
            reverse('detalle_producto', args=[privada['id']]),
            {'coleccion_privada': False},
            format='json'
        )
        self.assertIn(resp_anon.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

        # Intentar modificar autenticado como cliente normal
        self.client.force_authenticate(user=self.comprador)
        resp_cliente = self.client.patch(
            reverse('detalle_producto', args=[privada['id']]),
            {'coleccion_privada': False},
            format='json'
        )
        self.assertEqual(resp_cliente.status_code, status.HTTP_403_FORBIDDEN)
