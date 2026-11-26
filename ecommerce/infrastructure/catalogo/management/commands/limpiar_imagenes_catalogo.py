from django.core.management.base import BaseCommand

from ecommerce.infrastructure.catalogo.documents import ImagenPendienteBorrado
from ecommerce.infrastructure.catalogo.image_adapters import servicio_galeria


class Command(BaseCommand):
    help = 'Reintenta el borrado de imágenes desasociadas, sin eliminar archivos todavía referenciados.'

    def add_arguments(self, parser):
        parser.add_argument('--limite', type=int, default=100)

    def handle(self, *args, **options):
        if options['limite'] <= 0:
            self.stderr.write('El límite debe ser positivo.')
            return
        servicio = servicio_galeria()
        claves = list(ImagenPendienteBorrado.objects.order_by('fecha_creacion').limit(options['limite']).scalar('clave'))
        borradas = sum(servicio.limpiar_pendiente(clave) for clave in claves)
        self.stdout.write(f'Imágenes borradas: {borradas}; pendientes o todavía asociadas: {len(claves) - borradas}.')
