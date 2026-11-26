"""Casos de uso de los medios de pago: configurarlos desde el panel y decidir cuáles se ofrecen (RN-02)."""

from abc import ABC, abstractmethod

from ecommerce.domain.medios_pago import (
    MEDIOS_PAGO, CodigoMedioPago, MedioPagoConfigurado, MedioPagoNoDisponible, aplicar_cambios,
)


class RepositorioMediosPago(ABC):
    """Puerto de salida: configuración de cada medio de pago (las credenciales se guardan cifradas)."""

    @abstractmethod
    def obtener(self, codigo: CodigoMedioPago) -> MedioPagoConfigurado:
        """Devuelve el medio sin configurar (deshabilitado y sin datos) si aún no existe."""
        raise NotImplementedError

    def obtener_varios(self, codigos: list[CodigoMedioPago]) -> list[MedioPagoConfigurado]:
        """Lectura en orden; los adaptadores existentes conservan su compatibilidad."""
        return [self.obtener(codigo) for codigo in codigos]

    @abstractmethod
    def guardar(self, medio: MedioPagoConfigurado) -> None:
        raise NotImplementedError


class ConfigurarMedioPago:
    """RN-02: el admin habilita un medio y carga sus datos desde el panel.

    Se puede guardar incompleto; mientras le falten datos obligatorios no se ofrece al comprador.
    """

    def __init__(self, repositorio: RepositorioMediosPago):
        self.repositorio = repositorio

    def ejecutar(self, codigo, habilitado: bool, datos: dict[str, str]) -> MedioPagoConfigurado:
        medio = aplicar_cambios(self.repositorio.obtener(CodigoMedioPago(codigo)), habilitado, datos)
        self.repositorio.guardar(medio)
        return medio


class MediosPagoDisponibles:
    """RN-02: solo los medios habilitados y configurados, en el orden definido en el dominio."""

    def __init__(self, repositorio: RepositorioMediosPago):
        self.repositorio = repositorio

    def listar(self) -> list[MedioPagoConfigurado]:
        return self.repositorio.obtener_varios([d.codigo for d in MEDIOS_PAGO])

    def disponibles(self) -> list[CodigoMedioPago]:
        return [medio.codigo for medio in self.listar() if medio.disponible]

    def exigir(self, codigo) -> MedioPagoConfigurado:
        """Para el checkout y las pasarelas: el medio con sus datos, o MedioPagoNoDisponible."""
        try:
            medio = self.repositorio.obtener(CodigoMedioPago(codigo))
        except ValueError:
            raise MedioPagoNoDisponible(codigo) from None
        if not medio.disponible:
            raise MedioPagoNoDisponible(codigo)
        return medio
