"""Renombrar o unir categorías del catálogo (RF-03.2, RF-01.3): caso de uso y puertos.

Los productos viven en MongoDB y lo que nombra a una categoría (orden del catálogo, planes de suscripción) en
PostgreSQL. No hay una transacción común: primero se cambian las referencias y después los productos. Si falla a medias,
la categoría sigue en sus productos y basta con volver a renombrarla: las referencias ya cambiadas quedan igual.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ecommerce.domain.categorias import (
    CategoriaInvalida, Renombre, planificar_renombre, renombrar_en_orden, renombrar_en_plan,
)


@dataclass(frozen=True)
class CategoriaCatalogo:
    nombre: str
    # Todos sus productos, publicados o en borrador
    productos: int
    publicados: int


class CategoriasCatalogo(ABC):
    """Las categorías tal como están en los productos (MongoDB)."""

    @abstractmethod
    def listar(self) -> list[CategoriaCatalogo]:
        raise NotImplementedError

    @abstractmethod
    def renombrar(self, desde: str, hacia: str) -> int:
        """Cambia la categoría de todos los productos que la tienen; devuelve cuántos cambiaron."""
        raise NotImplementedError


class ReferenciasCategorias(ABC):
    """Lo que nombra a una categoría fuera de los productos (PostgreSQL)."""

    @abstractmethod
    def orden(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def guardar_orden(self, orden: list[str]) -> None:
        raise NotImplementedError

    @abstractmethod
    def categorias_de_planes(self) -> dict[int, list[str]]:
        """Las categorías elegibles de cada plan de suscripción, por id."""
        raise NotImplementedError

    @abstractmethod
    def guardar_categorias_de_plan(self, plan_id: int, categorias: list[str]) -> None:
        raise NotImplementedError


class CategoriaNoEncontrada(CategoriaInvalida):
    def __init__(self):
        super().__init__('Esa categoría ya no existe. Recarga la página.')


@dataclass(frozen=True)
class CategoriaRenombrada:
    desde: str
    hacia: str
    une: bool
    productos: int


class RenombrarCategoria:
    """El admin renombra una categoría; si el nombre nuevo es el de otra, las une."""

    def __init__(self, categorias: CategoriasCatalogo, referencias: ReferenciasCategorias):
        self.categorias = categorias
        self.referencias = referencias

    def ejecutar(self, desde: str, nuevo) -> CategoriaRenombrada:
        existentes = [categoria.nombre for categoria in self.categorias.listar()]
        if desde not in existentes:
            raise CategoriaNoEncontrada()
        renombre = planificar_renombre(desde, nuevo, existentes)
        restantes = [nombre for nombre in existentes if nombre != renombre.desde] + [renombre.hacia]
        self._renombrar_referencias(renombre, restantes)
        productos = self.categorias.renombrar(renombre.desde, renombre.hacia)
        return CategoriaRenombrada(renombre.desde, renombre.hacia, renombre.une, productos)

    def _renombrar_referencias(self, renombre: Renombre, restantes: list[str]) -> None:
        orden = self.referencias.orden()
        nuevo_orden = renombrar_en_orden(orden, renombre)
        if nuevo_orden != orden:
            self.referencias.guardar_orden(nuevo_orden)
        for plan_id, categorias in self.referencias.categorias_de_planes().items():
            nuevas = renombrar_en_plan(categorias, renombre, restantes)
            if nuevas != categorias:
                self.referencias.guardar_categorias_de_plan(plan_id, nuevas)
