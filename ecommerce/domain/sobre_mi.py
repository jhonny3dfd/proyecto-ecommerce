"""Reglas de la página Sobre mí, independientes de Django y de la persistencia."""

NOMBRE_SOBRE_MI_POR_DEFECTO = 'Sobre mí'
LARGO_NOMBRE_SOBRE_MI = 30
# Hasta 2 fotos junto a la biografía (pedido de un cliente, opcionales); el texto alternativo describe cada una
MAX_FOTOS_SOBRE_MI = 2
LARGO_ALT_FOTO_SOBRE_MI = 150


class SobreMiNoDisponible(ValueError):
    def __init__(self):
        super().__init__('La página Sobre mí no está disponible.')


class NombreSobreMiInvalido(ValueError):
    def __init__(self):
        super().__init__(f'El nombre no puede superar los {LARGO_NOMBRE_SOBRE_MI} caracteres.')


class ProyectosSobreMiInvalidos(ValueError):
    """La selección de proyectos contiene IDs con un formato inválido."""


def exigir_sobre_mi_disponible(activo) -> None:
    if not activo:
        raise SobreMiNoDisponible()


def muestra_proyectos_sobre_mi(blog_activo) -> bool:
    """RF-01.7: los proyectos son publicaciones del blog; con el blog apagado no se muestran, porque sus enlaces
    llevarían a una página que no existe. Es la misma regla de los Destacados (application/vitrina.py)."""
    return bool(blog_activo)


def normalizar_nombre_sobre_mi(valor: str) -> str:
    nombre = ' '.join(valor.split())
    if not nombre:
        return NOMBRE_SOBRE_MI_POR_DEFECTO
    if len(nombre) > LARGO_NOMBRE_SOBRE_MI:
        raise NombreSobreMiInvalido()
    return nombre


def construir_contacto_sobre_mi(telefono=None, correo=None, instagram=None) -> dict:
    contacto = {}
    if telefono:
        contacto['telefono'] = telefono
    if correo:
        contacto['correo'] = correo
    if instagram:
        contacto['instagram'] = instagram
    return contacto


def fotos_sobre_mi(fotos) -> list[dict]:
    """Las fotos subidas, en su orden (una sola si falta la otra). `fotos`: pares (url o None, texto alternativo)."""
    return [{'url': url, 'alt': (alt or '').strip()} for url, alt in fotos if url][:MAX_FOTOS_SOBRE_MI]


def validar_ids_proyectos_sobre_mi(ids) -> list:
    if not isinstance(ids, list):
        raise ProyectosSobreMiInvalidos('Debes enviar una lista de IDs.')
    if any(type(pk) is not int or pk <= 0 for pk in ids):
        raise ProyectosSobreMiInvalidos('Todos los IDs deben ser números enteros positivos.')
    if len(ids) != len(set(ids)):
        raise ProyectosSobreMiInvalidos('No puedes seleccionar una publicación más de una vez.')
    return ids
