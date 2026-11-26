"""Casos de uso de las reseñas: quien recibió su pedido califica la tienda y los productos, y el admin las modera.

Las reseñas son opcionales (el admin las activa en Configuración). Con la opción apagada no se reciben reseñas y la
tienda no muestra ninguna, aunque haya aprobadas de antes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from ecommerce.domain.resenas import (
    DatosResena, EstadoResena, ProductoDelPedido, ResenaYaEnviada, nombre_publico_sugerido, promedio,
    validar_moderacion, validar_pedido_para_resena, validar_plazo_resena,
)


@dataclass(frozen=True)
class PedidoParaResenar:
    """Lo que el caso de uso necesita saber del pedido que se va a reseñar."""

    orden_id: int
    estado: str
    # Cuándo pasó a Entregado; None si se entregó antes de que se registrara la fecha
    entregado_en: datetime | None
    nombre_comprador: str
    # Sin repetir, aunque el pedido traiga varias variantes del mismo producto
    productos: list[ProductoDelPedido]
    tiene_resena: bool


@dataclass(frozen=True)
class FormularioResena:
    orden_id: int
    productos: list[ProductoDelPedido]
    nombre_sugerido: str


@dataclass(frozen=True)
class ResenaPublica:
    """Lo que ve el público: nunca el correo ni el número del pedido."""

    nombre_publico: str
    estrellas: int
    comentario: str
    fecha: datetime


@dataclass(frozen=True)
class ResumenResenas:
    # None si todavía no hay reseñas aprobadas
    promedio: float | None
    total: int
    resenas: list[ResenaPublica] = field(default_factory=list)


SIN_RESENAS = ResumenResenas(promedio=None, total=0)


class PedidosParaResenar(ABC):
    """Puerto de salida: el pedido, sus productos y si ya tiene reseña."""

    @abstractmethod
    def obtener(self, orden_id: int) -> PedidoParaResenar | None:
        raise NotImplementedError


class RepositorioResenas(ABC):
    """Puerto de salida: dónde se guardan las reseñas. Las consultas públicas solo ven las aprobadas."""

    @abstractmethod
    def guardar(self, orden_id: int, datos: DatosResena) -> int | None:
        """Guarda la reseña como Pendiente y devuelve su id; None si el pedido ya tenía una (envío simultáneo)."""
        raise NotImplementedError

    @abstractmethod
    def estado(self, resena_id: int) -> EstadoResena | None:
        """None si la reseña no existe."""
        raise NotImplementedError

    @abstractmethod
    def cambiar_estado(self, resena_id: int, estado: EstadoResena) -> None:
        raise NotImplementedError

    @abstractmethod
    def estrellas_tienda(self) -> list[int]:
        """Las estrellas de la tienda de todas las aprobadas."""
        raise NotImplementedError

    @abstractmethod
    def recientes_tienda(self, cantidad: int) -> list[ResenaPublica]:
        """Las aprobadas con comentario de la tienda, las más recientes primero."""
        raise NotImplementedError

    @abstractmethod
    def estrellas_producto(self, producto_id: str) -> list[int]:
        raise NotImplementedError

    @abstractmethod
    def recientes_producto(self, producto_id: str, cantidad: int) -> list[ResenaPublica]:
        """Las calificaciones aprobadas con comentario del producto, las más recientes primero."""
        raise NotImplementedError


class ResenasDesactivadas(Exception):
    def __init__(self):
        super().__init__('Esta tienda no está recibiendo reseñas por ahora.')


class PedidoNoEncontrado(Exception):
    def __init__(self):
        super().__init__('Pedido no encontrado.')


class ResenaNoEncontrada(Exception):
    def __init__(self):
        super().__init__('Reseña no encontrada.')


def _pedido_resenable(pedidos: PedidosParaResenar, orden_id: int, resenas_activas: bool,
                      ahora: datetime) -> PedidoParaResenar:
    if not resenas_activas:
        raise ResenasDesactivadas()
    pedido = pedidos.obtener(orden_id)
    if pedido is None:
        raise PedidoNoEncontrado()
    validar_pedido_para_resena(pedido.estado, pedido.tiene_resena)
    validar_plazo_resena(pedido.entregado_en, ahora)
    return pedido


class PrepararFormularioResena:
    """Lo que muestra el formulario /resena: los productos del pedido y el nombre sugerido ("Ana P.")."""

    def __init__(self, pedidos: PedidosParaResenar):
        self.pedidos = pedidos

    def ejecutar(self, orden_id: int, resenas_activas: bool, ahora: datetime) -> FormularioResena:
        pedido = _pedido_resenable(self.pedidos, orden_id, resenas_activas, ahora)
        return FormularioResena(orden_id=pedido.orden_id, productos=pedido.productos,
                                nombre_sugerido=nombre_publico_sugerido(pedido.nombre_comprador))


class EnviarResena:
    """El comprador reseña un pedido Entregado, una sola vez y dentro del plazo. Queda pendiente de aprobación."""

    def __init__(self, pedidos: PedidosParaResenar, resenas: RepositorioResenas):
        self.pedidos = pedidos
        self.resenas = resenas

    def ejecutar(self, orden_id: int, datos: dict, resenas_activas: bool, ahora: datetime) -> int:
        pedido = _pedido_resenable(self.pedidos, orden_id, resenas_activas, ahora)
        resena = DatosResena.desde(datos, pedido.productos)
        resena_id = self.resenas.guardar(pedido.orden_id, resena)
        if resena_id is None:
            raise ResenaYaEnviada()
        return resena_id


class ModerarResena:
    """El admin aprueba u oculta una reseña. No puede crearlas ni editarlas, para que el promedio sea real."""

    def __init__(self, resenas: RepositorioResenas):
        self.resenas = resenas

    def ejecutar(self, resena_id: int, estado) -> EstadoResena:
        actual = self.resenas.estado(resena_id)
        if actual is None:
            raise ResenaNoEncontrada()
        nuevo = validar_moderacion(actual, estado)
        self.resenas.cambiar_estado(resena_id, nuevo)
        return nuevo


class ResenasDeLaTienda:
    """Sección de la landing: promedio de las aprobadas y las últimas con comentario."""

    def __init__(self, resenas: RepositorioResenas, cantidad: int = 6):
        self.resenas = resenas
        self.cantidad = cantidad

    def ejecutar(self, resenas_activas: bool) -> ResumenResenas:
        if not resenas_activas:
            return SIN_RESENAS
        estrellas = self.resenas.estrellas_tienda()
        if not estrellas:
            return SIN_RESENAS
        return ResumenResenas(promedio=promedio(estrellas), total=len(estrellas),
                              resenas=self.resenas.recientes_tienda(self.cantidad))


class ResenasDeProducto:
    """Ficha del producto: promedio de sus calificaciones aprobadas y las últimas con comentario."""

    def __init__(self, resenas: RepositorioResenas, cantidad: int = 20):
        self.resenas = resenas
        self.cantidad = cantidad

    def ejecutar(self, producto_id: str, resenas_activas: bool) -> ResumenResenas:
        if not resenas_activas:
            return SIN_RESENAS
        estrellas = self.resenas.estrellas_producto(producto_id)
        if not estrellas:
            return SIN_RESENAS
        return ResumenResenas(promedio=promedio(estrellas), total=len(estrellas),
                              resenas=self.resenas.recientes_producto(producto_id, self.cantidad))
