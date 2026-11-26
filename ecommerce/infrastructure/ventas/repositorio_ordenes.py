"""Adaptador Django (PostgreSQL) del puerto RepositorioOrdenes."""

from decimal import Decimal

from django.db.models import Value
from django.db.models.functions import Coalesce, Concat
from django.utils import timezone

from ecommerce.application.ventas import RepositorioOrdenes
from ecommerce.domain.logistica import EnvioSolicitado, Paquete
from ecommerce.domain.ventas import EstadoPedido, ItemSolicitado, OrdenRegistrada

from .models import OrdenCompra

CAMPOS_PAQUETE = ('peso_kg', 'alto_cm', 'ancho_cm', 'largo_cm')


class DjangoRepositorioOrdenes(RepositorioOrdenes):
    def obtener(self, orden_id):
        try:
            orden = OrdenCompra.objects.get(id=orden_id)
        except (OrdenCompra.DoesNotExist, ValueError):
            return None
        items = tuple(
            ItemSolicitado(detalle.producto_mongo_id, detalle.variante_sku, detalle.cantidad)
            for detalle in orden.detalles.order_by('id')
        )
        return OrdenRegistrada(orden.id, EstadoPedido(orden.estado), items, orden.stock_descontado,
                               orden.requiere_revision, Decimal(str(round(orden.total_final))),
                               motivo_cancelacion=orden.motivo_cancelacion,
                               )

    def cambiar_estado(self, orden_id, desde, hacia, motivo_cancelacion='', motivo_revision=''):
        # Un UPDATE condicional es atómico: de dos cambios simultáneos solo uno se aplica
        cambios = {'estado': EstadoPedido(hacia).value}
        if motivo_cancelacion:
            cambios['motivo_cancelacion'] = motivo_cancelacion
        if motivo_revision:
            cambios.update(requiere_revision=True, motivo_revision=motivo_revision)
        if hacia == EstadoPedido.PAGADO:
            # El dashboard cuenta la venta el día del pago, no el de la orden (una transferencia se valida después)
            cambios['fecha_pago'] = timezone.now()
        if hacia == EstadoPedido.ENTREGADO:
            # Desde aquí corre el plazo para dejar la reseña (domain/resenas.py)
            cambios['fecha_entrega'] = timezone.now()
        return OrdenCompra.objects.filter(
            id=orden_id, estado=EstadoPedido(desde).value).update(**cambios) == 1

    def registrar_stock_descontado(self, orden_id, descontado=True):
        OrdenCompra.objects.filter(id=orden_id).update(stock_descontado=descontado)

    def completar_pago(self, orden_id):
        OrdenCompra.objects.filter(id=orden_id).update(
            stock_descontado=True, requiere_revision=False, motivo_revision='')

    def marcar_revision(self, orden_id, motivo):
        OrdenCompra.objects.filter(id=orden_id).update(requiere_revision=True, motivo_revision=motivo)

    def resolver_revision(self, orden_id):
        return OrdenCompra.objects.filter(id=orden_id, requiere_revision=True).update(
            requiere_revision=False) == 1

    def obtener_envio(self, orden_id):
        try:
            orden = OrdenCompra.objects.select_related('usuario').get(id=orden_id)
        except (OrdenCompra.DoesNotExist, ValueError):
            return None
        direccion = orden.direccion_envio_snapshot or {}
        paquete = orden.paquete
        usuario = orden.usuario
        # Usuario hereda de AbstractBaseUser: no tiene get_full_name
        nombre_cuenta = ' '.join(filter(None, [usuario.nombre, usuario.apellido_paterno])) if usuario else ''
        return EnvioSolicitado(
            orden_id=orden.id,
            proveedor=orden.proveedor_logistico or '',
            comuna=direccion.get('comuna', ''),
            calle=direccion.get('calle', ''),
            numero=str(direccion.get('numero', '')),
            complemento=direccion.get('dpto_casa', ''),
            # Órdenes anteriores a pedir el destinatario en el checkout: el nombre de la cuenta
            destinatario=orden.nombre_destinatario or nombre_cuenta or 'Cliente',
            email=orden.email_invitado or (orden.usuario.email if orden.usuario else ''),
            # Se declara el valor de los productos, no el del envío
            valor_declarado=int(orden.subtotal),
            telefono=orden.telefono_destinatario,
            paquete=Paquete(**{campo: Decimal(str(paquete[campo])) for campo in CAMPOS_PAQUETE})
            if paquete else None,
            codigo_sucursal=str(direccion.get('codigo_sucursal', '')),
            numero_ot=orden.numero_seguimiento_tracking or '',
        )

    @staticmethod
    def _pendientes(metodo_pago, **filtros):
        ordenes = OrdenCompra.objects.filter(estado=EstadoPedido.PENDIENTE.value, metodo_pago=metodo_pago, **filtros)
        return list(ordenes.order_by('id').values_list('id', flat=True))

    def pagos_vencidos(self, metodo_pago, ahora):
        return self._pendientes(metodo_pago, fecha_limite_pago__lt=ahora)

    def pagos_por_recordar(self, metodo_pago, ahora):
        return self._pendientes(metodo_pago, fecha_recordatorio_pago__lt=ahora, recordatorio_pago_enviado=False)

    def marcar_recordatorio_pago(self, orden_id):
        return OrdenCompra.objects.filter(
            id=orden_id, estado=EstadoPedido.PENDIENTE.value, recordatorio_pago_enviado=False,
        ).update(recordatorio_pago_enviado=True) == 1

    def registrar_orden_transporte(self, orden_id, numero_ot='', error=''):
        if not numero_ot:
            OrdenCompra.objects.filter(id=orden_id).update(error_orden_transporte=error[:255])
            return
        # La descarga de etiquetas y el historial del comprador leen la OT desde este campo
        OrdenCompra.objects.filter(id=orden_id).update(
            numero_seguimiento_tracking=numero_ot,
            error_orden_transporte='',
            id_transaccion_pasarela=Concat(
                Coalesce('id_transaccion_pasarela', Value('')), Value(f' | OT: {numero_ot}')),
        )
