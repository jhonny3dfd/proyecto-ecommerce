"""Copia una sola vez las llaves de Chilexpress del .env (CHILEXPRESS_API_KEY_*) a ProveedorEnvio, cifradas.

Después de migrar, las llaves se administran desde el panel y esas variables se pueden borrar del .env.
"""

import os

from django.db import migrations


def copiar_credenciales_chilexpress(apps, schema_editor):
    # El cifrado usa CLAVE_CIFRADO_CREDENCIALES, igual que el repositorio
    from ecommerce.infrastructure.ventas.cifrado import cifrar_json

    ProveedorEnvio = apps.get_model('ventas', 'ProveedorEnvio')
    if ProveedorEnvio.objects.filter(codigo='CHILEXPRESS').exists():
        return

    def leer(nombre):
        return os.environ.get(nombre, '').strip()

    llaves = {
        'cotizador': leer('CHILEXPRESS_API_KEY_COTIZADOR'),
        # Las sucursales usaban CHILEXPRESS_API_KEY_GEO: es la misma API de coberturas (Georeference)
        'coberturas': leer('CHILEXPRESS_API_KEY_COBERTURAS') or leer('CHILEXPRESS_API_KEY_GEO'),
        'envios': leer('CHILEXPRESS_API_KEY_ENVIOS'),
    }
    llaves = {k: v for k, v in llaves.items() if v}
    if llaves:
        ProveedorEnvio.objects.create(codigo='CHILEXPRESS', credenciales_cifradas=cifrar_json(llaves))


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0021_proveedor_envio'),
    ]

    operations = [
        migrations.RunPython(copiar_credenciales_chilexpress, migrations.RunPython.noop),
    ]
