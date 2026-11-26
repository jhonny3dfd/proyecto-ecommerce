import re
from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import mail
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APITestCase

from .factories import PASSWORD, create_user

NUEVA = 'Otra-Clave-Segura-2026'
ENLACE = re.compile(r'http://tienda\.test/restablecer-contrasena\?uid=(?P<uid>[\w-]+)&token=(?P<token>[\w-]+)')


def sin_hilo(funcion):
    funcion()


class BaseContrasena(APITestCase):
    def setUp(self):
        # En setUp y no como decorador de clase: así también valen en las subclases y en su setUp
        for parche in (patch.dict('os.environ', {'FRONTEND_URL': 'http://tienda.test'}),
                       patch('ecommerce.infrastructure.usuarios.cuentas.en_segundo_plano', sin_hilo)):
            parche.start()
            self.addCleanup(parche.stop)
        cache.clear()
        self.usuario = create_user()

    def pedir_enlace(self, email):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse('contrasena_olvido'), {'email': email}, format='json')

    def enlace_del_correo(self):
        return ENLACE.search(mail.outbox[-1].body).groupdict()

    def restablecer(self, uid, token, password=NUEVA, password2=NUEVA):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse('contrasena_restablecer'),
                                    {'uid': uid, 'token': token, 'password': password, 'password2': password2},
                                    format='json')

    def login(self, password):
        return self.client.post(reverse('token_obtain_pair'),
                                {'email': self.usuario.email, 'password': password}, format='json')


class OlvidoContrasenaTests(BaseContrasena):
    def test_un_correo_con_cuenta_recibe_el_enlace(self):
        response = self.pedir_enlace('Comprador@Example.test')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.usuario.email])
        self.assertIn('Elige una nueva contraseña', mail.outbox[0].subject)
        self.assertIn('vence en 1 hora', mail.outbox[0].body)
        self.assertTrue(ENLACE.search(mail.outbox[0].body))
        self.assertIn('Elegir nueva contraseña', mail.outbox[0].alternatives[0].content)

    def test_un_correo_sin_cuenta_recibe_la_misma_respuesta_y_no_se_envia_nada(self):
        con_cuenta = self.pedir_enlace(self.usuario.email)
        sin_cuenta = self.pedir_enlace('nadie@example.test')

        self.assertEqual((sin_cuenta.status_code, sin_cuenta.data), (con_cuenta.status_code, con_cuenta.data))
        self.assertEqual(len(mail.outbox), 1)

    def test_una_cuenta_desactivada_no_recibe_el_enlace(self):
        self.usuario.is_active = False
        self.usuario.save(update_fields=['is_active'])
        self.assertEqual(self.pedir_enlace(self.usuario.email).status_code, 200)
        self.assertEqual(mail.outbox, [])

    def test_una_cuenta_de_google_recibe_el_enlace_para_crear_su_contrasena(self):
        self.usuario.set_unusable_password()
        self.usuario.save(update_fields=['password'])

        self.pedir_enlace(self.usuario.email)
        self.assertIn('Hoy entras con Google', mail.outbox[0].body)

        uid_token = self.enlace_del_correo()
        self.assertEqual(self.restablecer(**uid_token).status_code, 200)
        self.assertEqual(self.login(NUEVA).status_code, 200)

    def test_el_correo_sale_en_segundo_plano(self):
        with patch('ecommerce.infrastructure.usuarios.cuentas.en_segundo_plano') as segundo_plano:
            self.pedir_enlace(self.usuario.email)
        segundo_plano.assert_called_once()
        self.assertEqual(mail.outbox, [])

    def test_mas_de_cinco_pedidos_por_hora_desde_la_misma_ip_se_frenan(self):
        for _ in range(5):
            self.assertEqual(self.pedir_enlace('nadie@example.test').status_code, 200)
        self.assertEqual(self.pedir_enlace('nadie@example.test').status_code, 429)

    def test_un_correo_mal_escrito_se_rechaza(self):
        self.assertEqual(self.pedir_enlace('no-es-correo').status_code, 400)


class RestablecerContrasenaTests(BaseContrasena):
    def setUp(self):
        super().setUp()
        self.pedir_enlace(self.usuario.email)
        self.uid_token = self.enlace_del_correo()

    def test_el_enlace_del_correo_cambia_la_contrasena_y_avisa_del_cambio(self):
        response = self.restablecer(**self.uid_token)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.login(PASSWORD).status_code, 401)
        self.assertEqual(self.login(NUEVA).status_code, 200)
        aviso = mail.outbox[-1]
        self.assertIn('Tu contraseña cambió', aviso.subject)
        self.assertIn('http://tienda.test/recuperar-contrasena', aviso.body)

    def test_el_enlace_sirve_una_sola_vez(self):
        self.restablecer(**self.uid_token)
        response = self.restablecer(**self.uid_token, password='Tercera-Clave-2026', password2='Tercera-Clave-2026')

        self.assertEqual(response.status_code, 400)
        self.assertIn('enlace', response.data)
        self.assertEqual(self.login(NUEVA).status_code, 200)

    def test_un_enlace_alterado_o_con_otro_uid_no_sirve(self):
        for uid, token in ((self.uid_token['uid'], 'inventado'), ('MTIzNDU', self.uid_token['token']),
                           ('no-es-base64!', self.uid_token['token'])):
            response = self.restablecer(uid, token)
            self.assertEqual(response.status_code, 400)
            self.assertIn('enlace', response.data)
        self.assertEqual(self.login(PASSWORD).status_code, 200)

    def test_el_enlace_vence_en_una_hora(self):
        en_dos_horas = datetime.now() + timedelta(hours=2)
        with patch.object(PasswordResetTokenGenerator, '_now', return_value=en_dos_horas):
            response = self.restablecer(**self.uid_token)
        self.assertEqual(response.status_code, 400)
        self.assertIn('enlace', response.data)

    def test_una_contrasena_debil_o_que_no_coincide_muestra_el_error_de_cada_campo_sin_gastar_el_enlace(self):
        response = self.restablecer(**self.uid_token, password='123', password2='456')

        self.assertEqual(response.status_code, 400)
        self.assertIn('password', response.data)
        self.assertEqual(response.data['password2'], ['Las contraseñas no coinciden.'])
        self.assertEqual(self.restablecer(**self.uid_token).status_code, 200)


class CambiarContrasenaTests(BaseContrasena):
    def cambiar(self, actual, password=NUEVA, password2=NUEVA):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse('contrasena_cambiar'),
                                    {'actual': actual, 'password': password, 'password2': password2}, format='json')

    def test_sin_sesion_no_se_puede_cambiar(self):
        self.assertEqual(self.cambiar(PASSWORD).status_code, 401)

    def test_con_la_actual_correcta_cambia_y_avisa_del_cambio(self):
        self.client.force_authenticate(self.usuario)
        response = self.cambiar(PASSWORD)

        self.assertEqual(response.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(NUEVA))
        self.assertIn('Tu contraseña cambió', mail.outbox[-1].subject)

    def test_con_la_actual_incorrecta_no_cambia(self):
        self.client.force_authenticate(self.usuario)
        response = self.cambiar('equivocada')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'actual': ['La contraseña actual no es correcta.']})
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(PASSWORD))
        self.assertEqual(mail.outbox, [])

    def test_una_cuenta_de_google_crea_su_contrasena_sin_la_actual(self):
        self.usuario.set_unusable_password()
        self.usuario.save(update_fields=['password'])
        self.client.force_authenticate(self.usuario)

        self.assertFalse(self.client.get(reverse('usuario_actual')).data['tiene_contrasena'])
        self.assertEqual(self.cambiar('').status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(NUEVA))
        self.client.force_authenticate(self.usuario)
        self.assertTrue(self.client.get(reverse('usuario_actual')).data['tiene_contrasena'])

    def test_los_intentos_por_cuenta_se_frenan_despues_de_diez(self):
        self.client.force_authenticate(self.usuario)
        for _ in range(10):
            self.assertEqual(self.cambiar('equivocada').status_code, 400)
        self.assertEqual(self.cambiar(PASSWORD).status_code, 429)
