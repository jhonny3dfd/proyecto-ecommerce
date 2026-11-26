"""Datos de contacto de la tienda (pie de página e Instagram de la landing); independiente de Django."""

import re
from urllib.parse import urlparse
# Reglas de Instagram: hasta 30 letras, números, puntos o guiones bajos; sin punto al inicio, al final ni dos seguidos
_USUARIO_INSTAGRAM = re.compile(r'^(?!\.)(?!.*\.\.)[a-z0-9._]{1,30}(?<!\.)$')
_PERFIL_INSTAGRAM = re.compile(r'^(https?://)?(www\.)?instagram\.com/', re.IGNORECASE)


class UsuarioInstagramInvalido(ValueError):
    def __init__(self):
        super().__init__(
            'Escribe el usuario de Instagram (por ejemplo, @mitienda) o el enlace a tu perfil. '
            'Solo puede tener letras, números, puntos y guiones bajos.'
        )


def normalizar_usuario_instagram(texto):
    """Acepta 'mitienda', '@mitienda' o el enlace al perfil y devuelve 'mitienda' ('' si viene vacío)."""
    valor = (texto or '').strip()
    if not valor:
        return ''
    if _PERFIL_INSTAGRAM.match(valor):
        # instagram.com/mitienda/?hl=es -> mitienda
        valor = _PERFIL_INSTAGRAM.sub('', valor).split('?')[0].split('/')[0]
    # Instagram no distingue mayúsculas en los usuarios
    valor = valor.lstrip('@').lower()
    if not _USUARIO_INSTAGRAM.match(valor):
        raise UsuarioInstagramInvalido()
    return valor


def direccion_es_publica(retiro_en_local_activo, mostrar_direccion_pie):
    """La dirección del local solo se publica si el comprador la necesita (retiro) o el admin eligió mostrarla.

    Muchos emprendedores despachan desde su casa: sin una de las dos, la dirección no sale de la base.
    """
    return bool(retiro_en_local_activo or mostrar_direccion_pie)


# RN-01: el admin elige dónde va el logo de la Universidad: en el header junto al del negocio (por defecto) o en
# el footer, más grande, con el del negocio en el header (decidido el 2026-11-05). No hay ninguna opción para ocultarlo
LOGO_UNIVERSIDAD_HEADER = 'HEADER'
LOGO_UNIVERSIDAD_FOOTER = 'FOOTER'
UBICACIONES_LOGO_UNIVERSIDAD = (LOGO_UNIVERSIDAD_HEADER, LOGO_UNIVERSIDAD_FOOTER)

# Dominios permitidos para las redes sociales de la tienda.
DOMINIOS_REDES = {
    'facebook': {'facebook.com', 'www.facebook.com', 'm.facebook.com'},
    'x': {'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'},
    'youtube': {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be'},
    'tiktok': {'tiktok.com', 'www.tiktok.com'},
}

class EnlaceRedSocialInvalido(ValueError):
    def __init__(self, red):
        nombres = {
            'facebook': 'Facebook',
            'x': 'X',
            'youtube': 'YouTube',
            'tiktok': 'TikTok',
        }
        nombre = nombres.get(red, red.capitalize())
        super().__init__(
            f'Ingresa un enlace válido de {nombre} que comience con https://.'
        )



def validar_enlace_red_social(texto, red):
    """Valida que una URL HTTPS pertenezca a la red social indicada.

    Devuelve una cadena vacía cuando el campo es opcional y no se completó.
    """
    valor = (texto or '').strip()

    if not valor:
        return ''

    if red not in DOMINIOS_REDES:
        raise ValueError('Red social no reconocida.')

    try:
        url = urlparse(valor)
        dominio = (url.hostname or '').lower()

        if (
            url.scheme != 'https'
            or dominio not in DOMINIOS_REDES[red]
            or not url.path.strip('/')
            or url.username is not None
            or url.password is not None
            or url.port is not None
        ):
            raise EnlaceRedSocialInvalido(red)

    except ValueError:
        raise EnlaceRedSocialInvalido(red) from None

    return valor
