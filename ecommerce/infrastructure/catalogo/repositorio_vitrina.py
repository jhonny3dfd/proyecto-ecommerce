"""Adaptador MongoDB del puerto CatalogoVitrina (landing, RF-01.1)."""

from bson import ObjectId
from bson.errors import InvalidId

from ecommerce.application.vitrina import CatalogoVitrina

from .documents import Producto


def _object_ids(ids):
    validos = []
    for id_producto in ids:
        try:
            validos.append(ObjectId(id_producto))
        except (InvalidId, TypeError):
            continue
    return validos


class MongoCatalogoVitrina(CatalogoVitrina):
    def visibles(self, ids):
        encontrados = {str(p.id) for p in Producto.objects(
            id__in=_object_ids(ids), activo=True, publicado=True).only('id')}
        return [id_producto for id_producto in ids if id_producto in encontrados]

    def recientes(self, limite, excluir=()):
        if limite <= 0:
            return []
        productos = Producto.objects(activo=True, publicado=True, id__nin=_object_ids(excluir))
        return [str(p.id) for p in productos.order_by('-fecha_creacion', '-id').only('id').limit(limite)]

    def existentes(self, ids):
        # Publicados o no: un borrador también se puede elegir como destacado (application/vitrina.py)
        encontrados = {str(p.id) for p in Producto.objects(id__in=_object_ids(ids), activo=True).only('id')}
        return [id_producto for id_producto in ids if id_producto in encontrados]
