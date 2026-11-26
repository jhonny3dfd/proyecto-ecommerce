"""Reglas de ordenamiento del catálogo, independientes de Django."""

LARGO_NOMBRE_CATEGORIA = 100
LARGO_ETIQUETA_PRODUCTO = 20
# Se guardan roles de la paleta, nunca colores libres; al cambiar el tema se conservan.
COLORES_ETIQUETA_PRODUCTO = ('primary', 'secondary', 'accent', 'text')


class OrdenCategoriasInvalido(ValueError):
    """El orden de categorías que eligió el admin no cumple las reglas."""


def normalizar_orden_categorias(valor) -> list[str]:
    """Las categorías priorizadas, en orden: textos de 1 a 100 caracteres, sin espacios sobrantes ni repetidos."""
    if not isinstance(valor, list):
        raise OrdenCategoriasInvalido('El orden de categorías debe ser una lista.')
    resultado = []
    for nombre in valor:
        if not isinstance(nombre, str) or not nombre.strip() or len(nombre) > LARGO_NOMBRE_CATEGORIA:
            raise OrdenCategoriasInvalido(
                f'Cada categoría debe tener entre 1 y {LARGO_NOMBRE_CATEGORIA} caracteres.')
        nombre = nombre.strip()
        if nombre in resultado:
            raise OrdenCategoriasInvalido('Las categorías no pueden repetirse.')
        resultado.append(nombre)
    return resultado


def ordenar_categorias(categorias, prioridades):
    """Primero las priorizadas que existen, en su orden; después las demás, en orden alfabético."""
    disponibles = set(categorias)
    primeras = list(dict.fromkeys(nombre for nombre in prioridades if nombre in disponibles))
    return primeras + sorted(disponibles - set(primeras))


# Reglas de Colección Privada y Versión a la Venta (SCRUM-197)

class ColeccionPrivadaInvalida(ValueError):
    """Reglas de negocio de colección privada y versión a la venta."""


def validar_version_a_la_venta(
    producto_id: str | None,
    version_id: str | None,
    target_existe: bool,
    target_es_coleccion_privada: bool,
) -> None:
    """Valida la asignación de una versión a la venta para una obra."""
    if not version_id:
        return
    version_str = str(version_id).strip()
    if producto_id and str(producto_id).strip() == version_str:
        raise ColeccionPrivadaInvalida('Una obra no puede ser su propia versión a la venta.')
    if not target_existe:
        raise ColeccionPrivadaInvalida('El producto seleccionado como versión a la venta no existe.')
    if target_es_coleccion_privada:
        raise ColeccionPrivadaInvalida('No se puede enlazar a otra obra que es colección privada.')


def validar_obra_no_es_version_de_otra(
    producto_id: str | None,
    coleccion_privada: bool,
    nombre_referenciador: str | None,
) -> None:
    """Una obra no puede marcarse como colección privada si es la versión a la venta de otro producto."""
    if coleccion_privada and nombre_referenciador:
        raise ColeccionPrivadaInvalida(
            f'No se puede marcar como colección privada porque está asignada como versión a la venta de "{nombre_referenciador}".'
        )

def limpiar_colecciones(colecciones_brutas):
    """
    Limpia, normaliza y elimina duplicados de la lista de colecciones
    ingresadas en el formulario o recibidas por la API (sin distinguir mayúsculas/minúsculas).
    """
    if not colecciones_brutas:
        return []

    vistas = set()
    resultado = []

    for col in colecciones_brutas:
        if isinstance(col, str):
            col_limpia = col.strip()
            if col_limpia:
                col_key = col_limpia.lower()
                if col_key not in vistas:
                    vistas.add(col_key)
                    resultado.append(col_limpia)

    return resultado

