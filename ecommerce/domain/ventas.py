"""Reglas para armar un pedido, independientes de HTTP, Django y la base de catálogo."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
import re

from .logistica import MedidasEnvio


class ErrorPedido(Exception):
    """El pedido no se puede crear tal como viene."""


class PedidoVacio(ErrorPedido):
    def __init__(self):
        super().__init__('El carrito está vacío.')


class CantidadInvalida(ErrorPedido):
    def __init__(self, sku):
        self.sku = sku
        super().__init__(f'La cantidad de {sku} debe ser al menos 1.')


class VarianteNoDisponible(ErrorPedido):
    """La variante no existe, o su producto está inactivo o sin publicar."""

    def __init__(self, sku):
        self.sku = sku
        super().__init__(f'El producto {sku} ya no está disponible.')


class StockInsuficiente(ErrorPedido):
    def __init__(self, sku, disponible):
        self.sku = sku
        self.disponible = disponible
        super().__init__(f'Stock insuficiente para {sku}. Quedan {disponible} unidades disponibles.')


class SubtotalDesactualizado(ErrorPedido):
    """El subtotal del comprador no coincide con los precios vigentes del catálogo."""

    def __init__(self, subtotal_vigente, lineas=()):
        self.subtotal_vigente = subtotal_vigente
        self.lineas = list(lineas)
        super().__init__('Los precios de tu carrito cambiaron. Revisa el nuevo total antes de pagar.')


class TelefonoInvalido(ErrorPedido):
    def __init__(self):
        super().__init__('Ingresa un teléfono chileno de 9 dígitos, por ejemplo +56 9 1234 5678.')


def normalizar_telefono_chile(texto: str) -> str:
    """RF-02.3: teléfono de contacto del destinatario. Los envíos son dentro de Chile.

    Acepta 9 dígitos con o sin +56 (espacios, guiones y paréntesis se ignoran) y devuelve +56XXXXXXXXX.
    """
    digitos = ''.join(c for c in str(texto or '') if c.isdigit())
    if len(digitos) == 11 and digitos.startswith('56'):
        digitos = digitos[2:]
    if len(digitos) != 9 or digitos.startswith('0'):
        raise TelefonoInvalido()
    return f'+56{digitos}'


class NombreInvalido(ErrorPedido):
    def __init__(self):
        super().__init__('Escribe un nombre con letras (puede llevar espacios, guiones, apóstrofos o puntos).')


# Letras de cualquier idioma (con tildes y ñ), separadas por espacios, guiones, apóstrofos o puntos
_NOMBRE_PERSONA = re.compile(r"[^\W\d_]+(?:[\s'’.\-]+[^\W\d_]*)*")


def normalizar_nombre_persona(texto: str) -> str:
    """Nombre o apellido de una persona: 'María José', "O'Higgins" o 'Juan P.'; sin números ni símbolos.

    Devuelve el texto con los espacios repetidos juntados; NombreInvalido si no sirve.
    """
    nombre = ' '.join(str(texto or '').split())
    if not _NOMBRE_PERSONA.fullmatch(nombre):
        raise NombreInvalido()
    return nombre


@dataclass(frozen=True)
class ItemSolicitado:
    producto_id: str
    sku: str
    cantidad: int

    def __post_init__(self):
        if self.cantidad < 1:
            raise CantidadInvalida(self.sku)


@dataclass(frozen=True)
class VarianteCatalogo:
    nombre: str
    precio: Decimal
    stock: int
    # El producto padre está activo y publicado
    disponible: bool
    # Para armar el paquete del envío (RF-02.3)
    medidas: MedidasEnvio = MedidasEnvio()


@dataclass(frozen=True)
class LineaPedido:
    producto_id: str
    sku: str
    nombre: str
    precio_unitario: Decimal
    cantidad: int

    @property
    def total(self) -> Decimal:
        return self.precio_unitario * self.cantidad


def armar_linea(item: ItemSolicitado, variante: VarianteCatalogo | None) -> LineaPedido:
    """RN-03 / RF-03.4: no se vende una variante sin stock; el control es por SKU, no por producto."""
    if variante is None or not variante.disponible:
        raise VarianteNoDisponible(item.sku)
    if item.cantidad > variante.stock:
        raise StockInsuficiente(item.sku, max(variante.stock, 0))
    return LineaPedido(
        producto_id=item.producto_id, sku=item.sku, nombre=variante.nombre,
        precio_unitario=variante.precio, cantidad=item.cantidad,
    )


class ProblemaLinea(StrEnum):
    NO_DISPONIBLE = 'NO_DISPONIBLE'
    SIN_STOCK = 'SIN_STOCK'
    STOCK_INSUFICIENTE = 'STOCK_INSUFICIENTE'


@dataclass(frozen=True)
class LineaRevisada:
    """Una línea del carrito comparada con el catálogo vigente, antes de crear la orden."""

    producto_id: str
    sku: str
    cantidad: int
    # Unidades que se pueden comprar ahora (0 si la variante no se vende)
    disponible: int
    nombre: str | None = None
    precio: Decimal | None = None
    problema: ProblemaLinea | None = None

    @property
    def mensaje(self) -> str | None:
        if self.problema == ProblemaLinea.NO_DISPONIBLE:
            return f'El producto {self.sku} ya no está disponible.'
        if self.problema == ProblemaLinea.SIN_STOCK:
            return f'{self.nombre} está agotado.'
        if self.problema == ProblemaLinea.STOCK_INSUFICIENTE:
            return f'De {self.nombre} solo quedan {self.disponible} unidades.'
        return None


def revisar_linea(item: ItemSolicitado, variante: VarianteCatalogo | None) -> LineaRevisada:
    """RN-03: misma regla que `armar_linea`, pero informa el problema en vez de rechazar el pedido."""
    if variante is None or not variante.disponible:
        return LineaRevisada(item.producto_id, item.sku, item.cantidad, disponible=0,
                             problema=ProblemaLinea.NO_DISPONIBLE)
    disponible = max(variante.stock, 0)
    problema = None
    if disponible == 0:
        problema = ProblemaLinea.SIN_STOCK
    elif item.cantidad > disponible:
        problema = ProblemaLinea.STOCK_INSUFICIENTE
    return LineaRevisada(item.producto_id, item.sku, item.cantidad, disponible,
                         variante.nombre, variante.precio, problema)


class EstadoPedido(StrEnum):
    PENDIENTE = 'PENDIENTE'
    PAGADO = 'PAGADO'
    EN_PREPARACION = 'EN_PREPARACION'
    ENVIADO = 'ENVIADO'
    ENTREGADO = 'ENTREGADO'
    CANCELADO = 'CANCELADO'

    @property
    def etiqueta(self):
        return ETIQUETAS_ESTADO[self]


ETIQUETAS_ESTADO = {
    EstadoPedido.PENDIENTE: 'Pendiente',
    EstadoPedido.PAGADO: 'Pagado',
    EstadoPedido.EN_PREPARACION: 'En Preparación',
    EstadoPedido.ENVIADO: 'Despachado',
    EstadoPedido.ENTREGADO: 'Entregado',
    EstadoPedido.CANCELADO: 'Cancelado',
}

@dataclass(frozen=True)
class PlazoPago:
    """Plazo para pagar una transferencia (decidido el 2026-10-13; desde el 2026-10-19 lo elige cada tienda).

    Vencido, la orden se cancela. A la mitad del plazo se le recuerda el pago al comprador, una sola vez.
    """

    vence: datetime
    recordar: datetime


def plazo_pago(creada: datetime, plazo: timedelta) -> PlazoPago:
    """Se fija al crear la orden: si la tienda cambia el plazo después, los pedidos que ya existen conservan el suyo."""
    return PlazoPago(vence=creada + plazo, recordar=creada + plazo / 2)


# Estados en los que el pago ya se confirmó
ESTADOS_PAGADOS = frozenset({
    EstadoPedido.PAGADO, EstadoPedido.EN_PREPARACION, EstadoPedido.ENVIADO, EstadoPedido.ENTREGADO,
})

# Máquina de estados del pedido (RF-03.3): cualquier transición que no esté aquí se rechaza
TRANSICIONES_PERMITIDAS = {
    EstadoPedido.PENDIENTE: {EstadoPedido.PAGADO, EstadoPedido.CANCELADO},
    EstadoPedido.PAGADO: {EstadoPedido.EN_PREPARACION, EstadoPedido.CANCELADO},
    EstadoPedido.EN_PREPARACION: {EstadoPedido.ENVIADO, EstadoPedido.CANCELADO},
    EstadoPedido.ENVIADO: {EstadoPedido.ENTREGADO},
    EstadoPedido.ENTREGADO: set(),
    EstadoPedido.CANCELADO: set(),
}


class TransicionNoPermitida(Exception):
    def __init__(self, actual, nuevo):
        self.actual = actual
        self.nuevo = nuevo
        super().__init__(
            f'Un pedido {_etiqueta(actual)} no puede pasar a {_etiqueta(nuevo)}.')


def _etiqueta(estado):
    try:
        return EstadoPedido(estado).etiqueta
    except ValueError:
        return str(estado)


def transiciones_desde(estado) -> list[EstadoPedido]:
    """Estados a los que puede pasar un pedido, en el orden del flujo (vacío si es final)."""
    try:
        permitidas = TRANSICIONES_PERMITIDAS[EstadoPedido(estado)]
    except ValueError:
        return []
    return [siguiente for siguiente in EstadoPedido if siguiente in permitidas]


def validar_transicion(actual, nuevo) -> EstadoPedido:
    """RF-03.3: devuelve el nuevo estado si la transición está permitida."""
    try:
        actual, nuevo = EstadoPedido(actual), EstadoPedido(nuevo)
    except ValueError:
        raise TransicionNoPermitida(actual, nuevo) from None
    if nuevo not in TRANSICIONES_PERMITIDAS[actual]:
        raise TransicionNoPermitida(actual, nuevo)
    return nuevo


@dataclass(frozen=True)
class OrdenRegistrada:
    """Una orden ya creada, con lo necesario para confirmar su pago."""

    id: int
    estado: EstadoPedido
    items: tuple[ItemSolicitado, ...]
    # Al cancelar solo se repone el stock que realmente se descontó
    stock_descontado: bool = False
    requiere_revision: bool = False
    total_final: Decimal = Decimal('0')
    motivo_cancelacion: str = ''

class EventoPedido(StrEnum):
    """RF-04.2: hitos del pedido que se le avisan al comprador."""

    RECIBIDO = 'RECIBIDO'
    PAGO_APROBADO = 'PAGO_APROBADO'
    # Pago aprobado, pero el admin debe revisar la orden (ej. sin stock): no se le promete el pedido
    PAGO_EN_REVISION = 'PAGO_EN_REVISION'
    PAGO_RECHAZADO = 'PAGO_RECHAZADO'
    # Transferencia aún sin pagar: quedan 24 h antes de que el pedido se cancele
    RECORDATORIO_PAGO = 'RECORDATORIO_PAGO'
    CANCELADO = 'CANCELADO'
    EN_PREPARACION = 'EN_PREPARACION'
    DESPACHADO = 'DESPACHADO'
    ENTREGADO = 'ENTREGADO'


# Pagado y aún sin despachar: se puede generar (o reintentar) la orden de transporte
ESTADOS_CON_ORDEN_TRANSPORTE = frozenset({EstadoPedido.PAGADO, EstadoPedido.EN_PREPARACION})


class OrdenTransporteNoPermitida(Exception):
    pass


def validar_generacion_orden_transporte(estado, requiere_revision: bool) -> None:
    """RF-02.3: la OT se genera para pedidos pagados sin despachar y sin una revisión pendiente."""
    if requiere_revision:
        raise OrdenTransporteNoPermitida(
            'Resuelve la revisión del pedido antes de generar la orden de transporte.')
    if EstadoPedido(estado) not in ESTADOS_CON_ORDEN_TRANSPORTE:
        raise OrdenTransporteNoPermitida(
            f'Un pedido {_etiqueta(estado)} no puede generar una orden de transporte.')


# RF-04.4: el comprador acepta estas páginas en el checkout, así que deben estar publicadas para vender
PAGINAS_REQUERIDAS_PARA_VENDER = ('TERMINOS', 'PRIVACIDAD')


def paginas_legales_faltantes(publicadas) -> list[str]:
    """Páginas legales requeridas para vender que aún no están publicadas, en orden fijo."""
    publicadas = set(publicadas)
    return [tipo for tipo in PAGINAS_REQUERIDAS_PARA_VENDER if tipo not in publicadas]
