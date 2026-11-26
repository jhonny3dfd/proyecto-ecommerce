from django.contrib import admin
from .forms import MedioPagoAdminForm, PromocionAdminForm
from .models import OrdenCompra, ConfiguracionGlobal, MedioPago, Promocion


@admin.register(OrdenCompra)
class OrdenCompraAdmin(admin.ModelAdmin):
    # El checkout crea los pedidos; el panel gestiona pago, estados, stock y correos.
    campos_editables = ('nombre_destinatario', 'telefono_destinatario', 'direccion_envio_snapshot')

    def has_add_permission(self, request):
        return False

    def get_readonly_fields(self, request, obj=None):
        return tuple(campo.name for campo in self.model._meta.fields if campo.name not in self.campos_editables)

    def save_model(self, request, obj, form, change):
        # Corregir el destinatario no debe sobrescribir cambios simultáneos del panel.
        obj.save(update_fields=self.campos_editables)


admin.site.register(ConfiguracionGlobal)


@admin.register(MedioPago)
class MedioPagoAdmin(admin.ModelAdmin):
    # Las credenciales se gestionan desde el panel; tampoco se muestra el texto cifrado.
    form = MedioPagoAdminForm
    fields = ('codigo', 'habilitado', 'datos', 'actualizado')
    readonly_fields = ('actualizado',)
    list_display = ('codigo', 'habilitado', 'actualizado')

    def get_readonly_fields(self, request, obj=None):
        return (*self.readonly_fields, 'codigo') if obj is not None else self.readonly_fields

    def save_model(self, request, obj, form, change):
        if change:
            # Conservar las credenciales, incluso si el panel acaba de actualizarlas.
            obj.save(update_fields=('habilitado', 'datos', 'actualizado'))
        else:
            super().save_model(request, obj, form, change)


@admin.register(Promocion)
class PromocionAdmin(admin.ModelAdmin):
    form = PromocionAdminForm
    # Los usos los cuenta el checkout: editarlos a mano rompería el límite
    readonly_fields = ('usos',)
    list_display = ('codigo', 'tipo_descuento', 'valor_descuento', 'monto_minimo', 'automatica', 'usos',
                    'usos_maximos', 'is_active')
