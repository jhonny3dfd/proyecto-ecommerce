from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import UsuarioChangeForm, UsuarioCreationForm
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    add_form = UsuarioCreationForm
    form = UsuarioChangeForm
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Datos personales', {'fields': ('nombre', 'apellido_paterno', 'apellido_materno', 'telefono')}),
        ('Cuenta', {'fields': ('rol', 'google_sso_id', 'acepta_cookies')}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Acceso', {'fields': ('last_login',)}),
    )
    add_fieldsets = (
        (None, {'classes': ('wide',), 'fields': (
            'email', 'nombre', 'apellido_paterno', 'apellido_materno', 'telefono', 'rol',
            'usable_password', 'password1', 'password2',
        )}),
    )
    list_display = ('email', 'nombre', 'apellido_paterno', 'apellido_materno', 'rol', 'is_staff', 'is_active')
    list_filter = ('rol', 'is_staff', 'is_superuser', 'is_active', 'groups')
    search_fields = ('email', 'nombre', 'apellido_paterno', 'apellido_materno')
    ordering = ('email',)
    readonly_fields = ('last_login',)
