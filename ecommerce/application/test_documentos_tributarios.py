from django.test import SimpleTestCase

from ecommerce.application.documentos_tributarios import (
    PedidoNoEncontrado, PedidoParaDocumentar, PedidosDocumentos, RegistrarFolio, SinDocumentoPorRegistrar,
)
from ecommerce.domain.documentos_tributarios import FolioInvalido, ModeloEmision, TipoDocumento

VOUCHER, SIEMPRE = ModeloEmision.VOUCHER, ModeloEmision.SIEMPRE_BOLETA


class PedidosFalsos(PedidosDocumentos):
    def __init__(self, **pedidos):
        self.pedidos = {int(orden_id[1:]): pedido for orden_id, pedido in pedidos.items()}

    def obtener(self, orden_id):
        return self.pedidos.get(orden_id)

    def guardar_folio(self, orden_id, folio):
        self.pedidos[orden_id] = PedidoParaDocumentar(**{**self.pedidos[orden_id].__dict__, 'folio_documento': folio})

    def guardar_folio_nota_credito(self, orden_id, folio):
        self.pedidos[orden_id] = PedidoParaDocumentar(
            **{**self.pedidos[orden_id].__dict__, 'folio_nota_credito': folio})


class RegistrarFolioTests(SimpleTestCase):
    def setUp(self):
        self.pedidos = PedidosFalsos(
            p1=PedidoParaDocumentar('PAGADO', 'TRANSFERENCIA', es_empresa=False),
            p2=PedidoParaDocumentar('ENTREGADO', 'TRANSBANK', es_empresa=True),
            p3=PedidoParaDocumentar('PAGADO', 'TRANSBANK', es_empresa=False),
            p4=PedidoParaDocumentar('CANCELADO', 'TRANSFERENCIA', es_empresa=False, folio_documento='120'),
            p5=PedidoParaDocumentar('CANCELADO', 'TRANSFERENCIA', es_empresa=False),
            p6=PedidoParaDocumentar('PENDIENTE', 'TRANSFERENCIA', es_empresa=False),
        )
        self.caso = RegistrarFolio(self.pedidos)

    def test_anota_el_folio_de_la_boleta_de_una_transferencia(self):
        self.assertEqual(self.caso.ejecutar(1, ' 123 ', VOUCHER), TipoDocumento.BOLETA)
        self.assertEqual(self.pedidos.pedidos[1].folio_documento, '123')

    def test_anota_el_folio_de_la_factura_de_una_empresa(self):
        self.assertEqual(self.caso.ejecutar(2, '45', VOUCHER), TipoDocumento.FACTURA)
        self.assertEqual(self.pedidos.pedidos[2].folio_documento, '45')

    def test_un_folio_ya_anotado_se_puede_corregir(self):
        self.caso.ejecutar(1, '123', VOUCHER)
        self.caso.ejecutar(1, '132', VOUCHER)
        self.assertEqual(self.pedidos.pedidos[1].folio_documento, '132')

    def test_con_tarjeta_y_voucher_no_hay_documento_que_anotar_salvo_con_siempre_boleta(self):
        with self.assertRaises(SinDocumentoPorRegistrar):
            self.caso.ejecutar(3, '123', VOUCHER)
        self.assertEqual(self.pedidos.pedidos[3].folio_documento, '')
        self.assertEqual(self.caso.ejecutar(3, '123', SIEMPRE), TipoDocumento.BOLETA)

    def test_en_un_cancelado_con_documento_el_folio_es_el_de_la_nota_de_credito(self):
        self.assertEqual(self.caso.ejecutar(4, '7', VOUCHER), TipoDocumento.NOTA_CREDITO)
        self.assertEqual((self.pedidos.pedidos[4].folio_documento, self.pedidos.pedidos[4].folio_nota_credito),
                         ('120', '7'))

    def test_un_cancelado_sin_documento_o_un_pedido_sin_pagar_no_tienen_documento(self):
        for orden_id in (5, 6):
            with self.subTest(orden_id=orden_id), self.assertRaises(SinDocumentoPorRegistrar):
                self.caso.ejecutar(orden_id, '123', VOUCHER)

    def test_un_folio_invalido_no_guarda_nada(self):
        with self.assertRaises(FolioInvalido):
            self.caso.ejecutar(1, 'B-123', VOUCHER)
        self.assertEqual(self.pedidos.pedidos[1].folio_documento, '')

    def test_un_pedido_que_no_existe(self):
        with self.assertRaises(PedidoNoEncontrado):
            self.caso.ejecutar(99, '123', VOUCHER)
