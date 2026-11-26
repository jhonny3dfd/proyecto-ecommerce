"""Medios de pago configurables por el emprendedor (RN-02), independientes de Django."""

from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
import re

from .empresa import normalizar_rut

# Datos de la transferencia que el comprador copia para pagar: uno mal escrito hace rebotar el pago
FORMATO_RUT = 'rut'
FORMATO_CORREO = 'correo'
FORMATO_NUMERO_CUENTA = 'numero_cuenta'
_CORREO = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
_NUMERO_CUENTA = re.compile(r'^\d[\d -]{2,28}\d$')


def normalizar_formato(formato: str, valor: str) -> str:
    """El valor listo para guardar; ValueError con el mensaje para el admin si no tiene el formato."""
    if formato == FORMATO_RUT:
        return normalizar_rut(valor)
    if formato == FORMATO_CORREO:
        if not _CORREO.match(valor):
            raise ValueError('Escribe un correo válido, por ejemplo pagos@mitienda.cl.')
        return valor.lower()
    if formato == FORMATO_NUMERO_CUENTA:
        if not _NUMERO_CUENTA.match(valor):
            raise ValueError('Usa solo los números de la cuenta (pueden ir separados por guiones o espacios).')
        return ' '.join(valor.split())
    return valor


class CodigoMedioPago(StrEnum):
    TRANSBANK = 'TRANSBANK'
    MERCADO_PAGO = 'MERCADO_PAGO'
    TRANSFERENCIA = 'TRANSFERENCIA'


class EstadoPago(StrEnum):
    """Resultado de un pago en línea, igual para toda pasarela: cada adaptador traduce los estados de la suya."""

    APROBADO = 'APROBADO'
    PENDIENTE = 'PENDIENTE'
    RECHAZADO = 'RECHAZADO'
    # El comprador lo anuló o la pasarela lo canceló antes de cobrar
    ANULADO = 'ANULADO'
    # Ya cobrado y después devuelto (reembolso o contracargo)
    REEMBOLSADO = 'REEMBOLSADO'


class MedioPagoNoDisponible(Exception):
    """RN-02: el comprador eligió un medio que la tienda no tiene habilitado y configurado."""

    def __init__(self, codigo):
        self.codigo = codigo
        super().__init__('Ese medio de pago no está disponible en esta tienda.')


class DatosMedioPagoInvalidos(Exception):
    def __init__(self, errores: dict[str, str]):
        self.errores = errores
        super().__init__('; '.join(f'{campo}: {error}' for campo, error in errores.items()))


@dataclass(frozen=True)
class CampoMedioPago:
    nombre: str
    etiqueta: str
    # Credencial: se guarda cifrada y nunca se devuelve completa
    secreto: bool = False
    # Valores permitidos (vacío = texto libre)
    opciones: tuple[str, ...] = ()
    # Obligatorio solo si otro campo tiene cierto valor, ej. ('ambiente', 'PRODUCCION'); None = siempre
    obligatorio_si: tuple[str, str] | None = None
    obligatorio: bool = True
    # False para la configuración interna del medio (ej. activar Linkify): el admin la ve, el comprador no
    para_comprador: bool = True
    # Cómo se valida el texto (FORMATO_*); vacío = texto libre
    formato: str = ''

    def es_obligatorio(self, datos: dict) -> bool:
        if not self.obligatorio:
            return False
        if self.obligatorio_si is None:
            return True
        campo, valor = self.obligatorio_si
        return datos.get(campo) == valor


@dataclass(frozen=True)
class DefinicionMedioPago:
    codigo: CodigoMedioPago
    nombre: str
    campos: tuple[CampoMedioPago, ...]
    # False mientras el checkout no sepa cobrar con este medio: se pueden cargar sus datos, pero no se ofrece
    integracion_lista: bool = True

    def campo(self, nombre) -> CampoMedioPago | None:
        return next((c for c in self.campos if c.nombre == nombre), None)


AMBIENTE_INTEGRACION = 'INTEGRACION'
AMBIENTE_PRODUCCION = 'PRODUCCION'

# Horas para pagar una transferencia: las elige cada tienda (decidido el 2026-10-19); sin elegir, 48
PLAZOS_PAGO_TRANSFERENCIA = ('12', '24', '48', '72')
PLAZO_PAGO_TRANSFERENCIA_POR_DEFECTO = timedelta(hours=48)

# Orden en que se muestran al comprador y en el panel. Un medio nuevo (ej. Linkify) se agrega aquí.
MEDIOS_PAGO = (
    DefinicionMedioPago(CodigoMedioPago.TRANSBANK, 'Transbank Webpay Plus', (
        # En integración se usan las llaves públicas de prueba de Transbank: no hacen falta credenciales
        CampoMedioPago('ambiente', 'Ambiente', opciones=(AMBIENTE_INTEGRACION, AMBIENTE_PRODUCCION)),
        CampoMedioPago('commerce_code', 'Código de comercio',
                       obligatorio_si=('ambiente', AMBIENTE_PRODUCCION)),
        CampoMedioPago('api_key', 'API key (llave secreta)', secreto=True,
                       obligatorio_si=('ambiente', AMBIENTE_PRODUCCION)),
    )),
    DefinicionMedioPago(CodigoMedioPago.MERCADO_PAGO, 'Mercado Pago', (
        CampoMedioPago('access_token', 'Access token', secreto=True),
        # Valida la firma x-signature de las notificaciones (webhooks)
        CampoMedioPago('webhook_secret', 'Clave secreta de notificaciones', secreto=True),
    ), integracion_lista=True),
    DefinicionMedioPago(CodigoMedioPago.TRANSFERENCIA, 'Transferencia bancaria', (
        # Datos que ve el comprador para transferir: no son secretos
        CampoMedioPago('banco', 'Banco'),
        CampoMedioPago('tipo_cuenta', 'Tipo de cuenta',
                       opciones=('Cuenta corriente', 'Cuenta vista', 'Cuenta de ahorro')),
        CampoMedioPago('numero_cuenta', 'Número de cuenta', formato=FORMATO_NUMERO_CUENTA),
        CampoMedioPago('rut_titular', 'RUT del titular', formato=FORMATO_RUT),
        CampoMedioPago('nombre_titular', 'Nombre del titular'),
        CampoMedioPago('email', 'Correo para el comprobante', formato=FORMATO_CORREO),
        # Opcional para no dejar incompletas las tiendas que ya tenían la transferencia configurada
        CampoMedioPago('plazo_pago_horas', 'Plazo para pagar (si no eliges, 48 horas)',
                       opciones=PLAZOS_PAGO_TRANSFERENCIA, obligatorio=False, para_comprador=False),

        # Linkify valida las transferencias automáticamente; es opcional, así que una tienda sin Linkify
        # igual ofrece la transferencia
        CampoMedioPago('verificar_con_linkify', 'Verificar automáticamente con Linkify',
                       opciones=('No', 'Sí'), obligatorio=False, para_comprador=False),
        CampoMedioPago('linkify_secret', 'Llave secreta de Linkify', secreto=True,
                       obligatorio_si=('verificar_con_linkify', 'Sí')),
    )),
)

def plazo_pago_transferencia(medio: 'MedioPagoConfigurado') -> timedelta:
    """El plazo que eligió la tienda para pagar una transferencia; sin elegir, 48 horas."""
    horas = medio.datos.get('plazo_pago_horas')
    return timedelta(hours=int(horas)) if horas in PLAZOS_PAGO_TRANSFERENCIA else PLAZO_PAGO_TRANSFERENCIA_POR_DEFECTO


def definicion_medio(codigo) -> DefinicionMedioPago:
    codigo = CodigoMedioPago(codigo)
    return next(d for d in MEDIOS_PAGO if d.codigo == codigo)


MASCARA = '••••'


def enmascarar(valor: str) -> str:
    """Una credencial solo se muestra con sus últimos 4 caracteres."""
    if not valor:
        return ''
    return MASCARA + valor[-4:] if len(valor) > 8 else MASCARA


@dataclass(frozen=True)
class MedioPagoConfigurado:
    codigo: CodigoMedioPago
    habilitado: bool = False
    # Valores reales, incluidas las credenciales: no deben salir del backend
    datos: dict[str, str] = field(default_factory=dict)

    @property
    def definicion(self) -> DefinicionMedioPago:
        return definicion_medio(self.codigo)

    @property
    def faltantes(self) -> list[str]:
        """Campos obligatorios sin valor, en el orden de la definición."""
        return [c.nombre for c in self.definicion.campos
                if c.es_obligatorio(self.datos) and not self.datos.get(c.nombre)]

    @property
    def disponible(self) -> bool:
        """RN-02: se ofrece al comprador solo si está habilitado, tiene todos sus datos obligatorios y el
        checkout ya sabe cobrar con él."""
        return self.definicion.integracion_lista and self.habilitado and not self.faltantes

    def datos_para_comprador(self) -> dict[str, str]:
        """Lo que el comprador necesita para pagar (ej. los datos bancarios): nunca las credenciales."""
        return {c.nombre: self.datos[c.nombre] for c in self.definicion.campos
                if not c.secreto and c.para_comprador and self.datos.get(c.nombre)}

    def datos_visibles(self) -> dict[str, str]:
        """Para el panel del admin: las credenciales van enmascaradas."""
        return {c.nombre: enmascarar(self.datos.get(c.nombre, '')) if c.secreto else self.datos.get(c.nombre, '')
                for c in self.definicion.campos}


def aplicar_cambios(actual: MedioPagoConfigurado, habilitado: bool,
                    datos_nuevos: dict[str, str]) -> MedioPagoConfigurado:
    """Combina lo que envía el panel con lo guardado.

    - Una credencial que llega enmascarada (tal como el panel la mostró) o que no llega, se conserva.
    - Un texto vacío borra el valor.
    """
    definicion = actual.definicion
    errores = {nombre: 'Campo desconocido.' for nombre in datos_nuevos if definicion.campo(nombre) is None}
    datos = dict(actual.datos)
    for campo in definicion.campos:
        if campo.nombre not in datos_nuevos:
            continue
        valor = str(datos_nuevos[campo.nombre] or '').strip()
        if campo.secreto and valor and valor == enmascarar(actual.datos.get(campo.nombre, '')):
            continue
        if valor and campo.opciones and valor not in campo.opciones:
            errores[campo.nombre] = f"Debe ser una de: {', '.join(campo.opciones)}."
            continue
        if valor and campo.formato:
            try:
                valor = normalizar_formato(campo.formato, valor)
            except ValueError as error:
                errores[campo.nombre] = str(error)
                continue
        if valor:
            datos[campo.nombre] = valor
        else:
            datos.pop(campo.nombre, None)
    if errores:
        raise DatosMedioPagoInvalidos(errores)
    return MedioPagoConfigurado(actual.codigo, bool(habilitado), datos)