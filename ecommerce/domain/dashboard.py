"""Reglas del dashboard del admin (RF-03.1): el periodo que se mira, contra qué se compara y el stock que avisa.

Las ventas cuentan desde que se pagan (ESTADOS_PAGADOS de domain/ventas.py, igual que la vitrina) y por la fecha del
pago, no la de la orden: una transferencia creada el 31 y validada el 2 es venta del mes en que se validó.
"""

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum


class ClavePeriodo(StrEnum):
    ESTE_MES = 'ESTE_MES'
    MES_ANTERIOR = 'MES_ANTERIOR'
    ULTIMOS_30 = 'ULTIMOS_30'
    ESTE_ANO = 'ESTE_ANO'
    DESDE_INICIO = 'DESDE_INICIO'
    PERSONALIZADO = 'PERSONALIZADO'


PERIODO_POR_DEFECTO = ClavePeriodo.ESTE_MES


class PeriodoInvalido(ValueError):
    pass


class Agrupacion(StrEnum):
    DIA = 'DIA'
    MES = 'MES'


# Hasta dos meses el gráfico va por día; más largo, por mes (un año por día serían 365 puntos ilegibles)
DIAS_MAXIMOS_POR_DIA = 62


@dataclass(frozen=True)
class Periodo:
    """De `desde` a `hasta`, ambos incluidos. `desde` None: desde la primera venta de la tienda."""

    clave: ClavePeriodo
    desde: date | None
    hasta: date

    @property
    def agrupacion(self) -> Agrupacion:
        if self.desde is None or (self.hasta - self.desde).days >= DIAS_MAXIMOS_POR_DIA:
            return Agrupacion.MES
        return Agrupacion.DIA


def _fecha(valor, campo) -> date:
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor or ''))
    except ValueError:
        raise PeriodoInvalido(f'Indica la fecha "{campo}" (AAAA-MM-DD).') from None


def _mismo_dia_meses_antes(dia: date, meses: int) -> date:
    """El mismo día unos meses antes; si ese mes es más corto, su último día (31 de marzo -> 28 de febrero)."""
    mes = dia.month - meses
    ano = dia.year + (mes - 1) // 12
    mes = (mes - 1) % 12 + 1
    return date(ano, mes, min(dia.day, calendar.monthrange(ano, mes)[1]))


def resolver_periodo(clave, hoy: date, desde=None, hasta=None) -> Periodo:
    try:
        clave = ClavePeriodo(clave or PERIODO_POR_DEFECTO)
    except ValueError:
        raise PeriodoInvalido('Ese periodo no existe.') from None
    if clave == ClavePeriodo.ESTE_MES:
        return Periodo(clave, hoy.replace(day=1), hoy)
    if clave == ClavePeriodo.MES_ANTERIOR:
        fin = hoy.replace(day=1) - timedelta(days=1)
        return Periodo(clave, fin.replace(day=1), fin)
    if clave == ClavePeriodo.ULTIMOS_30:
        return Periodo(clave, hoy - timedelta(days=29), hoy)
    if clave == ClavePeriodo.ESTE_ANO:
        return Periodo(clave, date(hoy.year, 1, 1), hoy)
    if clave == ClavePeriodo.DESDE_INICIO:
        return Periodo(clave, None, hoy)
    inicio, fin = _fecha(desde, 'desde'), _fecha(hasta, 'hasta')
    if inicio > fin:
        raise PeriodoInvalido('La fecha "desde" no puede ser posterior a "hasta".')
    return Periodo(clave, inicio, fin)


def periodo_anterior(periodo: Periodo) -> Periodo | None:
    """Contra qué se compara: un mes contra el mismo tramo del mes anterior (del 1 al 5 de noviembre contra el 1 al 5
    de octubre), el año contra el mismo tramo del año anterior y un rango contra los mismos días justo antes.
    Desde el inicio no tiene con qué compararse."""
    if periodo.desde is None:
        return None
    if periodo.clave in (ClavePeriodo.ESTE_MES, ClavePeriodo.MES_ANTERIOR):
        hasta = _mismo_dia_meses_antes(periodo.hasta, 1)
        if periodo.clave == ClavePeriodo.MES_ANTERIOR:
            # El mes completo anterior, aunque sea más largo (octubre contra septiembre entero)
            hasta = hasta.replace(day=calendar.monthrange(hasta.year, hasta.month)[1])
        return Periodo(periodo.clave, _mismo_dia_meses_antes(periodo.desde, 1), hasta)
    if periodo.clave == ClavePeriodo.ESTE_ANO:
        return Periodo(periodo.clave, _mismo_dia_meses_antes(periodo.desde, 12),
                       _mismo_dia_meses_antes(periodo.hasta, 12))
    dias = (periodo.hasta - periodo.desde).days + 1
    return Periodo(periodo.clave, periodo.desde - timedelta(days=dias), periodo.desde - timedelta(days=1))


def variacion_porcentual(actual, anterior) -> int | None:
    """Cuánto cambió, en porcentaje entero. None si antes no hubo nada con qué comparar (no se puede dividir por 0)."""
    if not anterior:
        return None
    return round((actual - anterior) * 100 / anterior)


def ticket_promedio(total, pedidos: int) -> int:
    return round(total / pedidos) if pedidos else 0


def porcentajes(valores: list) -> list[int]:
    """La parte de cada valor en el total, en porcentaje entero (para las barras de "Más detalles")."""
    total = sum(valores)
    return [round(valor * 100 / total) if total else 0 for valor in valores]


# Stock bajo (decidido el 2026-11-05): 5 unidades o menos; 0 es agotado
UMBRAL_STOCK_BAJO = 5


class EstadoStock(StrEnum):
    AGOTADO = 'AGOTADO'
    BAJO = 'BAJO'


def estado_stock(stock: int) -> EstadoStock | None:
    if stock <= 0:
        return EstadoStock.AGOTADO
    return EstadoStock.BAJO if stock <= UMBRAL_STOCK_BAJO else None
