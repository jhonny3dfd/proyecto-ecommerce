"""Elige el servidor de correo (MAILERS de Django 6.1) a partir de las variables de entorno."""

RESEND = 'anymail.backends.resend.EmailBackend'
SMTP = 'django.core.mail.backends.smtp.EmailBackend'
CONSOLA = 'django.core.mail.backends.console.EmailBackend'


def _texto(entorno, nombre):
    return (entorno.get(nombre) or '').strip()


def mailer_por_defecto(entorno) -> dict:
    """Resend si hay RESEND_API_KEY; si no, SMTP si hay EMAIL_HOST; si no, la consola del runserver.

    Resend usa una API HTTPS: funciona en plataformas que bloquean el SMTP (ej. Render gratis, Railway).
    """
    # Un servidor de correo lento no debe dejar colgado el checkout ni la confirmación del pago
    timeout = int(_texto(entorno, 'EMAIL_TIMEOUT') or 10)
    if _texto(entorno, 'RESEND_API_KEY'):
        return {'BACKEND': RESEND, 'OPTIONS': {'api_key': _texto(entorno, 'RESEND_API_KEY'), 'timeout': timeout}}
    if _texto(entorno, 'EMAIL_HOST'):
        return {'BACKEND': SMTP, 'OPTIONS': {
            'host': _texto(entorno, 'EMAIL_HOST'),
            'port': int(_texto(entorno, 'EMAIL_PORT') or 587),
            'username': _texto(entorno, 'EMAIL_HOST_USER'),
            'password': _texto(entorno, 'EMAIL_HOST_PASSWORD'),
            'use_tls': _texto(entorno, 'EMAIL_USE_TLS').lower() not in ('false', '0', 'no', 'off'),
            'timeout': timeout,
        }}
    return {'BACKEND': CONSOLA}


def remitente_por_defecto(entorno) -> str:
    return _texto(entorno, 'DEFAULT_FROM_EMAIL') or _texto(entorno, 'EMAIL_HOST_USER') or 'no-responder@localhost'
