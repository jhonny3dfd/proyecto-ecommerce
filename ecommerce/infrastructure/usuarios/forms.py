"""Formularios del admin para el usuario de Ecode identificado por email."""

from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from .models import Usuario


class UsuarioCreationForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = Usuario
        fields = ('email', 'nombre', 'apellido_paterno', 'apellido_materno', 'telefono', 'rol')
        field_classes = {}


class UsuarioChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Usuario
        fields = '__all__'
        field_classes = {}
