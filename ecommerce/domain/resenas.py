"""Reseñas de la tienda y de sus productos: las deja quien recibió su pedido y el admin decide cuáles se publican.

Independiente de Django. Una reseña por pedido: estrellas para la tienda (obligatorias) y para cada producto del
pedido (opcionales). Solo lo aprobado se muestra y cuenta en el promedio.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from .ventas import EstadoPedido

ESTRELLAS_MINIMAS = 1
ESTRELLAS_MAXIMAS = 5
LARGO_COMENTARIO = 1000
LARGO_NOMBRE_PUBLICO = 40
# Desde que el pedido se marca como Entregado
DIAS_VIGENCIA_ENLACE = 60


class EstadoResena(StrEnum):
    PENDIENTE = 'PENDIENTE'
    APROBADA = 'APROBADA'
    OCULTA = 'OCULTA'


ETIQUETAS_ESTADO_RESENA = {
    EstadoResena.PENDIENTE: 'Pendiente',
    EstadoResena.APROBADA: 'Aprobada',
    EstadoResena.OCULTA: 'Oculta',
}

# El admin puede cambiar de opinión, pero una reseña ya revisada no vuelve a quedar pendiente
TRANSICIONES_RESENA = {
    EstadoResena.PENDIENTE: {EstadoResena.APROBADA, EstadoResena.OCULTA},
    EstadoResena.APROBADA: {EstadoResena.OCULTA},
    EstadoResena.OCULTA: {EstadoResena.APROBADA},
}


class ResenaInvalida(ValueError):
    """Errores por campo; los de cada producto van anidados en 'productos', por id del producto."""

    def __init__(self, errores: dict):
        self.errores = errores
        super().__init__('; '.join(f'{campo}: {error}' for campo, error in errores.items()))


class PedidoNoEntregado(Exception):
    def __init__(self):
        super().__init__('Podrás dejar tu reseña cuando recibas el pedido.')


class ResenaYaEnviada(Exception):
    def __init__(self):
        super().__init__('Ya dejaste una reseña para este pedido. ¡Gracias!')


class PlazoResenaVencido(Exception):
    def __init__(self):
        super().__init__(f'El plazo para dejar la reseña de este pedido ({DIAS_VIGENCIA_ENLACE} días) ya venció.')


class ModeracionNoPermitida(Exception):
    def __init__(self, actual: EstadoResena, nuevo: EstadoResena):
        super().__init__(
            f'Una reseña {ETIQUETAS_ESTADO_RESENA[actual].lower()} no puede quedar como '
            f'{ETIQUETAS_ESTADO_RESENA[nuevo].lower()}.')


@dataclass(frozen=True)
class ProductoDelPedido:
    producto_id: str
    nombre: str


@dataclass(frozen=True)
class CalificacionProducto:
    producto_id: str
    # Copiado del pedido, para que la reseña se lea igual aunque el producto cambie de nombre
    producto_nombre: str
    estrellas: int
    comentario: str = ''


def _error_estrellas(valor) -> str | None:
    if isinstance(valor, int) and not isinstance(valor, bool) and ESTRELLAS_MINIMAS <= valor <= ESTRELLAS_MAXIMAS:
        return None
    return f'Elige de {ESTRELLAS_MINIMAS} a {ESTRELLAS_MAXIMAS} estrellas.'


def _comentario(valor) -> str:
    return str(valor or '').strip()


ERROR_LARGO_COMENTARIO = f'El comentario puede tener hasta {LARGO_COMENTARIO} caracteres.'


@dataclass(frozen=True)
class DatosResena:
    estrellas_tienda: int
    comentario_tienda: str
    nombre_publico: str
    # En el orden del pedido; solo los que el comprador calificó
    productos: tuple[CalificacionProducto, ...] = ()

    @classmethod
    def desde(cls, datos: dict, productos_del_pedido: list[ProductoDelPedido]) -> 'DatosResena':
        """`productos_del_pedido` lo resuelve quien llama a partir de las líneas del pedido."""
        errores = {}
        estrellas = datos.get('estrellas')
        if error := _error_estrellas(estrellas):
            errores['estrellas'] = error
        comentario = _comentario(datos.get('comentario'))
        if len(comentario) > LARGO_COMENTARIO:
            errores['comentario'] = ERROR_LARGO_COMENTARIO

        nombre = ' '.join(str(datos.get('nombre_publico') or '').split())
        if not nombre:
            errores['nombre_publico'] = 'Escribe el nombre que quieres que se vea con tu reseña.'
        elif len(nombre) > LARGO_NOMBRE_PUBLICO:
            errores['nombre_publico'] = f'El nombre puede tener hasta {LARGO_NOMBRE_PUBLICO} caracteres.'
        elif '@' in nombre:
            # El correo del comprador nunca se publica, ni siquiera si lo escribe como nombre
            errores['nombre_publico'] = 'Usa tu nombre, no tu correo.'

        if datos.get('acepta_publicacion') is not True:
            errores['acepta_publicacion'] = 'Para enviar la reseña, acepta que se publique en la tienda.'

        calificaciones, errores_productos = cls._calificaciones(datos.get('productos') or [], productos_del_pedido)
        if errores_productos:
            errores['productos'] = errores_productos

        if errores:
            raise ResenaInvalida(errores)
        return cls(estrellas_tienda=estrellas, comentario_tienda=comentario, nombre_publico=nombre,
                   productos=calificaciones)

    @staticmethod
    def _calificaciones(enviadas: list, productos_del_pedido: list[ProductoDelPedido]):
        del_pedido = {producto.producto_id: producto for producto in productos_del_pedido}
        por_producto, errores = {}, {}
        for item in enviadas:
            item = item if isinstance(item, dict) else {}
            producto_id = str(item.get('producto_id') or '').strip()
            estrellas = item.get('estrellas')
            comentario = _comentario(item.get('comentario'))
            if producto_id not in del_pedido:
                errores[producto_id] = 'Ese producto no es parte de tu pedido.'
            elif producto_id in por_producto:
                errores[producto_id] = 'Este producto viene repetido.'
            elif estrellas is None and not comentario:
                # Calificar cada producto es opcional
                continue
            elif error := _error_estrellas(estrellas):
                errores[producto_id] = error if estrellas is not None else 'Para comentar un producto, califícalo.'
            elif len(comentario) > LARGO_COMENTARIO:
                errores[producto_id] = ERROR_LARGO_COMENTARIO
            else:
                por_producto[producto_id] = CalificacionProducto(
                    producto_id=producto_id, producto_nombre=del_pedido[producto_id].nombre,
                    estrellas=estrellas, comentario=comentario)
        orden = [producto_id for producto_id in del_pedido if producto_id in por_producto]
        return tuple(por_producto[producto_id] for producto_id in orden), errores


def validar_pedido_para_resena(estado, ya_tiene_resena: bool) -> None:
    """Solo quien recibió su pedido puede reseñarlo, y una sola vez."""
    if ya_tiene_resena:
        raise ResenaYaEnviada()
    if estado != EstadoPedido.ENTREGADO:
        raise PedidoNoEntregado()


def validar_plazo_resena(entregado_en: datetime | None, ahora: datetime) -> None:
    """Sin fecha de entrega (pedidos entregados antes de registrarla) no se puede saber si está en plazo."""
    if entregado_en is None or ahora - entregado_en > timedelta(days=DIAS_VIGENCIA_ENLACE):
        raise PlazoResenaVencido()


def puede_resenarse(estado, entregado_en: datetime | None, ya_tiene_resena: bool, ahora: datetime) -> bool:
    """Para ofrecer "Dejar reseña" en Mis pedidos: entregado, sin reseña y dentro del plazo."""
    try:
        validar_pedido_para_resena(estado, ya_tiene_resena)
        validar_plazo_resena(entregado_en, ahora)
    except (PedidoNoEntregado, ResenaYaEnviada, PlazoResenaVencido):
        return False
    return True


def validar_moderacion(actual, nuevo) -> EstadoResena:
    actual, nuevo = EstadoResena(actual), EstadoResena(nuevo)
    if nuevo not in TRANSICIONES_RESENA[actual]:
        raise ModeracionNoPermitida(actual, nuevo)
    return nuevo


def nombre_publico_sugerido(nombre_completo: str) -> str:
    """'Ana Pérez Soto' -> 'Ana P.': se reconoce a la persona sin publicar su nombre completo."""
    partes = str(nombre_completo or '').split()
    if not partes:
        return ''
    sugerido = partes[0] if len(partes) == 1 else f'{partes[0]} {partes[1][0].upper()}.'
    return sugerido[:LARGO_NOMBRE_PUBLICO]


def promedio(estrellas: list[int]) -> float | None:
    """Con un decimal, redondeando hacia arriba en la mitad (4,25 -> 4,3). None si aún no hay calificaciones."""
    if not estrellas:
        return None
    exacto = Decimal(sum(estrellas)) / Decimal(len(estrellas))
    return float(exacto.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))
