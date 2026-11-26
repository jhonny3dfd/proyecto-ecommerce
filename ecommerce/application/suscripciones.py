"""Suscripciones con entregas recurrentes (pedido de un cliente, opcional): casos de uso y sus puertos.

Cada ciclo es un pedido normal (OrdenCompra) con el precio del plan: se paga con los medios de la tienda, descuenta
stock y se despacha como cualquier compra. ConfirmarPago avisa a AlPagarPedido cuando un pedido pasa de Pendiente a
Pagado, y la suscripción avanza al ciclo siguiente. La tarea diaria (ProcesarCiclos) crea el pedido de cada ciclo
`dias_aviso` días antes de la entrega y cierra los ciclos que no se pagaron.

Las reglas (estados, fechas y planes) viven en ecommerce/domain/suscripciones.py.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
import logging

from ecommerce.domain.logistica import MedidasEnvio
from ecommerce.domain.suscripciones import (
    MOTIVO_CICLO_NO_PAGADO, MOTIVO_CICLO_SALTADO, MOTIVO_PRIMER_PAGO_NO_RECIBIDO, MOTIVO_SUSCRIPCION_CANCELADA,
    MOTIVO_SUSCRIPCION_PAUSADA, AccionNoPermitida, AccionSuscripcion, DatosPlan, EstadoSuscripcion,
    EventoSuscripcion, ciclo_vencido, fecha_al_adelantar, fecha_al_reanudar, fecha_primer_ciclo, siguiente_ciclo,
    validar_accion,
)
from ecommerce.domain.ventas import ESTADOS_PAGADOS, EstadoPedido

logger = logging.getLogger(__name__)


# ---------- Datos que cruzan los puertos ----------

@dataclass(frozen=True)
class PlanRegistrado:
    id: int
    datos: DatosPlan


@dataclass(frozen=True)
class Entrega:
    """Adónde y cómo se entrega, como en el checkout: el proveedor es RETIRO_LOCAL, ENTREGA_COORDINADA o un courier."""

    proveedor_logistico: str
    # Mismo formato que la dirección de un pedido (calle, numero, comuna, region, dpto_casa, codigo_sucursal...)
    direccion: dict = field(default_factory=dict)
    destinatario: str = ''
    telefono: str = ''


@dataclass(frozen=True)
class VarianteElegible:
    producto_id: str
    sku: str
    # Para el pedido y los correos, ej. "Catuai Amarillo - Grano"
    nombre: str
    categoria: str
    stock: int
    # El producto está activo y publicado
    disponible: bool
    medidas: MedidasEnvio = MedidasEnvio()


@dataclass(frozen=True)
class SuscripcionRegistrada:
    id: int
    usuario_id: int
    plan: PlanRegistrado
    estado: EstadoSuscripcion
    producto_id: str
    sku: str
    nombre_producto: str
    entrega: Entrega
    metodo_pago: str
    # Fecha de entrega del próximo ciclo (en una pendiente, la del primero)
    proxima_entrega: date | None


@dataclass(frozen=True)
class PedidoCiclo:
    orden_id: int
    suscripcion_id: int
    ciclo_fecha: date
    estado: EstadoPedido


# ---------- Errores ----------

class ErrorSuscripcion(Exception):
    """Algo que el cliente puede corregir: el mensaje se le muestra tal cual."""


class SuscripcionNoEncontrada(ErrorSuscripcion):
    def __init__(self):
        super().__init__('No encontramos esa suscripción.')


class PlanNoDisponible(ErrorSuscripcion):
    def __init__(self):
        super().__init__('Ese plan ya no está disponible.')


class VarianteNoElegible(ErrorSuscripcion):
    pass


class SinStockSuscripcion(ErrorSuscripcion):
    def __init__(self):
        super().__init__('No hay stock suficiente de esa opción. Elige otra.')


class TerminosNoAceptados(ErrorSuscripcion):
    def __init__(self):
        super().__init__('Debes aceptar los Términos y Condiciones y la Política de Privacidad.')


class CicloYaPagado(ErrorSuscripcion):
    def __init__(self):
        super().__init__('Tu próxima entrega ya está pagada: no se puede saltar. Llegará en la fecha indicada.')


class PedidoEnCurso(ErrorSuscripcion):
    def __init__(self):
        super().__init__('Ya tienes un pedido en curso para tu próxima entrega.')


class DestinatarioIncompleto(ErrorSuscripcion):
    def __init__(self):
        super().__init__('Indica el nombre y el teléfono de quien recibe las entregas.')


class DespachoNoDisponible(ErrorSuscripcion):
    """No se pudo calcular el despacho del ciclo (ej. el courier no respondió)."""


class CompraNoPermitida(ErrorSuscripcion):
    """El medio de pago o la forma de entrega no están disponibles en la tienda."""


# ---------- Puertos ----------

class RepositorioPlanes(ABC):
    @abstractmethod
    def obtener(self, plan_id) -> PlanRegistrado | None:
        raise NotImplementedError


class RepositorioSuscripciones(ABC):
    @abstractmethod
    def crear(self, usuario_id, plan_id, variante: VarianteElegible, entrega: Entrega, metodo_pago: str,
              proxima_entrega: date) -> int:
        raise NotImplementedError

    @abstractmethod
    def obtener(self, suscripcion_id) -> SuscripcionRegistrada | None:
        raise NotImplementedError

    @abstractmethod
    def cambiar_estado(self, suscripcion_id, desde: EstadoSuscripcion, hacia: EstadoSuscripcion,
                       motivo: str = '') -> bool:
        """Atómico: solo si sigue en `desde`; False si no. Registra la fecha de activación o de cancelación."""
        raise NotImplementedError

    @abstractmethod
    def fijar_proxima(self, suscripcion_id, fecha: date) -> None:
        raise NotImplementedError

    @abstractmethod
    def avanzar_si(self, suscripcion_id, ciclo_fecha: date, nueva: date) -> bool:
        """Atómico: mueve la próxima entrega a `nueva` solo si sigue siendo `ciclo_fecha`; False si no. Así un
        aviso repetido o dos procesos a la vez no avanzan dos veces."""
        raise NotImplementedError

    @abstractmethod
    def cambiar_datos(self, suscripcion_id, variante: VarianteElegible | None = None,
                      entrega: Entrega | None = None, metodo_pago: str | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def ids_por_avisar(self, hasta: date) -> list[int]:
        """Activas cuya próxima entrega es hasta esa fecha."""
        raise NotImplementedError

    @abstractmethod
    def ids_con_ciclo_vencido(self, hoy: date) -> list[int]:
        """Activas o pendientes del primer pago cuya próxima entrega ya pasó."""
        raise NotImplementedError

    @abstractmethod
    def planes_activos_de(self, usuario_id) -> list[DatosPlan]:
        """Los planes de las suscripciones activas del cliente (para sus beneficios en el checkout)."""
        raise NotImplementedError


class PedidosSuscripcion(ABC):
    """Los pedidos de los ciclos (OrdenCompra con su suscripción y la fecha del ciclo)."""

    @abstractmethod
    def crear(self, suscripcion: SuscripcionRegistrada, ciclo_fecha: date, costo_envio: Decimal) -> int | None:
        """Crea el pedido Pendiente del ciclo con el precio del plan; None si ese ciclo ya tiene un pedido vigente."""
        raise NotImplementedError

    @abstractmethod
    def del_ciclo(self, suscripcion_id, ciclo_fecha: date) -> PedidoCiclo | None:
        """El pedido vigente (no cancelado) de ese ciclo."""
        raise NotImplementedError

    @abstractmethod
    def pendientes(self, suscripcion_id) -> list[PedidoCiclo]:
        raise NotImplementedError

    @abstractmethod
    def ciclo_de(self, orden_id) -> PedidoCiclo | None:
        """Si el pedido es el de un ciclo de una suscripción."""
        raise NotImplementedError

    @abstractmethod
    def cancelar(self, orden_id, motivo: str) -> bool:
        """Cancela el pedido solo si sigue Pendiente (no se toca uno ya pagado)."""
        raise NotImplementedError


class CatalogoSuscripciones(ABC):
    @abstractmethod
    def variante(self, producto_id: str, sku: str) -> VarianteElegible | None:
        raise NotImplementedError


class CotizadorDespacho(ABC):
    @abstractmethod
    def costo(self, suscripcion: SuscripcionRegistrada) -> Decimal:
        """Lo que cuesta despachar un ciclo con su forma de entrega. Lanza DespachoNoDisponible."""
        raise NotImplementedError


class ReglasCompra(ABC):
    """Lo que la tienda tiene habilitado (RN-02, RF-02.3), las mismas reglas del checkout."""

    @abstractmethod
    def validar(self, metodo_pago: str, entrega: Entrega) -> None:
        """Lanza CompraNoPermitida con el motivo."""
        raise NotImplementedError


class NotificadorSuscripciones(ABC):
    @abstractmethod
    def notificar(self, suscripcion_id, evento: EventoSuscripcion, orden_id=None) -> None:
        """RF-04.2: después del commit."""
        raise NotImplementedError


# ---------- Casos de uso ----------

def _validar_variante(plan: DatosPlan, variante: VarianteElegible | None) -> VarianteElegible:
    """RN-03: solo variantes de productos elegibles del plan, disponibles y con stock para una entrega."""
    if variante is None or not variante.disponible:
        raise VarianteNoElegible('Ese producto no está disponible.')
    if not plan.admite(variante.producto_id, variante.categoria):
        raise VarianteNoElegible('Ese producto no es parte del plan.')
    if variante.stock < plan.unidades:
        raise SinStockSuscripcion()
    return variante


def _validar_destinatario(entrega: Entrega) -> None:
    """RF-02.3 (decidido el 2026-10-13): como en el checkout, cada entrega lleva el nombre y el teléfono de quien
    recibe; los usan la orden de transporte, el panel y los correos."""
    if not entrega.destinatario.strip() or not entrega.telefono.strip():
        raise DestinatarioIncompleto()


@dataclass(frozen=True)
class SolicitudSuscripcion:
    plan_id: int
    producto_id: str
    sku: str
    entrega: Entrega
    metodo_pago: str
    # RF-04.4: aceptó Términos y Condiciones y Política de Privacidad
    acepta_terminos: bool


@dataclass(frozen=True)
class SuscripcionIniciada:
    suscripcion_id: int
    orden_id: int


class _ConCiclos:
    """Lo común a los casos de uso que crean el pedido de un ciclo."""

    def __init__(self, suscripciones: RepositorioSuscripciones, pedidos: PedidosSuscripcion,
                 despacho: CotizadorDespacho, notificador: NotificadorSuscripciones | None = None):
        self.suscripciones = suscripciones
        self.pedidos = pedidos
        self.despacho = despacho
        self.notificador = notificador

    def _notificar(self, suscripcion_id, evento: EventoSuscripcion, orden_id=None):
        if self.notificador:
            self.notificador.notificar(suscripcion_id, evento, orden_id)

    def _crear_pedido(self, suscripcion: SuscripcionRegistrada, ciclo_fecha: date) -> int | None:
        """El pedido del ciclo con su despacho ($0 si el plan tiene envío gratis)."""
        costo = Decimal('0') if suscripcion.plan.datos.envio_gratis else self.despacho.costo(suscripcion)
        return self.pedidos.crear(suscripcion, ciclo_fecha, costo)


class Suscribirse(_ConCiclos):
    """El cliente se suscribe a un plan: queda Pendiente con el pedido del primer ciclo, que paga enseguida. Se activa
    al confirmarse ese pago (AlPagarPedido)."""

    def __init__(self, planes: RepositorioPlanes, catalogo: CatalogoSuscripciones, reglas: ReglasCompra, *args,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.planes = planes
        self.catalogo = catalogo
        self.reglas = reglas

    def ejecutar(self, usuario_id, solicitud: SolicitudSuscripcion, hoy: date, dias_aviso: int) -> SuscripcionIniciada:
        if not solicitud.acepta_terminos:
            raise TerminosNoAceptados()
        plan = self.planes.obtener(solicitud.plan_id)
        if plan is None or not plan.datos.activo:
            raise PlanNoDisponible()
        variante = _validar_variante(plan.datos, self.catalogo.variante(solicitud.producto_id, solicitud.sku))
        _validar_destinatario(solicitud.entrega)
        self.reglas.validar(solicitud.metodo_pago, solicitud.entrega)
        ciclo = fecha_primer_ciclo(hoy, dias_aviso)
        suscripcion_id = self.suscripciones.crear(usuario_id, plan.id, variante, solicitud.entrega,
                                                  solicitud.metodo_pago, ciclo)
        suscripcion = self.suscripciones.obtener(suscripcion_id)
        orden_id = self._crear_pedido(suscripcion, ciclo)
        return SuscripcionIniciada(suscripcion_id, orden_id)


class AlPagarPedido:
    """Se llama cuando un pedido pasa de Pendiente a Pagado (ConfirmarPago, una sola vez por pedido). Si es el de un
    ciclo, la suscripción avanza al ciclo siguiente y, si era el primero, se activa."""

    def __init__(self, suscripciones: RepositorioSuscripciones, pedidos: PedidosSuscripcion,
                 notificador: NotificadorSuscripciones | None = None):
        self.suscripciones = suscripciones
        self.pedidos = pedidos
        self.notificador = notificador

    def ejecutar(self, orden_id) -> None:
        pedido = self.pedidos.ciclo_de(orden_id)
        if pedido is None:
            return
        suscripcion = self.suscripciones.obtener(pedido.suscripcion_id)
        if suscripcion is None:
            return
        activada = (suscripcion.estado == EstadoSuscripcion.PENDIENTE and self.suscripciones.cambiar_estado(
            suscripcion.id, EstadoSuscripcion.PENDIENTE, EstadoSuscripcion.ACTIVA))
        nueva = siguiente_ciclo(pedido.ciclo_fecha, suscripcion.plan.datos.frecuencia_semanas)
        self.suscripciones.avanzar_si(suscripcion.id, pedido.ciclo_fecha, nueva)
        if activada and self.notificador:
            self.notificador.notificar(suscripcion.id, EventoSuscripcion.ACTIVADA, orden_id)


@dataclass
class ResumenCiclos:
    avisados: list = field(default_factory=list)
    no_pagados: list = field(default_factory=list)
    no_activadas: list = field(default_factory=list)
    # Ciclos cuyo pedido no se pudo crear (ej. el courier no respondió): se reintentan en la próxima ejecución
    con_error: list = field(default_factory=list)


class ProcesarCiclos(_ConCiclos):
    """Tarea diaria: cierra los ciclos vencidos sin pago y crea el pedido de los que toca avisar. Se puede correr
    varias veces: un ciclo tiene un solo pedido y cada suscripción avanza una sola vez por ciclo."""

    def ejecutar(self, hoy: date, dias_aviso: int) -> ResumenCiclos:
        resumen = ResumenCiclos()
        for suscripcion_id in self.suscripciones.ids_con_ciclo_vencido(hoy):
            self._cerrar_vencidos(suscripcion_id, hoy, resumen)
        hasta = date.fromordinal(hoy.toordinal() + dias_aviso)
        for suscripcion_id in self.suscripciones.ids_por_avisar(hasta):
            suscripcion = self.suscripciones.obtener(suscripcion_id)
            if (suscripcion is None or suscripcion.estado != EstadoSuscripcion.ACTIVA
                    or self.pedidos.del_ciclo(suscripcion.id, suscripcion.proxima_entrega) is not None):
                continue
            try:
                orden_id = self._crear_pedido(suscripcion, suscripcion.proxima_entrega)
            except DespachoNoDisponible as error:
                logger.warning('Suscripción %s: no se pudo calcular el despacho del ciclo: %s', suscripcion.id, error)
                resumen.con_error.append(suscripcion.id)
                continue
            if orden_id is not None:
                self._notificar(suscripcion.id, EventoSuscripcion.AVISO_COBRO, orden_id)
                resumen.avisados.append(suscripcion.id)
        return resumen

    def _cerrar_vencidos(self, suscripcion_id, hoy: date, resumen: ResumenCiclos):
        suscripcion = self.suscripciones.obtener(suscripcion_id)
        if suscripcion is None or suscripcion.proxima_entrega is None:
            return
        if suscripcion.estado == EstadoSuscripcion.PENDIENTE:
            # Nunca pagó el primer ciclo: la suscripción no se activa
            if not ciclo_vencido(suscripcion.proxima_entrega, hoy):
                return
            for pedido in self.pedidos.pendientes(suscripcion.id):
                self.pedidos.cancelar(pedido.orden_id, MOTIVO_PRIMER_PAGO_NO_RECIBIDO)
            if self.suscripciones.cambiar_estado(suscripcion.id, EstadoSuscripcion.PENDIENTE,
                                                 EstadoSuscripcion.CANCELADA, MOTIVO_PRIMER_PAGO_NO_RECIBIDO):
                self._notificar(suscripcion.id, EventoSuscripcion.NO_ACTIVADA)
                resumen.no_activadas.append(suscripcion.id)
            return
        if suscripcion.estado != EstadoSuscripcion.ACTIVA:
            return
        frecuencia = suscripcion.plan.datos.frecuencia_semanas
        ciclo, sin_pagar = suscripcion.proxima_entrega, False
        # Si la tarea no corrió varios días, se cierran todos los ciclos que quedaron atrás
        while ciclo_vencido(ciclo, hoy):
            pedido = self.pedidos.del_ciclo(suscripcion.id, ciclo)
            if pedido is not None and pedido.estado in ESTADOS_PAGADOS:
                # Pagado pero sin avanzar (no debería pasar): solo se avanza
                pass
            else:
                if pedido is not None:
                    self.pedidos.cancelar(pedido.orden_id, MOTIVO_CICLO_NO_PAGADO)
                sin_pagar = True
            nuevo = siguiente_ciclo(ciclo, frecuencia)
            if not self.suscripciones.avanzar_si(suscripcion.id, ciclo, nuevo):
                return
            ciclo = nuevo
        if sin_pagar:
            self._notificar(suscripcion.id, EventoSuscripcion.CICLO_NO_PAGADO)
            resumen.no_pagados.append(suscripcion.id)


@dataclass(frozen=True)
class CambiosSuscripcion:
    """Lo que el cliente quiere cambiar; None deja el dato como está. Rige desde el próximo pedido."""

    producto_id: str | None = None
    sku: str | None = None
    entrega: Entrega | None = None
    metodo_pago: str | None = None


class AccionesSuscripcion(_ConCiclos):
    """Mi cuenta > Mis suscripciones: pausar, reanudar, saltar un ciclo, adelantar la entrega, cancelar y cambiar los
    datos. Cada cliente solo actúa sobre sus propias suscripciones."""

    def __init__(self, catalogo: CatalogoSuscripciones, reglas: ReglasCompra, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.catalogo = catalogo
        self.reglas = reglas

    def _propia(self, usuario_id, suscripcion_id, accion: AccionSuscripcion) -> SuscripcionRegistrada:
        suscripcion = self.suscripciones.obtener(suscripcion_id)
        # Una ajena responde igual que una que no existe
        if suscripcion is None or suscripcion.usuario_id != usuario_id:
            raise SuscripcionNoEncontrada()
        validar_accion(accion, suscripcion.estado)
        return suscripcion

    def _cambiar_estado(self, suscripcion, hacia, motivo=''):
        if not self.suscripciones.cambiar_estado(suscripcion.id, suscripcion.estado, hacia, motivo):
            # Otro proceso la cambió entre medio
            raise AccionNoPermitida('La suscripción cambió mientras tanto. Recarga la página e inténtalo de nuevo.')

    def pausar(self, usuario_id, suscripcion_id) -> None:
        suscripcion = self._propia(usuario_id, suscripcion_id, AccionSuscripcion.PAUSAR)
        # Un ciclo ya pagado se entrega igual; uno sin pagar se cancela
        for pedido in self.pedidos.pendientes(suscripcion.id):
            self.pedidos.cancelar(pedido.orden_id, MOTIVO_SUSCRIPCION_PAUSADA)
        self._cambiar_estado(suscripcion, EstadoSuscripcion.PAUSADA)
        self._notificar(suscripcion.id, EventoSuscripcion.PAUSADA)

    def reanudar(self, usuario_id, suscripcion_id, hoy: date, dias_aviso: int) -> date:
        suscripcion = self._propia(usuario_id, suscripcion_id, AccionSuscripcion.REANUDAR)
        proxima = fecha_al_reanudar(suscripcion.proxima_entrega or hoy, hoy, dias_aviso)
        self.suscripciones.fijar_proxima(suscripcion.id, proxima)
        self._cambiar_estado(suscripcion, EstadoSuscripcion.ACTIVA)
        self._notificar(suscripcion.id, EventoSuscripcion.REANUDADA)
        return proxima

    def saltar(self, usuario_id, suscripcion_id) -> date:
        """Sin pedido para el próximo ciclo: se corre una frecuencia. Uno ya pagado no se salta."""
        suscripcion = self._propia(usuario_id, suscripcion_id, AccionSuscripcion.SALTAR)
        ciclo = suscripcion.proxima_entrega
        pedido = self.pedidos.del_ciclo(suscripcion.id, ciclo)
        if pedido is not None and pedido.estado != EstadoPedido.PENDIENTE:
            raise CicloYaPagado()
        if pedido is not None:
            self.pedidos.cancelar(pedido.orden_id, MOTIVO_CICLO_SALTADO)
        nueva = siguiente_ciclo(ciclo, suscripcion.plan.datos.frecuencia_semanas)
        if not self.suscripciones.avanzar_si(suscripcion.id, ciclo, nueva):
            raise AccionNoPermitida('La suscripción cambió mientras tanto. Recarga la página e inténtalo de nuevo.')
        return nueva

    def adelantar(self, usuario_id, suscripcion_id, hoy: date) -> int:
        """La próxima entrega pasa a hoy: su pedido se crea ahora y se pide el pago. Devuelve el pedido."""
        suscripcion = self._propia(usuario_id, suscripcion_id, AccionSuscripcion.ADELANTAR)
        if (self.pedidos.del_ciclo(suscripcion.id, suscripcion.proxima_entrega) is not None
                or self.pedidos.pendientes(suscripcion.id)):
            raise PedidoEnCurso()
        nueva = fecha_al_adelantar(hoy)
        orden_id = self._crear_pedido(replace(suscripcion, proxima_entrega=nueva), nueva)
        if orden_id is None:
            raise PedidoEnCurso()
        self.suscripciones.fijar_proxima(suscripcion.id, nueva)
        self._notificar(suscripcion.id, EventoSuscripcion.AVISO_COBRO, orden_id)
        return orden_id

    def cancelar(self, usuario_id, suscripcion_id) -> None:
        suscripcion = self._propia(usuario_id, suscripcion_id, AccionSuscripcion.CANCELAR)
        for pedido in self.pedidos.pendientes(suscripcion.id):
            self.pedidos.cancelar(pedido.orden_id, MOTIVO_SUSCRIPCION_CANCELADA)
        self._cambiar_estado(suscripcion, EstadoSuscripcion.CANCELADA, MOTIVO_SUSCRIPCION_CANCELADA)
        self._notificar(suscripcion.id, EventoSuscripcion.CANCELADA)

    def cambiar(self, usuario_id, suscripcion_id, cambios: CambiosSuscripcion) -> None:
        """Rige desde el próximo pedido: uno ya creado conserva lo que tenía."""
        suscripcion = self._propia(usuario_id, suscripcion_id, AccionSuscripcion.CAMBIAR)
        variante = None
        if cambios.producto_id is not None or cambios.sku is not None:
            variante = _validar_variante(suscripcion.plan.datos, self.catalogo.variante(
                cambios.producto_id or suscripcion.producto_id, cambios.sku or ''))
        if cambios.entrega is not None:
            _validar_destinatario(cambios.entrega)
        if cambios.entrega is not None or cambios.metodo_pago is not None:
            self.reglas.validar(cambios.metodo_pago or suscripcion.metodo_pago,
                                cambios.entrega or suscripcion.entrega)
        self.suscripciones.cambiar_datos(suscripcion.id, variante, cambios.entrega, cambios.metodo_pago)


@dataclass(frozen=True)
class BeneficiosCompra:
    """Lo que el suscriptor recibe en sus compras normales mientras tenga una suscripción activa."""

    descuento: int = 0
    envio_gratis: bool = False


def beneficios_de(suscripciones: RepositorioSuscripciones, usuario_id) -> BeneficiosCompra:
    """Con varias suscripciones activas vale el mayor descuento, y envío gratis si alguna lo da en todas sus compras."""
    if usuario_id is None:
        return BeneficiosCompra()
    planes = suscripciones.planes_activos_de(usuario_id)
    return BeneficiosCompra(descuento=max((plan.descuento for plan in planes), default=0),
                            envio_gratis=any(plan.envio_gratis_compras for plan in planes))
