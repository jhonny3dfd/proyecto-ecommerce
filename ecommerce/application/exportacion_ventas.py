"""Caso de uso: exportar a una planilla las ventas de un periodo del dashboard (RF-03.1).

Pedido de una clienta (2026-11-17). Entran las mismas ventas que cuenta el dashboard (pedidos pagados, por la fecha
del pago), para que el total de la planilla coincida con la cifra "Ventas" de la pantalla. Dos hojas: "Ventas", una
fila por pedido con los datos del cliente, y "Productos", una fila por producto vendido.

Aquí se decide qué columnas lleva y en qué orden; escribir el archivo (.xlsx) es de infraestructura.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from ecommerce.domain.dashboard import Periodo
from ecommerce.domain.ventas import EstadoPedido


@dataclass(frozen=True)
class LineaVendida:
    producto: str
    sku: str
    cantidad: int
    precio_unitario: int


@dataclass(frozen=True)
class VentaPeriodo:
    """Un pedido pagado, con los datos de quien compró tal como quedaron en el pedido."""

    numero: int
    # Fecha y hora del pago en la hora de la tienda, sin zona (una planilla no guarda zonas horarias)
    fecha: datetime
    estado: EstadoPedido
    cliente: str
    correo: str
    telefono: str
    registrado: bool
    destinatario: str
    telefono_destinatario: str
    entrega: str
    direccion: str
    comuna: str
    numero_seguimiento: str
    medio_pago: str
    subtotal: int
    costo_envio: int
    total: int
    cupon: str = ''
    # Solo en las compras como empresa
    razon_social: str = ''
    rut_empresa: str = ''
    giro: str = ''
    folio_documento: str = ''
    lineas: tuple[LineaVendida, ...] = ()


class VentasPeriodo(ABC):
    """Puerto de salida: los pedidos pagados de un periodo, por la fecha del pago, del más antiguo al más nuevo."""

    @abstractmethod
    def listar(self, periodo: Periodo) -> list[VentaPeriodo]:
        raise NotImplementedError


@dataclass(frozen=True)
class Hoja:
    nombre: str
    columnas: tuple[str, ...]
    filas: list[tuple]


@dataclass(frozen=True)
class Planilla:
    # Sin extensión: la pone quien escribe el archivo
    nombre: str
    hojas: tuple[Hoja, ...]


COLUMNAS_VENTAS = (
    'N° pedido', 'Fecha de pago', 'Estado', 'Cliente', 'Correo', 'Teléfono', 'Tipo de cliente',
    'Recibe', 'Teléfono de quien recibe', 'Entrega', 'Dirección', 'Comuna', 'N° de seguimiento',
    'Medio de pago', 'Subtotal', 'Descuento', 'Envío', 'Total', 'Cupón',
    'Razón social', 'RUT empresa', 'Giro', 'Folio boleta o factura',
)
COLUMNAS_PRODUCTOS = (
    'N° pedido', 'Fecha de pago', 'Cliente', 'Correo', 'Producto', 'SKU', 'Cantidad', 'Precio unitario', 'Total',
)


def descuento(venta: VentaPeriodo) -> int:
    """Lo que el cupón o las promociones rebajaron: la diferencia entre lo que sumaban productos y envío y lo pagado."""
    return max(venta.subtotal + venta.costo_envio - venta.total, 0)


def nombre_planilla(periodo: Periodo) -> str:
    if periodo.desde is None:
        return f'ventas_hasta_{periodo.hasta.isoformat()}'
    return f'ventas_{periodo.desde.isoformat()}_a_{periodo.hasta.isoformat()}'


class ExportarVentas:
    """RF-03.1: las ventas del periodo elegido en el dashboard, listas para abrir en Excel."""

    def __init__(self, ventas: VentasPeriodo):
        self.ventas = ventas

    def ejecutar(self, periodo: Periodo) -> Planilla:
        ventas = self.ventas.listar(periodo)
        filas_ventas = [(
            venta.numero, venta.fecha, venta.estado.etiqueta, venta.cliente, venta.correo, venta.telefono,
            'Registrado' if venta.registrado else 'Invitado',
            venta.destinatario, venta.telefono_destinatario, venta.entrega, venta.direccion, venta.comuna,
            venta.numero_seguimiento, venta.medio_pago, venta.subtotal, descuento(venta), venta.costo_envio,
            venta.total, venta.cupon, venta.razon_social, venta.rut_empresa, venta.giro, venta.folio_documento,
        ) for venta in ventas]
        filas_productos = [(
            venta.numero, venta.fecha, venta.cliente, venta.correo, linea.producto, linea.sku, linea.cantidad,
            linea.precio_unitario, linea.cantidad * linea.precio_unitario,
        ) for venta in ventas for linea in venta.lineas]
        return Planilla(nombre_planilla(periodo), (
            Hoja('Ventas', COLUMNAS_VENTAS, filas_ventas),
            Hoja('Productos', COLUMNAS_PRODUCTOS, filas_productos),
        ))
