"""Blog o portafolio de la tienda: publicaciones con texto y fotos que el admin activa desde el panel.

Independiente de Django. El HTML del texto lo limpia la infraestructura antes de llegar aquí.
"""

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from ecommerce.domain.youtube import extraer_id_youtube

MAX_FOTOS_PUBLICACION = 10
NOMBRE_BLOG_POR_DEFECTO = 'Nosotros'
LARGO_NOMBRE_BLOG = 30
LARGO_TITULO = 150
LARGO_RESUMEN = 300
# Con espacio para el sufijo de los títulos repetidos (-2, -3...)
LARGO_SLUG = 80

class EstadoPublicacion(StrEnum):
    BORRADOR = 'BORRADOR'
    PUBLICADA = 'PUBLICADA'


class PublicacionInvalida(ValueError):
    """Errores por campo, como los muestra el formulario del panel."""

    def __init__(self, errores: dict):
        self.errores = errores
        super().__init__('; '.join(f'{campo}: {error}' for campo, error in errores.items()))


class NombreBlogInvalido(ValueError):
    def __init__(self):
        super().__init__(f'El nombre del menú puede tener hasta {LARGO_NOMBRE_BLOG} caracteres.')


class LimiteFotosExcedido(ValueError):
    def __init__(self):
        super().__init__(f'Cada publicación puede tener hasta {MAX_FOTOS_PUBLICACION} fotos.')


@dataclass(frozen=True)
class DatosPublicacion:
    titulo: str
    resumen: str
    # HTML ya limpio; vacío si el editor no tenía texto
    contenido: str
    estado: EstadoPublicacion
    youtube_id: str = ''

    @classmethod
    def desde(cls, datos: dict, contenido_tiene_texto: bool, tiene_portada: bool) -> 'DatosPublicacion':
        """`contenido_tiene_texto` lo resuelve quien llama, porque el editor deja HTML aunque esté vacío."""
        titulo = str(datos.get('titulo') or '').strip()
        resumen = str(datos.get('resumen') or '').strip()
        errores = {}
        if not titulo:
            errores['titulo'] = 'Este dato es obligatorio.'
        elif len(titulo) > LARGO_TITULO:
            errores['titulo'] = f'El título puede tener hasta {LARGO_TITULO} caracteres.'
        if len(resumen) > LARGO_RESUMEN:
            errores['resumen'] = f'El resumen puede tener hasta {LARGO_RESUMEN} caracteres.'

        youtube_raw = datos.get('youtube') if 'youtube' in datos else datos.get('youtube_id')
        youtube_id = ''
        if youtube_raw:
            try:
                youtube_id = extraer_id_youtube(youtube_raw)
            except ValueError as exc:
                errores['youtube'] = str(exc)

        estado = None
        try:
            estado = EstadoPublicacion(datos.get('estado') or EstadoPublicacion.BORRADOR)
        except ValueError:
            errores['estado'] = 'Elige si la publicación queda como borrador o publicada.'
        # Un borrador puede estar a medias; lo que ve el público tiene que mostrar algo
        if estado == EstadoPublicacion.PUBLICADA and not contenido_tiene_texto and not tiene_portada and not youtube_id:
            errores['contenido'] = 'Para publicar, escribe el texto o sube una foto de portada.'

        if errores:
            raise PublicacionInvalida(errores)
        contenido = str(datos.get('contenido') or '') if contenido_tiene_texto else ''
        return cls(titulo=titulo, resumen=resumen, contenido=contenido, estado=estado, youtube_id=youtube_id)


def generar_slug(titulo: str) -> str:
    """'Nuestro taller en Ñuñoa' -> 'nuestro-taller-en-nunoa' (sin tildes, para que la dirección se lea bien)."""
    sin_tildes = unicodedata.normalize('NFKD', titulo or '').encode('ascii', 'ignore').decode('ascii')
    slug = re.sub(r'[^a-z0-9]+', '-', sin_tildes.lower()).strip('-')
    return slug[:LARGO_SLUG].rstrip('-') or 'publicacion'


def slug_unico(titulo: str, ocupados: set[str]) -> str:
    """Si otra publicación ya usa el slug, agrega -2, -3... hasta encontrar uno libre."""
    base = generar_slug(titulo)
    slug, numero = base, 2
    while slug in ocupados:
        slug, numero = f'{base}-{numero}', numero + 1
    return slug


def normalizar_nombre_blog(texto) -> str:
    """Nombre del enlace del menú ('Blog', 'Portafolio'...); vacío vuelve a 'Nosotros'."""
    valor = ' '.join(str(texto or '').split())
    if not valor:
        return NOMBRE_BLOG_POR_DEFECTO
    if len(valor) > LARGO_NOMBRE_BLOG:
        raise NombreBlogInvalido()
    return valor


def validar_cantidad_fotos(actuales: int, nuevas: int) -> None:
    if actuales + nuevas > MAX_FOTOS_PUBLICACION:
        raise LimiteFotosExcedido()
