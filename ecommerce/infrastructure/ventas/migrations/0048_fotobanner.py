import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0047_merge_destacados_sobre_mi'),
    ]

    operations = [
        migrations.CreateModel(
            name='FotoBanner',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('imagen', models.ImageField(upload_to='negocio/banners/')),
                ('orden', models.PositiveSmallIntegerField(default=0)),
                ('configuracion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fotos_banner', to='ventas.configuracionglobal')),
            ],
            options={
                'ordering': ['orden', 'id'],
            },
        ),
    ]

