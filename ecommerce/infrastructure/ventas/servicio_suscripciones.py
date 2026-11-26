"""Arma los casos de uso de suscripciones con sus adaptadores (las pruebas pueden reemplazar cada fábrica)."""

from ecommerce.application.suscripciones import AccionesSuscripcion, AlPagarPedido, ProcesarCiclos, Suscribirse

from ..catalogo.repositorio_variantes import MongoCatalogoSuscripciones
from .adapters.correo import CorreoNotificadorSuscripciones
from .repositorio_suscripciones import (
    DespachoSuscripcion, DjangoPedidosSuscripcion, DjangoRepositorioPlanes, DjangoRepositorioSuscripciones,
    ReglasCompraTienda,
)


def catalogo_suscripciones():
    return MongoCatalogoSuscripciones()


def notificador_suscripciones():
    return CorreoNotificadorSuscripciones()


def _comunes():
    catalogo = catalogo_suscripciones()
    return (DjangoRepositorioSuscripciones(), DjangoPedidosSuscripcion(catalogo), DespachoSuscripcion(catalogo),
            notificador_suscripciones())


def suscribirse() -> Suscribirse:
    return Suscribirse(DjangoRepositorioPlanes(), catalogo_suscripciones(), ReglasCompraTienda(), *_comunes())


def acciones_suscripcion() -> AccionesSuscripcion:
    return AccionesSuscripcion(catalogo_suscripciones(), ReglasCompraTienda(), *_comunes())


def procesar_ciclos() -> ProcesarCiclos:
    return ProcesarCiclos(*_comunes())


def al_pagar_pedido(orden_id) -> None:
    """Lo llama ConfirmarPago cuando un pedido pasa de Pendiente a Pagado: si es el de un ciclo, la suscripción avanza."""
    AlPagarPedido(DjangoRepositorioSuscripciones(), DjangoPedidosSuscripcion(catalogo_suscripciones()),
                  notificador_suscripciones()).ejecutar(orden_id)
