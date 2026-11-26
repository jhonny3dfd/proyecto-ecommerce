from django.core.management.base import BaseCommand

from ...repositorio_suscripciones import dias_aviso_tienda, hoy_local, suscripciones_activas_en_tienda
from ...servicio_suscripciones import procesar_ciclos


def _ids(lista) -> str:
    return ', '.join(f'#{i}' for i in lista)


class Command(BaseCommand):
    help = ('Suscripciones (si la tienda las activó): cierra los ciclos que no se pagaron a tiempo y crea el pedido '
            'de los que toca cobrar, con el aviso al cliente. Programarlo una vez al '
            'día; se puede correr más veces sin duplicar pedidos ni correos.')

    def handle(self, *args, **options):
        if not suscripciones_activas_en_tienda():
            self.stdout.write('Las suscripciones no están activas en esta tienda: no hay nada que procesar.')
            return
        resumen = procesar_ciclos().ejecutar(hoy_local(), dias_aviso_tienda())
        lineas = [
            ('Avisos de cobro enviados (suscripciones)', resumen.avisados),
            ('Ciclos no pagados a tiempo (suscripciones)', resumen.no_pagados),
            ('Suscripciones que no se activaron (sin primer pago)', resumen.no_activadas),
            ('No se pudo calcular el despacho; se reintenta mañana (suscripciones)', resumen.con_error),
        ]
        escritas = [f'{texto}: {_ids(ids)}.' for texto, ids in lineas if ids]
        for linea in escritas or ['No hay ciclos de suscripción que procesar hoy.']:
            self.stdout.write(linea)
