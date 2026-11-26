"""Pagos en línea (RF-02.2): iniciar el pago en la pasarela y aplicar su resultado a la orden.

Cada pasarela (Transbank, Mercado Pago…) es un adaptador del puerto `PasarelaPago` que traduce los estados de su
proveedor a `EstadoPago`. Qué se hace con un pago aprobado, rechazado o devuelto es igual para todas.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from ecommerce.application.ventas import MOTIVO_PAGO_ANULADO, MOTIVO_PAGO_RECHAZADO, ConfirmarPago, ResultadoPago
from ecommerce.domain.medios_pago import EstadoPago

MOTIVO_PAGO_REEMBOLSADO = 'La pasarela informó que devolvió el pago {referencia}'


class ErrorPasarelaPago(Exception):
    """La pasarela no respondió bien o le faltan sus llaves."""


class FirmaAvisoInvalida(Exception):
    """El aviso (webhook) no trae una firma válida de la pasarela."""


@dataclass(frozen=True)
class PagoIniciado:
    # Con la que la pasarela identifica el pago (token de Transbank, preferencia de Mercado Pago)
    referencia: str
    # Adonde se envía al comprador para pagar
    url_pago: str


@dataclass(frozen=True)
class PagoConsultado:
    referencia: str
    # Vacío si la pasarela no informa a qué orden pertenece
    orden_id: str
    estado: EstadoPago
    # None si la pasarela no lo informa; si viene, ConfirmarPago lo compara con el total de la orden
    monto: Decimal | None = None


class PasarelaPago(ABC):
    """Puerto de salida: una pasarela de pago con sus llaves ya cargadas. Lanza ErrorPasarelaPago."""

    # Para los mensajes al comprador ("No se pudo iniciar el pago con <nombre>")
    nombre: str = ''

    @abstractmethod
    def iniciar(self, orden_id: str, monto: Decimal, url_retorno: str, url_aviso: str = '') -> PagoIniciado:
        """Crea el pago. url_retorno: adonde vuelve el comprador; url_aviso: adonde avisa la pasarela (webhook)."""

    @abstractmethod
    def resultado(self, referencia: str) -> PagoConsultado:
        """El pago según la pasarela (en Transbank, además lo confirma)."""


class PasarelaConAvisos(PasarelaPago):
    """Una pasarela que avisa los pagos a la tienda con un webhook firmado."""

    @abstractmethod
    def aviso_autentico(self, firma: str, id_peticion: str, referencia: str) -> bool:
        raise NotImplementedError


class PasarelaConBusqueda(PasarelaPago):
    """Una pasarela que permite buscar los pagos, para poner al día las órdenes cuyo aviso no llegó."""

    @abstractmethod
    def pagos_de_orden(self, orden_id: str) -> list[PagoConsultado]:
        """Los intentos de pago de la orden, del más reciente al más antiguo."""

    @abstractmethod
    def pagos_recientes(self, limite: int) -> list[PagoConsultado]:
        """Los últimos pagos de la tienda, del más reciente al más antiguo."""


class AplicarResultadoPago:
    """RF-02.2: aplica a la orden lo que informó la pasarela, igual para todas.

    Aprobado confirma el pago (idempotente, ver ConfirmarPago); rechazado o anulado cancela la orden pendiente;
    devuelto deja en revisión una orden ya pagada; pendiente no cambia nada.
    """

    def __init__(self, confirmar_pago: ConfirmarPago):
        self.confirmar_pago = confirmar_pago

    def ejecutar(self, pago: PagoConsultado) -> ResultadoPago:
        if not pago.orden_id:
            return ResultadoPago.NO_ENCONTRADA
        if pago.estado == EstadoPago.APROBADO:
            return self.confirmar_pago.aprobar(pago.orden_id, monto_pagado=pago.monto)
        if pago.estado == EstadoPago.RECHAZADO:
            self.confirmar_pago.rechazar(pago.orden_id, MOTIVO_PAGO_RECHAZADO)
            return ResultadoPago.RECHAZADO
        if pago.estado == EstadoPago.ANULADO:
            self.confirmar_pago.rechazar(pago.orden_id, MOTIVO_PAGO_ANULADO)
            return ResultadoPago.CANCELADO
        if pago.estado == EstadoPago.REEMBOLSADO:
            return self.confirmar_pago.reembolsado(
                pago.orden_id, MOTIVO_PAGO_REEMBOLSADO.format(referencia=pago.referencia))
        return ResultadoPago.PENDIENTE


class ProcesarAvisoPago:
    """Aviso (webhook) de la pasarela: se verifica su firma y el resultado se consulta a la pasarela, nunca se toma
    del aviso. Lanza FirmaAvisoInvalida o ErrorPasarelaPago."""

    def __init__(self, pasarela: PasarelaConAvisos, aplicar: AplicarResultadoPago):
        self.pasarela = pasarela
        self.aplicar = aplicar

    def ejecutar(self, *, firma: str, id_peticion: str, referencia: str, es_pago: bool = True) -> ResultadoPago:
        if not self.pasarela.aviso_autentico(firma, id_peticion, referencia):
            raise FirmaAvisoInvalida('Firma del aviso inválida.')
        if not es_pago:
            return ResultadoPago.IGNORADO
        return self.aplicar.ejecutar(self.pasarela.resultado(referencia))


ESTADOS_FALLIDOS = (EstadoPago.RECHAZADO, EstadoPago.ANULADO, EstadoPago.REEMBOLSADO)


class ConciliarPagoOrden:
    """RF-02.2: pone al día una orden pendiente con sus intentos de pago en la pasarela (ej. si el aviso no llegó).

    Un comprador puede intentar varias veces con la misma orden. Gana un intento aprobado; si no hay, pero alguno
    sigue en proceso, la orden sigue pendiente; solo si todos fallaron se rechaza o anula. El intento elegido se
    vuelve a consultar a la pasarela y debe ser de esta orden.
    """

    def __init__(self, pasarela: PasarelaConBusqueda, aplicar: AplicarResultadoPago):
        self.pasarela = pasarela
        self.aplicar = aplicar

    def _confirmado(self, intento: PagoConsultado, orden_id) -> PagoConsultado | None:
        pago = self.pasarela.resultado(intento.referencia)
        return pago if str(pago.orden_id or '').strip() == str(orden_id) else None

    def ejecutar(self, orden_id) -> ResultadoPago:
        intentos = self.pasarela.pagos_de_orden(str(orden_id))

        aprobado = next((p for p in intentos if p.estado == EstadoPago.APROBADO), None)
        if aprobado:
            pago = self._confirmado(aprobado, orden_id)
            if pago and pago.estado == EstadoPago.APROBADO:
                return self.aplicar.ejecutar(pago)

        if any(p.estado == EstadoPago.PENDIENTE for p in intentos):
            return ResultadoPago.PENDIENTE

        fallido = next((p for p in intentos if p.estado in ESTADOS_FALLIDOS), None)
        if fallido:
            pago = self._confirmado(fallido, orden_id)
            if pago:
                return self.aplicar.ejecutar(pago)
        return ResultadoPago.PENDIENTE
