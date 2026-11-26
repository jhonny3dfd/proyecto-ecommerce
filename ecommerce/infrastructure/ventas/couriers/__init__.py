"""Couriers disponibles (RF-02.3): para sumar uno, se crea su adaptador del puerto Courier y se agrega a COURIERS.

Un courier está activo cuando el admin cargó en el panel todas sus llaves obligatorias.
"""

import logging

from ecommerce.application.couriers import CourierNoActivo, Couriers, RepositorioCredencialesCourier
from ecommerce.domain.logistica import CredencialesCourier

from ..cifrado import CredencialesIlegibles, cifrar_json, descifrar_json
from ..models import ProveedorEnvio
from .chilexpress import ChilexpressCourier

logger = logging.getLogger(__name__)

# Código → adaptador, en el orden en que se ofrecen
COURIERS = {ChilexpressCourier.codigo: ChilexpressCourier}
CODIGOS_COURIERS = tuple(COURIERS)


class DjangoRepositorioCredencialesCourier(RepositorioCredencialesCourier):
    """Las llaves de cada courier en ProveedorEnvio (una fila por código), cifradas con CLAVE_CIFRADO_CREDENCIALES."""

    def obtener(self, codigo, campos):
        fila = ProveedorEnvio.objects.filter(codigo=codigo).first()
        if fila is None:
            return CredencialesCourier.con(campos)
        try:
            datos = descifrar_json(fila.credenciales_cifradas)
        except CredencialesIlegibles:
            # Sin llaves no se cotiza: el admin debe volver a cargarlas
            logger.error('No se pudieron descifrar las credenciales de %s: ¿cambió CLAVE_CIFRADO_CREDENCIALES?', codigo)
            return CredencialesCourier.con(campos)
        return CredencialesCourier.con(campos, datos)

    def guardar(self, codigo, credenciales):
        ProveedorEnvio.objects.update_or_create(codigo=codigo, defaults={
            'credenciales_cifradas': cifrar_json({k: v for k, v in credenciales.como_dict().items() if v}),
        })


class DjangoCouriers(Couriers):
    def __init__(self, repositorio: RepositorioCredencialesCourier | None = None):
        self.repositorio = repositorio or DjangoRepositorioCredencialesCourier()

    def _crear(self, codigo):
        adaptador = COURIERS[codigo]
        return adaptador(self.repositorio.obtener(codigo, adaptador.CAMPOS))

    def activos(self):
        return [courier for courier in map(self._crear, COURIERS) if courier.credenciales.configuradas]

    def obtener(self, codigo, solo_activos=True):
        if codigo not in COURIERS:
            raise CourierNoActivo()
        courier = self._crear(codigo)
        if solo_activos and not courier.credenciales.configuradas:
            raise CourierNoActivo()
        return courier
