"""Django storage and atomic MongoEngine adapters for galleries."""

from datetime import datetime, timezone
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from mongoengine import Q

from ecommerce.application.imagenes import ServicioGaleria
from ecommerce.domain.imagenes import (
    AlmacenamientoImagenNoDisponible,
    GaleriaEnConflicto,
)
from .documents import ImagenPendienteBorrado, Producto, Variante
from .images import es_imagen_gestionada


def consulta_galeria(producto_id, anteriores):
    condicion = Q(imagenes=anteriores)
    if not anteriores:
        condicion |= Q(imagenes__exists=False)
    return Producto.objects(Q(id=producto_id) & condicion)


def modificar_con_referencias(consulta, actualizacion, desasociadas):
    if not desasociadas:
        return consulta.modify(new=True, __raw__=actualizacion)
    con_variantes = {
        **actualizacion,
        '$set': {**actualizacion.get('$set', {}), 'variantes.$[imagen].imagen_especifica': None},
    }
    actualizado = consulta.filter(__raw__={'variantes': {'$type': 'array'}}).modify(
        new=True, __raw__=con_variantes,
        array_filters=[{'imagen.imagen_especifica': {'$in': desasociadas}}],
    )
    if actualizado is not None:
        return actualizado
    # Older documents can lack the optional variants array. Each alternative
    # retains the same gallery precondition and commits in a single operation.
    return consulta.filter(__raw__={'variantes': {'$not': {'$type': 'array'}}}).modify(
        new=True, __raw__=actualizacion,
    )


class AlmacenImagenesDjango:
    def guardar(self, producto_id, imagen):
        nombre = f'catalogo/productos/{producto_id}/{uuid4().hex}.{imagen.extension}'
        try:
            clave = default_storage.save(nombre, ContentFile(imagen.contenido))
            if not es_imagen_gestionada(clave, producto_id):
                default_storage.delete(clave)
                raise AlmacenamientoImagenNoDisponible
            return clave
        except Exception as exc:
            # A write may leave a partial file before raising. Expose only the
            # generated key to the use case so compensation covers that file.
            raise AlmacenamientoImagenNoDisponible(clave=nombre) from exc

    def borrar(self, clave):
        if not es_imagen_gestionada(clave):
            raise ValueError('Solo se pueden borrar archivos gestionados por el catálogo.')
        default_storage.delete(clave)


class RepositorioGaleriaMongo:
    def asociar(self, producto_id, anteriores, nuevas):
        producto = consulta_galeria(producto_id, anteriores).modify(new=True, push_all__imagenes=nuevas)
        if producto is None:
            raise GaleriaEnConflicto
        return list(producto.imagenes)

    def desasociar(self, producto_id, anteriores, clave):
        producto = modificar_con_referencias(
            consulta_galeria(producto_id, anteriores),
            {'$pull': {'imagenes': clave}}, [clave],
        )
        if producto is None:
            raise GaleriaEnConflicto
        return list(producto.imagenes)

    def programar_borrado(self, claves):
        for clave in claves:
            if not es_imagen_gestionada(clave):
                raise ValueError('Clave de imagen inválida para limpieza.')
            ImagenPendienteBorrado.objects(clave=clave).update_one(
                upsert=True, set_on_insert__fecha_creacion=datetime.now(timezone.utc),
            )

    def esta_asociada(self, clave):
        return Producto.objects(Q(imagenes=clave) | Q(variantes__imagen_especifica=clave)).first() is not None

    def completar_borrado(self, clave):
        ImagenPendienteBorrado.objects(clave=clave).delete()


def servicio_galeria():
    return ServicioGaleria(RepositorioGaleriaMongo(), AlmacenImagenesDjango())


def actualizar_producto(producto, cambios):
    """Update only requested fields, with a gallery precondition for image edits."""
    if not cambios:
        return producto
    anteriores = list(producto.imagenes)
    nuevas = cambios.get('imagenes', anteriores)
    eliminadas = [clave for clave in anteriores if es_imagen_gestionada(clave) and clave not in nuevas]
    for attr, valor in cambios.items():
        if attr == 'variantes':
            valor = [Variante(**datos) for datos in valor]
        setattr(producto, attr, valor)

    # Mantener sincronizado precio_minimo_vigente al editar precios, ofertas o variantes (SCRUM-179 / E01)
    if 'variantes' in cambios or producto.precio_minimo_vigente is None:
        producto.actualizar_precio_minimo_vigente()

    producto.validate()
    mongo_data = producto.to_mongo()

    campos_set = {campo: mongo_data[campo] for campo in cambios}
    if 'variantes' in cambios or 'precio_minimo_vigente' in mongo_data:
        campos_set['precio_minimo_vigente'] = mongo_data.get('precio_minimo_vigente')

    actualizacion = {'$set': campos_set}
    repo = RepositorioGaleriaMongo()
    repo.programar_borrado(eliminadas)
    consulta = consulta_galeria(producto.id, anteriores) if (
        'imagenes' in cambios or 'variantes' in cambios
    ) else Producto.objects(id=producto.id)
    actualizado = modificar_con_referencias(
        consulta, actualizacion, eliminadas if 'variantes' not in cambios else [],
    )
    if actualizado is None:
        raise GaleriaEnConflicto
    servicio = servicio_galeria()
    for clave in eliminadas:
        servicio.limpiar_pendiente(clave)
    return actualizado


def eliminar_producto(producto):
    claves = [clave for clave in producto.imagenes if es_imagen_gestionada(clave)]
    repo = RepositorioGaleriaMongo()
    repo.programar_borrado(claves)
    eliminado = consulta_galeria(producto.id, list(producto.imagenes)).modify(remove=True)
    if eliminado is None:
        raise GaleriaEnConflicto
    servicio = servicio_galeria()
    for clave in claves:
        servicio.limpiar_pendiente(clave)
