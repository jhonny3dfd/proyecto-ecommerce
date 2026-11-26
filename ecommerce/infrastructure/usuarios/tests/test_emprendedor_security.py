"""Integration tests for the IsEmprendedor permission (SCRUM-94)."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .factories import create_user


class IsEmprendedorSecurityTests(APITestCase):
    """Exercise the production dashboard with signed Bearer access tokens."""

    @classmethod
    def setUpTestData(cls):
        cls.comprador = create_user()
        cls.emprendedor = create_user(
            'emprendedor@example.test',
            rol='ADMIN',
        )

    @staticmethod
    def access_token_for(user):
        """Include the claim consumed by the current permission adapter."""
        refresh = RefreshToken.for_user(user)
        refresh['rol'] = user.rol
        return str(refresh.access_token)

    def authorize(self, user):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {self.access_token_for(user)}',
        )

    def test_request_without_bearer_token_returns_401(self):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_comprador_returns_403(self):
        self.authorize(self.comprador)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authenticated_emprendedor_returns_200(self):
        self.authorize(self.emprendedor)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['emprendedor_id'],
            str(self.emprendedor.pk),
        )
