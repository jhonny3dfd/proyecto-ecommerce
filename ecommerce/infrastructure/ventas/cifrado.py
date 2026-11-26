"""Cifrado en reposo de credenciales con Fernet (AES + HMAC) de `cryptography`."""

import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class CredencialesIlegibles(Exception):
    """No se pudieron descifrar (ej. cambió CLAVE_CIFRADO_CREDENCIALES)."""


def _fernet(clave=None) -> Fernet:
    # Fernet pide 32 bytes en base64: se derivan de la clave del .env, que puede ser cualquier texto largo
    clave = clave if clave is not None else settings.CLAVE_CIFRADO_CREDENCIALES
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(clave.encode()).digest()))


def cifrar_json(datos: dict, clave=None) -> str:
    if not datos:
        return ''
    return _fernet(clave).encrypt(json.dumps(datos).encode()).decode()


def descifrar_json(texto: str, clave=None) -> dict:
    if not texto:
        return {}
    try:
        return json.loads(_fernet(clave).decrypt(texto.encode()))
    except (InvalidToken, ValueError) as error:
        raise CredencialesIlegibles() from error
