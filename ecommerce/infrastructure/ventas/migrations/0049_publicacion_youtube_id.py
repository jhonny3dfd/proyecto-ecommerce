from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0048_fotobanner'),
    ]

    operations = [
        migrations.AddField(
            model_name='publicacion',
            name='youtube_id',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
    ]

