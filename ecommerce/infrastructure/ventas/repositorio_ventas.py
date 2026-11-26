"""Adaptador PostgreSQL del puerto VentasPorProducto (landing, RF-01.1)."""

from django.db.models import Sum

from ecommerce.application.vitrina import VentasPorProducto
from ecommerce.domain.ventas import ESTADOS_PAGADOS

from .models import DetalleOrden


class DjangoVentasPorProducto(VentasPorProducto):
    def mas_vendidos(self, limite):
        # Solo cuentan los pedidos pagados (no los pendientes ni los cancelados)
        ranking = (DetalleOrden.objects
                   .filter(orden__estado__in=[estado.value for estado in ESTADOS_PAGADOS])
                   .values('producto_mongo_id')
                   .annotate(unidades=Sum('cantidad'))
                   .order_by('-unidades', 'producto_mongo_id')[:limite])
        return [fila['producto_mongo_id'] for fila in ranking]
