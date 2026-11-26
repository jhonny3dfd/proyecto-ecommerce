from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from .factories import PASSWORD, create_user


@override_settings(ROOT_URLCONF='ecommerce.infrastructure.usuarios.tests.urls')
class AccessControlTests(APITestCase):
    """Exercise real middleware, token lookup, SQL users and permissions."""

    admin_methods = ('get', 'post', 'put', 'patch', 'delete', 'head', 'options')

    @classmethod
    def setUpTestData(cls):
        cls.buyer = create_user()
        cls.admin = create_user('admin@example.test', rol='ADMIN')
        cls.buyer_token = Token.objects.create(user=cls.buyer)
        cls.admin_token = Token.objects.create(user=cls.admin)

    def request_admin(self, method='get'):
        return getattr(self.client, method)(reverse('security-admin'))

    def authorize(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def assert_unauthorized(self, response):
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response['WWW-Authenticate'], 'Token')
        self.assertIn('detail', response.data)

    def test_absent_invalid_and_malformed_tokens_return_401(self):
        headers = [None, '', 'Token', 'Token ', 'Token invalid',
                   'Token one two', 'Bearer invalid', 'Basic invalid',
                   'Token ' + '0' * 40, 'Token caf\xe9']
        for header in headers:
            self.client.credentials(**(
                {} if header is None else {'HTTP_AUTHORIZATION': header}
            ))
            for method in self.admin_methods:
                with self.subTest(header=header, method=method):
                    self.assert_unauthorized(self.request_admin(method))
            with self.subTest(header=header, route='private'):
                self.assert_unauthorized(
                    self.client.get(reverse('security-private'))
                )

    def test_buyer_is_forbidden_for_every_admin_method(self):
        self.authorize(self.buyer_token)
        for method in self.admin_methods:
            with self.subTest(method=method):
                response = self.request_admin(method)
                self.assertEqual(response.status_code,
                                 status.HTTP_403_FORBIDDEN)
                self.assertNotIn('WWW-Authenticate', response)
                self.assertEqual(set(response.data), {'detail'})

    def test_admin_can_read_and_write_without_staff_flags(self):
        self.assertFalse(self.admin.is_staff)
        self.assertFalse(self.admin.is_superuser)
        self.authorize(self.admin_token)
        for method in self.admin_methods:
            with self.subTest(method=method):
                response = self.request_admin(method)
                self.assertEqual(response.status_code, 201 if method == 'post'
                                 else 200)

    def test_any_authenticated_role_can_use_default_protected_route(self):
        for token in (self.buyer_token, self.admin_token):
            with self.subTest(role=token.user.rol):
                self.authorize(token)
                response = self.client.get(reverse('security-private'))
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data, {'id': token.user_id})

    def test_staff_and_superuser_do_not_bypass_explicit_role(self):
        self.buyer.is_staff = True
        self.buyer.is_superuser = True
        self.buyer.save()
        self.authorize(self.buyer_token)
        self.assertEqual(self.request_admin().status_code, 403)

    def test_role_demotion_takes_effect_with_existing_token(self):
        self.authorize(self.admin_token)
        self.assertEqual(self.request_admin().status_code, 200)
        self.admin.rol = 'COMPRADOR'
        self.admin.save(update_fields=['rol'])
        self.assertEqual(self.request_admin().status_code, 403)

    def test_inactive_account_token_returns_401(self):
        self.admin.is_active = False
        self.admin.save(update_fields=['is_active'])
        self.authorize(self.admin_token)
        self.assert_unauthorized(self.request_admin())

    def test_revoked_token_returns_401(self):
        self.authorize(self.admin_token)
        self.admin_token.delete()
        self.assert_unauthorized(self.request_admin())

    def test_deleted_account_token_returns_401(self):
        self.authorize(self.admin_token)
        self.admin.delete()
        self.assert_unauthorized(self.request_admin())

    def test_session_authentication_preserves_role_checks(self):
        for user, expected in ((self.buyer, 403), (self.admin, 200)):
            with self.subTest(role=user.rol):
                self.client.logout()
                self.assertTrue(self.client.login(email=user.email,
                                                  password=PASSWORD))
                self.assertEqual(self.request_admin().status_code, expected)

    def test_session_write_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        self.assertTrue(client.login(email=self.admin.email,
                                     password=PASSWORD))
        self.assertEqual(
            client.post(reverse('security-admin')).status_code, 403,
        )
        csrf_secret = 'a' * 32
        client.cookies['csrftoken'] = csrf_secret
        response = client.post(reverse('security-admin'),
                               HTTP_X_CSRFTOKEN=csrf_secret)
        self.assertEqual(response.status_code, 201)

    def test_token_write_does_not_require_session_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        self.assertEqual(
            client.post(reverse('security-admin')).status_code, 201,
        )

    def test_invalid_token_does_not_fall_back_to_valid_session(self):
        self.assertTrue(self.client.login(email=self.admin.email,
                                          password=PASSWORD))
        self.client.credentials(HTTP_AUTHORIZATION='Token invalid')
        self.assert_unauthorized(self.request_admin())
