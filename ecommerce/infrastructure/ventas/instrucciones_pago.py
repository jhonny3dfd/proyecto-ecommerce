"""Instrucciones para pagar una orden por transferencia: van en la respuesta del checkout y en el correo."""

from datetime import datetime, time

from django.utils import timezone

from ecommerce.domain.medios_pago import CodigoMedioPago, PLAZO_PAGO_TRANSFERENCIA_POR_DEFECTO

from .repositorio_medios_pago import DjangoRepositorioMediosPago


def instrucciones_transferencia(orden) -> dict | None:
    """Datos bancarios de la tienda, monto y referencia; None si la orden no se paga por transferencia.

    No se publican en la configuración pública: solo los recibe quien hizo un pedido.
    """
    if orden.metodo_pago != CodigoMedioPago.TRANSFERENCIA.value:
        return None
    medio = DjangoRepositorioMediosPago().obtener(CodigoMedioPago.TRANSFERENCIA)
    datos = medio.datos_para_comprador()
    if not datos:
        return None
    return {
        'datos': [{'etiqueta': campo.etiqueta, 'valor': datos[campo.nombre]}
                  for campo in medio.definicion.campos if campo.nombre in datos],
        'monto': int(round(orden.total_final)),
        # El comprador la indica al transferir para que la tienda identifique el pago
        'referencia': f'Pedido #{orden.id}',
        # Plazo de pago que tenía la tienda al crear la orden: después, se cancela (manage.py cancelar_pagos_vencidos)
        'vence': fecha_limite_pago(orden),
    }


def fecha_limite_pago(orden):
    """La guardada al crear la orden; las anteriores a guardarla tenían el plazo fijo de 48 horas.

    El pedido de un ciclo de una suscripción se puede pagar hasta el final del día de su entrega (lo cierra
    manage.py procesar_suscripciones, no el plazo de las transferencias).
    """
    if getattr(orden, 'ciclo_fecha', None):
        return timezone.make_aware(datetime.combine(orden.ciclo_fecha, time(23, 59)))
    return orden.fecha_limite_pago or orden.fecha_creacion + PLAZO_PAGO_TRANSFERENCIA_POR_DEFECTO
