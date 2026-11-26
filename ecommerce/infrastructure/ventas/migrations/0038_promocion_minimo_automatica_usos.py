from django.db import migrations, models


def un_uso_para_los_existentes(apps, schema_editor):
    # Hasta ahora cada código servía para una sola compra: los que ya existen siguen igual
    apps.get_model('ventas', 'Promocion').objects.update(usos_maximos=1)


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0037_proveedor_envio_cualquier_courier'),
    ]

    operations = [
        migrations.AddField(
            model_name='promocion',
            name='monto_minimo',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='promocion',
            name='automatica',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='promocion',
            name='usos_maximos',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='promocion',
            name='usos',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(un_uso_para_los_existentes, migrations.RunPython.noop),
    ]
