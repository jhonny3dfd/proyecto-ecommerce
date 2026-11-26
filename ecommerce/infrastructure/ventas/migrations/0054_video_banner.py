from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('ventas', '0053_unir_fotos_y_regalo_cumpleanos')]
    operations = [
        migrations.AddField(model_name='configuracionglobal', name='video_banner_activo', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='fotobanner', name='video', field=models.FileField(blank=True, null=True, upload_to='negocio/banners/videos/')),
    ]
