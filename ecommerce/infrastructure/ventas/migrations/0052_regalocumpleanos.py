# Generada por Django 6.1.2 el 11 de noviembre de 2026.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0051_suscripciones'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RegaloCumpleanos',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('anio', models.PositiveSmallIntegerField()),
                ('fecha_envio', models.DateTimeField(auto_now_add=True)),
                ('enviado_por', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='regalos_cumpleanos', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('usuario', 'anio'), name='regalo_cumpleanos_usuario_anio')],
            },
        ),
    ]
