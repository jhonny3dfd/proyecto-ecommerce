"""Casos de uso del dashboard del admin (RF-03.1).

- ResumenDashboard: cómo le va a la tienda en un periodo, comparado con el anterior, y el detalle de por qué.
- TareasPendientes: "Para hoy", lo que el admin tiene que atender (solo lo que no está en cero).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

from ecommerce.application.pagos import MOTIVO_PAGO_REEMBOLSADO
from ecommerce.application.ventas import (
    MOTIVO_CANCELACION_ADMIN, MOTIVO_PAGO_ANULADO, MOTIVO_PAGO_RECHAZADO, MOTIVO_PAGO_VENCIDO,
)
from ecommerce.domain.dashboard import (
    UMBRAL_STOCK_BAJO, EstadoStock, Periodo, estado_stock, periodo_anterior, porcentajes, ticket_promedio,
    variacion_porcentual,
)
from ecommerce.domain.resenas import promedio

CANTIDAD_MAS_VENDIDOS = 5
CANTIDAD_COMUNAS = 5
# Una transferencia "vence pronto" si su plazo termina en las próximas 24 horas
HORAS_POR_VENCER = 24


@dataclass(frozen=True)
class ResumenVentas:
    total: int
    pedidos: int


@dataclass(frozen=True)
class PuntoSerie:
    """Un día o, con la agrupación por mes, el día 1 de ese mes."""
    fecha: date
    total: int
    pedidos: int


@dataclass(frozen=True)
class ProductoVendido:
    producto_id: str
    nombre: str
    unidades: int
    total: int


@dataclass(frozen=True)
class Grupo:
    """Las ventas de un medio de pago, un tipo de entrega o una comuna."""
    clave: str
    nombre: str
    total: int
    pedidos: int


@dataclass(frozen=True)
class Barra:
    nombre: str
    total: int
    pedidos: int
    porcentaje: int


@dataclass(frozen=True)
class UsoCupon:
    codigo: str
    usos: int
    descontado: int


@dataclass(frozen=True)
class ResumenClientes:
    """De quienes compraron en el periodo. Nuevo: su primera compra pagada cae en el periodo. Recurrente: ya había
    comprado antes o compró más de una vez en el periodo."""
    nuevos: int
    recurrentes: int
    registrados: int
    invitados: int


@dataclass(frozen=True)
class VariantePocoStock:
    producto_id: str
    producto: str
    sku: str
    detalle: str
    stock: int


@dataclass(frozen=True)
class ConteoPendientes:
    por_preparar: int = 0
    transferencias: int = 0
    transferencias_por_vencer: int = 0
    revision: int = 0
    orden_transporte: int = 0
    documentos: int = 0
    cotizaciones: int = 0
    resenas: int = 0


class MetricasVentas(ABC):
    """Puerto de salida: las ventas pagadas de un periodo, contadas por la fecha del pago (PostgreSQL)."""

    @abstractmethod
    def resumen(self, periodo: Periodo) -> ResumenVentas:
        raise NotImplementedError

    @abstractmethod
    def serie(self, periodo: Periodo) -> list[PuntoSerie]:
        """Por día o por mes según periodo.agrupacion, solo los que tuvieron ventas, del más antiguo al más nuevo."""
        raise NotImplementedError

    @abstractmethod
    def mas_vendidos(self, periodo: Periodo, limite: int) -> list[ProductoVendido]:
        """Por unidades, de más a menos."""
        raise NotImplementedError

    @abstractmethod
    def por_medio_pago(self, periodo: Periodo) -> list[Grupo]:
        raise NotImplementedError

    @abstractmethod
    def por_entrega(self, periodo: Periodo) -> list[Grupo]:
        raise NotImplementedError

    @abstractmethod
    def por_comuna(self, periodo: Periodo, limite: int) -> list[Grupo]:
        """Las comunas de despacho con más ventas (sin los retiros en el local)."""
        raise NotImplementedError

    @abstractmethod
    def cancelaciones(self, periodo: Periodo) -> list[tuple[str, int]]:
        """(motivo, cantidad) de las órdenes canceladas que se crearon en el periodo."""
        raise NotImplementedError

    @abstractmethod
    def cupones(self, periodo: Periodo) -> list[UsoCupon]:
        raise NotImplementedError

    @abstractmethod
    def clientes(self, periodo: Periodo) -> ResumenClientes:
        raise NotImplementedError

    @abstractmethod
    def calificaciones(self) -> list[int] | None:
        """Las estrellas de las reseñas aprobadas de la tienda, o None si la tienda no tiene las reseñas activas."""
        raise NotImplementedError


class PendientesTienda(ABC):
    """Puerto de salida: cuántas cosas esperan al admin (PostgreSQL)."""

    @abstractmethod
    def contar(self, por_vencer_antes: datetime) -> ConteoPendientes:
        """`por_vencer_antes`: las transferencias cuyo plazo termina antes de ese momento vencen pronto."""
        raise NotImplementedError


class StockCatalogo(ABC):
    """Puerto de salida: las variantes de productos activos con `umbral` unidades o menos (MongoDB)."""

    @abstractmethod
    def con_poco_stock(self, umbral: int) -> list[VariantePocoStock]:
        raise NotImplementedError


class CausaCancelacion(StrEnum):
    PAGO_RECHAZADO = 'PAGO_RECHAZADO'
    PAGO_VENCIDO = 'PAGO_VENCIDO'
    PAGO_DEVUELTO = 'PAGO_DEVUELTO'
    TIENDA = 'TIENDA'
    OTRO = 'OTRO'


ETIQUETAS_CAUSA_CANCELACION = {
    CausaCancelacion.PAGO_RECHAZADO: 'Pago rechazado o anulado',
    CausaCancelacion.PAGO_VENCIDO: 'Transferencia no pagada a tiempo',
    CausaCancelacion.PAGO_DEVUELTO: 'Pago devuelto por la pasarela',
    CausaCancelacion.TIENDA: 'Cancelado por la tienda',
    CausaCancelacion.OTRO: 'Otro motivo',
}


def causa_cancelacion(motivo: str) -> CausaCancelacion:
    """El motivo es texto libre (ventas.py y pagos.py lo arman con sus constantes): se agrupa por su causa."""
    motivo = (motivo or '').strip()
    if motivo in (MOTIVO_PAGO_RECHAZADO, MOTIVO_PAGO_ANULADO):
        return CausaCancelacion.PAGO_RECHAZADO
    if motivo == MOTIVO_PAGO_VENCIDO:
        return CausaCancelacion.PAGO_VENCIDO
    if motivo.startswith(MOTIVO_PAGO_REEMBOLSADO.split('{')[0]):
        return CausaCancelacion.PAGO_DEVUELTO
    if motivo == MOTIVO_CANCELACION_ADMIN:
        return CausaCancelacion.TIENDA
    return CausaCancelacion.OTRO


@dataclass(frozen=True)
class Tarjetas:
    ventas: int
    variacion_ventas: int | None
    pedidos: int
    # Pedidos: la diferencia en unidades ("5 más"), no un porcentaje
    diferencia_pedidos: int | None
    ticket_promedio: int
    variacion_ticket: int | None
    clientes_nuevos: int


@dataclass(frozen=True)
class Calificacion:
    promedio: float
    cantidad: int


@dataclass(frozen=True)
class Dashboard:
    periodo: Periodo
    anterior: Periodo | None
    tarjetas: Tarjetas
    serie: list[PuntoSerie]
    mas_vendidos: list[ProductoVendido]
    medios_pago: list[Barra]
    entregas: list[Barra]
    comunas: list[Barra]
    cancelaciones: list[tuple[CausaCancelacion, int]]
    cupones: list[UsoCupon]
    clientes: ResumenClientes
    # None: la tienda no tiene las reseñas activas (la pestaña no la muestra)
    calificacion: Calificacion | None


def _barras(grupos: list[Grupo], total: int | None = None) -> list[Barra]:
    grupos = sorted(grupos, key=lambda grupo: (-grupo.total, grupo.nombre))
    if total is None:
        partes = porcentajes([grupo.total for grupo in grupos])
    else:
        # Las comunas son solo las primeras: su parte es del total vendido, no de la suma de las que se muestran
        partes = [round(grupo.total * 100 / total) if total else 0 for grupo in grupos]
    return [Barra(grupo.nombre, grupo.total, grupo.pedidos, parte) for grupo, parte in zip(grupos, partes)]


class ResumenDashboard:
    """RF-03.1: las ventas del periodo (por fecha de pago y contando los pedidos que ya avanzaron), comparadas con el
    periodo anterior, y su detalle."""

    def __init__(self, metricas: MetricasVentas):
        self.metricas = metricas

    def ejecutar(self, periodo: Periodo) -> Dashboard:
        actual = self.metricas.resumen(periodo)
        anterior = periodo_anterior(periodo)
        previo = self.metricas.resumen(anterior) if anterior else None
        ticket = ticket_promedio(actual.total, actual.pedidos)
        clientes = self.metricas.clientes(periodo)
        tarjetas = Tarjetas(
            ventas=actual.total,
            variacion_ventas=variacion_porcentual(actual.total, previo.total) if previo else None,
            pedidos=actual.pedidos,
            diferencia_pedidos=actual.pedidos - previo.pedidos if previo else None,
            ticket_promedio=ticket,
            variacion_ticket=(variacion_porcentual(ticket, ticket_promedio(previo.total, previo.pedidos))
                              if previo else None),
            clientes_nuevos=clientes.nuevos,
        )

        causas = {}
        for motivo, cantidad in self.metricas.cancelaciones(periodo):
            causa = causa_cancelacion(motivo)
            causas[causa] = causas.get(causa, 0) + cantidad
        estrellas = self.metricas.calificaciones()
        calificacion = Calificacion(promedio(estrellas), len(estrellas)) if estrellas else None

        return Dashboard(
            periodo=periodo,
            anterior=anterior,
            tarjetas=tarjetas,
            serie=self.metricas.serie(periodo),
            mas_vendidos=self.metricas.mas_vendidos(periodo, CANTIDAD_MAS_VENDIDOS),
            medios_pago=_barras(self.metricas.por_medio_pago(periodo)),
            entregas=_barras(self.metricas.por_entrega(periodo)),
            comunas=_barras(self.metricas.por_comuna(periodo, CANTIDAD_COMUNAS), total=actual.total),
            cancelaciones=sorted(causas.items(), key=lambda par: (-par[1], par[0])),
            cupones=sorted(self.metricas.cupones(periodo), key=lambda cupon: (-cupon.usos, cupon.codigo)),
            clientes=clientes,
            calificacion=calificacion,
        )


class Tarea(StrEnum):
    POR_PREPARAR = 'POR_PREPARAR'
    TRANSFERENCIAS = 'TRANSFERENCIAS'
    REVISION = 'REVISION'
    ORDEN_TRANSPORTE = 'ORDEN_TRANSPORTE'
    DOCUMENTOS = 'DOCUMENTOS'
    COTIZACIONES = 'COTIZACIONES'
    RESENAS = 'RESENAS'


# Orden en "Para hoy": primero lo que tiene clientes esperando
_TAREAS = (
    (Tarea.POR_PREPARAR, 'por_preparar'),
    (Tarea.TRANSFERENCIAS, 'transferencias'),
    (Tarea.REVISION, 'revision'),
    (Tarea.ORDEN_TRANSPORTE, 'orden_transporte'),
    (Tarea.DOCUMENTOS, 'documentos'),
    (Tarea.COTIZACIONES, 'cotizaciones'),
    (Tarea.RESENAS, 'resenas'),
)


@dataclass(frozen=True)
class TareaPendiente:
    tarea: Tarea
    cantidad: int
    # Solo en las transferencias: cuántas vencen en las próximas 24 horas
    por_vencer: int = 0


@dataclass(frozen=True)
class ParaHoy:
    tareas: list[TareaPendiente]
    agotadas: list[VariantePocoStock]
    stock_bajo: list[VariantePocoStock]

    @property
    def al_dia(self) -> bool:
        return not (self.tareas or self.agotadas or self.stock_bajo)


class TareasPendientes:
    """RF-03.1: "Para hoy" muestra solo lo que tiene algo que hacer, para no llenar el dashboard de ceros."""

    def __init__(self, pendientes: PendientesTienda, stock: StockCatalogo):
        self.pendientes = pendientes
        self.stock = stock

    def ejecutar(self, ahora: datetime) -> ParaHoy:
        conteo = self.pendientes.contar(por_vencer_antes=ahora + timedelta(hours=HORAS_POR_VENCER))
        tareas = [
            TareaPendiente(tarea, getattr(conteo, campo),
                           conteo.transferencias_por_vencer if tarea == Tarea.TRANSFERENCIAS else 0)
            for tarea, campo in _TAREAS if getattr(conteo, campo) > 0
        ]
        variantes = sorted(self.stock.con_poco_stock(UMBRAL_STOCK_BAJO),
                           key=lambda variante: (variante.stock, variante.producto, variante.sku))
        return ParaHoy(
            tareas=tareas,
            agotadas=[v for v in variantes if estado_stock(v.stock) == EstadoStock.AGOTADO],
            stock_bajo=[v for v in variantes if estado_stock(v.stock) == EstadoStock.BAJO],
        )
