"""Access policy for the store's configurable guest checkout."""

from rest_framework.permissions import BasePermission

from .models import ConfiguracionGlobal


class CanCheckout(BasePermission):
    message = 'Esta tienda requiere que inicies sesión para comprar.'

    def has_permission(self, request, view):
        config = ConfiguracionGlobal.objects.first()
        requires_account = (
            config is not None
            and config.modo_autenticacion == 'REGISTRO_OBLIGATORIO'
        )
        return not requires_account or bool(request.user.is_authenticated)
