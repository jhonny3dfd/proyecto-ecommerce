"""Reglas de los códigos de descuento (RF-04.1); independiente de Django.

El checkout igual limita el descuento al subtotal (el total nunca queda negativo), pero un código mal configurado,
como un 250 % o un umbral de envío gratis negativo, regalaría la compra o el envío: se rechaza al guardarlo.

Un código puede exigir un monto mínimo de compra y tener un límite de usos. Uno automático se aplica solo, sin
escribirlo, a toda compra desde su monto mínimo. Si el comprador además escribe un código, se aplica el que más
ahorra (los descuentos no se suman).
"""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Iterable, TypeVar

PORCENTAJE = 'PORCENTAJE'
MONTO_FIJO = 'MONTO_FIJO'
LARGO_CODIGO = 50

_CODIGO = re.compile(r'^[A-ZÑ0-9_-]+$')


class PromocionInvalida(ValueError):
    def __init__(self, errores: dict[str, str]):
        self.errores = errores
        super().__init__('; '.join(f'{campo}: {error}' for campo, error in errores.items()))


def normalizar_codigo(texto) -> str:
    """En mayúsculas y sin espacios a los lados: el comprador lo escribe como quiera."""
    return str(texto or '').strip().upper()


def validar_promocion(codigo, tipo_descuento, valor_descuento, umbral_envio_gratis, monto_minimo=None,
                      automatica=False, usos_maximos=None) -> str:
    """Devuelve el código normalizado; PromocionInvalida con un error por campo si algo no sirve."""
    errores = {}
    codigo = normalizar_codigo(codigo)
    if not codigo:
        errores['codigo'] = 'Escribe el código.'
    elif len(codigo) > LARGO_CODIGO:
        errores['codigo'] = f'El código puede tener hasta {LARGO_CODIGO} caracteres.'
    elif not _CODIGO.match(codigo):
        errores['codigo'] = 'Usa solo letras, números, guiones o guiones bajos, sin espacios (ej. VERANO20).'

    valor = None if valor_descuento is None else Decimal(str(valor_descuento))
    if valor is None or valor <= 0:
        errores['valor_descuento'] = 'El descuento debe ser mayor a cero.'
    elif tipo_descuento == PORCENTAJE and valor > 100:
        errores['valor_descuento'] = 'Un descuento en porcentaje puede ser de hasta 100.'
    elif tipo_descuento == MONTO_FIJO and valor != valor.to_integral_value():
        errores['valor_descuento'] = 'El monto va en pesos, sin decimales.'

    if umbral_envio_gratis is not None and Decimal(str(umbral_envio_gratis)) <= 0:
        errores['umbral_envio_gratis'] = 'El monto para el envío gratis debe ser mayor a cero, o déjalo vacío.'

    if monto_minimo is not None and Decimal(str(monto_minimo)) <= 0:
        errores['monto_minimo'] = 'El monto mínimo debe ser mayor a cero, o déjalo vacío.'
    elif automatica and monto_minimo is None:
        # Sin mínimo, un descuento automático se aplicaría a todas las compras de la tienda
        errores['monto_minimo'] = 'Un descuento automático necesita el monto de compra desde el que se aplica.'

    if usos_maximos is not None and int(usos_maximos) < 1:
        errores['usos_maximos'] = 'Indica al menos 1 uso, o déjalo vacío para que no tenga límite.'

    if errores:
        raise PromocionInvalida(errores)
    return codigo


@dataclass(frozen=True)
class ReglaDescuento:
    """Lo que hace un código en una compra; el checkout y la vista previa del navegador usan la misma regla."""
    tipo_descuento: str
    valor_descuento: Decimal
    umbral_envio_gratis: Decimal | None = None
    monto_minimo: Decimal | None = None


def cumple_minimo(regla: ReglaDescuento, subtotal: Decimal) -> bool:
    return regla.monto_minimo is None or Decimal(subtotal) >= regla.monto_minimo


def monto_descuento(regla: ReglaDescuento, subtotal: Decimal) -> Decimal:
    """Lo que se descuenta del subtotal: nunca más que el subtotal, y cero bajo el monto mínimo."""
    subtotal = Decimal(subtotal)
    if not cumple_minimo(regla, subtotal):
        return Decimal('0')
    if regla.tipo_descuento == PORCENTAJE:
        descuento = subtotal * regla.valor_descuento / 100
    else:
        descuento = regla.valor_descuento
    return max(Decimal('0'), min(descuento, subtotal))


def da_envio_gratis(regla: ReglaDescuento, subtotal: Decimal) -> bool:
    return (cumple_minimo(regla, subtotal) and regla.umbral_envio_gratis is not None
            and Decimal(subtotal) >= regla.umbral_envio_gratis)


def ahorro(regla: ReglaDescuento, subtotal: Decimal, costo_envio: Decimal) -> Decimal:
    """Cuánto se ahorra el comprador con este código: el descuento más el envío, si lo deja gratis."""
    envio = Decimal(costo_envio) if da_envio_gratis(regla, subtotal) else Decimal('0')
    return monto_descuento(regla, subtotal) + envio


T = TypeVar('T')


def elegir_promocion(candidatas: Iterable[T], subtotal: Decimal, costo_envio: Decimal,
                     regla_de: Callable[[T], ReglaDescuento]) -> T | None:
    """El código que más ahorra entre el escrito y los automáticos (no se suman); None si ninguno ahorra nada.

    Con el mismo ahorro gana el primero: quien llama pone primero el código que escribió el comprador.
    """
    mejor, mejor_ahorro = None, Decimal('0')
    for candidata in candidatas:
        valor = ahorro(regla_de(candidata), subtotal, costo_envio)
        if valor > mejor_ahorro:
            mejor, mejor_ahorro = candidata, valor
    return mejor
