"""Reglas de dominio para el carrusel de banner de la portada (RF-01.1, SCRUM-194)."""

from dataclasses import dataclass
from pathlib import PurePath

# Diapositivas del carrusel: fotos y el video (opcional, pedido de Alan) cuentan juntos
MAX_DIAPOSITIVAS_BANNER = 10
MAX_VIDEOS_BANNER = 1
MAX_VIDEO_BANNER_BYTES = 10 * 1024 * 1024

# Textos de cada foto: los mismos límites que los de la portada (CAMPOS_TEXTO del modo edición)
LARGO_ANTETITULO = 200
LARGO_TITULO = 300
LARGO_TEXTO = 1000

# Páginas del header a las que puede llevar el botón de una foto. Blog y Cotizar solo se muestran si su
# módulo está activo; eso lo decide la portada al mostrarla, no se valida al guardar
DESTINOS_BOTON = ('INICIO', 'CATALOGO', 'BLOG', 'COTIZAR')
DESTINO_POR_DEFECTO = 'CATALOGO'


class LimiteFotosBannerExcedido(Exception):
    """Se intenta subir más de MAX_DIAPOSITIVAS_BANNER diapositivas."""


class EstructuraBannerInvalida(Exception):
    """El manifiesto de orden o los identificadores de banner no son válidos."""


class TextosFotoInvalidos(ValueError):
    """Los textos o el destino del botón de una foto no cumplen las reglas."""

class LimiteVideosBannerExcedido(Exception):
    """El banner admite como máximo un video."""

class VideoBannerInvalido(ValueError):
    """El archivo de video no cumple las reglas del banner."""

@dataclass(frozen=True)
class TextosFoto:
    """Lo que muestra una foto del carrusel: sus textos y a qué página lleva su botón."""

    antetitulo: str
    titulo: str
    texto: str
    destino: str = DESTINO_POR_DEFECTO


def validar_cantidad_fotos_banner(cantidad: int):
    if cantidad > MAX_DIAPOSITIVAS_BANNER:
        raise LimiteFotosBannerExcedido(f'El banner admite hasta {MAX_DIAPOSITIVAS_BANNER} diapositivas.')

def validar_cantidad_videos_banner(cantidad: int):
    if cantidad > MAX_VIDEOS_BANNER:
        raise LimiteVideosBannerExcedido(
            f'El banner admite como máximo {MAX_VIDEOS_BANNER} video.')

def validar_video_banner(nombre: str, tipo_contenido: str, tamano: int, encabezado: bytes):
    """Valida nombre, MIME, tamaño y firma básica de un archivo MP4.

    encabezado debe contener al menos los primeros 8 bytes del archivo.
    """
    if not isinstance(nombre, str) or PurePath(nombre).suffix.lower() != '.mp4':
        raise VideoBannerInvalido('El video debe tener extensión .mp4.')

    if tipo_contenido != 'video/mp4':
        raise VideoBannerInvalido('El video debe tener formato MP4 (video/mp4).')

    if not isinstance(tamano, int) or isinstance(tamano, bool) or tamano <= 0:
        raise VideoBannerInvalido('El archivo de video está vacío o tiene un tamaño inválido.')

    if tamano > MAX_VIDEO_BANNER_BYTES:
        raise VideoBannerInvalido('El video no puede superar los 10 MB.')

    if not isinstance(encabezado, bytes) or len(encabezado) < 8 or encabezado[4:8] != b'ftyp':
        raise VideoBannerInvalido('El archivo no parece ser un video MP4 válido.')

def _texto(valor, nombre: str, largo: int) -> str:
    if valor is None:
        return ''
    if not isinstance(valor, str):
        raise TextosFotoInvalidos(f'El {nombre} de la foto debe ser texto.')
    valor = valor.strip()
    if len(valor) > largo:
        raise TextosFotoInvalidos(f'El {nombre} de la foto puede tener hasta {largo} caracteres.')
    return valor


def normalizar_textos_foto(datos: dict) -> TextosFoto:
    """Valida los textos de una foto (SCRUM-194): el título es obligatorio porque es el h1 de la portada.

    Sin destino, el botón lleva al catálogo, como el botón de la portada antes del carrusel.
    """
    if not isinstance(datos, dict):
        raise TextosFotoInvalidos('Los textos de la foto no tienen un formato válido.')
    titulo = _texto(datos.get('titulo'), 'título', LARGO_TITULO)
    if not titulo:
        raise TextosFotoInvalidos('Cada foto del carrusel necesita un título.')
    destino = datos.get('destino') or DESTINO_POR_DEFECTO
    if destino not in DESTINOS_BOTON:
        raise TextosFotoInvalidos('El botón solo puede llevar a Inicio, Catálogo, Blog o Cotizar.')
    return TextosFoto(
        antetitulo=_texto(datos.get('antetitulo'), 'antetítulo', LARGO_ANTETITULO),
        titulo=titulo,
        texto=_texto(datos.get('texto'), 'texto', LARGO_TEXTO),
        destino=destino,
    )
