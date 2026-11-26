import os
import sys

import django

# Configurar entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_project.settings')
django.setup()

from ecommerce.application.couriers import TransportistaSegunProveedor
from ecommerce.application.ventas import GenerarOrdenTransporte
from ecommerce.infrastructure.ventas.couriers import DjangoCouriers
from ecommerce.infrastructure.ventas.models import OrdenCompra
from ecommerce.infrastructure.ventas.repositorio_ordenes import DjangoRepositorioOrdenes


def simular_pago_y_ot(orden_id):
    """Marca la orden como pagada y genera su OT con el courier que eligió el comprador (sandbox)."""
    orden = OrdenCompra.objects.get(id=orden_id)
    orden.estado = 'PAGADO'
    orden.save()
    print(f"Orden {orden.id} marcada como PAGADO.")

    numero_ot = GenerarOrdenTransporte(DjangoRepositorioOrdenes(),
                                       TransportistaSegunProveedor(DjangoCouriers())).ejecutar(orden.id)
    if numero_ot:
        print(f"¡ÉXITO! Orden de Transporte generada: #{numero_ot}")
    else:
        orden.refresh_from_db()
        print(f"No se generó la OT: {orden.error_orden_transporte or 'la orden no se despacha con un courier'}")


if __name__ == '__main__':
    simular_pago_y_ot(int(sys.argv[1]) if len(sys.argv) > 1 else 19)
