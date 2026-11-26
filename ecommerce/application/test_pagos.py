from decimal import Decimal

from django.test import SimpleTestCase

from ecommerce.application.pagos import (
    AplicarResultadoPago, FirmaAvisoInvalida, PagoConsultado, PagoIniciado, PasarelaConAvisos, ProcesarAvisoPago,
)
from ecommerce.application.test_ventas import InventarioFalso, NotificadorFalso, RepositorioOrdenesFalso
from ecommerce.application.ventas import (
    MOTIVO_PAGO_ANULADO, MOTIVO_PAGO_RECHAZADO, ConfirmarPago, ResultadoPago,
)
from ecommerce.domain.medios_pago import EstadoPago
from ecommerce.domain.ventas import EstadoPedido, EventoPedido


class PasarelaFalsa(PasarelaConAvisos):
    def __init__(self, pago=None, firma_valida=True):
        self.pago, self.firma_valida = pago, firma_valida
        self.consultadas = []

    def iniciar(self, orden_id, monto, url_retorno, url_aviso=''):
        return PagoIniciado(referencia=f'ref-{orden_id}', url_pago='https://pasarela.test/pagar')

    def resultado(self, referencia):
        self.consultadas.append(referencia)
        return self.pago

    def aviso_autentico(self, firma, id_peticion, referencia):
        return self.firma_valida


def pago(estado, orden_id='1', monto=None):
    return PagoConsultado(referencia='801', orden_id=orden_id, estado=estado, monto=monto)


class AplicarResultadoPagoTests(SimpleTestCase):
    def setUp(self):
        self.ordenes = RepositorioOrdenesFalso()
        self.notificador = NotificadorFalso()
        self.inventario = InventarioFalso({('camisa', 'CAMISA-S'): 1})
        self.orden = self.ordenes.agregar('1', 'PENDIENTE', [('camisa', 'CAMISA-S', 1)])
        self.caso = AplicarResultadoPago(ConfirmarPago(self.ordenes, self.inventario, notificador=self.notificador))

    def test_aprobado_confirma_el_pago_y_descuenta_stock(self):
        self.assertEqual(self.caso.ejecutar(pago(EstadoPago.APROBADO)), ResultadoPago.PAGADO)
        self.assertEqual(self.orden['estado'], EstadoPedido.PAGADO)
        self.assertEqual(self.inventario.stock[('camisa', 'CAMISA-S')], 0)

    def test_aprobado_dos_veces_no_descuenta_de_nuevo(self):
        self.caso.ejecutar(pago(EstadoPago.APROBADO))
        self.assertEqual(self.caso.ejecutar(pago(EstadoPago.APROBADO)), ResultadoPago.REPETIDO)
        self.assertEqual(self.notificador.enviados, [('1', EventoPedido.PAGO_APROBADO)])

    def test_rechazado_cancela_la_orden(self):
        self.assertEqual(self.caso.ejecutar(pago(EstadoPago.RECHAZADO)), ResultadoPago.RECHAZADO)
        self.assertEqual(self.orden['estado'], EstadoPedido.CANCELADO)
        self.assertEqual(self.orden['motivo_cancelacion'], MOTIVO_PAGO_RECHAZADO)

    def test_anulado_cancela_la_orden_con_su_motivo(self):
        self.assertEqual(self.caso.ejecutar(pago(EstadoPago.ANULADO)), ResultadoPago.CANCELADO)
        self.assertEqual(self.orden['motivo_cancelacion'], MOTIVO_PAGO_ANULADO)
        self.assertEqual(self.notificador.enviados, [('1', EventoPedido.CANCELADO)])

    def test_pendiente_no_cambia_la_orden(self):
        self.assertEqual(self.caso.ejecutar(pago(EstadoPago.PENDIENTE)), ResultadoPago.PENDIENTE)
        self.assertEqual(self.orden['estado'], EstadoPedido.PENDIENTE)
        self.assertEqual(self.notificador.enviados, [])

    def test_reembolso_de_una_orden_pagada_la_deja_en_revision(self):
        self.caso.ejecutar(pago(EstadoPago.APROBADO))
        self.assertEqual(self.caso.ejecutar(pago(EstadoPago.REEMBOLSADO)), ResultadoPago.EN_REVISION)
        self.assertEqual(self.orden['estado'], EstadoPedido.PAGADO)
        self.assertTrue(self.orden['requiere_revision'])
        self.assertIn('801', self.orden['motivo_revision'])
        self.assertEqual(self.notificador.enviados[-1], ('1', EventoPedido.PAGO_EN_REVISION))

    def test_reembolso_de_una_orden_pendiente_la_cancela(self):
        self.assertEqual(self.caso.ejecutar(pago(EstadoPago.REEMBOLSADO)), ResultadoPago.CANCELADO)
        self.assertEqual(self.orden['estado'], EstadoPedido.CANCELADO)
        self.assertEqual(self.orden['motivo_cancelacion'], MOTIVO_PAGO_ANULADO)

    def test_pago_sin_orden_no_toca_nada(self):
        self.assertEqual(self.caso.ejecutar(pago(EstadoPago.APROBADO, orden_id='')), ResultadoPago.NO_ENCONTRADA)
        self.assertEqual(self.orden['estado'], EstadoPedido.PENDIENTE)

    def test_orden_inexistente(self):
        self.assertEqual(self.caso.ejecutar(pago(EstadoPago.APROBADO, orden_id='99')), ResultadoPago.NO_ENCONTRADA)


class ProcesarAvisoPagoTests(SimpleTestCase):
    def setUp(self):
        self.ordenes = RepositorioOrdenesFalso()
        self.orden = self.ordenes.agregar('1', 'PENDIENTE', [('camisa', 'CAMISA-S', 1)])
        confirmar = ConfirmarPago(self.ordenes, InventarioFalso({('camisa', 'CAMISA-S'): 1}))
        self.aplicar = AplicarResultadoPago(confirmar)

    def procesar(self, pasarela, **kwargs):
        return ProcesarAvisoPago(pasarela, self.aplicar).ejecutar(
            firma='ts=1,v1=abc', id_peticion='req-1', referencia='801', **kwargs)

    def test_aviso_valido_consulta_el_pago_a_la_pasarela_y_lo_aplica(self):
        pasarela = PasarelaFalsa(pago(EstadoPago.APROBADO, monto=None))
        self.assertEqual(self.procesar(pasarela), ResultadoPago.PAGADO)
        self.assertEqual(pasarela.consultadas, ['801'])
        self.assertEqual(self.orden['estado'], EstadoPedido.PAGADO)

    def test_firma_invalida_no_consulta_ni_cambia_la_orden(self):
        pasarela = PasarelaFalsa(pago(EstadoPago.APROBADO), firma_valida=False)
        with self.assertRaises(FirmaAvisoInvalida):
            self.procesar(pasarela)
        self.assertEqual(pasarela.consultadas, [])
        self.assertEqual(self.orden['estado'], EstadoPedido.PENDIENTE)

    def test_aviso_que_no_es_de_pago_se_ignora_despues_de_verificar_la_firma(self):
        pasarela = PasarelaFalsa(pago(EstadoPago.APROBADO))
        self.assertEqual(self.procesar(pasarela, es_pago=False), ResultadoPago.IGNORADO)
        self.assertEqual(pasarela.consultadas, [])
        with self.assertRaises(FirmaAvisoInvalida):
            self.procesar(PasarelaFalsa(firma_valida=False), es_pago=False)

    def test_el_resultado_es_comparable_con_el_texto_que_responde_el_webhook(self):
        pasarela = PasarelaFalsa(pago(EstadoPago.RECHAZADO))
        self.assertEqual(str(self.procesar(pasarela)), 'RECHAZADO')

    def test_monto_distinto_deja_la_orden_en_revision(self):
        # La orden falsa tiene total 0
        pasarela = PasarelaFalsa(pago(EstadoPago.APROBADO, monto=Decimal('1')))
        resultado = self.procesar(pasarela)
        self.assertEqual(resultado, ResultadoPago.EN_REVISION)
        self.assertTrue(self.orden['requiere_revision'])
