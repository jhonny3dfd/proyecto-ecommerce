"""Limpieza del HTML que guarda el editor de páginas legales (React Quill 2, tema Snow).

El contenido se muestra tal cual en la tienda pública, así que se limpia al guardarlo:
solo queda el formato que produce el editor y se elimina cualquier script o atributo peligroso (XSS).
"""

import re

import nh3

_ALINEACION = {'ql-align-center', 'ql-align-right', 'ql-align-justify', 'ql-direction-rtl'}
_SANGRIA = {f'ql-indent-{nivel}' for nivel in range(1, 10)}
_CLASES_BLOQUE = _ALINEACION | _SANGRIA

ETIQUETAS = {
    'p', 'br', 'strong', 'em', 'u', 's', 'h1', 'h2', 'h3', 'blockquote', 'ol', 'ul', 'li', 'a', 'span',
}
ATRIBUTOS = {'a': {'href'}}
# Quill 2 escribe todas las listas como <ol> y distingue el tipo con data-list
VALORES_PERMITIDOS = {
    'a': {'target': {'_blank'}},
    'li': {'data-list': {'bullet', 'ordered', 'checked', 'unchecked'}},
}
CLASES = {
    **{etiqueta: _CLASES_BLOQUE for etiqueta in ('p', 'h1', 'h2', 'h3', 'blockquote', 'li')},
    # Donde el CSS de Quill dibuja la viñeta o el número de cada ítem
    'span': {'ql-ui'},
}
ESQUEMAS_URL = {'http', 'https', 'mailto'}

# Un espacio de no separación junto a una letra (no entre etiquetas, como el '<p>&nbsp;</p>' de un párrafo vacío).
# nh3 escribe así también el carácter U+00A0
_NBSP_EN_TEXTO = re.compile(r'(?<=[^\s<>;])&nbsp;|&nbsp;(?=[^\s<>&])')


def espacios_normales(html: str) -> str:
    """El texto pegado desde otro programa suele traer '&nbsp;' en vez de espacios: el navegador ve cada párrafo como
    una sola palabra y la corta en cualquier letra. Se cambian por espacios normales."""
    return _NBSP_EN_TEXTO.sub(' ', html or '')


def limpiar_html(contenido: str) -> str:
    return espacios_normales(nh3.clean(
        contenido or '',
        tags=ETIQUETAS,
        attributes=ATRIBUTOS,
        tag_attribute_values=VALORES_PERMITIDOS,
        allowed_classes=CLASES,
        url_schemes=ESQUEMAS_URL,
        link_rel='noopener noreferrer',
    ))


def tiene_texto(contenido: str) -> bool:
    """Quill deja '<p><br></p>' cuando el editor está vacío."""
    texto = nh3.clean(contenido or '', tags=set()).replace('&nbsp;', ' ')
    return bool(texto.strip())
