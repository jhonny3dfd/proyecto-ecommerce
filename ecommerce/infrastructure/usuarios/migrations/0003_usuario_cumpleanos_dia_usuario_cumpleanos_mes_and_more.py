# Generada por Django 6.1.2 el 11 de noviembre de 2026.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('usuarios', '0002_alter_usuario_options_alter_usuario_managers_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='cumpleanos_dia',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='usuario',
            name='cumpleanos_mes',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name='usuario',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('cumpleanos_dia__isnull', True), ('cumpleanos_mes__isnull', True)), models.Q(('cumpleanos_dia__gte', 1), ('cumpleanos_dia__isnull', False), ('cumpleanos_dia__lte', 31), ('cumpleanos_mes__gte', 1), ('cumpleanos_mes__isnull', False), ('cumpleanos_mes__lte', 12), models.Q(('cumpleanos_dia', 31), ('cumpleanos_mes__in', [4, 6, 9, 11]), _negated=True), models.Q(('cumpleanos_dia__gte', 30), ('cumpleanos_mes', 2), _negated=True)), _connector='OR'), name='usuario_cumpleanos_valido'),
        ),
    ]
