"""Vitrina de la landing (RF-01.1): los productos más vendidos, los últimos agregados y los destacados.

Los destacados son obras y proyectos (productos y publicaciones del blog) que el admin elige a mano para mostrarlos
en vez de "Más vendidos". Son opcionales: por defecto la vitrina sigue como antes (domain/destacados.py).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ecommerce.domain.destacados import (
    DestacadosInvalidos, ModoVitrina, TipoDestacado, ids_por_tipo, normalizar_destacados,
)


class VentasPorProducto(ABC):
    """Puerto de salida: unidades vendidas en pedidos pagados (PostgreSQL)."""

    @abstractmethod
    def mas_vendidos(self, limite: int) -> list[str]:
        """IDs de producto ordenados de más a menos unidades vendidas."""
        raise NotImplementedError


class CatalogoVitrina(ABC):
    """Puerto de salida: productos visibles para el público (MongoDB)."""

    @abstractmethod
    def visibles(self, ids: list[str]) -> list[str]:
        """De esos IDs, los que siguen activos y publicados, en el mismo orden."""
        raise NotImplementedError

    @abstractmethod
    def recientes(self, limite: int, excluir: list[str] = ()) -> list[str]:
        """IDs de los productos visibles más nuevos primero, sin los excluidos."""
        raise NotImplementedError

    @abstractmethod
    def existentes(self, ids: list[str]) -> list[str]:
        """De esos IDs, los productos que existen en el catálogo, publicados o no."""
        raise NotImplementedError


class PublicacionesVitrina(ABC):
    """Puerto de salida: publicaciones del blog (PostgreSQL)."""

    @abstractmethod
    def visibles(self, ids: list[str]) -> list[str]:
        """De esos IDs, las publicaciones publicadas (no borradores), en el mismo orden."""
        raise NotImplementedError

    @abstractmethod
    def existentes(self, ids: list[str]) -> list[str]:
        """De esos IDs, las publicaciones que existen, publicadas o en borrador."""
        raise NotImplementedError


@dataclass(frozen=True)
class Vitrina:
    mas_vendidos: list[str]
    recientes: list[str]
    # [{'tipo': 'PRODUCTO' | 'PUBLICACION', 'id': '...'}] en el orden que eligió el admin; vacía = "Más vendidos"
    destacados: list[dict] = field(default_factory=list)


class SeleccionarVitrina:
    """Arma las secciones de la landing.

    - Destacados: con el modo DESTACADOS, los que eligió el admin y se pueden ver. Un producto despublicado o una
      publicación en borrador no aparecen, y las publicaciones tampoco si el blog está apagado (sus enlaces no
      llevarían a nada; decidido el 2026-11-08). Si no queda ninguno, la landing vuelve a "Más vendidos".
    - Más vendidos: por unidades en pedidos pagados. Si no alcanzan (una tienda nueva no tiene ventas), se
      completa con otros productos visibles, primero los que no aparecen en "últimos agregados" (decidido
      el 2026-10-18). No se calcula si se muestran los destacados, que van en su lugar.
    - Últimos agregados: los productos visibles más nuevos; no cambian con los destacados.
    """

    def __init__(self, ventas: VentasPorProducto, catalogo: CatalogoVitrina, cantidad: int = 4,
                 publicaciones: PublicacionesVitrina | None = None):
        self.ventas = ventas
        self.catalogo = catalogo
        self.publicaciones = publicaciones
        self.cantidad = cantidad

    def ejecutar(self, modo=ModoVitrina.MAS_VENDIDOS, destacados=(), blog_activo: bool = False) -> Vitrina:
        recientes = self.catalogo.recientes(self.cantidad)
        elegidos = self._destacados_visibles(modo, destacados, blog_activo)
        if elegidos:
            return Vitrina(mas_vendidos=[], recientes=recientes, destacados=elegidos)
        return Vitrina(mas_vendidos=self._mas_vendidos(recientes), recientes=recientes)

    def _destacados_visibles(self, modo, destacados, blog_activo):
        if modo != ModoVitrina.DESTACADOS or not destacados:
            return []
        try:
            destacados = normalizar_destacados(list(destacados))
        except DestacadosInvalidos:
            # Lo guardado ya se validó; si igual no tiene la forma esperada, la landing no se rompe
            return []

        visibles = {
            TipoDestacado.PRODUCTO: set(self.catalogo.visibles(ids_por_tipo(destacados, TipoDestacado.PRODUCTO))),
            TipoDestacado.PUBLICACION: set(),
        }
        ids_publicaciones = ids_por_tipo(destacados, TipoDestacado.PUBLICACION)
        if blog_activo and ids_publicaciones and self.publicaciones is not None:
            visibles[TipoDestacado.PUBLICACION] = set(self.publicaciones.visibles(ids_publicaciones))
        return [destacado for destacado in destacados if destacado['id'] in visibles[destacado['tipo']]]

    def _mas_vendidos(self, recientes):
        # Se piden más de los necesarios: algunos vendidos pueden estar despublicados o borrados
        vendidos = self.catalogo.visibles(self.ventas.mas_vendidos(self.cantidad * 3))[:self.cantidad]

        faltan = self.cantidad - len(vendidos)
        if faltan > 0:
            vendidos += self.catalogo.recientes(faltan, excluir=vendidos + recientes)
        faltan = self.cantidad - len(vendidos)
        if faltan > 0:
            # Catálogo chico: se repiten productos de "últimos agregados" antes que dejar la sección corta
            vendidos += self.catalogo.recientes(faltan, excluir=vendidos)
        return vendidos


class ValidarDestacados:
    """La selección que guarda el admin: hasta 8, sin repetir y solo productos y publicaciones que existen.

    Se aceptan productos sin publicar y publicaciones en borrador: el admin puede elegirlos antes de publicarlos,
    y la landing no los muestra mientras tanto.
    """

    def __init__(self, catalogo: CatalogoVitrina, publicaciones: PublicacionesVitrina):
        self.catalogo = catalogo
        self.publicaciones = publicaciones

    def ejecutar(self, lista) -> list[dict]:
        destacados = normalizar_destacados(lista)
        for tipo, puerto in ((TipoDestacado.PRODUCTO, self.catalogo), (TipoDestacado.PUBLICACION, self.publicaciones)):
            ids = ids_por_tipo(destacados, tipo)
            if ids and set(puerto.existentes(ids)) != set(ids):
                raise DestacadosInvalidos(
                    'Uno de los destacados ya no existe. Quítalo de la lista y vuelve a guardar.')
        return destacados
