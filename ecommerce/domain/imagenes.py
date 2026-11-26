"""Types and ports for product galleries; independent of Django and MongoDB."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ImagenProcesada:
    contenido: bytes
    extension: str


class GaleriaEnConflicto(Exception):
    """The gallery changed after it was read; the caller must reload it."""


class LimiteGaleriaExcedido(Exception):
    pass


class AlmacenamientoImagenNoDisponible(Exception):
    def __init__(self, clave=None):
        super().__init__('El almacenamiento de imágenes no está disponible.')
        self.clave = clave


class AlmacenImagenes(Protocol):
    def guardar(self, producto_id: str, imagen: ImagenProcesada) -> str: ...

    def borrar(self, clave: str) -> None: ...


class RepositorioGaleria(Protocol):
    def asociar(self, producto_id: str, anteriores: list[str], nuevas: list[str]) -> list[str]: ...

    def desasociar(self, producto_id: str, anteriores: list[str], clave: str) -> list[str]: ...

    def programar_borrado(self, claves: list[str]) -> None: ...

    def esta_asociada(self, clave: str) -> bool: ...

    def completar_borrado(self, clave: str) -> None: ...
