"""Videos de YouTube: el ID de 11 caracteres a partir del enlace que pega el admin.

Lo usan el blog (SCRUM-195) y la ficha del producto (pedido de Alan). Independiente de Django.
"""

import re
from urllib.parse import parse_qs, urlparse

PATRON_ID_YOUTUBE = re.compile(r'^[a-zA-Z0-9_-]{11}$')
DOMINIOS_YOUTUBE = ('youtube.com', 'youtu.be', 'youtube-nocookie.com')


def extraer_id_youtube(enlace: str | None) -> str:
    """Extrae y valida el ID de un video de YouTube (SCRUM-195).

    Acepta enlaces estándar (youtube.com/watch?v=...), cortos (youtu.be/...),
    Shorts (youtube.com/shorts/...), embebidos o el ID directo de 11 caracteres.
    Devuelve '' si el valor es vacío o None.
    Lanza ValueError si el enlace no es de YouTube o no contiene un ID válido.
    """
    if not enlace:
        return ''
    texto = str(enlace).strip()
    if not texto:
        return ''

    # Si ya es un ID directo de 11 caracteres válidos
    if PATRON_ID_YOUTUBE.match(texto):
        return texto

    url = texto
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise ValueError('El enlace de YouTube no tiene un formato válido.') from exc

    hostname = (parsed.hostname or '').lower()
    es_valido = any(hostname == d or hostname.endswith('.' + d) for d in DOMINIOS_YOUTUBE)
    if not es_valido:
        raise ValueError('El enlace debe ser de YouTube (youtube.com o youtu.be).')

    candidato = ''
    if hostname == 'youtu.be' or hostname.endswith('.youtu.be'):
        segmentos = [s for s in parsed.path.strip('/').split('/') if s]
        if segmentos:
            candidato = segmentos[0]
    else:
        path = parsed.path
        if path.startswith('/shorts/'):
            segmentos = [s for s in path[len('/shorts/'):].strip('/').split('/') if s]
            if segmentos:
                candidato = segmentos[0]
        elif path.startswith('/embed/'):
            segmentos = [s for s in path[len('/embed/'):].strip('/').split('/') if s]
            if segmentos:
                candidato = segmentos[0]
        else:
            qs = parse_qs(parsed.query)
            candidato = qs.get('v', [''])[0]
            if not candidato:
                segmentos = [s for s in path.strip('/').split('/') if s]
                if segmentos and PATRON_ID_YOUTUBE.match(segmentos[0]):
                    candidato = segmentos[0]

    if not candidato or not PATRON_ID_YOUTUBE.match(candidato):
        raise ValueError('No se encontró un ID de video válido en el enlace de YouTube.')

    return candidato
