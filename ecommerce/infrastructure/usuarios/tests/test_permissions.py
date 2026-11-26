from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase

from ecommerce.infrastructure.usuarios.models import Usuario
from ecommerce.infrastructure.usuarios.permissions import IsAdministrador


class AdministratorPermissionTests(SimpleTestCase):
    def test_role_and_active_status_are_required_for_view_and_object(self):
        cases = [
            (AnonymousUser(), False),
            (None, False),
            (Usuario(rol='COMPRADOR'), False),
            (Usuario(rol='COMPRADOR', is_staff=True), False),
            (Usuario(rol='COMPRADOR', is_superuser=True), False),
            (Usuario(rol='VENDEDOR'), False),
            (Usuario(rol=''), False),
            (Usuario(rol='admin'), False),
            (Usuario(rol='ADMIN', is_active=False), False),
            (Usuario(rol='ADMIN', is_staff=False), True),
        ]
        permission = IsAdministrador()
        for user, expected in cases:
            with self.subTest(user=user):
                request = SimpleNamespace(user=user)
                self.assertIs(
                    permission.has_permission(request, None), expected,
                )
                self.assertIs(
                    permission.has_object_permission(request, None, object()),
                    expected,
                )
