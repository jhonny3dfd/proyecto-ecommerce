"""Archivos que solo ve el admin (las fotos de las cotizaciones): en ARCHIVOS_PRIVADOS_ROOT, fuera de MEDIA_ROOT.

MEDIA_ROOT se publica tal cual en /media/ (Caddy o el servidor de archivos de la tienda). Esta carpeta no tiene URL:
sus archivos los entrega la API al admin, con su sesión (AdminFotoCotizacionView).
"""

from django.conf import settings
from django.core.files.storage import FileSystemStorage


def almacen_privado():
    # Se arma en cada uso: así las pruebas pueden cambiar la carpeta con override_settings
    return FileSystemStorage(location=settings.ARCHIVOS_PRIVADOS_ROOT)
