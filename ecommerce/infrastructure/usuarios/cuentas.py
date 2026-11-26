"""Adaptadores de los casos de uso de la contraseña (application/cuentas.py): cuentas, enlace firmado y correos."""

import logging
import os
import threading

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from ecommerce.application.cuentas import (
    CuentasUsuario, EnlacesRestablecimiento, NotificadorCuentas, ValidadorContrasenas,
)
from ecommerce.infrastructure.ventas.models import ConfiguracionGlobal

from .models import Usuario

logger = logging.getLogger(__name__)


def frontend_url():
    return os.getenv('FRONTEND_URL', 'http://localhost:5173').rstrip('/')


class CuentasDjango(CuentasUsuario):
    def buscar_activa_por_correo(self, correo):
        # El correo es único tal como se escribió; si dos cuentas solo difieren en mayúsculas, gana la exacta
        candidatas = list(Usuario.objects.filter(email__iexact=correo, is_active=True).order_by('id')[:2])
        exacta = next((usuario for usuario in candidatas if usuario.email == correo), None)
        if exacta:
            return exacta.id
        return candidatas[0].id if len(candidatas) == 1 else None

    def tiene_contrasena(self, usuario_id):
        return Usuario.objects.get(id=usuario_id).has_usable_password()

    def contrasena_correcta(self, usuario_id, contrasena):
        return Usuario.objects.get(id=usuario_id).check_password(contrasena)

    def cambiar_contrasena(self, usuario_id, contrasena):
        usuario = Usuario.objects.get(id=usuario_id)
        usuario.set_password(contrasena)
        usuario.save(update_fields=['password'])


class EnlacesDjango(EnlacesRestablecimiento):
    """El token de Django vence con PASSWORD_RESET_TIMEOUT y deja de servir cuando cambia la contraseña."""

    def crear(self, usuario_id):
        usuario = Usuario.objects.get(id=usuario_id)
        uid = urlsafe_base64_encode(force_bytes(usuario.pk))
        return f'{frontend_url()}/restablecer-contrasena?uid={uid}&token={default_token_generator.make_token(usuario)}'

    def usuario_del_enlace(self, uid, token):
        try:
            usuario = Usuario.objects.get(pk=int(force_str(urlsafe_base64_decode(uid or ''))), is_active=True)
        except (TypeError, ValueError, OverflowError, Usuario.DoesNotExist):
            return None
        return usuario.id if default_token_generator.check_token(usuario, token or '') else None


class ValidadorDjango(ValidadorContrasenas):
    """Las mismas reglas que el registro (AUTH_PASSWORD_VALIDATORS)."""

    def errores(self, contrasena, usuario_id):
        try:
            validate_password(contrasena, user=Usuario.objects.get(id=usuario_id))
        except ValidationError as error:
            return list(error.messages)
        return []


def en_segundo_plano(funcion):
    """El envío sale en otro hilo: así pedir el enlace tarda lo mismo exista o no la cuenta."""
    threading.Thread(target=funcion, daemon=True).start()


class CorreoNotificadorCuentas(NotificadorCuentas):
    def enviar_enlace(self, usuario_id, enlace):
        transaction.on_commit(lambda: self._enviar(usuario_id, 'restablecer', 'Elige una nueva contraseña',
                                                   {'url_restablecer': enlace}))

    def avisar_cambio(self, usuario_id):
        # Solo si el cambio quedó guardado
        transaction.on_commit(lambda: self._enviar(usuario_id, 'contrasena_cambiada', 'Tu contraseña cambió',
                                                   {'url_recuperar': f'{frontend_url()}/recuperar-contrasena'}))

    def _enviar(self, usuario_id, plantilla, asunto, extra):
        # El mensaje se arma aquí (lee la base) y solo el envío por SMTP o API sale en segundo plano
        try:
            usuario = Usuario.objects.get(id=usuario_id)
            config = ConfiguracionGlobal.objects.filter(pk=1).first()
            tienda = config.nombre_tienda if config and config.nombre_tienda else 'Nuestra tienda'
            contexto = {'tienda': tienda, 'nombre': usuario.nombre,
                        'sin_contrasena': not usuario.has_usable_password(), **extra}
            correo = EmailMultiAlternatives(
                subject=f'{asunto} | {tienda}',
                body=render_to_string(f'usuarios/correos/{plantilla}.txt', contexto),
                from_email=settings.DEFAULT_FROM_EMAIL, to=[usuario.email],
            )
            correo.attach_alternative(render_to_string(f'usuarios/correos/{plantilla}.html', contexto), 'text/html')
        except Exception:
            logger.exception('No se pudo preparar el correo %s de la cuenta %s', plantilla, usuario_id)
            return
        en_segundo_plano(lambda: self._mandar(correo, plantilla, usuario_id))

    @staticmethod
    def _mandar(correo, plantilla, usuario_id):
        try:
            correo.send()
        except Exception:
            # Sin el correo ni el enlace en el log
            logger.exception('No se pudo enviar el correo %s de la cuenta %s', plantilla, usuario_id)
