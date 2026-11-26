from django.db import migrations, models
from django.db.models import F

ESTADOS_PAGADOS = ['PAGADO', 'EN_PREPARACION', 'ENVIADO', 'ENTREGADO']


def rellenar_fecha_pago(apps, schema_editor):
    """Los pedidos ya pagados no guardaron cuándo: la única fecha que hay es la de creación."""
    OrdenCompra = apps.get_model('ventas', 'OrdenCompra')
    OrdenCompra.objects.filter(estado__in=ESTADOS_PAGADOS, fecha_pago__isnull=True).update(
        fecha_pago=F('fecha_creacion'))


class Migration(migrations.Migration):

    dependencies = [
        ("ventas", "0040_ubicacion_logo_universidad"),
    ]

    operations = [
        migrations.AddField(
            model_name="ordencompra",
            name="fecha_pago",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(rellenar_fecha_pago, migrations.RunPython.noop),
    ]
