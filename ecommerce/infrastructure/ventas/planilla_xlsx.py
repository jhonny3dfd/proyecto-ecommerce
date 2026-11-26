"""Escribe una Planilla (application/exportacion_ventas.py) como archivo de Excel (.xlsx) con openpyxl."""

from datetime import datetime
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

TIPO_XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
FORMATO_FECHA = 'DD-MM-YYYY HH:MM'
ANCHO_MINIMO, ANCHO_MAXIMO = 10, 45
ANCHO_FECHA = 17


def _ancho(valor) -> int:
    return ANCHO_FECHA if isinstance(valor, datetime) else len(str(valor))


def escribir_xlsx(planilla) -> bytes:
    libro = Workbook()
    libro.remove(libro.active)
    for hoja in planilla.hojas:
        pagina = libro.create_sheet(hoja.nombre)
        pagina.append(hoja.columnas)
        for celda in pagina[1]:
            celda.font = Font(bold=True)
        for valores in hoja.filas:
            pagina.append(valores)
            for celda in pagina[pagina.max_row]:
                if isinstance(celda.value, str):
                    # Lo escribió un comprador (nombre, dirección): siempre texto, nunca una fórmula que empiece con "="
                    celda.data_type = 's'
                elif isinstance(celda.value, datetime):
                    celda.number_format = FORMATO_FECHA
        # Los títulos quedan fijos al bajar y cada columna se puede filtrar y ordenar
        pagina.freeze_panes = 'A2'
        pagina.auto_filter.ref = pagina.dimensions
        for indice, columna in enumerate(hoja.columnas, start=1):
            largo = max([len(columna)] + [_ancho(valores[indice - 1]) for valores in hoja.filas])
            pagina.column_dimensions[get_column_letter(indice)].width = min(max(largo + 2, ANCHO_MINIMO), ANCHO_MAXIMO)
    archivo = BytesIO()
    libro.save(archivo)
    return archivo.getvalue()
