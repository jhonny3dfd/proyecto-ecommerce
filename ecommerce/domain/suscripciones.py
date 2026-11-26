"""Suscripciones con entregas recurrentes (pedido de un cliente, opcional y apagado por defecto).

El admin ofrece planes (precio por ciclo, cada cuántas semanas, beneficios y qué productos se pueden elegir). El cliente
se suscribe con su cuenta, elige una variante de un producto elegible y paga ciclo a ciclo con los medios de la tienda:
cada ciclo es un pedido normal. Sin cobro automático (fase 3). La fase 2 añade el acceso a productos exclusivos;
la fecha opcional de cumpleaños se valida en domain/cumpleanos.py.

Independiente de Django: estados y transiciones, fechas de los ciclos y validación de los planes.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum


def permite_producto_exclusivo(modulo_activo, exclusivo, planes_permitidos, planes_vigentes, plan_elegido=None):
    """Un exclusivo exige una suscripción activa; una lista vacía admite cualquier plan vigente.

    Al elegir la entrega de un plan también se respeta la lista de planes del producto.
    Desactivar el módulo suspende todas las restricciones, incluso las guardadas antes.
    """
    if not modulo_activo or not exclusivo:
        return True
    vigentes = set(planes_vigentes)
    permitidos = set(planes_permitidos)
    return bool(vigentes and (not permitidos or (
        vigentes & permitidos and (plan_elegido is None or plan_elegido in permitidos))))

LARGO_NOMBRE_PLAN = 60
LARGO_DESCRIPCION_PLAN = 300
MAX_BENEFICIOS = 10
LARGO_BENEFICIO = 120
MAX_ELEGIBLES = 50
FRECUENCIA_MINIMA_SEMANAS = 1
FRECUENCIA_MAXIMA_SEMANAS = 12
UNIDADES_MAXIMAS = 20
DESCUENTO_MAXIMO = 90
# El mismo tope de un precio del catálogo (pesos enteros)
PRECIO_MAXIMO = 99_999_999

# Días antes de cada entrega en que se crea el pedido del ciclo y se le pide el pago al cliente
DIAS_AVISO_POR_DEFECTO = 3
DIAS_AVISO_MINIMO = 1
DIAS_AVISO_MAXIMO = 14

MOTIVO_CICLO_NO_PAGADO = 'Ciclo de suscripción no pagado'
MOTIVO_CICLO_SALTADO = 'El cliente saltó este ciclo de su suscripción'
MOTIVO_SUSCRIPCION_PAUSADA = 'El cliente pausó su suscripción'
MOTIVO_SUSCRIPCION_CANCELADA = 'El cliente canceló su suscripción'
MOTIVO_PRIMER_PAGO_NO_RECIBIDO = 'No se recibió el pago del primer ciclo'


class EventoSuscripcion(StrEnum):
    """RF-04.2: hitos de la suscripción que se le avisan al cliente por correo. El pago aprobado o rechazado de cada
    ciclo lo avisa el correo del pedido, como en cualquier compra."""

    ACTIVADA = 'ACTIVADA'
    # El pedido del ciclo ya está creado: se le pide el pago con un enlace
    AVISO_COBRO = 'AVISO_COBRO'
    CICLO_NO_PAGADO = 'CICLO_NO_PAGADO'
    PAUSADA = 'PAUSADA'
    REANUDADA = 'REANUDADA'
    CANCELADA = 'CANCELADA'
    # No pagó el primer ciclo a tiempo: la suscripción nunca se activó
    NO_ACTIVADA = 'NO_ACTIVADA'


class EstadoSuscripcion(StrEnum):
    # Creada al suscribirse: espera el pago del primer ciclo
    PENDIENTE = 'PENDIENTE'
    ACTIVA = 'ACTIVA'
    PAUSADA = 'PAUSADA'
    CANCELADA = 'CANCELADA'


ETIQUETAS_ESTADO_SUSCRIPCION = {
    EstadoSuscripcion.PENDIENTE: 'Esperando el primer pago',
    EstadoSuscripcion.ACTIVA: 'Activa',
    EstadoSuscripcion.PAUSADA: 'Pausada',
    EstadoSuscripcion.CANCELADA: 'Cancelada',
}

TRANSICIONES_SUSCRIPCION = {
    EstadoSuscripcion.PENDIENTE: {EstadoSuscripcion.ACTIVA, EstadoSuscripcion.CANCELADA},
    EstadoSuscripcion.ACTIVA: {EstadoSuscripcion.PAUSADA, EstadoSuscripcion.CANCELADA},
    EstadoSuscripcion.PAUSADA: {EstadoSuscripcion.ACTIVA, EstadoSuscripcion.CANCELADA},
    EstadoSuscripcion.CANCELADA: set(),
}


class TransicionSuscripcionNoPermitida(Exception):
    def __init__(self, actual, nuevo):
        self.actual = actual
        self.nuevo = nuevo
        super().__init__(f'Una suscripción {_etiqueta(actual).lower()} no puede pasar a {_etiqueta(nuevo).lower()}.')


def _etiqueta(estado) -> str:
    try:
        return ETIQUETAS_ESTADO_SUSCRIPCION[EstadoSuscripcion(estado)]
    except ValueError:
        return str(estado)


def validar_transicion_suscripcion(actual, nuevo) -> EstadoSuscripcion:
    """El nuevo estado si la transición está permitida; si no, TransicionSuscripcionNoPermitida."""
    try:
        actual, nuevo = EstadoSuscripcion(actual), EstadoSuscripcion(nuevo)
    except ValueError:
        raise TransicionSuscripcionNoPermitida(actual, nuevo) from None
    if nuevo not in TRANSICIONES_SUSCRIPCION[actual]:
        raise TransicionSuscripcionNoPermitida(actual, nuevo)
    return nuevo


# ---------- Acciones del suscriptor (Mi cuenta) ----------

class AccionSuscripcion(StrEnum):
    PAUSAR = 'PAUSAR'
    REANUDAR = 'REANUDAR'
    SALTAR = 'SALTAR'
    ADELANTAR = 'ADELANTAR'
    CANCELAR = 'CANCELAR'
    # Cambiar la variante elegida, la dirección, la forma de entrega o el medio de pago
    CAMBIAR = 'CAMBIAR'


# En qué estados se puede hacer cada acción
ESTADOS_DE_ACCION = {
    AccionSuscripcion.PAUSAR: {EstadoSuscripcion.ACTIVA},
    AccionSuscripcion.REANUDAR: {EstadoSuscripcion.PAUSADA},
    AccionSuscripcion.SALTAR: {EstadoSuscripcion.ACTIVA},
    AccionSuscripcion.ADELANTAR: {EstadoSuscripcion.ACTIVA},
    AccionSuscripcion.CANCELAR: {EstadoSuscripcion.PENDIENTE, EstadoSuscripcion.ACTIVA, EstadoSuscripcion.PAUSADA},
    AccionSuscripcion.CAMBIAR: {EstadoSuscripcion.PENDIENTE, EstadoSuscripcion.ACTIVA, EstadoSuscripcion.PAUSADA},
}

MENSAJES_ACCION_NO_PERMITIDA = {
    AccionSuscripcion.PAUSAR: 'Solo se puede pausar una suscripción activa.',
    AccionSuscripcion.REANUDAR: 'Solo se puede reanudar una suscripción pausada.',
    AccionSuscripcion.SALTAR: 'Solo se puede saltar un ciclo de una suscripción activa.',
    AccionSuscripcion.ADELANTAR: 'Solo se puede adelantar la entrega de una suscripción activa.',
    AccionSuscripcion.CANCELAR: 'Esta suscripción ya está cancelada.',
    AccionSuscripcion.CAMBIAR: 'Una suscripción cancelada no se puede modificar.',
}


class AccionNoPermitida(Exception):
    def __init__(self, mensaje: str):
        super().__init__(mensaje)


def validar_accion(accion, estado) -> AccionSuscripcion:
    accion, estado = AccionSuscripcion(accion), EstadoSuscripcion(estado)
    if estado not in ESTADOS_DE_ACCION[accion]:
        raise AccionNoPermitida(MENSAJES_ACCION_NO_PERMITIDA[accion])
    return accion


# ---------- Fechas de los ciclos ----------
# La fecha de un ciclo es el día de su entrega. Su pedido se crea `dias_aviso` días antes (con el aviso de cobro) y,
# si al terminar ese día no se pagó, el ciclo no se entrega. Cada ciclo siguiente se calcula desde la fecha del
# anterior, no desde el día del pago, para que el calendario no se corra.

def fecha_primer_ciclo(hoy: date, dias_aviso: int) -> date:
    """El primer pedido se crea al suscribirse, con la misma anticipación de todos los ciclos: hay `dias_aviso` días
    para pagarlo (alcanza también para una transferencia)."""
    return hoy + timedelta(days=dias_aviso)


def siguiente_ciclo(fecha_ciclo: date, frecuencia_semanas: int) -> date:
    return fecha_ciclo + timedelta(weeks=frecuencia_semanas)


def fecha_aviso(fecha_ciclo: date, dias_aviso: int) -> date:
    """Desde qué día se crea el pedido del ciclo y se pide el pago."""
    return fecha_ciclo - timedelta(days=dias_aviso)


def toca_avisar(fecha_ciclo: date, hoy: date, dias_aviso: int) -> bool:
    return hoy >= fecha_aviso(fecha_ciclo, dias_aviso)


def ciclo_vencido(fecha_ciclo: date, hoy: date) -> bool:
    """El ciclo se puede pagar hasta el mismo día de su entrega; desde el día siguiente ya no."""
    return hoy > fecha_ciclo


def fecha_al_reanudar(proxima: date, hoy: date, dias_aviso: int) -> date:
    """Al reanudar se conserva la próxima entrega si todavía alcanza a avisarse con la anticipación de siempre; si no,
    queda para cuando sí alcanza (la pausa no hace cobrar de un día para otro)."""
    return max(proxima, hoy + timedelta(days=dias_aviso))


def fecha_al_adelantar(hoy: date) -> date:
    """Adelantar trae la próxima entrega a hoy: su pedido se crea y se cobra de inmediato."""
    return hoy


def validar_dias_aviso(valor) -> int:
    try:
        dias = int(valor)
    except (TypeError, ValueError):
        raise ValueError('Indica un número de días.') from None
    if not DIAS_AVISO_MINIMO <= dias <= DIAS_AVISO_MAXIMO:
        raise ValueError(f'Debe estar entre {DIAS_AVISO_MINIMO} y {DIAS_AVISO_MAXIMO} días.')
    return dias


# ---------- Beneficios ----------

def descuento_suscriptor(subtotal: Decimal, porcentaje: int) -> Decimal:
    """Pesos de descuento sobre el subtotal de una compra, en pesos enteros; nunca más que el subtotal (RF-04.1)."""
    subtotal = max(Decimal(subtotal), Decimal('0'))
    if porcentaje <= 0:
        return Decimal('0')
    descuento = (subtotal * Decimal(porcentaje) / Decimal(100)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return min(descuento, subtotal)


# ---------- Planes ----------

class PlanInvalido(ValueError):
    """Errores por campo, para mostrarlos junto a cada uno en el panel."""

    def __init__(self, errores: dict):
        self.errores = errores
        super().__init__('; '.join(f'{campo}: {error}' for campo, error in errores.items()))


def _texto(valor) -> str:
    return ' '.join(str(valor or '').split())


def _entero(valor, nombre: str, errores: dict, minimo: int, maximo: int, por_defecto: int | None = None) -> int:
    if valor in (None, ''):
        if por_defecto is None:
            errores[nombre] = 'Este dato es obligatorio.'
            return 0
        return por_defecto
    try:
        numero = Decimal(str(valor).strip())
    except Exception:
        errores[nombre] = 'Debe ser un número.'
        return por_defecto or 0
    if not numero.is_finite() or numero != numero.to_integral_value():
        errores[nombre] = 'Debe ser un número entero.'
        return por_defecto or 0
    numero = int(numero)
    if not minimo <= numero <= maximo:
        errores[nombre] = f'Debe estar entre {minimo:,} y {maximo:,}.'.replace(',', '.')
    return numero


def _lista_textos(valor, nombre: str, errores: dict, maximo: int, largo: int | None = None) -> tuple[str, ...]:
    if valor in (None, ''):
        return ()
    if not isinstance(valor, (list, tuple)):
        errores[nombre] = 'Debe ser una lista.'
        return ()
    resultado, vistos = [], set()
    for elemento in valor:
        texto = _texto(elemento)
        if not texto or texto.lower() in vistos:
            continue
        if largo is not None and len(texto) > largo:
            errores[nombre] = f'Cada uno puede tener hasta {largo} caracteres.'
            continue
        vistos.add(texto.lower())
        resultado.append(texto)
    if len(resultado) > maximo:
        errores[nombre] = f'Puedes indicar hasta {maximo}.'
    return tuple(resultado[:maximo])


@dataclass(frozen=True)
class DatosPlan:
    nombre: str
    precio: int
    frecuencia_semanas: int
    unidades: int = 1
    descripcion: str = ''
    beneficios: tuple[str, ...] = ()
    # Qué se puede elegir: los productos de estas categorías y estos productos puntuales (ids del catálogo)
    categorias: tuple[str, ...] = ()
    productos: tuple[str, ...] = ()
    envio_gratis: bool = False
    # Además del despacho de la suscripción, todas las compras del suscriptor (exige envio_gratis)
    envio_gratis_compras: bool = False
    descuento: int = 0
    activo: bool = True

    @classmethod
    def desde(cls, datos: dict) -> 'DatosPlan':
        errores = {}
        nombre = _texto(datos.get('nombre'))
        if not nombre:
            errores['nombre'] = 'El nombre es obligatorio.'
        elif len(nombre) > LARGO_NOMBRE_PLAN:
            errores['nombre'] = f'Puede tener hasta {LARGO_NOMBRE_PLAN} caracteres.'
        descripcion = str(datos.get('descripcion') or '').strip()
        if len(descripcion) > LARGO_DESCRIPCION_PLAN:
            errores['descripcion'] = f'Puede tener hasta {LARGO_DESCRIPCION_PLAN} caracteres.'
        precio = _entero(datos.get('precio'), 'precio', errores, 1, PRECIO_MAXIMO)
        frecuencia = _entero(datos.get('frecuencia_semanas'), 'frecuencia_semanas', errores,
                             FRECUENCIA_MINIMA_SEMANAS, FRECUENCIA_MAXIMA_SEMANAS)
        unidades = _entero(datos.get('unidades'), 'unidades', errores, 1, UNIDADES_MAXIMAS, por_defecto=1)
        descuento = _entero(datos.get('descuento'), 'descuento', errores, 0, DESCUENTO_MAXIMO, por_defecto=0)
        beneficios = _lista_textos(datos.get('beneficios'), 'beneficios', errores, MAX_BENEFICIOS, LARGO_BENEFICIO)
        categorias = _lista_textos(datos.get('categorias'), 'categorias', errores, MAX_ELEGIBLES)
        productos = _lista_textos(datos.get('productos'), 'productos', errores, MAX_ELEGIBLES)
        if not categorias and not productos and 'categorias' not in errores and 'productos' not in errores:
            errores['productos'] = 'Elige al menos una categoría o un producto que el cliente pueda recibir.'
        envio_gratis = bool(datos.get('envio_gratis'))
        envio_gratis_compras = bool(datos.get('envio_gratis_compras'))
        if envio_gratis_compras and not envio_gratis:
            errores['envio_gratis_compras'] = 'Para dar envío gratis en todas sus compras, activa primero el envío ' \
                                              'gratis de la suscripción.'
        if errores:
            raise PlanInvalido(errores)
        return cls(nombre=nombre, precio=precio, frecuencia_semanas=frecuencia, unidades=unidades,
                   descripcion=descripcion, beneficios=beneficios, categorias=categorias, productos=productos,
                   envio_gratis=envio_gratis, envio_gratis_compras=envio_gratis_compras, descuento=descuento,
                   activo=bool(datos.get('activo', True)))

    def admite(self, producto_id: str, categoria: str) -> bool:
        """Si el cliente puede elegir ese producto (por su id o su categoría, sin distinguir mayúsculas)."""
        if str(producto_id) in self.productos:
            return True
        clave = _texto(categoria).lower()
        return bool(clave) and clave in {c.lower() for c in self.categorias}


def frecuencia_legible(semanas: int) -> str:
    """'Cada semana', 'Cada 2 semanas', 'Cada 4 semanas'."""
    return 'Cada semana' if semanas == 1 else f'Cada {semanas} semanas'
