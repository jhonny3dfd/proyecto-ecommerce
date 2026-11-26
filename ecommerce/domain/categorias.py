"""Renombrar o unir categorías del catálogo (RF-03.2, RF-01.3). Python puro.

Una categoría no existe aparte: es el texto `categoria` de cada producto. Renombrarla cambia ese texto en todos sus
productos y en lo que la nombra (el orden de categorías del catálogo y los planes de suscripción). Si el nombre nuevo
ya es el de otra categoría, las dos quedan unidas; así también se "elimina" una categoría, pasando sus productos a otra.
"""

from dataclasses import dataclass

from .catalogo import LARGO_NOMBRE_CATEGORIA


class CategoriaInvalida(ValueError):
    """El nombre nuevo no sirve o el cambio no tiene efecto. El mensaje se le muestra al admin."""


def clave(nombre: str) -> str:
    """Para comparar sin distinguir mayúsculas ("Café" y "café" son la misma para unir)."""
    return ' '.join(str(nombre or '').split()).casefold()


def normalizar_nombre_categoria(valor) -> str:
    """Sin espacios sobrantes (tampoco dobles), de 1 a 100 caracteres."""
    nombre = ' '.join(str(valor or '').split()) if isinstance(valor, str) else ''
    if not nombre:
        raise CategoriaInvalida('Escribe el nombre nuevo de la categoría.')
    if len(nombre) > LARGO_NOMBRE_CATEGORIA:
        raise CategoriaInvalida(f'El nombre puede tener hasta {LARGO_NOMBRE_CATEGORIA} caracteres.')
    return nombre


@dataclass(frozen=True)
class Renombre:
    """Qué categoría cambia (`desde`, tal como está escrita en sus productos) y cómo queda (`hacia`)."""

    desde: str
    hacia: str
    # Hacia es otra categoría que ya existía: sus productos quedan juntos
    une: bool


def planificar_renombre(desde: str, nuevo, existentes: list[str]) -> Renombre:
    """Decide el nombre final. Si coincide (sin distinguir mayúsculas) con otra categoría existente, se usa esa, tal
    como está escrita, y las dos se unen. Si es la misma con otras mayúsculas o espacios, solo se corrige su escritura.
    """
    hacia = normalizar_nombre_categoria(nuevo)
    if hacia == desde:
        raise CategoriaInvalida('Escribe un nombre distinto al actual.')
    otras = [nombre for nombre in existentes if nombre != desde and clave(nombre) == clave(hacia)]
    if otras:
        # Si hay varias escritas distinto ("Café" y "CAFÉ"), se usa la primera; las demás se unen después igual
        return Renombre(desde, otras[0], une=True)
    return Renombre(desde, hacia, une=False)


def renombrar_en_orden(orden: list[str], renombre: Renombre) -> list[str]:
    """El orden de categorías priorizadas guarda los nombres exactos: la renombrada queda en su lugar, y al unir dos
    priorizadas queda la que estaba primero."""
    resultado = []
    for nombre in orden:
        nuevo = renombre.hacia if nombre == renombre.desde else nombre
        if nuevo not in resultado:
            resultado.append(nuevo)
    return resultado


def renombrar_en_plan(categorias: list[str], renombre: Renombre, restantes: list[str]) -> list[str]:
    """Un plan admite categorías sin distinguir mayúsculas. La que nombraba a la renombrada pasa a nombrar la nueva;
    se conserva también si todavía nombra a otra categoría que sigue existiendo ("Café" y "café" eran dos)."""
    if not any(clave(nombre) == clave(renombre.desde) for nombre in categorias):
        return list(categorias)
    siguen = {clave(nombre) for nombre in restantes}
    resultado = []
    for nombre in categorias:
        if clave(nombre) != clave(renombre.desde) or clave(nombre) in siguen:
            resultado.append(nombre)
    if all(clave(nombre) != clave(renombre.hacia) for nombre in resultado):
        resultado.append(renombre.hacia)
    return resultado
