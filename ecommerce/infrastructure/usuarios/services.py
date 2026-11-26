from google.oauth2 import id_token
from google.auth.transport import requests
from django.conf import settings
from rest_framework.exceptions import APIException, AuthenticationFailed

TOLERANCIA_RELOJ_SEGUNDOS = 10


class GoogleNoConfigurado(APIException):
    status_code = 503
    default_detail = 'El inicio de sesión con Google no está disponible en esta tienda.'
    default_code = 'google_no_configurado'


class GoogleAuthService:
    @staticmethod
    def verificar_token(token: str) -> dict:
        # Sin ID de cliente no se puede comprobar para qué aplicación se emitió el token:
        # se aceptarían tokens obtenidos por cualquier otra app con Google
        client_id = settings.GOOGLE_CLIENT_ID
        if not client_id:
            raise GoogleNoConfigurado()

        try:
            # Tolera unos segundos de desfase entre el reloj del servidor y el de Google: sin esto, un reloj
            # apenas atrasado rechaza tokens recién emitidos ("Token used too early")
            payload = id_token.verify_oauth2_token(
                token, requests.Request(), audience=client_id, clock_skew_in_seconds=TOLERANCIA_RELOJ_SEGUNDOS)
        except ValueError as exc:
            raise AuthenticationFailed(f"Token de Google inválido o expirado: {str(exc)}")

        # La cuenta se vincula por correo: un correo sin verificar podría tomar la cuenta de otra persona
        if payload.get('email_verified') is not True:
            raise AuthenticationFailed('La cuenta de Google no tiene el correo verificado.')
        return payload
