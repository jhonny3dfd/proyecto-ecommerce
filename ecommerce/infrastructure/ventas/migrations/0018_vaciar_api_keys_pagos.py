"""Borra las credenciales en texto plano de api_keys_pagos: ya están cifradas en MedioPago (0017)."""

from django.db import migrations


def vaciar_api_keys_pagos(apps, schema_editor):
    apps.get_model('ventas', 'ConfiguracionGlobal').objects.update(api_keys_pagos={})


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0017_copiar_medios_pago'),
    ]

    operations = [
        # Sin vuelta atrás: las credenciales viven ahora solo en MedioPago
        migrations.RunPython(vaciar_api_keys_pagos, migrations.RunPython.noop),
    ]
