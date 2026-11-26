"""Cotizaciones y encargos: productos personalizados, hechos a pedido o en cantidad, que no pasan por el carrito.

Independiente de Django. La tienda responde cada solicitud por su cuenta (correo o teléfono) y registra en el panel
en qué quedó.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from .empresa import DatosEmpresa, DatosEmpresaInvalidos
from .imagenes import ImagenProcesada
from .ventas import NombreInvalido, TelefonoInvalido, normalizar_nombre_persona, normalizar_telefono_chile

CANTIDAD_MAXIMA = 100_000
# Fotos de la idea del cliente: las ve solo la tienda (se guardan fuera de los archivos públicos)
MAX_FOTOS_COTIZACION = 3


class EstadoCotizacion(StrEnum):
    NUEVA = 'NUEVA'
    RESPONDIDA = 'RESPONDIDA'
    ACEPTADA = 'ACEPTADA'
    DESCARTADA = 'DESCARTADA'


ETIQUETAS_ESTADO_COTIZACION = {
    EstadoCotizacion.NUEVA: 'Nueva',
    EstadoCotizacion.RESPONDIDA: 'Respondida',
    EstadoCotizacion.ACEPTADA: 'Aceptada',
    EstadoCotizacion.DESCARTADA: 'Descartada',
}


class CotizacionInvalida(ValueError):
    """Errores por campo; los de la empresa van anidados en 'empresa'."""

    def __init__(self, errores: dict):
        self.errores = errores
        super().__init__('; '.join(f'{campo}: {error}' for campo, error in errores.items()))


@dataclass(frozen=True)
class SolicitudCotizacion:
    nombre: str
    correo: str
    telefono: str
    cantidad: int
    # Del catálogo (id y nombre al momento de cotizar) o descrito por el cliente; al menos uno de los dos
    producto_id: str = ''
    producto_nombre: str = ''
    descripcion: str = ''
    personalizacion: str = ''
    fecha_requerida: date | None = None
    # Solo si cotiza como empresa (para la factura)
    empresa: DatosEmpresa | None = None
    # Ya validadas y limpias (formato, tamaño y sin los datos de la cámara)
    fotos: tuple[ImagenProcesada, ...] = ()

    @classmethod
    def desde(cls, datos: dict, hoy: date, producto_nombre: str = '',
              fotos: tuple[ImagenProcesada, ...] = ()) -> 'SolicitudCotizacion':
        """`producto_nombre` lo resuelve quien llama a partir de `producto_id` (vacío si no existe)."""
        texto = {campo: str(datos.get(campo) or '').strip()
                 for campo in ('nombre', 'correo', 'telefono', 'producto_id', 'descripcion', 'personalizacion')}
        errores = {}
        for campo in ('nombre', 'correo', 'telefono'):
            if not texto[campo]:
                errores[campo] = 'Este dato es obligatorio.'
        if texto['nombre']:
            try:
                texto['nombre'] = normalizar_nombre_persona(texto['nombre'])
            except NombreInvalido as error:
                errores['nombre'] = str(error)
        if texto['telefono']:
            try:
                texto['telefono'] = normalizar_telefono_chile(texto['telefono'])
            except TelefonoInvalido as error:
                errores['telefono'] = str(error)

        if texto['producto_id'] and not producto_nombre:
            errores['producto_id'] = 'Ese producto ya no está disponible. Elige otro o descríbelo.'
        elif not texto['producto_id'] and not texto['descripcion']:
            errores['descripcion'] = 'Elige un producto del catálogo o describe lo que necesitas.'

        cantidad = datos.get('cantidad')
        if not isinstance(cantidad, int) or isinstance(cantidad, bool) or not 1 <= cantidad <= CANTIDAD_MAXIMA:
            errores['cantidad'] = f'Indica una cantidad entre 1 y {CANTIDAD_MAXIMA:,}.'.replace(',', '.')

        fecha = datos.get('fecha_requerida')
        if fecha is not None and fecha < hoy:
            errores['fecha_requerida'] = 'La fecha no puede estar en el pasado.'

        empresa = None
        if datos.get('como_empresa'):
            try:
                empresa = DatosEmpresa.desde(datos.get('empresa') or {})
            except DatosEmpresaInvalidos as error:
                errores['empresa'] = error.errores

        if len(fotos) > MAX_FOTOS_COTIZACION:
            errores['fotos'] = f'Puedes adjuntar hasta {MAX_FOTOS_COTIZACION} fotos.'

        if errores:
            raise CotizacionInvalida(errores)
        return cls(
            nombre=texto['nombre'], correo=texto['correo'], telefono=texto['telefono'], cantidad=cantidad,
            producto_id=texto['producto_id'], producto_nombre=producto_nombre if texto['producto_id'] else '',
            descripcion=texto['descripcion'], personalizacion=texto['personalizacion'], fecha_requerida=fecha,
            empresa=empresa, fotos=tuple(fotos),
        )
