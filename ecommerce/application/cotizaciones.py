"""Casos de uso de cotizaciones y encargos: el cliente pide una cotización y la tienda registra en qué quedó."""

from abc import ABC, abstractmethod
from datetime import date

from ecommerce.domain.cotizaciones import EstadoCotizacion, SolicitudCotizacion


class RepositorioCotizaciones(ABC):
    """Puerto de salida: dónde se guardan las solicitudes de cotización."""

    @abstractmethod
    def guardar(self, solicitud: SolicitudCotizacion) -> int:
        """Guarda la solicitud como Nueva, con sus fotos donde solo la tienda las ve, y devuelve su número."""
        raise NotImplementedError

    @abstractmethod
    def cambiar_estado(self, cotizacion_id: int, estado: EstadoCotizacion) -> bool:
        """False si la cotización no existe."""
        raise NotImplementedError


class NotificadorCotizaciones(ABC):
    """Puerto de salida: avisa a la tienda de la solicitud y le confirma al cliente que llegó."""

    @abstractmethod
    def notificar_nueva(self, cotizacion_id: int) -> None:
        raise NotImplementedError


class NombresProductos(ABC):
    """Puerto de salida: nombre de un producto publicado del catálogo, o None si no existe o no está publicado."""

    @abstractmethod
    def nombre(self, producto_id: str) -> str | None:
        raise NotImplementedError


class FormularioCotizacionDesactivado(Exception):
    def __init__(self):
        super().__init__('Esta tienda no está recibiendo cotizaciones por ahora.')


class CotizacionNoEncontrada(Exception):
    def __init__(self):
        super().__init__('Cotización no encontrada.')


class SolicitarCotizacion:
    """Encargos, productos personalizados y compras en cantidad, para personas o empresas.

    Solo si el admin activó el formulario. El aviso a la tienda y al cliente sale después de guardar.
    """

    def __init__(self, cotizaciones: RepositorioCotizaciones, notificador: NotificadorCotizaciones,
                 productos: NombresProductos):
        self.cotizaciones = cotizaciones
        self.notificador = notificador
        self.productos = productos

    def ejecutar(self, datos: dict, formulario_activo: bool, hoy: date, fotos=()) -> int:
        """`fotos`: hasta MAX_FOTOS_COTIZACION ImagenProcesada, ya validadas por el adaptador de entrada."""
        if not formulario_activo:
            raise FormularioCotizacionDesactivado()
        producto_id = str(datos.get('producto_id') or '').strip()
        nombre_producto = (self.productos.nombre(producto_id) or '') if producto_id else ''
        solicitud = SolicitudCotizacion.desde(datos, hoy, producto_nombre=nombre_producto, fotos=tuple(fotos))
        cotizacion_id = self.cotizaciones.guardar(solicitud)
        self.notificador.notificar_nueva(cotizacion_id)
        return cotizacion_id


class CambiarEstadoCotizacion:
    """La tienda marca la cotización como Respondida, Aceptada o Descartada (o de vuelta en Nueva)."""

    def __init__(self, cotizaciones: RepositorioCotizaciones):
        self.cotizaciones = cotizaciones

    def ejecutar(self, cotizacion_id: int, estado) -> EstadoCotizacion:
        estado = EstadoCotizacion(estado)
        if not self.cotizaciones.cambiar_estado(cotizacion_id, estado):
            raise CotizacionNoEncontrada()
        return estado
