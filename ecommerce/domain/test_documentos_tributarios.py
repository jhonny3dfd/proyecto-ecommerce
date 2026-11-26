from django.test import SimpleTestCase

from ecommerce.domain.documentos_tributarios import (
    FolioInvalido, ModeloEmision, TipoDocumento, documento_por_emitir, documento_requerido, validar_folio,
)
from ecommerce.domain.ventas import EstadoPedido

VOUCHER, SIEMPRE = ModeloEmision.VOUCHER, ModeloEmision.SIEMPRE_BOLETA


class DocumentoRequeridoTests(SimpleTestCase):
    def test_con_tarjeta_y_el_modelo_voucher_basta_el_comprobante_de_pago(self):
        for medio in ('TRANSBANK', 'MERCADO_PAGO'):
            with self.subTest(medio=medio):
                self.assertIsNone(documento_requerido(medio, es_empresa=False, modelo=VOUCHER))

    def test_con_siempre_boleta_tambien_la_pide_con_tarjeta(self):
        self.assertEqual(documento_requerido('TRANSBANK', False, SIEMPRE), TipoDocumento.BOLETA)

    def test_una_transferencia_o_paypal_siempre_llevan_boleta(self):
        for medio in ('TRANSFERENCIA', 'LINKIFY', 'PAYPAL'):
            for modelo in (VOUCHER, SIEMPRE):
                with self.subTest(medio=medio, modelo=modelo):
                    self.assertEqual(documento_requerido(medio, False, modelo), TipoDocumento.BOLETA)

    def test_una_compra_como_empresa_siempre_lleva_factura(self):
        for medio in ('TRANSBANK', 'TRANSFERENCIA'):
            with self.subTest(medio=medio):
                self.assertEqual(documento_requerido(medio, True, VOUCHER), TipoDocumento.FACTURA)

    def test_acepta_el_modelo_como_texto_y_rechaza_uno_desconocido(self):
        self.assertIsNone(documento_requerido('TRANSBANK', False, 'VOUCHER'))
        with self.assertRaises(ValueError):
            documento_requerido('TRANSBANK', False, 'OTRO')


class DocumentoPorEmitirTests(SimpleTestCase):
    def test_solo_un_pedido_ya_pagado_pide_su_documento(self):
        for estado in (EstadoPedido.PAGADO, EstadoPedido.EN_PREPARACION, EstadoPedido.ENVIADO, EstadoPedido.ENTREGADO):
            with self.subTest(estado=estado):
                self.assertEqual(documento_por_emitir(estado, 'TRANSFERENCIA', False, VOUCHER), TipoDocumento.BOLETA)
        self.assertIsNone(documento_por_emitir(EstadoPedido.PENDIENTE, 'TRANSFERENCIA', False, VOUCHER))

    def test_con_folio_ya_no_falta_nada(self):
        self.assertIsNone(documento_por_emitir('PAGADO', 'TRANSFERENCIA', False, VOUCHER, folio_documento='123'))
        self.assertIsNone(documento_por_emitir('ENTREGADO', 'TRANSBANK', True, VOUCHER, folio_documento='45'))

    def test_un_pago_con_voucher_no_pide_nada(self):
        self.assertIsNone(documento_por_emitir('PAGADO', 'MERCADO_PAGO', False, VOUCHER))

    def test_un_cancelado_con_documento_pide_nota_de_credito_hasta_que_se_anota(self):
        self.assertEqual(documento_por_emitir('CANCELADO', 'TRANSFERENCIA', False, VOUCHER, folio_documento='123'),
                         TipoDocumento.NOTA_CREDITO)
        self.assertIsNone(documento_por_emitir('CANCELADO', 'TRANSFERENCIA', False, VOUCHER,
                                               folio_documento='123', folio_nota_credito='7'))

    def test_un_cancelado_sin_documento_no_pide_nada(self):
        # Nunca se documentó (ej. una transferencia que no se pagó): no hay venta que anular
        self.assertIsNone(documento_por_emitir('CANCELADO', 'TRANSFERENCIA', False, VOUCHER))


class FolioTests(SimpleTestCase):
    def test_un_folio_son_de_1_a_10_digitos(self):
        self.assertEqual(validar_folio(' 000123 '), '000123')
        self.assertEqual(validar_folio(9876543210), '9876543210')

    def test_rechaza_vacio_letras_signos_o_demasiado_largo(self):
        for texto in ('', None, 'B-123', '12.345', '-5', '12345678901'):
            with self.subTest(texto=texto), self.assertRaises(FolioInvalido):
                validar_folio(texto)
