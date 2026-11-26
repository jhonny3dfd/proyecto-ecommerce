"""Casos de uso del blog o portafolio de la tienda: el admin publica entradas con fotos y el público las lee.

El blog es opcional (el admin lo activa en Configuración). Con el blog apagado el público no ve nada, pero el
panel sigue funcionando para dejar publicaciones listas antes de activarlo.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from ecommerce.domain.blog import (
    DatosPublicacion, EstadoPublicacion, generar_slug, slug_unico, validar_cantidad_fotos,
)
from ecommerce.domain.imagenes import ImagenProcesada


class _SinCambio:
    def __repr__(self):
        return 'SIN_CAMBIO'


# Al editar sin tocar la portada; None la quita
SIN_CAMBIO = _SinCambio()


@dataclass(frozen=True)
class PublicacionGuardada:
    """Lo que el caso de uso necesita saber de una publicación que ya existe."""

    slug: str
    # Se fija la primera vez que se publica; None si nunca salió de borrador
    fecha_publicacion: datetime | None
    tiene_portada: bool
    cantidad_fotos: int
    youtube_id: str = ''


@dataclass(frozen=True)
class PaginaBlog:
    ids: list[int]
    total: int


class RepositorioPublicaciones(ABC):
    """Puerto de salida: dónde se guardan las publicaciones y sus fotos."""

    @abstractmethod
    def obtener(self, publicacion_id: int) -> PublicacionGuardada | None:
        raise NotImplementedError

    @abstractmethod
    def slugs_parecidos(self, base: str, excepto_id: int | None) -> set[str]:
        """Slugs de otras publicaciones que empiezan con `base` (para no repetir uno)."""
        raise NotImplementedError

    @abstractmethod
    def guardar(self, publicacion_id: int | None, datos: DatosPublicacion, slug: str,
                fecha_publicacion: datetime | None, portada) -> int:
        """Crea (id None) o actualiza y devuelve el id. `portada`: ImagenProcesada, None (quitarla) o SIN_CAMBIO."""
        raise NotImplementedError

    @abstractmethod
    def eliminar(self, publicacion_id: int) -> bool:
        """Borra la publicación con su portada y sus fotos. False si no existe."""
        raise NotImplementedError

    @abstractmethod
    def agregar_fotos(self, publicacion_id: int, imagenes: list[ImagenProcesada]) -> list[int]:
        """Agrega las fotos al final de la galería y devuelve sus ids."""
        raise NotImplementedError

    @abstractmethod
    def quitar_foto(self, publicacion_id: int, foto_id: int) -> bool:
        """False si la foto no existe o es de otra publicación."""
        raise NotImplementedError

    @abstractmethod
    def publicadas(self, desde: int, cantidad: int) -> PaginaBlog:
        """Ids de las publicadas, las más recientes primero, y cuántas hay en total."""
        raise NotImplementedError

    @abstractmethod
    def id_publicada(self, slug: str) -> int | None:
        """None si no existe o es un borrador."""
        raise NotImplementedError


class BlogDesactivado(Exception):
    def __init__(self):
        super().__init__('Esta página no está disponible.')


class PublicacionNoEncontrada(Exception):
    def __init__(self):
        super().__init__('Publicación no encontrada.')


class FotoNoEncontrada(Exception):
    def __init__(self):
        super().__init__('Foto no encontrada.')


class VerBlog:
    """Lista pública del blog (RF-01.1): solo las publicadas y solo si el admin activó el blog."""

    def __init__(self, publicaciones: RepositorioPublicaciones, por_pagina: int = 9):
        self.publicaciones = publicaciones
        self.por_pagina = por_pagina

    def ejecutar(self, blog_activo: bool, pagina: int = 1) -> PaginaBlog:
        if not blog_activo:
            raise BlogDesactivado()
        pagina = max(pagina, 1)
        return self.publicaciones.publicadas((pagina - 1) * self.por_pagina, self.por_pagina)


class VerPublicacion:
    """Página pública de una publicación. Un borrador responde igual que una que no existe."""

    def __init__(self, publicaciones: RepositorioPublicaciones):
        self.publicaciones = publicaciones

    def ejecutar(self, slug: str, blog_activo: bool) -> int:
        if not blog_activo:
            raise BlogDesactivado()
        publicacion_id = self.publicaciones.id_publicada(slug)
        if publicacion_id is None:
            raise PublicacionNoEncontrada()
        return publicacion_id


class GuardarPublicacion:
    """El admin crea o edita una publicación, como borrador o publicada.

    El slug sigue al título mientras la publicación nunca se haya publicado; desde la primera vez que se publica
    queda fijo, para no romper los enlaces que ya se compartieron.
    """

    def __init__(self, publicaciones: RepositorioPublicaciones):
        self.publicaciones = publicaciones

    def ejecutar(self, publicacion_id: int | None, datos: dict, contenido_tiene_texto: bool,
                 ahora: datetime, portada=SIN_CAMBIO) -> int:
        actual = None
        if publicacion_id is not None:
            actual = self.publicaciones.obtener(publicacion_id)
            if actual is None:
                raise PublicacionNoEncontrada()

        tiene_portada = bool(actual and actual.tiene_portada) if portada is SIN_CAMBIO else portada is not None
        publicacion = DatosPublicacion.desde(datos, contenido_tiene_texto, tiene_portada)

        fecha_publicacion = actual.fecha_publicacion if actual else None
        if actual and fecha_publicacion is not None:
            slug = actual.slug
        else:
            ocupados = self.publicaciones.slugs_parecidos(generar_slug(publicacion.titulo), publicacion_id)
            slug = slug_unico(publicacion.titulo, ocupados)
        if publicacion.estado == EstadoPublicacion.PUBLICADA and fecha_publicacion is None:
            fecha_publicacion = ahora

        return self.publicaciones.guardar(publicacion_id, publicacion, slug, fecha_publicacion, portada)


class EliminarPublicacion:
    def __init__(self, publicaciones: RepositorioPublicaciones):
        self.publicaciones = publicaciones

    def ejecutar(self, publicacion_id: int) -> None:
        if not self.publicaciones.eliminar(publicacion_id):
            raise PublicacionNoEncontrada()


class AgregarFotos:
    """Galería de la publicación: hasta MAX_FOTOS_PUBLICACION fotos en total."""

    def __init__(self, publicaciones: RepositorioPublicaciones):
        self.publicaciones = publicaciones

    def ejecutar(self, publicacion_id: int, imagenes: list[ImagenProcesada]) -> list[int]:
        actual = self.publicaciones.obtener(publicacion_id)
        if actual is None:
            raise PublicacionNoEncontrada()
        validar_cantidad_fotos(actual.cantidad_fotos, len(imagenes))
        return self.publicaciones.agregar_fotos(publicacion_id, imagenes)


class QuitarFoto:
    def __init__(self, publicaciones: RepositorioPublicaciones):
        self.publicaciones = publicaciones

    def ejecutar(self, publicacion_id: int, foto_id: int) -> None:
        if not self.publicaciones.quitar_foto(publicacion_id, foto_id):
            raise FotoNoEncontrada()
