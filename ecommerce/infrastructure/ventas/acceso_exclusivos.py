"""Acceso a exclusivos con la configuración y las suscripciones actuales, sin caché de sesión."""
from bson import ObjectId
from rest_framework.exceptions import ValidationError

from ecommerce.domain.suscripciones import EstadoSuscripcion, permite_producto_exclusivo
from ..catalogo.documents import Producto
from .models import Suscripcion
from .repositorio_suscripciones import suscripciones_activas_en_tienda

AVISO_EXCLUSIVO = 'Este producto es exclusivo para suscriptores con un plan vigente que permita acceder a él.'


def planes_vigentes_de(usuario):
    if not (usuario and usuario.is_authenticated and usuario.is_active):
        return set()
    return set(Suscripcion.objects.filter(usuario=usuario, estado=EstadoSuscripcion.ACTIVA.value)
               .values_list('plan_id', flat=True))


def productos_sin_acceso(productos, usuario, plan_elegido=None, contratando=False, suscripcion=None):
    if not suscripciones_activas_en_tienda():
        return set()
    exclusivos = [p for p in productos if p.solo_suscriptores]
    if not exclusivos:
        return set()
    if suscripcion is not None:
        if suscripcion.estado in ('PAUSADA', 'CANCELADA'):
            return {str(p.id) for p in exclusivos}
        contratando = suscripcion.estado == 'PENDIENTE'
        plan_elegido = suscripcion.plan_id
    # Solo al contratar, el plan elegido habilita su propia entrega pendiente de pago.
    vigentes = {plan_elegido} if contratando and plan_elegido is not None else planes_vigentes_de(usuario)
    return {str(p.id) for p in exclusivos if not permite_producto_exclusivo(
        True, True, p.planes_suscripcion, vigentes, plan_elegido)}


def ids_sin_acceso(items, usuario, plan_elegido=None, contratando=False, suscripcion=None):
    ids = {str(i.get('producto_mongo_id') or i.get('producto_id') or i.get('id') or '') for i in items}
    ids = [ObjectId(i) for i in ids if ObjectId.is_valid(i)]
    if not ids or not suscripciones_activas_en_tienda():
        return set()
    productos = Producto.objects(id__in=ids, solo_suscriptores=True).only('solo_suscriptores', 'planes_suscripcion')
    return productos_sin_acceso(productos, usuario, plan_elegido, contratando, suscripcion)


def exigir_acceso_productos(items, usuario, plan_elegido=None, contratando=False, suscripcion=None):
    if ids_sin_acceso(items, usuario, plan_elegido, contratando, suscripcion):
        raise ValidationError({'items': [AVISO_EXCLUSIVO]})
