"""Compra como empresa: el checkout recibe los datos para la factura, que la tienda emite por su cuenta."""

from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.urls import reverse
from rest_framework.test import APITestCase

from ecommerce.domain.ventas import VarianteCatalogo
from ecommerce.infrastructure.usuarios.tests.factories import create_user

from .models import ConfiguracionGlobal, EmpresaComprador, OrdenCompra
from .tests import DESTINATARIO, habilitar_medios_pago, usar_catalogo_falso

EMPRESA = {'razon_social': 'Comercial Andes SpA', 'rut': '76123456-0', 'giro': 'Venta de artículos de regalo',
           'direccion': 'Av. Providencia 1234, Providencia', 'correo': 'facturas@andes.test'}


@patch.dict('os.environ', {'FRONTEND_URL': 'http://tienda.test'})
class CheckoutCompraEmpresaTests(APITestCase):
    def setUp(self):
        habilitar_medios_pago('TRANSFERENCIA')
        ConfiguracionGlobal.objects.create(pk=1, nombre_tienda='Tienda QA', retiro_en_local_activo=True)
        usar_catalogo_falso(self, {
            ('polera', 'POLERA-M'): VarianteCatalogo('Polera - POLERA-M', Decimal('25000'), 5, True),
        })

    def comprar(self, sin_empresa=False, **cambios):
        payload = {
            'email_invitado': 'compras@andes.test', 'metodo_pago': 'TRANSFERENCIA', 'acepta_terminos': True,
            'items': [{'producto_mongo_id': 'polera', 'variante_sku': 'POLERA-M', 'cantidad': 1}],
            'direccion_envio_snapshot': {}, 'subtotal': 25000, 'proveedor_logistico': 'RETIRO_LOCAL',
            'datos_empresa': EMPRESA, **DESTINATARIO, **cambios,
        }
        if sin_empresa:
            del payload['datos_empresa']
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse('checkout'), payload, format='json')

    def test_guarda_los_datos_de_la_empresa_con_el_rut_normalizado(self):
        response = self.comprar()

        self.assertEqual(response.status_code, 201, response.data)
        esperado = {**EMPRESA, 'rut': '76.123.456-0'}
        self.assertEqual(OrdenCompra.objects.get().datos_empresa, esperado)
        self.assertEqual(response.data['datos_empresa'], esperado)

    def test_una_persona_compra_sin_datos_de_empresa(self):
        # El checkout envía null; un cliente anterior a este cambio no envía el campo
        for cambios in ({'datos_empresa': None}, {'sin_empresa': True}):
            with self.subTest(cambios=cambios):
                OrdenCompra.objects.all().delete()
                response = self.comprar(**cambios)
                self.assertEqual(response.status_code, 201, response.data)
                self.assertIsNone(OrdenCompra.objects.get().datos_empresa)

    def test_rechaza_un_rut_invalido_o_datos_incompletos_sin_crear_la_orden(self):
        for empresa, campos in (({**EMPRESA, 'rut': '76.123.456-1'}, {'rut'}),
                                ({**EMPRESA, 'giro': '', 'razon_social': '  '}, {'giro', 'razon_social'}),
                                ({**EMPRESA, 'correo': 'no-es-un-correo'}, {'correo'})):
            with self.subTest(campos=campos):
                response = self.comprar(datos_empresa=empresa)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(set(response.data['datos_empresa']), campos)
        self.assertFalse(OrdenCompra.objects.exists())

    def test_el_correo_de_confirmacion_lleva_los_datos_para_la_factura(self):
        self.comprar()

        correo, = mail.outbox
        self.assertIn('DATOS PARA LA FACTURA', correo.body)
        self.assertIn('RUT: 76.123.456-0', correo.body)
        self.assertIn('Razón social: Comercial Andes SpA', correo.body)
        self.assertIn('Datos para la factura', correo.alternatives[0][0])

    def test_el_correo_de_una_persona_no_menciona_la_factura(self):
        self.comprar(datos_empresa=None)
        self.assertNotIn('FACTURA', mail.outbox[0].body)

    def test_el_panel_de_ventas_muestra_los_datos_para_la_factura(self):
        self.comprar()
        self.client.force_authenticate(create_user('admin-factura@example.test', rol='ADMIN'))

        pedido, = self.client.get(reverse('admin-ordenes-list')).data['results']

        self.assertEqual(pedido['datos_empresa']['rut'], '76.123.456-0')


class EmpresaGuardadaTests(APITestCase):
    """Un comprador registrado guarda los datos de su empresa para las próximas compras."""

    def setUp(self):
        habilitar_medios_pago('TRANSFERENCIA')
        ConfiguracionGlobal.objects.create(pk=1, nombre_tienda='Tienda QA', retiro_en_local_activo=True)
        usar_catalogo_falso(self, {
            ('polera', 'POLERA-M'): VarianteCatalogo('Polera - POLERA-M', Decimal('25000'), 5, True),
        })
        self.comprador = create_user('compras-andes@example.test')

    def comprar(self, **cambios):
        return self.client.post(reverse('checkout'), {
            'metodo_pago': 'TRANSFERENCIA', 'acepta_terminos': True, 'subtotal': 25000,
            'items': [{'producto_mongo_id': 'polera', 'variante_sku': 'POLERA-M', 'cantidad': 1}],
            'direccion_envio_snapshot': {}, 'proveedor_logistico': 'RETIRO_LOCAL', 'datos_empresa': EMPRESA,
            **DESTINATARIO, **cambios,
        }, format='json')

    def test_guarda_y_actualiza_los_datos_cuando_el_comprador_lo_pide(self):
        self.client.force_authenticate(self.comprador)
        self.assertEqual(self.client.get(reverse('empresa-comprador')).status_code, 204)

        self.assertEqual(self.comprar(guardar_datos_empresa=True).status_code, 201)
        guardados = self.client.get(reverse('empresa-comprador'))
        self.assertEqual(guardados.status_code, 200)
        self.assertEqual(guardados.data, {**EMPRESA, 'rut': '76.123.456-0'})

        self.comprar(guardar_datos_empresa=True, datos_empresa={**EMPRESA, 'giro': 'Merchandising'})
        self.assertEqual(EmpresaComprador.objects.get(usuario=self.comprador).giro, 'Merchandising')

    def test_sin_pedirlo_no_se_guardan(self):
        self.client.force_authenticate(self.comprador)
        self.assertEqual(self.comprar().status_code, 201)
        self.assertFalse(EmpresaComprador.objects.exists())

    def test_un_invitado_no_guarda_datos_aunque_lo_pida(self):
        response = self.comprar(guardar_datos_empresa=True, email_invitado='invitado@example.test')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertFalse(EmpresaComprador.objects.exists())

    def test_cada_comprador_ve_solo_sus_datos_y_un_anonimo_ninguno(self):
        EmpresaComprador.objects.create(usuario=self.comprador, **EMPRESA)
        self.assertEqual(self.client.get(reverse('empresa-comprador')).status_code, 401)
        self.client.force_authenticate(create_user('otro-comprador@example.test'))
        self.assertEqual(self.client.get(reverse('empresa-comprador')).status_code, 204)
