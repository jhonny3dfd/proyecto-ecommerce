"""Datos de facturación de un comprador que compra como empresa; independiente de Django.

La tienda recibe estos datos y emite la factura por su cuenta: la integración con el SII queda fuera de alcance.
"""

import re
from dataclasses import dataclass
from itertools import cycle

_RUT = re.compile(r'^(\d{7,8})([\dK])$')


class RutInvalido(ValueError):
    def __init__(self):
        super().__init__('El RUT no es válido. Revisa los números y el dígito verificador (ej. 76.123.456-0).')


def digito_verificador(cuerpo: str) -> str:
    """Módulo 11: los dígitos, de derecha a izquierda, se multiplican por 2, 3, 4, 5, 6, 7, 2, 3..."""
    suma = sum(int(digito) * factor for digito, factor in zip(reversed(cuerpo), cycle(range(2, 8))))
    resto = 11 - suma % 11
    return {11: '0', 10: 'K'}.get(resto, str(resto))


def normalizar_rut(texto) -> str:
    """Acepta '76.123.456-0', '76123456-0' o '761234560' y devuelve '76.123.456-0'; RutInvalido si no cuadra."""
    limpio = re.sub(r'[.\-\s]', '', str(texto or '')).upper()
    coincidencia = _RUT.match(limpio)
    if not coincidencia or digito_verificador(coincidencia[1]) != coincidencia[2]:
        raise RutInvalido()
    cuerpo, dv = coincidencia.groups()
    return f'{int(cuerpo):,}'.replace(',', '.') + f'-{dv}'


class DatosEmpresaInvalidos(ValueError):
    def __init__(self, errores: dict[str, str]):
        self.errores = errores
        super().__init__('; '.join(f'{campo}: {error}' for campo, error in errores.items()))


@dataclass(frozen=True)
class DatosEmpresa:
    razon_social: str
    rut: str
    giro: str
    direccion: str
    correo: str

    # (campo, etiqueta), en el orden del formulario y de los correos
    CAMPOS = (
        ('razon_social', 'Razón social'),
        ('rut', 'RUT'),
        ('giro', 'Giro'),
        ('direccion', 'Dirección comercial'),
        ('correo', 'Correo para la factura'),
    )

    @classmethod
    def desde(cls, datos: dict) -> 'DatosEmpresa':
        """Todos los campos son obligatorios: sin ellos la tienda no puede emitir la factura."""
        valores = {campo: str(datos.get(campo) or '').strip() for campo, _ in cls.CAMPOS}
        errores = {campo: 'Este dato es obligatorio para la factura.' for campo, valor in valores.items() if not valor}
        if valores['rut']:
            try:
                valores['rut'] = normalizar_rut(valores['rut'])
            except RutInvalido as error:
                errores['rut'] = str(error)
        if errores:
            raise DatosEmpresaInvalidos(errores)
        return cls(**valores)

    def como_dict(self) -> dict[str, str]:
        return {campo: getattr(self, campo) for campo, _ in self.CAMPOS}
