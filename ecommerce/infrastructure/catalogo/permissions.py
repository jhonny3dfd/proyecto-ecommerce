from rest_framework.permissions import BasePermission, SAFE_METHODS

from ecommerce.infrastructure.usuarios.permissions import IsAdministrador


class LecturaPublicaEscrituraAdmin(BasePermission):
    message = IsAdministrador.message

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or IsAdministrador().has_permission(request, view)
