"""Copia los medios de pago de ConfiguracionGlobal.api_keys_pagos (JSON sin cifrar) a MedioPago."""

import os

from django.db import migrations


def copiar_medios_pago(apps, schema_editor):
    # El cifrado usa CLAVE_CIFRADO_CREDENCIALES, igual que el repositorio
    from ecommerce.infrastructure.ventas.cifrado import cifrar_json

    ConfiguracionGlobal = apps.get_model('ventas', 'ConfiguracionGlobal')
    MedioPago = apps.get_model('ventas', 'MedioPago')
    config = ConfiguracionGlobal.objects.filter(pk=1).first()
    claves = (config.api_keys_pagos or {}) if config else {}

    def crear(codigo, habilitado, datos, secretos):
        if MedioPago.objects.filter(codigo=codigo).exists():
            return
        MedioPago.objects.create(codigo=codigo, habilitado=habilitado, datos=datos,
                                 credenciales_cifradas=cifrar_json({k: v for k, v in secretos.items() if v}))

    transbank = claves.get('TRANSBANK')
    if isinstance(transbank, dict):
        # El ambiente y las credenciales de producción se leían del .env, no del JSON
        ambiente = os.environ.get('TRANSBANK_ENVIRONMENT', 'INTEGRACION').strip().upper()
        if ambiente not in ('INTEGRACION', 'PRODUCCION'):
            ambiente = 'INTEGRACION'
        datos = {'ambiente': ambiente}
        secretos = {}
        if ambiente == 'PRODUCCION':
            datos['commerce_code'] = os.environ.get('TRANSBANK_WEBPAY_COMMERCE_CODE', '').strip()
            secretos['api_key'] = os.environ.get('TRANSBANK_WEBPAY_API_KEY', '').strip()
        crear('TRANSBANK', bool(transbank.get('activo', True)), {k: v for k, v in datos.items() if v}, secretos)

    mercado_pago = claves.get('MERCADO_PAGO')
    if isinstance(mercado_pago, dict):
        crear('MERCADO_PAGO', bool(mercado_pago.get('activo', True)), {},
              {'access_token': str(mercado_pago.get('access_token') or '')})


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0016_medio_pago'),
    ]

    operations = [
        migrations.RunPython(copiar_medios_pago, migrations.RunPython.noop),
    ]
