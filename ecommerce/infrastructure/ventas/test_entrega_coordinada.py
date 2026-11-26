"""Entrega coordinada (RF-02.3): la tienda acuerda la entrega con el comprador, sin transportista."""

from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse
from rest_framework.test import APITestCase

from ecommerce.domain.ventas import VarianteCatalogo
from ecommerce.infrastructure.usuarios.tests.factories import create_user

from .models import ConfiguracionGlobal, OrdenCompra, Promocion, ProveedorEnvio
from .test_chilexpress import guardar_credenciales
from .test_logistica import ADAPTADOR_CHILEXPRESS, ITEMS
from .tests import DESTINATARIO, habilitar_medios_pago, usar_catalogo_falso

DIRECCION = {'calle': 'Los Aromos', 'numero': '1550', 'comuna': 'Ñuñoa', 'ciudad': 'Santiago'}


class CheckoutEntregaCoordinadaTests(APITestCase):
    def setUp(self):
        habilitar_medios_pago('TRANSFERENCIA')
        self.config = ConfiguracionGlobal.objects.create(
            pk=1, nombre_tienda='QA', retiro_en_local_activo=False,
            entrega_coordinada_activa=True, costo_entrega_coordinada=3000,
        )
        usar_catalogo_falso(self, {
            ('polera', 'POLERA-M'): VarianteCatalogo('Polera - POLERA-M', Decimal('25000'), 5, True),
        })

    def comprar(self, **cambios):
        payload = {
            'email_invitado': 'cliente@example.test', 'metodo_pago': 'TRANSFERENCIA',
            'acepta_terminos': True, 'items': ITEMS, **DESTINATARIO,
            'direccion_envio_snapshot': DIRECCION, 'subtotal': 25000,
            # El navegador no decide el costo: se ignora
            'costo_envio': 1, 'total_final': 1,
            'proveedor_logistico': 'ENTREGA_COORDINADA', **cambios,
        }
        return self.client.post(reverse('checkout'), payload, format='json')

    @patch(f'{ADAPTADOR_CHILEXPRESS}.requests.post')
    def test_cobra_el_costo_del_admin_sin_cotizar_con_un_transportista(self, post):
        response = self.comprar()

        self.assertEqual(response.status_code, 201, response.data)
        orden = OrdenCompra.objects.get()
        self.assertEqual(orden.proveedor_logistico, 'ENTREGA_COORDINADA')
        self.assertEqual(orden.costo_envio, 3000)
        self.assertEqual(orden.total_final, 28000)
        self.assertEqual(orden.direccion_envio_snapshot['calle'], 'Los Aromos')
        self.assertIsNone(orden.paquete)
        post.assert_not_called()

    def test_se_rechaza_si_el_admin_no_la_activo(self):
        self.config.entrega_coordinada_activa = False
        self.config.save(update_fields=['entrega_coordinada_activa'])

        response = self.comprar()

        self.assertEqual(response.status_code, 400)
        self.assertIn('proveedor_logistico', response.data)
        self.assertFalse(OrdenCompra.objects.exists())

    def test_activarla_no_habilita_el_retiro_en_local(self):
        response = self.comprar(proveedor_logistico='RETIRO_LOCAL', direccion_envio_snapshot={})

        self.assertEqual(response.status_code, 400)
        self.assertIn('proveedor_logistico', response.data)

    def test_la_direccion_es_opcional_y_la_tienda_la_acuerda_con_el_comprador(self):
        response = self.comprar(direccion_envio_snapshot={})

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(OrdenCompra.objects.get().direccion_envio_snapshot, {})

    def test_si_escribe_una_direccion_exige_la_calle_y_la_comuna(self):
        for direccion in ({'calle': 'Los Aromos'}, {'comuna': 'Ñuñoa'}, {'comuna': 'Ñuñoa', 'calle': '  '},
                          {'numero': '1550'}):
            with self.subTest(direccion=direccion):
                response = self.comprar(direccion_envio_snapshot=direccion)
                self.assertEqual(response.status_code, 400)
                self.assertIn('direccion_envio_snapshot', response.data)
        self.assertFalse(OrdenCompra.objects.exists())

    def test_el_panel_muestra_la_direccion_para_coordinar_la_entrega(self):
        self.assertEqual(self.comprar().status_code, 201)
        self.client.force_authenticate(create_user('admin-pedidos@example.test', rol='ADMIN'))

        pedido, = self.client.get(reverse('admin-ordenes-list')).data['results']

        self.assertEqual(pedido['proveedor_logistico'], 'ENTREGA_COORDINADA')
        self.assertEqual(pedido['direccion_envio_snapshot']['calle'], 'Los Aromos')
        self.assertFalse(pedido['puede_generar_orden_transporte'])

    def test_el_envio_gratis_sobre_un_monto_tambien_la_cubre(self):
        Promocion.objects.create(codigo='GRATIS', tipo_descuento='MONTO_FIJO', valor_descuento=0,
                                 umbral_envio_gratis=20000)

        response = self.comprar(codigo_promocion='GRATIS')

        self.assertEqual(response.status_code, 201, response.data)
        orden = OrdenCompra.objects.get()
        self.assertEqual(orden.costo_envio, 0)
        self.assertEqual(orden.total_final, 25000)


class ConfiguracionEntregaCoordinadaTests(APITestCase):
    def setUp(self):
        ConfiguracionGlobal.objects.create(pk=1, nombre_tienda='QA')
        # La migración 0022 copia a la base las llaves que haya en el entorno: se parte sin ninguna
        ProveedorEnvio.objects.all().delete()
        self.client.force_authenticate(create_user('admin-entrega@example.test', rol='ADMIN'))

    def editar(self, **datos):
        return self.client.patch(reverse('configuracion-negocio'), datos, format='json')

    def publica(self):
        self.client.force_authenticate(None)
        return self.client.get(reverse('configuracion-global')).data

    def test_el_admin_la_activa_y_el_checkout_la_ve_con_su_costo_e_instrucciones(self):
        response = self.editar(entrega_coordinada_activa=True, costo_entrega_coordinada=2500,
                               instrucciones_entrega_coordinada='Te escribimos por WhatsApp para coordinar.')

        self.assertEqual(response.status_code, 200, response.data)
        datos = self.publica()
        self.assertTrue(datos['entrega_coordinada_activa'])
        self.assertEqual(datos['costo_entrega_coordinada'], 2500)
        self.assertEqual(datos['instrucciones_entrega_coordinada'], 'Te escribimos por WhatsApp para coordinar.')

    def test_viene_desactivada_y_gratis(self):
        datos = self.publica()
        self.assertFalse(datos['entrega_coordinada_activa'])
        self.assertEqual(datos['costo_entrega_coordinada'], 0)

    def test_rechaza_un_costo_negativo_o_desmedido_y_unas_instrucciones_muy_largas(self):
        for datos in ({'costo_entrega_coordinada': -1}, {'costo_entrega_coordinada': 1_000_001},
                      {'instrucciones_entrega_coordinada': 'x' * 301}):
            with self.subTest(datos=datos):
                response = self.editar(**datos)
                self.assertEqual(response.status_code, 400)
                self.assertIn(next(iter(datos)), response.data)
        self.assertEqual(ConfiguracionGlobal.objects.get().costo_entrega_coordinada, 0)

    def test_un_comprador_no_puede_cambiarla(self):
        self.client.force_authenticate(create_user('comprador-entrega@example.test'))
        response = self.editar(entrega_coordinada_activa=True)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ConfiguracionGlobal.objects.get().entrega_coordinada_activa)

    def test_la_configuracion_publica_dice_que_couriers_hay_sin_mostrar_sus_llaves(self):
        self.assertEqual(self.publica()['couriers'], [])

        guardar_credenciales(cotizador='llave-secreta-1234')

        datos = self.publica()
        self.assertEqual(datos['couriers'], [{'codigo': 'CHILEXPRESS', 'nombre': 'Chilexpress', 'sucursales': True}])
        self.assertNotIn('llave-secreta', str(datos))
