"""Adaptador Django (PostgreSQL) del puerto RepositorioCotizaciones."""

import uuid

from django.core.files.base import ContentFile
from django.db import transaction

from ecommerce.application.cotizaciones import RepositorioCotizaciones

from .almacen_privado import almacen_privado
from .models import Cotizacion, FotoCotizacion


class DjangoRepositorioCotizaciones(RepositorioCotizaciones):
    def guardar(self, solicitud):
        almacen = almacen_privado()
        guardadas = []
        try:
            with transaction.atomic():
                cotizacion = Cotizacion.objects.create(
                    nombre=solicitud.nombre, correo=solicitud.correo, telefono=solicitud.telefono,
                    producto_id=solicitud.producto_id, producto_nombre=solicitud.producto_nombre,
                    descripcion=solicitud.descripcion, cantidad=solicitud.cantidad,
                    personalizacion=solicitud.personalizacion, fecha_requerida=solicitud.fecha_requerida,
                    datos_empresa=solicitud.empresa.como_dict() if solicitud.empresa else None,
                )
                for foto in solicitud.fotos:
                    # Nombre al azar: no deja adivinar las demás ni repite el que puso el cliente
                    ruta = almacen.save(f'cotizaciones/{cotizacion.id}/{uuid.uuid4().hex}.{foto.extension}',
                                        ContentFile(foto.contenido))
                    guardadas.append(ruta)
                    FotoCotizacion.objects.create(cotizacion=cotizacion, ruta=ruta)
        except Exception:
            # Sin la cotización, sus fotos sobran: no quedan archivos huérfanos
            for ruta in guardadas:
                almacen.delete(ruta)
            raise
        return cotizacion.id

    def cambiar_estado(self, cotizacion_id, estado):
        return Cotizacion.objects.filter(id=cotizacion_id).update(estado=estado.value) == 1
