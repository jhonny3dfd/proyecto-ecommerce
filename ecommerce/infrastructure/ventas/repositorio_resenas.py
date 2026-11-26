"""Adaptadores Django (PostgreSQL) de los puertos de reseñas: el pedido que se reseña y las reseñas."""

from django.db import IntegrityError, transaction

from ecommerce.application.resenas import PedidoParaResenar, PedidosParaResenar, RepositorioResenas, ResenaPublica
from ecommerce.domain.resenas import EstadoResena, ProductoDelPedido

from .models import OrdenCompra, Resena, ResenaProducto

APROBADA = EstadoResena.APROBADA.value


class DjangoPedidosParaResenar(PedidosParaResenar):
    def obtener(self, orden_id):
        try:
            orden = OrdenCompra.objects.select_related('usuario').get(id=orden_id)
        except (OrdenCompra.DoesNotExist, ValueError):
            return None
        productos = {}
        for detalle in orden.detalles.order_by('id'):
            # La línea se llama "<producto> - <SKU>": la reseña es del producto, no de la variante
            nombre = detalle.nombre_producto_snapshot.removesuffix(f' - {detalle.variante_sku}')
            productos.setdefault(detalle.producto_mongo_id, ProductoDelPedido(detalle.producto_mongo_id, nombre))
        usuario = orden.usuario
        return PedidoParaResenar(
            orden_id=orden.id, estado=orden.estado, entregado_en=orden.fecha_entrega,
            # El de la cuenta si compró registrado; el invitado solo dejó el del destinatario
            nombre_comprador=f'{usuario.nombre} {usuario.apellido_paterno}' if usuario else orden.nombre_destinatario,
            productos=list(productos.values()),
            tiene_resena=Resena.objects.filter(orden_id=orden.id).exists(),
        )


def _publica(resena, estrellas, comentario):
    return ResenaPublica(nombre_publico=resena.nombre_publico, estrellas=estrellas, comentario=comentario,
                         fecha=resena.fecha_creacion)


class DjangoRepositorioResenas(RepositorioResenas):
    def guardar(self, orden_id, datos):
        try:
            with transaction.atomic():
                resena = Resena.objects.create(orden_id=orden_id, estrellas=datos.estrellas_tienda,
                                               comentario=datos.comentario_tienda,
                                               nombre_publico=datos.nombre_publico)
                ResenaProducto.objects.bulk_create([
                    ResenaProducto(resena=resena, producto_mongo_id=producto.producto_id,
                                   producto_nombre=producto.producto_nombre, estrellas=producto.estrellas,
                                   comentario=producto.comentario)
                    for producto in datos.productos
                ])
        except IntegrityError:
            # Una reseña por pedido (OneToOne): otro envío del mismo pedido se guardó primero
            if Resena.objects.filter(orden_id=orden_id).exists():
                return None
            raise
        return resena.id

    def estado(self, resena_id):
        estado = Resena.objects.filter(id=resena_id).values_list('estado', flat=True).first()
        return EstadoResena(estado) if estado else None

    def cambiar_estado(self, resena_id, estado):
        Resena.objects.filter(id=resena_id).update(estado=EstadoResena(estado).value)

    def estrellas_tienda(self):
        return list(Resena.objects.filter(estado=APROBADA).values_list('estrellas', flat=True))

    def recientes_tienda(self, cantidad):
        resenas = Resena.objects.filter(estado=APROBADA).exclude(comentario='').order_by('-fecha_creacion', '-id')
        return [_publica(resena, resena.estrellas, resena.comentario) for resena in resenas[:cantidad]]

    def estrellas_producto(self, producto_id):
        return list(ResenaProducto.objects.filter(producto_mongo_id=producto_id, resena__estado=APROBADA)
                    .values_list('estrellas', flat=True))

    def recientes_producto(self, producto_id, cantidad):
        calificaciones = (ResenaProducto.objects.select_related('resena')
                          .filter(producto_mongo_id=producto_id, resena__estado=APROBADA)
                          .exclude(comentario='').order_by('-resena__fecha_creacion', '-id'))
        return [_publica(c.resena, c.estrellas, c.comentario) for c in calificaciones[:cantidad]]
