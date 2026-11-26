"""Folios de los documentos tributarios en PostgreSQL (application/documentos_tributarios.py)."""

from django.db.models import Q

from ecommerce.application.documentos_tributarios import PedidoParaDocumentar, PedidosDocumentos
from ecommerce.domain.documentos_tributarios import ESTADOS_VENDIDOS, PAGOS_CON_VOUCHER, ModeloEmision
from ecommerce.domain.ventas import EstadoPedido

from .models import ConfiguracionGlobal, OrdenCompra


def modelo_emision_tienda() -> ModeloEmision:
    modelo = ConfiguracionGlobal.objects.filter(pk=1).values_list('modelo_emision', flat=True).first()
    return ModeloEmision(modelo or ModeloEmision.VOUCHER)


def es_empresa(orden) -> bool:
    # Una compra que no es como empresa deja datos_empresa vacío (NULL)
    return bool(orden.datos_empresa)


def filtro_documento_pendiente(modelo: ModeloEmision) -> Q:
    """documento_por_emitir (domain/documentos_tributarios.py) como consulta: los pedidos con algo por emitir."""
    if ModeloEmision(modelo) == ModeloEmision.SIEMPRE_BOLETA:
        requiere = Q()
    else:
        # Con el voucher como boleta, la tarjeta solo pide documento si es una compra como empresa (factura)
        requiere = Q(datos_empresa__isnull=False) | ~Q(metodo_pago__in=PAGOS_CON_VOUCHER)
    venta_sin_folio = Q(estado__in=[estado.value for estado in ESTADOS_VENDIDOS], folio_documento='') & requiere
    nota_credito = Q(estado=EstadoPedido.CANCELADO.value, folio_nota_credito='') & ~Q(folio_documento='')
    return venta_sin_folio | nota_credito


class DjangoPedidosDocumentos(PedidosDocumentos):
    def obtener(self, orden_id):
        orden = OrdenCompra.objects.filter(id=orden_id).first()
        if orden is None:
            return None
        return PedidoParaDocumentar(estado=orden.estado, metodo_pago=orden.metodo_pago, es_empresa=es_empresa(orden),
                                    folio_documento=orden.folio_documento,
                                    folio_nota_credito=orden.folio_nota_credito)

    def guardar_folio(self, orden_id, folio):
        OrdenCompra.objects.filter(id=orden_id).update(folio_documento=folio)

    def guardar_folio_nota_credito(self, orden_id, folio):
        OrdenCompra.objects.filter(id=orden_id).update(folio_nota_credito=folio)
