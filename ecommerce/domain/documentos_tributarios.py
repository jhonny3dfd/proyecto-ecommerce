"""Qué documento tributario (boleta, factura o nota de crédito) le toca emitir a la tienda por un pedido.

La tienda los emite por su cuenta, en el sistema gratuito del SII o en el que use: la integración con el SII queda
fuera de alcance. Esta regla solo le indica al emprendedor qué pedidos necesitan documento y cuáles ya lo tienen.

- Un pago con tarjeta deja un comprobante (voucher) que el SII acepta como boleta, salvo que la tienda haya declarado
  el modelo de emisión "siempre emito boleta".
- Por una transferencia siempre se emite boleta: su comprobante no es un documento tributario.
- Una compra como empresa siempre lleva factura: el voucher no la reemplaza.
- Un pedido cancelado que ya tenía documento necesita una nota de crédito.
"""

import re
from enum import StrEnum

from ecommerce.domain.ventas import EstadoPedido


class TipoDocumento(StrEnum):
    BOLETA = 'BOLETA'
    FACTURA = 'FACTURA'
    NOTA_CREDITO = 'NOTA_CREDITO'


class ModeloEmision(StrEnum):
    """El que la tienda declaró en sii.cl. Sin declarar, el SII asume VOUCHER."""
    VOUCHER = 'VOUCHER'
    SIEMPRE_BOLETA = 'SIEMPRE_BOLETA'


# Medios cuyo comprobante de pago electrónico vale como boleta: tarjetas por operadores autorizados en Chile.
# Transferencia y Linkify no; PayPal tampoco (no informa al SII), así que pide boleta.
PAGOS_CON_VOUCHER = frozenset({'TRANSBANK', 'MERCADO_PAGO'})

# Pedidos ya pagados: la venta ocurrió y se documenta
ESTADOS_VENDIDOS = frozenset({EstadoPedido.PAGADO, EstadoPedido.EN_PREPARACION, EstadoPedido.ENVIADO,
                              EstadoPedido.ENTREGADO})

_FOLIO = re.compile(r'^\d{1,10}$')


class FolioInvalido(ValueError):
    def __init__(self):
        super().__init__('El folio son solo números, de 1 a 10 dígitos.')


def documento_requerido(metodo_pago: str, es_empresa: bool, modelo: ModeloEmision | str) -> TipoDocumento | None:
    """El documento que corresponde a la venta, o None si basta el voucher del pago con tarjeta."""
    if es_empresa:
        return TipoDocumento.FACTURA
    if metodo_pago in PAGOS_CON_VOUCHER and ModeloEmision(modelo) == ModeloEmision.VOUCHER:
        return None
    return TipoDocumento.BOLETA


def documento_por_emitir(estado: EstadoPedido | str, metodo_pago: str, es_empresa: bool, modelo: ModeloEmision | str,
                         folio_documento: str = '', folio_nota_credito: str = '') -> TipoDocumento | None:
    """Lo que falta emitir: la boleta o factura de una venta sin folio, o la nota de crédito de una cancelada."""
    estado = EstadoPedido(estado)
    if estado == EstadoPedido.CANCELADO:
        return TipoDocumento.NOTA_CREDITO if folio_documento and not folio_nota_credito else None
    if estado not in ESTADOS_VENDIDOS or folio_documento:
        return None
    return documento_requerido(metodo_pago, es_empresa, modelo)


def validar_folio(texto) -> str:
    folio = str(texto or '').strip()
    if not _FOLIO.match(folio):
        raise FolioInvalido()
    return folio
