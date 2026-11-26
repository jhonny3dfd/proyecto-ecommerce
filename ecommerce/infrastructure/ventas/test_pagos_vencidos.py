from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.test import APITestCase

from ecommerce.domain.medios_pago import CodigoMedioPago, MedioPagoConfigurado
from ecommerce.domain.ventas import VarianteCatalogo, plazo_pago

from .models import ConfiguracionGlobal, OrdenCompra
from .repositorio_medios_pago import DjangoRepositorioMediosPago
from .tests import DATOS_MEDIOS_PAGO, DESTINATARIO, habilitar_medios_pago, usar_catalogo_falso


@patch.dict('os.environ', {'FRONTEND_URL': 'http://tienda.test'})
class ComandoCancelarPagosVencidosTests(TestCase):
    """Plazo de pago: `manage.py cancelar_pagos_vencidos` cancela las transferencias vencidas y avisa."""

    def setUp(self):
        ConfiguracionGlobal.objects.create(id=1, nombre_tienda='Tienda QA')
        habilitar_medios_pago('TRANSFERENCIA')

    def crear(self, horas, metodo_pago='TRANSFERENCIA', estado='PENDIENTE', plazo=48):
        orden = OrdenCompra.objects.create(
            email_invitado='invitado@example.test', metodo_pago=metodo_pago, estado=estado,
            direccion_envio_snapshot={}, subtotal=10000, costo_envio=0, total_final=10000,
            proveedor_logistico='RETIRO_LOCAL')
        # fecha_creacion es auto_now_add: se ajusta después de crear, con el plazo que fijaría el checkout
        creada = timezone.now() - timedelta(hours=horas)
        fechas = plazo_pago(creada, timedelta(hours=plazo)) if metodo_pago == 'TRANSFERENCIA' else None
        OrdenCompra.objects.filter(id=orden.id).update(
            fecha_creacion=creada, fecha_limite_pago=fechas and fechas.vence,
            fecha_recordatorio_pago=fechas and fechas.recordar)
        return orden

    def ejecutar(self):
        salida = StringIO()
        with self.captureOnCommitCallbacks(execute=True):
            call_command('cancelar_pagos_vencidos', stdout=salida)
        return salida.getvalue()

    def test_cancela_la_transferencia_vencida_y_envia_el_correo(self):
        vencida = self.crear(49)
        a_tiempo = self.crear(1)
        webpay = self.crear(49, metodo_pago='TRANSBANK')

        salida = self.ejecutar()

        self.assertIn(f'#{vencida.id}', salida)
        vencida.refresh_from_db()
        self.assertEqual((vencida.estado, vencida.motivo_cancelacion), ('CANCELADO', 'Pago no recibido a tiempo'))
        for orden in (a_tiempo, webpay):
            orden.refresh_from_db()
            self.assertEqual(orden.estado, 'PENDIENTE')
        correo, = mail.outbox
        self.assertEqual(correo.subject, f'Tu pedido #{vencida.id} fue cancelado | Tienda QA')
        self.assertIn('No recibimos el pago de tu transferencia dentro de las 48 horas', correo.body)

    def test_sin_ordenes_vencidas_no_hace_nada(self):
        self.crear(1)
        salida = self.ejecutar()
        self.assertIn('No hay órdenes con el pago vencido', salida)
        self.assertNotIn('Recordatorios', salida)
        self.assertEqual(mail.outbox, [])

    def test_a_las_24_horas_recuerda_el_pago_una_sola_vez_con_el_plazo(self):
        por_vencer = self.crear(25)
        self.crear(1)

        self.assertIn(f'Recordatorios de pago enviados: #{por_vencer.id}.', self.ejecutar())

        por_vencer.refresh_from_db()
        self.assertEqual((por_vencer.estado, por_vencer.recordatorio_pago_enviado), ('PENDIENTE', True))
        correo, = mail.outbox
        self.assertEqual(correo.subject, f'Recuerda pagar tu pedido #{por_vencer.id} | Tienda QA')
        vence = timezone.localtime(por_vencer.fecha_creacion + timedelta(hours=48))
        self.assertIn(f"Tienes hasta el {vence.strftime('%d-%m-%Y a las %H:%M')} para transferir", correo.body)
        self.assertIn(f'Número de cuenta: {DATOS_MEDIOS_PAGO["TRANSFERENCIA"]["numero_cuenta"]}', correo.body)
        self.assertIn('Tienes hasta el', correo.alternatives[0][0])

        self.ejecutar()
        self.assertEqual(len(mail.outbox), 1)

    def test_una_orden_vencida_se_cancela_sin_recordatorio(self):
        self.crear(49)
        self.assertNotIn('Recordatorios', self.ejecutar())
        correo, = mail.outbox
        self.assertIn('fue cancelado', correo.subject)

    def test_cada_orden_vence_con_el_plazo_que_tenia_la_tienda(self):
        corta = self.crear(13, plazo=12)
        larga = self.crear(49, plazo=72)

        self.ejecutar()

        corta.refresh_from_db()
        larga.refresh_from_db()
        self.assertEqual(corta.estado, 'CANCELADO')
        self.assertEqual(larga.estado, 'PENDIENTE')
        correo = next(c for c in mail.outbox if 'fue cancelado' in c.subject)
        self.assertIn('No recibimos el pago de tu transferencia dentro de las 12 horas', correo.body)

    def test_recuerda_a_la_mitad_de_un_plazo_de_12_horas(self):
        por_vencer = self.crear(7, plazo=12)
        self.assertIn(f'Recordatorios de pago enviados: #{por_vencer.id}.', self.ejecutar())
        por_vencer.refresh_from_db()
        vence = timezone.localtime(por_vencer.fecha_creacion + timedelta(hours=12))
        self.assertIn(f"Tienes hasta el {vence.strftime('%d-%m-%Y a las %H:%M')} para transferir", mail.outbox[0].body)


class CheckoutPlazoPagoTests(APITestCase):
    """El checkout fija en la orden el plazo que la tienda eligió en Medios de pago > Transferencia."""

    def setUp(self):
        ConfiguracionGlobal.objects.create(id=1, nombre_tienda='Tienda QA', retiro_en_local_activo=True)
        usar_catalogo_falso(self, {
            ('polera', 'POLERA-M'): VarianteCatalogo('Polera - POLERA-M', Decimal('25000'), 5, True),
        })

    def elegir_plazo(self, horas):
        datos = dict(DATOS_MEDIOS_PAGO['TRANSFERENCIA'])
        if horas:
            datos['plazo_pago_horas'] = horas
        DjangoRepositorioMediosPago().guardar(MedioPagoConfigurado(CodigoMedioPago.TRANSFERENCIA, True, datos))

    def comprar(self, metodo_pago='TRANSFERENCIA'):
        return self.client.post(reverse('checkout'), {
            'email_invitado': 'cliente@example.test', 'metodo_pago': metodo_pago, 'acepta_terminos': True,
            'items': [{'producto_mongo_id': 'polera', 'variante_sku': 'POLERA-M', 'cantidad': 1}],
            'direccion_envio_snapshot': {}, 'subtotal': 25000, 'proveedor_logistico': 'RETIRO_LOCAL',
            **DESTINATARIO,
        }, format='json')

    def test_guarda_la_fecha_limite_y_la_del_recordatorio_con_el_plazo_de_la_tienda(self):
        self.elegir_plazo('24')

        response = self.comprar()

        self.assertEqual(response.status_code, 201, response.data)
        orden = OrdenCompra.objects.get()
        self.assertEqual(orden.fecha_limite_pago, orden.fecha_creacion + timedelta(hours=24))
        self.assertEqual(orden.fecha_recordatorio_pago, orden.fecha_creacion + timedelta(hours=12))
        # El comprador ve la misma fecha límite en la pantalla de pedido recibido
        self.assertEqual(parse_datetime(str(response.data['instrucciones_pago']['vence'])), orden.fecha_limite_pago)

    def test_sin_elegir_plazo_son_48_horas(self):
        self.elegir_plazo(None)
        self.assertEqual(self.comprar().status_code, 201)
        orden = OrdenCompra.objects.get()
        self.assertEqual(orden.fecha_limite_pago, orden.fecha_creacion + timedelta(hours=48))

    def test_cambiar_el_plazo_no_altera_los_pedidos_que_ya_existen(self):
        self.elegir_plazo('12')
        self.comprar()
        orden = OrdenCompra.objects.get()

        self.elegir_plazo('72')

        orden.refresh_from_db()
        self.assertEqual(orden.fecha_limite_pago, orden.fecha_creacion + timedelta(hours=12))

    def test_los_demas_medios_de_pago_no_tienen_plazo(self):
        habilitar_medios_pago('TRANSBANK')
        with patch('ecommerce.infrastructure.ventas.adapters.transbank_adapter.TransbankWebpayAdapter.iniciar_transaccion',
                   return_value={'exito': True, 'url_pago': 'https://webpay.test', 'token': 'tok'}):
            self.assertEqual(self.comprar('TRANSBANK').status_code, 201)
        orden = OrdenCompra.objects.get()
        self.assertIsNone(orden.fecha_limite_pago)
        self.assertIsNone(orden.fecha_recordatorio_pago)
