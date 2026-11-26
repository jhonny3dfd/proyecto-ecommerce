"""Gallery use cases with compensating cleanup across storage and MongoDB."""

import logging

from ecommerce.domain.imagenes import (
    AlmacenamientoImagenNoDisponible,
    AlmacenImagenes,
    ImagenProcesada,
    LimiteGaleriaExcedido,
    RepositorioGaleria,
)


logger = logging.getLogger(__name__)


class ServicioGaleria:
    def __init__(self, repositorio: RepositorioGaleria, almacen: AlmacenImagenes):
        self.repositorio = repositorio
        self.almacen = almacen

    def subir(
        self, producto_id: str, anteriores: list[str],
        imagenes: list[ImagenProcesada], maximo: int,
    ) -> tuple[list[str], list[str]]:
        if len(anteriores) + len(imagenes) > maximo:
            raise LimiteGaleriaExcedido
        guardadas = []
        try:
            for imagen in imagenes:
                guardadas.append(self.almacen.guardar(producto_id, imagen))
            galeria = self.repositorio.asociar(producto_id, anteriores, guardadas)
        except Exception as exc:
            if isinstance(exc, AlmacenamientoImagenNoDisponible) and exc.clave:
                guardadas.append(exc.clave)
            # A database timeout can occur after a successful write. Never delete
            # a file until its absence from the gallery has been confirmed.
            for clave in guardadas:
                self.limpiar_pendiente(clave, programar=True)
            raise
        return galeria, guardadas

    def eliminar(self, producto_id: str, anteriores: list[str], clave: str) -> list[str]:
        # Persist the cleanup intent before detaching, so a storage outage is
        # recoverable by the cleanup command, even after a process restart.
        self.repositorio.programar_borrado([clave])
        galeria = self.repositorio.desasociar(producto_id, anteriores, clave)
        self.limpiar_pendiente(clave)
        return galeria

    def quitar_enlace(self, producto_id: str, anteriores: list[str], url: str) -> list[str]:
        """RF-03.2: un enlace externo no tiene archivo en la tienda, así que solo se quita de la galería."""
        return self.repositorio.desasociar(producto_id, anteriores, url)

    def limpiar_pendiente(self, clave: str, *, programar: bool = False) -> bool:
        try:
            if programar:
                self.repositorio.programar_borrado([clave])
            if self.repositorio.esta_asociada(clave):
                return False
            self.almacen.borrar(clave)
            self.repositorio.completar_borrado(clave)
            return True
        except Exception:
            # Leave the durable intent in MongoDB and retry later. The caller's
            # original exception must not be masked by a cleanup failure.
            logger.exception('No se pudo limpiar la imagen de catálogo %s', clave)
            return False
