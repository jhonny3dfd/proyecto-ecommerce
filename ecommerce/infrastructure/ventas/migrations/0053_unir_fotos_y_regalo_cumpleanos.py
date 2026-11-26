"""Unir las fotos de Sobre mí y el regalo anual sin operaciones adicionales."""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0052_regalocumpleanos'),
        ('ventas', '0052_sobre_mi_fotos'),
    ]

    operations = [
    ]
