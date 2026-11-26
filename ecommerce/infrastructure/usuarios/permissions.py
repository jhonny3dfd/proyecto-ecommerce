"""DRF adapter for the explicit administrator/seller role."""

from rest_framework.permissions import BasePermission

class IsEmprendedor(BasePermission):
    """
    Verifica que el usuario esté autenticado, activo y tenga el rol de 'ADMIN' 
    (Administrador / Vendedor de la tienda).
    """
    message = 'Se requiere el rol de Administrador/Vendedor para acceder a este panel.'

    def has_permission(self, request, view):
        user = request.user
        
        # DRF ya decodificó el token e inyectó al usuario en request.user
        return bool(
            user 
            and user.is_authenticated 
            and user.is_active 
            and user.rol == 'ADMIN'
        )

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class IsAdministrador(IsEmprendedor):
    """Nombre histórico del mismo permiso usado por las pruebas de seguridad."""
