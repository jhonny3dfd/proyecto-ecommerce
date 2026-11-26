"""Caso de uso de los documentos tributarios: la tienda anota el folio de la boleta, factura o nota de crédito que
emitió por su cuenta. Las reglas viven en domain/documentos_tributarios.py."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ecommerce.domain.documentos_tributarios import (
    ESTADOS_VENDIDOS, ModeloEmision, TipoDocumento, documento_requerido, validar_folio,
)
from ecommerce.domain.ventas import EstadoPedido


@dataclass(frozen=True)
class PedidoParaDocumentar:
    estado: str
    metodo_pago: str
    es_empresa: bool
    folio_documento: str = ''
    folio_nota_credito: str = ''


class PedidosDocumentos(ABC):
    """Puerto de salida: los datos del pedido que usa la regla y dónde se guardan los folios."""

    @abstractmethod
    def obtener(self, orden_id: int) -> PedidoParaDocumentar | None:
        raise NotImplementedError

    @abstractmethod
    def guardar_folio(self, orden_id: int, folio: str) -> None:
        """El de la boleta o factura."""
        raise NotImplementedError

    @abstractmethod
    def guardar_folio_nota_credito(self, orden_id: int, folio: str) -> None:
        raise NotImplementedError


class PedidoNoEncontrado(Exception):
    def __init__(self):
        super().__init__('Pedido no encontrado.')


class SinDocumentoPorRegistrar(Exception):
    def __init__(self):
        super().__init__('Este pedido no necesita boleta, factura ni nota de crédito.')


class RegistrarFolio:
    """Anota (o corrige) el folio del documento que le corresponde al pedido.

    En un pedido cancelado que ya tenía boleta o factura, el folio es el de su nota de crédito. Un pedido sin pagar,
    o pagado con tarjeta cuando el voucher vale como boleta, no tiene documento que anotar.
    """

    def __init__(self, pedidos: PedidosDocumentos):
        self.pedidos = pedidos

    def ejecutar(self, orden_id: int, folio, modelo: ModeloEmision | str) -> TipoDocumento:
        pedido = self.pedidos.obtener(orden_id)
        if pedido is None:
            raise PedidoNoEncontrado()
        folio = validar_folio(folio)
        estado = EstadoPedido(pedido.estado)

        if estado == EstadoPedido.CANCELADO:
            if not pedido.folio_documento:
                raise SinDocumentoPorRegistrar()
            self.pedidos.guardar_folio_nota_credito(orden_id, folio)
            return TipoDocumento.NOTA_CREDITO

        tipo = documento_requerido(pedido.metodo_pago, pedido.es_empresa, modelo)
        if estado not in ESTADOS_VENDIDOS or tipo is None:
            raise SinDocumentoPorRegistrar()
        self.pedidos.guardar_folio(orden_id, folio)
        return tipo
