"""Adaptador Django (PostgreSQL) del puerto RepositorioMediosPago, con las credenciales cifradas."""

import logging

from ecommerce.application.medios_pago import RepositorioMediosPago
from ecommerce.domain.medios_pago import CodigoMedioPago, MedioPagoConfigurado, definicion_medio

from .cifrado import CredencialesIlegibles, cifrar_json, descifrar_json
from .models import MedioPago

logger = logging.getLogger(__name__)


class DjangoRepositorioMediosPago(RepositorioMediosPago):
    def obtener(self, codigo):
        codigo = CodigoMedioPago(codigo)
        fila = MedioPago.objects.filter(codigo=codigo.value).first()
        return self._desde_fila(codigo, fila)

    def obtener_varios(self, codigos):
        codigos = [CodigoMedioPago(codigo) for codigo in codigos]
        filas = MedioPago.objects.filter(codigo__in=[c.value for c in codigos]).in_bulk(field_name='codigo')
        return [self._desde_fila(codigo, filas.get(codigo.value)) for codigo in codigos]

    @staticmethod
    def _desde_fila(codigo, fila):
        if fila is None:
            return MedioPagoConfigurado(codigo)
        try:
            credenciales = descifrar_json(fila.credenciales_cifradas)
        except CredencialesIlegibles:
            # Sin credenciales el medio queda incompleto y no se ofrece: el admin debe volver a cargarlas
            logger.error('No se pudieron descifrar las credenciales de %s: ¿cambió CLAVE_CIFRADO_CREDENCIALES?',
                         codigo.value)
            credenciales = {}
        return MedioPagoConfigurado(codigo, fila.habilitado, {**fila.datos, **credenciales})

    def guardar(self, medio):
        secretos = {c.nombre for c in definicion_medio(medio.codigo).campos if c.secreto}
        MedioPago.objects.update_or_create(codigo=medio.codigo.value, defaults={
            'habilitado': medio.habilitado,
            'datos': {k: v for k, v in medio.datos.items() if k not in secretos},
            'credenciales_cifradas': cifrar_json({k: v for k, v in medio.datos.items() if k in secretos}),
        })
