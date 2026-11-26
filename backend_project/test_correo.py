from django.test import SimpleTestCase

from .correo import CONSOLA, RESEND, SMTP, mailer_por_defecto, remitente_por_defecto


class MailerPorDefectoTests(SimpleTestCase):
    """Resend por API; SMTP solo como alternativa (ej. Gmail en desarrollo)."""

    def test_con_resend_se_usa_su_api_aunque_haya_smtp(self):
        mailer = mailer_por_defecto({'RESEND_API_KEY': ' re_prueba_123 ', 'EMAIL_HOST': 'smtp.gmail.com'})
        self.assertEqual(mailer, {'BACKEND': RESEND, 'OPTIONS': {'api_key': 're_prueba_123', 'timeout': 10}})

    def test_sin_resend_se_usa_smtp_si_esta_configurado(self):
        mailer = mailer_por_defecto({'EMAIL_HOST': 'smtp.gmail.com', 'EMAIL_HOST_USER': 'tienda@example.test',
                                     'EMAIL_HOST_PASSWORD': 'clave', 'EMAIL_TIMEOUT': '5'})
        self.assertEqual(mailer['BACKEND'], SMTP)
        self.assertEqual(mailer['OPTIONS'], {'host': 'smtp.gmail.com', 'port': 587, 'username': 'tienda@example.test',
                                             'password': 'clave', 'use_tls': True, 'timeout': 5})
        self.assertFalse(mailer_por_defecto({'EMAIL_HOST': 'x', 'EMAIL_USE_TLS': 'False'})['OPTIONS']['use_tls'])

    def test_sin_configurar_los_correos_salen_por_la_consola(self):
        self.assertEqual(mailer_por_defecto({'RESEND_API_KEY': '  ', 'EMAIL_HOST': ''}), {'BACKEND': CONSOLA})

    def test_remitente(self):
        self.assertEqual(remitente_por_defecto({'DEFAULT_FROM_EMAIL': 'Tienda <ventas@tienda.cl>'}),
                         'Tienda <ventas@tienda.cl>')
        self.assertEqual(remitente_por_defecto({'EMAIL_HOST_USER': 'yo@gmail.com'}), 'yo@gmail.com')
        self.assertEqual(remitente_por_defecto({}), 'no-responder@localhost')
