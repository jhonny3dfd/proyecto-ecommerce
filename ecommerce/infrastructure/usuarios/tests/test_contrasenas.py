from django.contrib.auth.hashers import make_password
from django.urls import reverse
from rest_framework.test import APITestCase

from .factories import PASSWORD, create_user


class ContrasenasArgon2Tests(APITestCase):
    """RNF-03: las contraseñas se guardan con Argon2."""

    def test_una_contrasena_nueva_se_guarda_con_argon2(self):
        usuario = create_user()
        self.assertTrue(usuario.password.startswith('argon2$'))
        self.assertTrue(usuario.check_password(PASSWORD))

    def test_una_cuenta_con_pbkdf2_inicia_sesion_y_queda_con_argon2(self):
        usuario = create_user()
        # Cuenta creada antes del cambio, con el hasher por defecto de Django
        usuario.password = make_password(PASSWORD, hasher='pbkdf2_sha256')
        usuario.save(update_fields=['password'])

        response = self.client.post(reverse('token_obtain_pair'),
                                    {'email': usuario.email, 'password': PASSWORD}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        usuario.refresh_from_db()
        self.assertTrue(usuario.password.startswith('argon2$'))
        self.assertTrue(usuario.check_password(PASSWORD))

    def test_una_contrasena_incorrecta_no_migra_el_hash(self):
        usuario = create_user()
        anterior = make_password(PASSWORD, hasher='pbkdf2_sha256')
        usuario.password = anterior
        usuario.save(update_fields=['password'])

        response = self.client.post(reverse('token_obtain_pair'),
                                    {'email': usuario.email, 'password': 'otra-clave-incorrecta'}, format='json')

        self.assertEqual(response.status_code, 401)
        usuario.refresh_from_db()
        self.assertEqual(usuario.password, anterior)
