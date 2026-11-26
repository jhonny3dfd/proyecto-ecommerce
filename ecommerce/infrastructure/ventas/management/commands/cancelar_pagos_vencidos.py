from django.core.management.base import BaseCommand
from django.utils import timezone

from ecommerce.application.ventas import CancelarPagosVencidos, RecordarPagosPorVencer

from ...repositorio_ordenes import DjangoRepositorioOrdenes
from ...views import notificador_pedidos


class Command(BaseCommand):
    help = ('Cancela las órdenes por transferencia que no se pagaron dentro del plazo de la tienda y avisa al '
            'comprador; a la mitad del plazo sin pagar les envía un recordatorio. '
            'Programarlo para que corra periódicamente, por ejemplo cada hora.')

    def handle(self, *args, **options):
        ahora = timezone.now()
        ordenes, notificador = DjangoRepositorioOrdenes(), notificador_pedidos()
        # Primero se cancela: así no se le recuerda el pago a una orden que ya venció
        canceladas = CancelarPagosVencidos(ordenes, notificador).ejecutar(ahora)
        recordadas = RecordarPagosPorVencer(ordenes, notificador).ejecutar(ahora)
        if canceladas:
            self.stdout.write(f"Órdenes canceladas por pago vencido: {', '.join(f'#{i}' for i in canceladas)}.")
        else:
            self.stdout.write('No hay órdenes con el pago vencido.')
        if recordadas:
            self.stdout.write(f"Recordatorios de pago enviados: {', '.join(f'#{i}' for i in recordadas)}.")
