from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from .factories import create_user

User = get_user_model()

CLIENT_ID = 'tienda-qa.apps.googleusercontent.com'
VERIFICAR = 'ecommerce.infrastructure.usuarios.services.id_token.verify_oauth2_token'


def payload_google(**cambios):
    return {'sub': 'google-123', 'email': 'nueva@example.test', 'email_verified': True,
            'given_name': 'Nueva', 'family_name': 'Persona', **cambios}


@override_settings(GOOGLE_CLIENT_ID=CLIENT_ID)
@patch(VERIFICAR)
class GoogleLoginTests(APITestCase):
    """RN-04: inicio de sesión con Google. La verificación del token con Google se simula."""

    def login(self):
        return self.client.post(reverse('google_login'), {'id_token': 'token-de-google'}, format='json')

    def test_crea_un_comprador_y_entrega_jwt(self, verificar):
        verificar.return_value = payload_google()
        response = self.login()

        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data['tokens'])
        usuario = User.objects.get(email='nueva@example.test')
        self.assertEqual((usuario.rol, usuario.google_sso_id), ('COMPRADOR', 'google-123'))
        self.assertFalse(usuario.has_usable_password())

    def test_reconoce_la_cuenta_aunque_se_haya_registrado_con_otras_mayusculas(self, verificar):
        # Una cuenta antigua, de antes de guardar los correos en minúsculas
        existente = User.objects.create(email='Nueva@Example.test', nombre='Nueva', apellido_paterno='Persona')
        verificar.return_value = payload_google()

        self.assertEqual(self.login().status_code, 200)
        self.assertEqual(list(User.objects.values_list('id', flat=True)), [existente.id])

    def test_verifica_que_el_token_sea_para_esta_tienda(self, verificar):
        verificar.return_value = payload_google()
        self.login()
        self.assertEqual(verificar.call_args.kwargs['audience'], CLIENT_ID)

    def test_tolera_unos_segundos_de_desfase_del_reloj(self, verificar):
        # Con el reloj del servidor un poco atrasado, Google rechazaba los tokens recién emitidos
        verificar.return_value = payload_google()
        self.assertEqual(self.login().status_code, 200)
        self.assertEqual(verificar.call_args.kwargs['clock_skew_in_seconds'], 10)

    def test_correo_sin_verificar_no_entra_ni_se_vincula_a_una_cuenta_existente(self, verificar):
        admin = create_user('admin@example.test', rol='ADMIN')
        for verificado in (False, None):
            with self.subTest(email_verified=verificado):
                verificar.return_value = payload_google(email='admin@example.test', email_verified=verificado)
                response = self.login()
                self.assertEqual(response.status_code, 401)
                self.assertNotIn('tokens', response.data)
        admin.refresh_from_db()
        self.assertIsNone(admin.google_sso_id)

    def test_token_invalido_o_de_otra_aplicacion_se_rechaza(self, verificar):
        verificar.side_effect = ValueError('Token has wrong audience')
        response = self.login()
        self.assertEqual(response.status_code, 401)
        self.assertFalse(User.objects.exists())

    def test_cuenta_existente_con_correo_verificado_se_vincula(self, verificar):
        create_user('nueva@example.test')
        verificar.return_value = payload_google()
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.get(email='nueva@example.test').google_sso_id, 'google-123')

    @override_settings(GOOGLE_CLIENT_ID='')
    def test_sin_client_id_responde_503_sin_consultar_a_google(self, verificar):
        response = self.login()
        self.assertEqual(response.status_code, 503)
        verificar.assert_not_called()
        self.assertFalse(User.objects.exists())
