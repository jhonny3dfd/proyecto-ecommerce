"""Couriers (RF-02.3): cotizar, comunas, sucursales, orden de transporte, etiqueta y seguimiento.

Cada courier (Chilexpress, Starken…) es un adaptador del puerto `Courier`. El núcleo no sabe cuál es: los toma del
puerto `Couriers`, que entrega los que la tienda tiene activos (con sus llaves cargadas en el panel).
"""

from abc import ABC, abstractmethod
from decimal import Decimal

from ecommerce.application.ventas import TransportistaOrdenes
from ecommerce.domain.logistica import (
    CampoCredencial, CotizacionEnvio, CourierNoDisponible, CredencialesCourier, EnvioSolicitado, ErrorOrdenTransporte,
    Paquete, SinCobertura, Sucursal,
)


class CourierNoActivo(Exception):
    """El courier pedido no existe o la tienda no lo tiene activo."""


class Courier(TransportistaOrdenes):
    """Puerto de salida: un courier con sus llaves ya cargadas.

    Las consultas lanzan SinCobertura (la comuna no la atiende) o CourierNoDisponible (no respondió bien);
    la orden de transporte lanza ErrorOrdenTransporte, como pide TransportistaOrdenes.
    """

    codigo: str = ''
    nombre: str = ''
    # Las llaves que pide en el panel, en su orden
    CAMPOS: tuple[CampoCredencial, ...] = ()
    # Si el comprador puede retirar en una oficina del courier
    con_sucursales: bool = False
    # Para el panel: dónde se obtienen sus llaves y cómo se usan
    ayuda: str = ''

    @abstractmethod
    def comunas(self) -> list[str]:
        """Nombres de las comunas que atiende."""

    @abstractmethod
    def cotizar(self, origen: str, destino: str, paquete: Paquete) -> CotizacionEnvio:
        raise NotImplementedError

    @abstractmethod
    def sucursales(self, comuna: str) -> list[Sucursal]:
        raise NotImplementedError

    @abstractmethod
    def etiqueta(self, numero_ot: str) -> str:
        """La etiqueta de la orden de transporte, en base64."""

    @abstractmethod
    def consultar_estado(self, codigo_seguimiento: str) -> str:
        """RF-02.4: el estado en la línea de tiempo estándar (En origen → En tránsito → En reparto → Entregado)."""


class Couriers(ABC):
    """Puerto de salida: los couriers que la tienda puede usar."""

    @abstractmethod
    def activos(self) -> list[Courier]:
        """Los que tienen sus llaves completas, en un orden fijo."""

    @abstractmethod
    def obtener(self, codigo: str, solo_activos: bool = True) -> Courier:
        """Lanza CourierNoActivo si no existe o, con solo_activos, si no está activo."""


class RepositorioCredencialesCourier(ABC):
    """Puerto de salida: las llaves de cada courier, guardadas cifradas."""

    @abstractmethod
    def obtener(self, codigo: str, campos: tuple[CampoCredencial, ...]) -> CredencialesCourier:
        """Devuelve credenciales vacías si aún no se configuraron."""

    @abstractmethod
    def guardar(self, codigo: str, credenciales: CredencialesCourier) -> None:
        raise NotImplementedError


class CotizarEnvio:
    """RF-02.3: la tarifa de envío de uno o de todos los couriers activos.

    - Con un proveedor, sus errores llegan tal cual (el checkout cobra exactamente esa opción).
    - Sin proveedor, un courier caído o sin cobertura no tapa a los demás; si ninguno cotiza, se informa
      SinCobertura cuando todos dijeron que no llegan, y CourierNoDisponible en otro caso.
    """

    def __init__(self, couriers: Couriers):
        self.couriers = couriers

    def ejecutar(self, origen: str, destino: str, paquete: Paquete, proveedor: str | None = None) -> list[CotizacionEnvio]:
        if proveedor:
            return [self.couriers.obtener(proveedor).cotizar(origen, destino, paquete)]
        activos = self.couriers.activos()
        if not activos:
            raise CourierNoActivo()
        opciones, sin_cobertura = [], []
        for courier in activos:
            try:
                opciones.append(courier.cotizar(origen, destino, paquete))
            except SinCobertura as error:
                sin_cobertura.append(error)
            except CourierNoDisponible:
                continue
        if opciones:
            return opciones
        if len(sin_cobertura) == len(activos):
            raise sin_cobertura[0]
        raise CourierNoDisponible('Ningún courier pudo cotizar el envío.')

    def precio(self, origen: str, destino: str, paquete: Paquete, proveedor: str) -> Decimal:
        """El costo que se cobra en el checkout: el del courier elegido, cotizado en el servidor."""
        return Decimal(self.ejecutar(origen, destino, paquete, proveedor)[0].precio)


class ComunasConCobertura:
    """Las comunas que atiende al menos un courier activo; uno caído no deja sin comunas a los demás."""

    def __init__(self, couriers: Couriers):
        self.couriers = couriers

    def ejecutar(self) -> list[str]:
        activos = self.couriers.activos()
        if not activos:
            raise CourierNoActivo()
        comunas, respondieron = set(), False
        for courier in activos:
            try:
                comunas.update(courier.comunas())
                respondieron = True
            except CourierNoDisponible:
                continue
        if not respondieron:
            raise CourierNoDisponible('Servicio de coberturas no disponible en este momento.')
        return sorted(comunas)


class ConfigurarCourier:
    """RNF-03: el admin carga o reemplaza las llaves de un courier desde el panel.

    Se puede guardar incompleto; sin las llaves obligatorias el courier no se ofrece en el checkout.
    """

    def __init__(self, repositorio: RepositorioCredencialesCourier, couriers: Couriers):
        self.repositorio = repositorio
        self.couriers = couriers

    def ejecutar(self, codigo: str, datos: dict[str, str]) -> CredencialesCourier:
        campos = self.couriers.obtener(codigo, solo_activos=False).CAMPOS
        credenciales = self.repositorio.obtener(codigo, campos).con_cambios(datos)
        self.repositorio.guardar(codigo, credenciales)
        return credenciales


class TransportistaSegunProveedor(TransportistaOrdenes):
    """La orden de transporte la genera el courier que eligió el comprador (GenerarOrdenTransporte)."""

    def __init__(self, couriers: Couriers):
        self.couriers = couriers

    def generar_orden_transporte(self, envio: EnvioSolicitado) -> str:
        try:
            courier = self.couriers.obtener(envio.proveedor)
        except CourierNoActivo as error:
            raise ErrorOrdenTransporte(f'El courier {envio.proveedor} no está activo en la tienda.') from error
        return courier.generar_orden_transporte(envio)
