"""Cumpleaños opcional sin guardar el año de nacimiento."""
from datetime import date


def validar_cumpleanos(dia, mes):
    """Ambos vacíos eliminan la fecha. El 29 de febrero es una fecha de cumpleaños válida."""
    if dia is None and mes is None:
        return None, None
    if type(dia) is not int or type(mes) is not int:
        raise ValueError('Completa el día y el mes, o deja ambos vacíos.')
    try:
        date(2000, mes, dia)
    except ValueError:
        raise ValueError('Indica un día y un mes que formen una fecha real.') from None
    return dia, mes
