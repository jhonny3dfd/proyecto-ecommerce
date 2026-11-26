from decimal import Decimal
from unittest.mock import patch
import json
import tempfile

from django.test import override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from ecommerce.application.test_medios_pago import DATOS_BANCO
from ecommerce.application.test_ventas import CatalogoFalso, InventarioFalso
from ecommerce.domain.logistica import ErrorOrdenTransporte
from ecommerce.domain.medios_pago import CodigoMedioPago, MedioPagoConfigurado
from ecommerce.domain.ventas import VarianteCatalogo
from ecommerce.infrastructure.usuarios.tests.factories import create_user
from ecommerce.infrastructure.ventas.models import FotoBanner

from .models import ConfiguracionGlobal, DetalleOrden, OrdenCompra, PaginaLegal, ProveedorEnvio
from .repositorio_medios_pago import DjangoRepositorioMediosPago
from .serializers import ConfiguracionGlobalSerializer
from .views import token_verificacion_valido
from .test_chilexpress import guardar_credenciales


TRANSPORTISTA = 'ecommerce.infrastructure.ventas.views.transportista_ordenes'


def usar_catalogo_falso(test, variantes):
    """Reemplaza el catálogo de MongoDB del checkout por uno en memoria."""
    catalogo = patch('ecommerce.infrastructure.ventas.serializers.catalogo_variantes',
                     return_value=CatalogoFalso(variantes))
    catalogo.start()
    test.addCleanup(catalogo.stop)


# RF-02.3: quién recibe o retira; el checkout lo exige
DESTINATARIO = {'nombre_destinatario': 'Ana Pérez', 'telefono_destinatario': '+56 9 1234 5678'}

DATOS_MEDIOS_PAGO = {
    'TRANSBANK': {'ambiente': 'INTEGRACION'},
    'MERCADO_PAGO': {'access_token': 'APP_USR-1234567890-prueba-abcd', 'webhook_secret': 'secreto-webhook-1234'},
    'TRANSFERENCIA': DATOS_BANCO,
}


def habilitar_medios_pago(*codigos):
    """RN-02: el checkout solo acepta medios habilitados y configurados."""
    for codigo in codigos:
        DjangoRepositorioMediosPago().guardar(
            MedioPagoConfigurado(CodigoMedioPago(codigo), True, DATOS_MEDIOS_PAGO[codigo]))


class ConfiguracionGlobalSerializerTests(APITestCase):
    def test_exposes_only_landing_page_fields(self):
        configuracion = ConfiguracionGlobal.objects.create(
            nombre_tienda='Tienda privada',
            texto_bienvenida='Descubre nuestros productos',
            texto_boton_ingreso='Ir al catálogo',
            banner_url='https://example.com/banner.jpg',
        )

        data = ConfiguracionGlobalSerializer(configuracion).data

        self.assertEqual(
            set(data),
            {'orden_catalogo', 'orden_categorias', 'menu_principal', 'google_client_id', 'texto_bienvenida', 'texto_boton_ingreso', 'banner_url',
             'tema_seleccionado', 'tipografia_seleccionada', 'layout_catalogo',
             'pasarelas_activas', 'google_analytics_id', 'meta_pixel_id', 'modo_autenticacion',
             'comuna_origen', 'region_origen', 'calle_origen',
             'numero_origen', 'dpto_casa_origen', 'retiro_en_local_activo',
             'entrega_coordinada_activa', 'costo_entrega_coordinada', 'instrucciones_entrega_coordinada',
             'couriers', 'cotizaciones_activas', 'suscripciones_activas', 'blog_activo', 'blog_nombre', 'resenas_activas',
             'vitrina_modo', 'destacados_titulo', 'destacados', 'fotos_completas', 'ficha_horizontal', 'logo_grande', 'video_banner_activo',
             'google_analytics_id', 'meta_pixel_id',
             'nombre_tienda', 'logo', 'favicon', 'banner', 'banners', 'subtitulo_bienvenida', 'texto_landing',
             'nosotros_titulo', 'nosotros_texto', 'nosotros_imagen',
             'correo_contacto', 'horario_atencion', 'mostrar_direccion_pie', 'ubicacion_logo_universidad',
             'instagram_usuario',
             *(f'instagram_foto_{numero}' for numero in range(1, 7)), 'sobre_mi_activo','sobre_mi_nombre',
            'telefono_comercial','facebook_url','x_url','youtube_url','tiktok_url',})

    def test_validates_url_and_button_length(self):
        serializer = ConfiguracionGlobalSerializer(data={
            'texto_bienvenida': 'Bienvenida',
            'texto_boton_ingreso': 'x' * 101,
            'banner_url': 'no-es-una-url',
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn('texto_boton_ingreso', serializer.errors)
        self.assertIn('banner_url', serializer.errors)


class ConfiguracionGlobalAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.configuracion = ConfiguracionGlobal.objects.create(
            pk=1,
            nombre_tienda='Tienda QA',
            texto_bienvenida='Bienvenido a Tienda QA',
            texto_boton_ingreso='Ver productos',
            banner_url='https://example.com/hero.jpg',
        )
        # La migración 0022 copia a la base las llaves de Chilexpress que haya en el entorno
        ProveedorEnvio.objects.all().delete()

    @override_settings(GOOGLE_CLIENT_ID='cliente-qa.apps.googleusercontent.com')
    def test_public_endpoint_matches_frontend_contract(self):
        url = reverse('configuracion-global')

        response = self.client.get(
            url,
            HTTP_AUTHORIZATION='Token credencial-invalida',
        )

        self.assertEqual(url, '/api/configuracion/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {
            'orden_catalogo': 'destacados',
            'orden_categorias': [],
            'menu_principal': {},
            'google_client_id': 'cliente-qa.apps.googleusercontent.com',
            'texto_bienvenida': 'Bienvenido a Tienda QA',
            'texto_boton_ingreso': 'Ver productos',
            'banner_url': 'https://example.com/hero.jpg',
            'tema_seleccionado': 1,
            'tipografia_seleccionada': 1,
            'layout_catalogo': 'GRID_3',
            'pasarelas_activas': [],
            'google_analytics_id': None,
            'meta_pixel_id': None,
            'modo_autenticacion': 'MIXTO',
            'comuna_origen': 'Santiago',
            'region_origen': 'Metropolitana',
            'calle_origen': 'Av. Principal',
            'numero_origen': '123',
            'dpto_casa_origen': None,
            'retiro_en_local_activo': True,
            'entrega_coordinada_activa': False,
            'costo_entrega_coordinada': 0,
            'instrucciones_entrega_coordinada': '',
            'couriers': [],
            'cotizaciones_activas': False,
            'suscripciones_activas': False,
            'blog_activo': False,
            'blog_nombre': 'Nosotros',
            'sobre_mi_activo': False,
            'sobre_mi_nombre': 'Sobre mí',
            'resenas_activas': False,
            'vitrina_modo': 'MAS_VENDIDOS',
            'destacados_titulo': 'Destacados',
            'destacados': [],
            'fotos_completas': False,
            'ficha_horizontal': False,
            'logo_grande': False,
            'video_banner_activo': False,
            'google_analytics_id': None,
            'meta_pixel_id': None,
            'nombre_tienda': 'Tienda QA',
            'logo': None,
            'favicon': None,
            'banner': None,
            'banners': [{'id': 'legacy', 'imagen': 'https://example.com/hero.jpg', 'orden': 0, 'antetitulo': '',
                         'titulo': 'Bienvenido a Tienda QA', 'texto': '', 'destino': 'CATALOGO'}],
            'subtitulo_bienvenida': '',
            'texto_landing': '',
            'nosotros_titulo': '',
            'nosotros_texto': '',
            'nosotros_imagen': None,
            'correo_contacto': '',
            'horario_atencion': '',
            'mostrar_direccion_pie': False,
            'telefono_comercial': '',
            'facebook_url': '',
            'x_url': '',
            'youtube_url': '',
            'tiktok_url': '',
            'ubicacion_logo_universidad': 'HEADER',
            'instagram_usuario': '',
            **{f'instagram_foto_{numero}': None for numero in range(1, 7)},
        })

    def test_returns_not_found_when_configuration_does_not_exist(self):
        ConfiguracionGlobal.objects.all().delete()

        response = self.client.get(reverse('configuracion-global'))

        self.assertEqual(response.status_code, 404)

    def test_endpoint_is_read_only(self):
        response = self.client.post(
            reverse('configuracion-global'),
            {'texto_bienvenida': 'Intento de cambio'},
            format='json',
        )

        self.assertEqual(response.status_code, 405)


class ConfiguracionNegocioAccessTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.configuracion = ConfiguracionGlobal.objects.create(
            pk=1, nombre_tienda='Tienda QA', texto_bienvenida='Original',
        )
        cls.buyer_token = Token.objects.create(user=create_user())
        cls.admin_token = Token.objects.create(
            user=create_user('admin@example.test', rol='ADMIN'),
        )

    def patch(self, token=None):
        if token:
            self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        return self.client.patch(reverse('configuracion-negocio'),
                                 {'texto_bienvenida': 'Modificado'},
                                 format='json')

    def test_anonymous_cannot_read_or_modify(self):
        self.assertEqual(
            self.client.get(reverse('configuracion-negocio')).status_code, 401)
        self.assertEqual(self.patch().status_code, 401)
        self.configuracion.refresh_from_db()
        self.assertEqual(self.configuracion.texto_bienvenida, 'Original')

    def test_buyer_cannot_modify(self):
        self.assertEqual(self.patch(self.buyer_token).status_code, 403)
        self.configuracion.refresh_from_db()
        self.assertEqual(self.configuracion.texto_bienvenida, 'Original')

    def test_admin_can_modify(self):
        response = self.patch(self.admin_token)
        self.assertEqual(response.status_code, 200)
        self.configuracion.refresh_from_db()
        self.assertEqual(self.configuracion.texto_bienvenida, 'Modificado')


    def patch_analytics(self, datos):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Token {self.admin_token.key}'
        )
        return self.client.patch(
            reverse('configuracion-negocio'),
            datos,
            format='json',
        )

    def test_admin_can_save_valid_analytics_ids(self):
        response = self.patch_analytics({
            'google_analytics_id': 'G-ABC1234567',
            'meta_pixel_id': '123456789012345',
        })

        self.assertEqual(response.status_code, 200)
        self.configuracion.refresh_from_db()
        self.assertEqual(
            self.configuracion.google_analytics_id, 'G-ABC1234567'
        )
        self.assertEqual(
            self.configuracion.meta_pixel_id, '123456789012345'
        )

    def test_invalid_google_analytics_id_is_rejected(self):
        response = self.patch_analytics({
            'google_analytics_id': 'G-123',
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('google_analytics_id', response.data)

    def test_invalid_meta_pixel_id_is_rejected(self):
        response = self.patch_analytics({
            'meta_pixel_id': 'pixel-invalido',
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('meta_pixel_id', response.data)

    def test_empty_analytics_ids_can_disable_integrations(self):
        response = self.patch_analytics({
            'google_analytics_id': '',
            'meta_pixel_id': '',
        })

        self.assertEqual(response.status_code, 200)
        self.configuracion.refresh_from_db()
        self.assertEqual(self.configuracion.google_analytics_id, '')
        self.assertEqual(self.configuracion.meta_pixel_id, '')


class CheckoutAccessTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.buyer = create_user()
        cls.admin = create_user('admin@example.test', rol='ADMIN')
        cls.tokens = [Token.objects.create(user=user)
                      for user in (cls.buyer, cls.admin)]

    def setUp(self):
        habilitar_medios_pago('TRANSFERENCIA', 'TRANSBANK')
        usar_catalogo_falso(self, {
            ('camisa', 'CAMISA-S'): VarianteCatalogo(
                'Camisa - CAMISA-S', Decimal('10000.00'), 3, True),
        })
        # Estas pruebas validan acceso: la cotización del courier se simula sin red
        # Chilexpress activo (sus llaves en la base) y su tarifa simulada, sin red
        guardar_credenciales(cotizador='llave-de-prueba')
        cotizacion = patch('ecommerce.infrastructure.ventas.serializers.precio_envio', return_value=Decimal('1000'))
        cotizacion.start()
        self.addCleanup(cotizacion.stop)
        # Mismo formato que arma Checkout.jsx
        self.payload = {
            'items': [{'producto_mongo_id': 'camisa', 'variante_sku': 'CAMISA-S', 'cantidad': 1}],
            'email_invitado': 'invitado@example.test',
            'metodo_pago': 'TRANSFERENCIA',
            'direccion_envio_snapshot': {
                'calle': 'Prueba', 'ciudad': 'Santiago', 'comuna': 'Santiago',
            },
            'subtotal': 10000,
            'proveedor_logistico': 'CHILEXPRESS',
            'acepta_terminos': True,
            **DESTINATARIO,
        }

    def configure(self, mode):
        ConfiguracionGlobal.objects.update_or_create(
            pk=1, defaults={'nombre_tienda': 'Tienda QA',
                            'modo_autenticacion': mode,
                            # Estas pruebas validan acceso, no logística
                            'retiro_en_local_activo': False},
        )

    def checkout(self, payload=None):
        return self.client.post(reverse('checkout'),
                                self.payload if payload is None else payload,
                                format='json')

    def test_guest_checkout_remains_public_when_allowed(self):
        for mode in (None, 'INVITADO', 'MIXTO'):
            with self.subTest(mode=mode):
                if mode:
                    self.configure(mode)
                self.assertEqual(self.checkout().status_code, 201)
                order = OrdenCompra.objects.latest('pk')
                self.assertIsNone(order.usuario_id)
                self.assertEqual(order.email_invitado,
                                 self.payload['email_invitado'])
                self.assertEqual((order.costo_envio, order.total_final), (1000, 11000))

    def test_el_pedido_tiene_hasta_100_lineas_como_el_carrito(self):
        lineas = [{**self.payload['items'][0], 'variante_sku': f'SKU-{numero}'} for numero in range(101)]
        respuesta = self.checkout({**self.payload, 'items': lineas})
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('items', respuesta.data)

    def test_la_direccion_solo_guarda_sus_campos_con_largo_maximo(self):
        for direccion in ({'calle': 'x' * 100_000, 'comuna': 'Santiago'}, 'Santiago', ['Santiago']):
            with self.subTest(direccion=str(direccion)[:30]):
                respuesta = self.checkout({**self.payload, 'direccion_envio_snapshot': direccion})
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn('direccion_envio_snapshot', respuesta.data)
        self.assertFalse(OrdenCompra.objects.exists())

        direccion = {**self.payload['direccion_envio_snapshot'], 'dpto_casa': None, 'script': '<script>x</script>'}
        self.assertEqual(self.checkout({**self.payload, 'direccion_envio_snapshot': direccion}).status_code, 201)
        guardada = OrdenCompra.objects.get().direccion_envio_snapshot
        self.assertNotIn('script', guardada)
        self.assertEqual(guardada['dpto_casa'], '')

    def test_el_correo_del_invitado_se_valida_y_se_guarda_en_minusculas(self):
        respuesta = self.checkout({**self.payload, 'email_invitado': 'no-es-un-correo'})
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('email_invitado', respuesta.data)
        self.assertFalse(OrdenCompra.objects.exists())

        self.assertEqual(self.checkout({**self.payload, 'email_invitado': ' Ana.Perez@Example.TEST '}).status_code, 201)
        self.assertEqual(OrdenCompra.objects.get().email_invitado, 'ana.perez@example.test')

    def test_la_respuesta_trae_el_token_para_consultar_el_pago_de_esa_orden(self):
        response = self.checkout()
        self.assertEqual(response.status_code, 201)
        token = response.data['token_verificacion']
        self.assertTrue(token_verificacion_valido(token, response.data['orden_id']))
        self.assertFalse(token_verificacion_valido(token, response.data['orden_id'] + 1))

    def test_required_registration_rejects_anonymous_before_validation(self):
        self.configure('REGISTRO_OBLIGATORIO')
        for payload in (self.payload, {}):
            with self.subTest(payload=payload):
                response = self.checkout(payload)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response['WWW-Authenticate'], 'Token')
                self.assertFalse(OrdenCompra.objects.exists())

    def test_invalid_token_never_creates_an_order_in_any_mode(self):
        for mode in ('INVITADO', 'MIXTO', 'REGISTRO_OBLIGATORIO'):
            self.configure(mode)
            for header in ('Token', 'Token invalid', 'Token one two'):
                with self.subTest(mode=mode, header=header):
                    self.client.credentials(HTTP_AUTHORIZATION=header)
                    self.assertEqual(self.checkout().status_code, 401)
                    self.assertFalse(OrdenCompra.objects.exists())

    def test_authenticated_roles_can_checkout_in_every_mode(self):
        for mode in ('INVITADO', 'MIXTO', 'REGISTRO_OBLIGATORIO'):
            self.configure(mode)
            for token in self.tokens:
                with self.subTest(mode=mode, role=token.user.rol):
                    self.client.credentials(
                        HTTP_AUTHORIZATION=f'Token {token.key}',
                    )
                    payload = dict(self.payload, usuario=self.admin.pk,
                                   rol='ADMIN')
                    self.assertEqual(self.checkout(payload).status_code, 201)
                    order = OrdenCompra.objects.latest('pk')
                    self.assertEqual(order.usuario_id, token.user_id)
                    self.assertEqual(order.email_invitado, '')

    def test_inactive_account_cannot_fall_back_to_guest_checkout(self):
        self.configure('MIXTO')
        self.buyer.is_active = False
        self.buyer.save(update_fields=['is_active'])
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Token {self.tokens[0].key}',
        )
        self.assertEqual(self.checkout().status_code, 401)
        self.assertFalse(OrdenCompra.objects.exists())

    def test_guest_email_is_still_required(self):
        self.payload.pop('email_invitado')
        response = self.checkout()
        self.assertEqual(response.status_code, 400)
        self.assertIn('email_invitado', response.data)
        self.assertFalse(OrdenCompra.objects.exists())

    def test_destinatario_es_obligatorio_y_el_telefono_se_normaliza(self):
        self.configure('INVITADO')
        for campo, valor in (('nombre_destinatario', ''), ('nombre_destinatario', '12345'),
                             ('telefono_destinatario', ''), ('telefono_destinatario', '+1 555 123 4567'),
                             ('telefono_destinatario', 'llamame')):
            with self.subTest(campo=campo, valor=valor):
                response = self.checkout({**self.payload, campo: valor})
                self.assertEqual(response.status_code, 400)
                self.assertIn(campo, response.data)
        self.assertFalse(OrdenCompra.objects.exists())

        response = self.checkout()
        self.assertEqual(response.status_code, 201, response.data)
        orden = OrdenCompra.objects.get()
        self.assertEqual((orden.nombre_destinatario, orden.telefono_destinatario), ('Ana Pérez', '+56912345678'))

    def test_checkout_rejected_without_accepting_terms(self):
        for valor in (False, None):
            with self.subTest(acepta_terminos=valor):
                payload = dict(self.payload)
                if valor is None:
                    payload.pop('acepta_terminos')
                else:
                    payload['acepta_terminos'] = valor
                response = self.checkout(payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn('acepta_terminos', response.data)
                self.assertFalse(OrdenCompra.objects.exists())

    def test_order_detail_uses_catalog_name_and_price_not_the_browser_ones(self):
        self.configure('INVITADO')
        # Mismo formato que arma Checkout.jsx, con nombre y precio manipulados
        payload = dict(self.payload, subtotal=20000, items=[{
            'producto_mongo_id': 'camisa', 'variante_sku': 'CAMISA-S',
            'nombre_producto_snapshot': 'Otro nombre', 'precio_unitario_snapshot': '1',
            'cantidad': 2,
        }])
        self.assertEqual(self.checkout(payload).status_code, 201)
        detalle = DetalleOrden.objects.get(orden=OrdenCompra.objects.latest('pk'))
        self.assertEqual(detalle.nombre_producto_snapshot, 'Camisa - CAMISA-S')
        self.assertEqual(detalle.precio_unitario_snapshot, 10000.0)
        self.assertEqual(detalle.variante_sku, 'CAMISA-S')
        self.assertEqual(detalle.cantidad, 2)

    def test_tampered_subtotal_is_rejected_with_current_prices(self):
        self.configure('INVITADO')
        response = self.checkout(dict(self.payload, subtotal=1))
        self.assertEqual(response.status_code, 400)
        self.assertIn('subtotal', response.data)
        self.assertEqual(response.data['precios_vigentes'][0]['precio'], '10000.00')
        self.assertFalse(OrdenCompra.objects.exists())

    def test_insufficient_stock_or_empty_cart_creates_no_order(self):
        self.configure('INVITADO')
        sin_stock = [{'producto_mongo_id': 'camisa', 'variante_sku': 'CAMISA-S', 'cantidad': 4}]
        for items, subtotal in ((sin_stock, 40000), ([], 0)):
            with self.subTest(items=items):
                response = self.checkout(dict(self.payload, items=items, subtotal=subtotal))
                self.assertEqual(response.status_code, 400)
                self.assertIn('items', response.data)
                self.assertFalse(OrdenCompra.objects.exists())

    def test_checkout_does_not_expose_order_listing(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Token {self.tokens[1].key}',
        )
        self.assertEqual(self.client.get(reverse('checkout')).status_code, 405)

    def publicar(self, tipo):
        PaginaLegal.objects.create(tipo_pagina=tipo, titulo=tipo, contenido='<p>Texto</p>', publicada=True)

    @override_settings(EXIGIR_PAGINAS_LEGALES=True)
    def test_en_produccion_no_se_vende_sin_terminos_y_privacidad_publicados(self):
        self.configure('INVITADO')
        response = self.checkout()
        self.assertEqual(response.status_code, 400)
        self.assertIn('Términos y Condiciones ni Política de Privacidad', str(response.data['acepta_terminos']))

        # Un borrador o solo una de las dos no basta
        PaginaLegal.objects.create(tipo_pagina='PRIVACIDAD', titulo='Privacidad', contenido='<p>x</p>')
        self.publicar('TERMINOS')
        response = self.checkout()
        self.assertEqual(response.status_code, 400)
        self.assertIn('Política de Privacidad', str(response.data['acepta_terminos']))
        self.assertNotIn('Términos', str(response.data['acepta_terminos']))
        self.assertFalse(OrdenCompra.objects.exists())

        PaginaLegal.objects.filter(tipo_pagina='PRIVACIDAD').update(publicada=True)
        self.assertEqual(self.checkout().status_code, 201)

    @override_settings(EXIGIR_PAGINAS_LEGALES=False)
    def test_en_desarrollo_se_vende_sin_paginas_legales(self):
        self.configure('INVITADO')
        self.assertEqual(self.checkout().status_code, 201)


class ValidarCarritoTests(APITestCase):
    def setUp(self):
        usar_catalogo_falso(self, {
            ('camisa', 'CAMISA-S'): VarianteCatalogo('Camisa - CAMISA-S', Decimal('10000.00'), 3, True),
            ('camisa', 'CAMISA-M'): VarianteCatalogo('Camisa - CAMISA-M', Decimal('10000.00'), 0, True),
        })

    def validar(self, *items):
        return self.client.post(reverse('carrito-validar'), {'items': [
            {'producto_mongo_id': producto, 'variante_sku': sku, 'cantidad': cantidad}
            for producto, sku, cantidad in items
        ]}, format='json')

    def test_invitado_valida_su_carrito_sin_sesion(self):
        response = self.validar(('camisa', 'CAMISA-S', 3))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['valido'])
        linea, = response.data['items']
        self.assertEqual((linea['disponible'], linea['precio'], linea['problema']), (3, '10000.00', None))

    def test_informa_cada_linea_con_problema(self):
        response = self.validar(('camisa', 'CAMISA-S', 4), ('camisa', 'CAMISA-M', 1), ('otro', 'X', 1))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['valido'])
        self.assertEqual([(l['variante_sku'], l['problema'], l['disponible']) for l in response.data['items']], [
            ('CAMISA-S', 'STOCK_INSUFICIENTE', 3),
            ('CAMISA-M', 'SIN_STOCK', 0),
            ('X', 'NO_DISPONIBLE', 0),
        ])
        self.assertIn('solo quedan 3', response.data['items'][0]['mensaje'])

    def test_cantidad_invalida_o_sin_items_es_400(self):
        self.assertEqual(self.validar(('camisa', 'CAMISA-S', 0)).status_code, 400)
        self.assertEqual(self.client.post(reverse('carrito-validar'), {}, format='json').status_code, 400)


@patch('ecommerce.infrastructure.ventas.views.consultar_estado_envio', return_value='En tránsito')
class SeguimientoEnvioTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.orden = OrdenCompra.objects.create(
            email_invitado='invitado@example.test', metodo_pago='TRANSBANK',
            direccion_envio_snapshot={'comuna': 'SANTIAGO'},
            subtotal=10000, costo_envio=1000, total_final=11000,
            proveedor_logistico='CHILEXPRESS', numero_seguimiento_tracking='712678903156',
        )

    def consultar(self, numero_orden, email='invitado@example.test'):
        return self.client.post(reverse('tracking-envio'),
                                {'numero_orden': numero_orden, 'email': email},
                                format='json')

    def test_guest_with_matching_order_and_email_sees_timeline(self, consultar_estado):
        response = self.consultar(self.orden.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['estado_actual'], 'En tránsito')
        self.assertEqual(response.data['codigo_seguimiento'], '712678903156')
        consultar_estado.assert_called_once_with('CHILEXPRESS', '712678903156')

    def test_el_correo_no_distingue_mayusculas_ni_espacios(self, consultar_estado):
        self.assertEqual(self.consultar(self.orden.id, '  Invitado@Example.TEST ').status_code, 200)

    def test_mismatch_gets_same_generic_response_as_missing_order(self, consultar_estado):
        esperado = self.consultar(999999)
        self.assertEqual(esperado.status_code, 404)
        for numero_orden, email in ((self.orden.id, 'otro@example.test'),
                                    ('abc', 'invitado@example.test')):
            with self.subTest(numero_orden=numero_orden, email=email):
                response = self.consultar(numero_orden, email)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.data, esperado.data)
        consultar_estado.assert_not_called()

    def orden_de_la_tienda(self, proveedor, estado):
        return OrdenCompra.objects.create(
            email_invitado='invitado@example.test', metodo_pago='TRANSBANK', estado=estado,
            direccion_envio_snapshot={'comuna': 'PROVIDENCIA', 'calle': 'Los Olmos', 'numero': '123'},
            subtotal=10000, costo_envio=0, total_final=10000, proveedor_logistico=proveedor,
        )

    def test_entrega_coordinada_sin_courier_ni_codigo_y_con_las_instrucciones(self, consultar_estado):
        ConfiguracionGlobal.objects.update_or_create(pk=1, defaults={
            'nombre_tienda': 'Tienda QA', 'instrucciones_entrega_coordinada': 'Te escribimos por WhatsApp.'})
        orden = self.orden_de_la_tienda('ENTREGA_COORDINADA', 'ENVIADO')

        response = self.consultar(orden.id)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['entrega_de_la_tienda'])
        self.assertEqual(response.data['proveedor'], 'Entrega coordinada')
        self.assertEqual(response.data['estado_actual'], 'La tienda coordinará la entrega contigo')
        self.assertEqual(response.data['instrucciones'], 'Te escribimos por WhatsApp.')
        self.assertIsNone(response.data['codigo_seguimiento'])
        self.assertEqual(response.data['linea_tiempo_estandar'], [])
        consultar_estado.assert_not_called()

    def test_entrega_coordinada_sin_instrucciones_avisa_que_la_tienda_contactara(self, consultar_estado):
        orden = self.orden_de_la_tienda('ENTREGA_COORDINADA', 'PAGADO')

        response = self.consultar(orden.id)

        self.assertEqual(response.data['estado_actual'], 'Pago confirmado')
        self.assertEqual(response.data['instrucciones'],
                         'La tienda te contactará para acordar el día y la hora de la entrega.')

    def test_retiro_en_local_dice_donde_retirar(self, consultar_estado):
        ConfiguracionGlobal.objects.update_or_create(pk=1, defaults={
            'nombre_tienda': 'Tienda QA', 'calle_origen': 'Av. Central', 'numero_origen': '50',
            'comuna_origen': 'Providencia'})
        orden = self.orden_de_la_tienda('RETIRO_LOCAL', 'ENVIADO')

        response = self.consultar(orden.id)

        self.assertEqual(response.data['proveedor'], 'Retiro en local')
        self.assertEqual(response.data['estado_actual'], 'Listo para retirar')
        self.assertEqual(response.data['instrucciones'],
                         'Retíralo en Av. Central 50 Providencia presentando tu número de orden.')
        consultar_estado.assert_not_called()

    def test_entrega_de_la_tienda_con_otro_correo_recibe_la_respuesta_generica(self, consultar_estado):
        orden = self.orden_de_la_tienda('ENTREGA_COORDINADA', 'ENVIADO')
        esperado = self.consultar(999999)

        response = self.consultar(orden.id, 'otro@example.test')

        self.assertEqual((response.status_code, response.data), (404, esperado.data))


    def test_sin_numero_seguimiento_queda_pendiente_de_despacho(self, consultar_estado):
        # Vacío o nulo (el campo admite los dos): todavía no hay orden de transporte que consultar
        for numero in ('', None):
            with self.subTest(numero=numero):
                self.orden.numero_seguimiento_tracking = numero
                self.orden.save(update_fields=['numero_seguimiento_tracking'])
                response = self.consultar(self.orden.id)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data['estado_actual'], 'Pendiente de despacho')
        consultar_estado.assert_not_called()


    def test_retiro_local_muestra_mensaje_propio(self, consultar_estado):
        self.orden.proveedor_logistico = 'RETIRO_LOCAL'
        self.orden.numero_seguimiento_tracking = ''
        self.orden.save(
            update_fields=[
                'proveedor_logistico',
                'numero_seguimiento_tracking',
            ]
        )
        response = self.consultar(self.orden.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data['estado_actual'],
            'Esperando el pago',
        )
        consultar_estado.assert_not_called()


    def test_retiro_local_entregado_muestra_entregado(self, consultar_estado):
        self.orden.proveedor_logistico = 'RETIRO_LOCAL'
        self.orden.estado = 'ENTREGADO'
        self.orden.numero_seguimiento_tracking = ''
        self.orden.save(
            update_fields=[
                'proveedor_logistico',
                'estado',
                'numero_seguimiento_tracking',
            ]
        )
        response = self.consultar(self.orden.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['estado_actual'], 'Retirado')
        consultar_estado.assert_not_called()


    def test_pedido_cancelado_sin_ot_muestra_cancelado(self, consultar_estado):
        self.orden.estado = 'CANCELADO'
        self.orden.numero_seguimiento_tracking = ''
        self.orden.save(
            update_fields=['estado', 'numero_seguimiento_tracking']
        )
        response = self.consultar(self.orden.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['estado_actual'], 'Cancelado')
        consultar_estado.assert_not_called()



class CambioEstadoAdminTests(APITestCase):
    """RF-03.3: el admin solo puede hacer las transiciones permitidas."""

    @classmethod
    def setUpTestData(cls):
        cls.buyer_token = Token.objects.create(user=create_user())
        cls.admin_token = Token.objects.create(user=create_user('admin@example.test', rol='ADMIN'))

    def setUp(self):
        self.orden = OrdenCompra.objects.create(
            email_invitado='invitado@example.test', metodo_pago='TRANSBANK',
            direccion_envio_snapshot={}, subtotal=20000, costo_envio=0, total_final=20000,
            estado='PAGADO', stock_descontado=True,
        )
        DetalleOrden.objects.create(
            orden=self.orden, producto_mongo_id='camisa', variante_sku='CAMISA-S',
            nombre_producto_snapshot='Camisa - CAMISA-S', precio_unitario_snapshot=10000, cantidad=2,
        )
        self.inventario = InventarioFalso({('camisa', 'CAMISA-S'): 3})
        inventario = patch('ecommerce.infrastructure.ventas.views.inventario_variantes',
                           return_value=self.inventario)
        inventario.start()
        self.addCleanup(inventario.stop)

    def cambiar(self, estado, token=None, orden_id=None):
        if token:
            self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        return self.client.patch(reverse('admin-ordenes-patch', args=[orden_id or self.orden.id]),
                                 {'estado': estado}, format='json')

    def stock(self):
        return self.inventario.stock[('camisa', 'CAMISA-S')]

    def assertEstado(self, estado):
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, estado)

    def test_solo_el_admin_puede_cambiar_el_estado(self):
        self.assertEqual(self.cambiar('EN_PREPARACION').status_code, 401)
        self.assertEqual(self.cambiar('EN_PREPARACION', self.buyer_token).status_code, 403)
        self.assertEstado('PAGADO')

    def test_transicion_permitida(self):
        response = self.cambiar('EN_PREPARACION', self.admin_token)
        self.assertEqual(response.status_code, 200)
        self.assertEstado('EN_PREPARACION')

    def test_transicion_no_permitida_se_rechaza_sin_cambios(self):
        for actual, nuevo in (('CANCELADO', 'PAGADO'), ('PAGADO', 'PENDIENTE'), ('PAGADO', 'PAGADO')):
            with self.subTest(actual=actual, nuevo=nuevo):
                OrdenCompra.objects.filter(id=self.orden.id).update(estado=actual)
                response = self.cambiar(nuevo, self.admin_token)
                self.assertEqual(response.status_code, 400)
                self.assertIn('no puede pasar a', str(response.data['estado']))
                self.assertEstado(actual)
        self.assertEqual(self.stock(), 3)

    def test_estado_desconocido_u_orden_inexistente(self):
        self.assertEqual(self.cambiar('RECHAZADO', self.admin_token).status_code, 400)
        self.assertEqual(self.cambiar('CANCELADO', self.admin_token, orden_id=999999).status_code, 404)
        self.assertEstado('PAGADO')

    def test_cancelar_repone_el_stock_descontado(self):
        response = self.cambiar('CANCELADO', self.admin_token)
        self.assertEqual(response.status_code, 200)
        self.assertEstado('CANCELADO')
        self.assertEqual(self.orden.motivo_cancelacion, 'Cancelado por el administrador')
        self.assertFalse(self.orden.stock_descontado)
        self.assertEqual(self.stock(), 5)

    def test_pagar_a_mano_descuenta_stock_y_avisa_si_queda_en_revision(self):
        OrdenCompra.objects.filter(id=self.orden.id).update(estado='PENDIENTE', stock_descontado=False)
        response = self.cambiar('PAGADO', self.admin_token)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['requiere_revision'])
        self.assertEqual(self.stock(), 1)

        otra = OrdenCompra.objects.create(
            email_invitado='otro@example.test', metodo_pago='TRANSFERENCIA',
            direccion_envio_snapshot={}, subtotal=20000, costo_envio=0, total_final=20000,
        )
        DetalleOrden.objects.create(
            orden=otra, producto_mongo_id='camisa', variante_sku='CAMISA-S',
            nombre_producto_snapshot='Camisa - CAMISA-S', precio_unitario_snapshot=10000, cantidad=2,
        )
        response = self.cambiar('PAGADO', orden_id=otra.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['estado'], 'PAGADO')
        self.assertTrue(response.data['requiere_revision'])
        self.assertEqual(response.data['motivo_revision'], 'Pago confirmado sin stock para CAMISA-S')
        self.assertEqual(self.stock(), 1)


class PanelPedidosAdminTests(APITestCase):
    """RF-03.3: listado del panel y resolución de revisiones."""

    @classmethod
    def setUpTestData(cls):
        cls.buyer_token = Token.objects.create(user=create_user())
        cls.admin_token = Token.objects.create(user=create_user('admin@example.test', rol='ADMIN'))
        cls.orden = OrdenCompra.objects.create(
            email_invitado='invitado@example.test', metodo_pago='TRANSBANK',
            direccion_envio_snapshot={}, subtotal=10000, costo_envio=0, total_final=10000,
            estado='PAGADO', requiere_revision=True,
            motivo_revision='Pago confirmado sin stock para CAMISA-S',
            nombre_destinatario='Ana Pérez', telefono_destinatario='+56912345678',
        )

    def autenticar(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def resolver(self, orden_id=None):
        return self.client.post(
            reverse('admin-ordenes-resolver-revision', args=[orden_id or self.orden.id]))

    def test_listado_incluye_revision_y_transiciones_permitidas(self):
        self.autenticar(self.admin_token)
        orden, = self.client.get(reverse('admin-ordenes-list')).data['results']
        self.assertEqual(orden['estado'], 'PAGADO')
        self.assertTrue(orden['requiere_revision'])
        self.assertEqual(orden['motivo_revision'], 'Pago confirmado sin stock para CAMISA-S')
        self.assertEqual(orden['transiciones_permitidas'], ['EN_PREPARACION', 'CANCELADO'])
        self.assertEqual(orden['email_cliente'], 'invitado@example.test')
        # A quién contactar para coordinar la entrega (RF-02.3)
        self.assertEqual((orden['nombre_destinatario'], orden['telefono_destinatario']), ('Ana Pérez', '+56912345678'))

    def test_resolver_revision_quita_la_marca_una_sola_vez(self):
        self.autenticar(self.admin_token)
        response = self.resolver()
        self.assertEqual(response.status_code, 200)
        self.orden.refresh_from_db()
        self.assertFalse(self.orden.requiere_revision)
        self.assertEqual(self.orden.motivo_revision, 'Pago confirmado sin stock para CAMISA-S')

        self.assertEqual(self.resolver().status_code, 409)
        self.assertEqual(self.resolver(orden_id=999999).status_code, 404)

    def test_solo_el_admin_ve_el_panel_y_resuelve_revisiones(self):
        self.autenticar(self.buyer_token)
        self.assertEqual(self.client.get(reverse('admin-ordenes-list')).status_code, 403)
        self.assertEqual(self.resolver().status_code, 403)
        self.orden.refresh_from_db()
        self.assertTrue(self.orden.requiere_revision)


    def crear_orden_cancelada(self, motivo):
        return OrdenCompra.objects.create(
            email_invitado='prueba@example.test',
            metodo_pago='TRANSFERENCIA',
            direccion_envio_snapshot={},
            subtotal=10000,
            costo_envio=0,
            total_final=10000,
            estado='CANCELADO',
            motivo_cancelacion=motivo,
        )

    def test_registrar_pago_fuera_plazo_deja_orden_cancelada_en_revision(self):
        self.autenticar(self.admin_token)
        orden = self.crear_orden_cancelada('Pago no recibido a tiempo')

        response = self.client.post(
            reverse('admin-ordenes-pago-fuera-plazo', args=[orden.id])
        )

        self.assertEqual(response.status_code, 200)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, 'CANCELADO')
        self.assertTrue(orden.requiere_revision)
        self.assertEqual(
            orden.motivo_revision,
            'Transferencia recibida fuera de plazo: reembolsar o crear un pedido nuevo.',
        )

    def test_no_permite_registrar_pago_si_se_cancelo_por_otro_motivo(self):
        self.autenticar(self.admin_token)
        orden = self.crear_orden_cancelada('Cancelado por el administrador')

        response = self.client.post(
            reverse('admin-ordenes-pago-fuera-plazo', args=[orden.id])
        )

        self.assertEqual(response.status_code, 409)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, 'CANCELADO')
        self.assertFalse(orden.requiere_revision)

    def test_solo_el_admin_puede_registrar_pago_fuera_plazo(self):
        orden = self.crear_orden_cancelada('Pago no recibido a tiempo')
        self.autenticar(self.buyer_token)

        response = self.client.post(
            reverse('admin-ordenes-pago-fuera-plazo', args=[orden.id])
        )

        self.assertEqual(response.status_code, 403)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, 'CANCELADO')
        self.assertFalse(orden.requiere_revision)


class AdminOrdenTransporteTests(APITestCase):
    """RF-02.3: el admin genera o reintenta la OT desde el panel."""

    @classmethod
    def setUpTestData(cls):
        cls.buyer_token = Token.objects.create(user=create_user())
        cls.admin_token = Token.objects.create(user=create_user('admin@example.test', rol='ADMIN'))

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        self.orden = OrdenCompra.objects.create(
            email_invitado='invitado@example.test', metodo_pago='TRANSBANK',
            direccion_envio_snapshot={'comuna': 'PROVIDENCIA'}, subtotal=10000, costo_envio=0,
            total_final=10000, estado='PAGADO', proveedor_logistico='CHILEXPRESS',
            error_orden_transporte='Chilexpress no respondió',
        )
        parche = patch(TRANSPORTISTA)
        self.transportista = parche.start().return_value
        self.addCleanup(parche.stop)
        self.transportista.generar_orden_transporte.return_value = '712678904136'

    def generar(self, orden_id=None):
        return self.client.post(reverse('admin-ordenes-orden-transporte', args=[orden_id or self.orden.id]))

    def listado(self):
        orden, = self.client.get(reverse('admin-ordenes-list')).data['results']
        return orden

    def test_panel_ofrece_reintentar_y_el_reintento_guarda_la_ot(self):
        orden = self.listado()
        self.assertTrue(orden['puede_generar_orden_transporte'])
        self.assertEqual(orden['error_orden_transporte'], 'Chilexpress no respondió')

        response = self.generar()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['numero_seguimiento_tracking'], '712678904136')
        orden = self.listado()
        self.assertEqual((orden['numero_seguimiento_tracking'], orden['error_orden_transporte']),
                         ('712678904136', ''))
        self.assertFalse(orden['puede_generar_orden_transporte'])

    def test_fallo_del_transportista_es_502_y_queda_guardado(self):
        self.transportista.generar_orden_transporte.side_effect = ErrorOrdenTransporte('Sin cobertura')
        response = self.generar()
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data['detail'], 'Sin cobertura')
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.error_orden_transporte, 'Sin cobertura')

    def test_pedido_cancelado_o_en_revision_no_genera_ot(self):
        for cambios in ({'estado': 'CANCELADO'}, {'requiere_revision': True}):
            with self.subTest(cambios=cambios):
                OrdenCompra.objects.filter(id=self.orden.id).update(
                    **{'estado': 'PAGADO', 'requiere_revision': False, **cambios})
                self.assertFalse(self.listado()['puede_generar_orden_transporte'])
                self.assertEqual(self.generar().status_code, 409)
        self.transportista.generar_orden_transporte.assert_not_called()
        self.assertEqual(self.generar(orden_id=999999).status_code, 404)

    def test_solo_el_admin_genera_ot(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.buyer_token.key}')
        self.assertEqual(self.generar().status_code, 403)
        self.transportista.generar_orden_transporte.assert_not_called()


@patch.dict('os.environ', {'FRONTEND_URL': 'http://tienda.test'})
class AnulacionTransbankTests(APITestCase):
    def anular(self, orden_compra):
        return self.client.get(reverse('transbank_retorno'),
                               {'TBK_TOKEN': 'token-anulado', 'TBK_ORDEN_COMPRA': orden_compra})

    def test_anulacion_cancela_la_orden_y_lleva_a_pagina_publica(self):
        orden = OrdenCompra.objects.create(
            email_invitado='invitado@example.test', metodo_pago='TRANSBANK',
            direccion_envio_snapshot={}, subtotal=10000, costo_envio=0, total_final=10000,
        )
        response = self.anular(f'ORD-{orden.id}')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], f'http://tienda.test/pago-cancelado?orden={orden.id}')
        orden.refresh_from_db()
        self.assertEqual(orden.estado, 'CANCELADO')
        self.assertEqual(orden.motivo_cancelacion, 'Pago anulado por el comprador')

    def test_orden_invalida_redirige_sin_numero(self):
        for orden_compra in ('ORD-999999', 'ORD-abc'):
            with self.subTest(orden_compra=orden_compra):
                response = self.anular(orden_compra)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response['Location'], 'http://tienda.test/pago-cancelado')


@patch.dict('os.environ', {'FRONTEND_URL': 'http://tienda.test'})
class PagoAprobadoTransbankTests(APITestCase):
    """RF-02.2: la vista delega en ConfirmarPago (idempotente, stock todo o nada)."""

    def setUp(self):
        self.orden = OrdenCompra.objects.create(
            email_invitado='invitado@example.test', metodo_pago='TRANSBANK',
            direccion_envio_snapshot={}, subtotal=20000, costo_envio=0, total_final=20000,
        )
        DetalleOrden.objects.create(
            orden=self.orden, producto_mongo_id='camisa', variante_sku='CAMISA-S',
            nombre_producto_snapshot='Camisa - CAMISA-S', precio_unitario_snapshot=10000, cantidad=2,
        )
        self.inventario = InventarioFalso({('camisa', 'CAMISA-S'): 3})
        for objetivo, opciones in (
            ('views.inventario_variantes', {'return_value': self.inventario}),
            ('adapters.transbank_adapter.TransbankWebpayAdapter.confirmar_transaccion',
             {'return_value': {'exito': True, 'aprobado': True,
                               'data_completa': {'buy_order': f'ORD-{self.orden.id}'}}}),
        ):
            parche = patch(f'ecommerce.infrastructure.ventas.{objetivo}', **opciones)
            self.confirmar = parche.start()
            self.addCleanup(parche.stop)

    def confirmar_pago(self):
        return self.client.get(reverse('transbank_retorno'), {'token_ws': 'token-tbk'})

    def test_pago_aprobado_descuenta_stock_de_cada_detalle(self):
        response = self.confirmar_pago()

        self.assertEqual(response['Location'], f'http://tienda.test/pago-exitoso?orden={self.orden.id}')
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, 'PAGADO')
        self.assertTrue(self.orden.stock_descontado)
        self.assertFalse(self.orden.requiere_revision)
        self.assertEqual(self.inventario.stock[('camisa', 'CAMISA-S')], 1)

    def test_si_el_proceso_cae_al_descontar_la_orden_ya_esta_marcada_para_revision(self):
        class ProcesoInterrumpido(BaseException):
            pass

        self.inventario.falla_en = ('camisa', 'CAMISA-S')
        self.inventario.error = ProcesoInterrumpido()
        with self.assertRaises(ProcesoInterrumpido):
            self.confirmar_pago()

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, 'PAGADO')
        self.assertTrue(self.orden.requiere_revision)
        self.assertIn('la confirmación del stock no terminó', self.orden.motivo_revision)
        self.assertFalse(self.orden.stock_descontado)

    def test_error_del_inventario_lleva_al_comprador_al_aviso_de_revision(self):
        self.inventario.falla_en = ('camisa', 'CAMISA-S')
        with self.assertLogs('ecommerce.infrastructure.ventas.views', level='ERROR'):
            response = self.confirmar_pago()

        self.assertEqual(response['Location'], f'http://tienda.test/pago-exitoso?orden={self.orden.id}&revision=1')

    def test_confirmacion_duplicada_no_descuenta_stock_dos_veces(self):
        # Si la orden fuera de Chilexpress, una segunda OT también sería un efecto duplicado
        OrdenCompra.objects.filter(id=self.orden.id).update(
            proveedor_logistico='CHILEXPRESS', direccion_envio_snapshot={'comuna': 'Santiago'},
            telefono_destinatario='+56912345678')
        with patch(TRANSPORTISTA) as transportista:
            logistica = transportista.return_value
            logistica.generar_orden_transporte.return_value = '1'
            self.confirmar_pago()
            response = self.confirmar_pago()

        self.assertEqual(response['Location'], f'http://tienda.test/pago-exitoso?orden={self.orden.id}')
        self.assertEqual(self.inventario.stock[('camisa', 'CAMISA-S')], 1)
        logistica.generar_orden_transporte.assert_called_once()
        # Guardar la OT no debe pisar el estado ni las marcas que dejó el caso de uso
        self.orden.refresh_from_db()
        self.assertEqual((self.orden.estado, self.orden.stock_descontado, self.orden.numero_seguimiento_tracking),
                         ('PAGADO', True, '1'))

    def test_pago_confirmado_sin_stock_queda_pagado_y_en_revision_sin_ot(self):
        self.inventario.stock[('camisa', 'CAMISA-S')] = 1
        OrdenCompra.objects.filter(id=self.orden.id).update(proveedor_logistico='CHILEXPRESS')
        with patch(TRANSPORTISTA) as transportista, \
                self.assertLogs('ecommerce.infrastructure.ventas.views', level='ERROR') as logs:
            logistica = transportista.return_value
            response = self.confirmar_pago()

        # El comprador ve que su pago llegó y que la tienda revisará el pedido
        self.assertEqual(response['Location'], f'http://tienda.test/pago-exitoso?orden={self.orden.id}&revision=1')
        self.assertIn('Pago confirmado sin stock para CAMISA-S', logs.output[0])
        logistica.generar_orden_transporte.assert_not_called()
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, 'PAGADO')
        self.assertTrue(self.orden.requiere_revision)
        self.assertEqual(self.orden.motivo_revision, 'Pago confirmado sin stock para CAMISA-S')
        self.assertFalse(self.orden.stock_descontado)
        self.assertEqual(self.inventario.stock[('camisa', 'CAMISA-S')], 1)

    def test_pago_rechazado_cancela_la_orden_con_motivo(self):
        self.confirmar.return_value = {**self.confirmar.return_value, 'aprobado': False}
        response = self.confirmar_pago()

        self.assertEqual(response['Location'], f'http://tienda.test/pago-rechazado?orden={self.orden.id}')
        self.orden.refresh_from_db()
        self.assertEqual((self.orden.estado, self.orden.motivo_cancelacion), ('CANCELADO', 'Pago rechazado'))
        self.assertEqual(self.inventario.stock[('camisa', 'CAMISA-S')], 3)


class DireccionesEnvioTests(APITestCase):
    def setUp(self):
        self.client.force_authenticate(create_user('direcciones@example.test'))
        self.direccion = {'calle': 'Av. Principal', 'calle_numero': '123', 'dpto_casa': '',
                          'comuna': 'SANTIAGO CENTRO', 'ciudad': 'Santiago', 'es_predeterminado': True}

    def test_la_region_es_opcional_como_la_envia_el_checkout(self):
        # El checkout no pide la región (Chilexpress usa la comuna) y la manda vacía al guardar la dirección
        for region in ('', None):
            with self.subTest(region=region):
                datos = {**self.direccion, 'region': ''} if region == '' else self.direccion
                response = self.client.post(reverse('direcciones-list-create'), datos, format='json')

                self.assertEqual(response.status_code, 201, response.data)
                self.assertEqual(response.data['region'], '')

    def test_la_region_se_guarda_si_viene(self):
        response = self.client.post(reverse('direcciones-list-create'), {**self.direccion, 'region': 'Metropolitana'},
                                    format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['region'], 'Metropolitana')

class BannerVideoAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.configuracion = ConfiguracionGlobal.objects.create(
            pk=1,
            nombre_tienda='Tienda QA Video',
            texto_bienvenida='Bienvenido a Tienda QA',
        )
        cls.admin = create_user(
            'admin-video@example.test',
            rol='ADMIN',
        )

    def setUp(self):
        self.client.force_authenticate(user=self.admin)

    def crear_video(self):
        return SimpleUploadedFile(
            'banner.mp4',
            b'\x00\x00\x00\x18ftypisom' + b'\x00' * 100,
            content_type='video/mp4',
        )

    def crear_imagen(self):
        import io
        from PIL import Image

        buffer = io.BytesIO()
        Image.new('RGB', (100, 100), color='red').save(
            buffer,
            format='PNG',
        )

        return SimpleUploadedFile(
            'portada.png',
            buffer.getvalue(),
            content_type='image/png',
        )

    def subir_video(self):
        return self.client.put(
            reverse('configuracion-negocio'),
            {
                'banner_orden': json.dumps([
                    {
                        'ref': 'nuevo:0',
                        'titulo': 'Banner con video',
                        'video_indice': 0,
                    }
                ]),
                'banner_fotos': [self.crear_imagen()],
                'banner_videos': [self.crear_video()],
                'video_banner_activo': 'true',
            },
            format='multipart',
        )

    def test_admin_puede_subir_video_con_portada(self):
        with tempfile.TemporaryDirectory() as carpeta:
            with override_settings(MEDIA_ROOT=carpeta):
                response = self.client.put(
                    reverse('configuracion-negocio'),
                    {
                        'banner_orden': json.dumps([
                            {
                                'ref': 'nuevo:0',
                                'titulo': 'Banner con video',
                                'video_indice': 0,
                            }
                        ]),
                        'banner_fotos': [self.crear_imagen()],
                        'banner_videos': [self.crear_video()],
                        'video_banner_activo': 'true',
                    },
                    format='multipart',
                )

                self.assertEqual(
                    response.status_code,
                    200,
                    response.data,
                )

                foto = FotoBanner.objects.get(
                    configuracion=self.configuracion
                )

                self.assertTrue(bool(foto.imagen))
                self.assertTrue(bool(foto.video))
                self.assertTrue(foto.video.name.endswith('.mp4'))

                self.assertEqual(
                    len(response.data['banners']),
                    1,
                )
                self.assertIsNotNone(
                    response.data['banners'][0]['video']
                )

    def test_admin_puede_reordenar_video(self):
        with tempfile.TemporaryDirectory() as carpeta:
            with override_settings(MEDIA_ROOT=carpeta):
                response = self.subir_video()
                self.assertEqual(response.status_code, 200, response.data)

                video = FotoBanner.objects.get(
                    configuracion=self.configuracion
                )
                nombre_video = video.video.name

                response = self.client.put(
                    reverse('configuracion-negocio'),
                    {
                        'banner_orden': json.dumps([
                            {
                                'ref': 'nuevo:0',
                                'titulo': 'Banner de imagen',
                            },
                            {
                                'ref': f'id:{video.id}',
                                'titulo': 'Banner con video',
                            },
                        ]),
                        'banner_fotos': [self.crear_imagen()],
                    },
                    format='multipart',
                )

                self.assertEqual(response.status_code, 200, response.data)

                video.refresh_from_db()
                self.assertEqual(video.orden, 1)
                self.assertEqual(video.video.name, nombre_video)
                self.assertEqual(
                    FotoBanner.objects.filter(
                        configuracion=self.configuracion
                    ).count(),
                    2,
                )

    def test_admin_puede_eliminar_video(self):
        with tempfile.TemporaryDirectory() as carpeta:
            with override_settings(MEDIA_ROOT=carpeta):
                response = self.subir_video()
                self.assertEqual(response.status_code, 200, response.data)

                video = FotoBanner.objects.get(
                    configuracion=self.configuracion
                )
                video_id = video.id

                response = self.client.put(
                    reverse('configuracion-negocio'),
                    {
                        'banner_orden': '[]',
                    },
                    format='multipart',
                )

                self.assertEqual(response.status_code, 200, response.data)

                self.assertFalse(
                    FotoBanner.objects.filter(
                        id=video_id
                    ).exists()
                )
                self.assertEqual(response.data['banners'], [])

    def test_rechaza_segundo_video_en_banner(self):
        with tempfile.TemporaryDirectory() as carpeta:
            with override_settings(MEDIA_ROOT=carpeta):
                response = self.subir_video()
                self.assertEqual(response.status_code, 200, response.data)

                video_original = FotoBanner.objects.get(
                    configuracion=self.configuracion
                )
                nombre_original = video_original.video.name

                response = self.client.put(
                    reverse('configuracion-negocio'),
                    {
                        'banner_orden': json.dumps([
                            {'ref': f'id:{video_original.id}'},
                            {'ref': 'nuevo:0', 'video_indice': 0},
                        ]),
                        'banner_fotos': [self.crear_imagen()],
                        'banner_videos': [self.crear_video()],
                    },
                    format='multipart',
                )

                self.assertEqual(response.status_code, 400, response.data)

                self.assertEqual(
                    FotoBanner.objects.filter(
                        configuracion=self.configuracion
                    ).count(),
                    1,
                )

                video_original.refresh_from_db()
                self.assertEqual(video_original.video.name, nombre_original)

    def test_rechaza_video_mayor_a_10_mb(self):
        with tempfile.TemporaryDirectory() as carpeta:
            with override_settings(MEDIA_ROOT=carpeta):
                video_grande = SimpleUploadedFile(
                    'video_grande.mp4',
                    b'\x00\x00\x00\x18ftypisom'
                    + b'\x00' * (10 * 1024 * 1024),
                    content_type='video/mp4',
                )

                response = self.client.put(
                    reverse('configuracion-negocio'),
                    {
                        'banner_orden': json.dumps([
                            {'ref': 'nuevo:0', 'video_indice': 0}
                        ]),
                        'banner_fotos': [self.crear_imagen()],
                        'banner_videos': [video_grande],
                    },
                    format='multipart',
                )

                self.assertEqual(response.status_code, 400, response.data)

                self.assertFalse(
                    FotoBanner.objects.filter(
                        configuracion=self.configuracion
                    ).exists()
                )