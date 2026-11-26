"""Destacados de la landing (RF-01.1): obras y proyectos que el admin elige a mano en vez de "Más vendidos".

Pedido de un cliente, opcional: por defecto la vitrina sigue mostrando "Más vendidos" (decidido el 2026-11-08).
Independiente de Django. Que cada destacado exista y se vea lo decide la aplicación con sus puertos.
"""

from enum import StrEnum

MAX_DESTACADOS = 8  # 2 filas de 4 en el computador (pedido de Alan, 2026-11-13)
TITULO_POR_DEFECTO = 'Destacados'
LARGO_TITULO = 60
# Un id de MongoDB tiene 24 caracteres y uno de PostgreSQL unos pocos dígitos: 40 sobra para ambos
LARGO_ID = 40


class ModoVitrina(StrEnum):
    MAS_VENDIDOS = 'MAS_VENDIDOS'
    DESTACADOS = 'DESTACADOS'


class TipoDestacado(StrEnum):
    PRODUCTO = 'PRODUCTO'
    PUBLICACION = 'PUBLICACION'


class DestacadosInvalidos(ValueError):
    pass


class TituloDestacadosInvalido(ValueError):
    def __init__(self):
        super().__init__(f'El título puede tener hasta {LARGO_TITULO} caracteres.')


def normalizar_titulo_destacados(texto) -> str:
    """Título de la sección; vacío vuelve a 'Destacados'."""
    valor = ' '.join(str(texto or '').split())
    if not valor:
        return TITULO_POR_DEFECTO
    if len(valor) > LARGO_TITULO:
        raise TituloDestacadosInvalido()
    return valor


def normalizar_destacados(lista) -> list[dict]:
    """La selección en orden: [{'tipo': 'PRODUCTO' | 'PUBLICACION', 'id': '...'}], hasta 8 y sin repetir."""
    if not isinstance(lista, list):
        raise DestacadosInvalidos('Los destacados deben ser una lista.')
    if len(lista) > MAX_DESTACADOS:
        raise DestacadosInvalidos(f'Puedes elegir hasta {MAX_DESTACADOS} destacados.')

    resultado = []
    for elemento in lista:
        if not isinstance(elemento, dict) or set(elemento) != {'tipo', 'id'}:
            raise DestacadosInvalidos('Cada destacado debe indicar su tipo y su id.')
        try:
            tipo = TipoDestacado(elemento['tipo'])
        except ValueError:
            raise DestacadosInvalidos('Un destacado solo puede ser un producto o una publicación.') from None
        # El id llega como texto o como número (las publicaciones); se guarda siempre como texto
        id_destacado = elemento['id']
        if isinstance(id_destacado, bool) or not isinstance(id_destacado, (str, int)):
            raise DestacadosInvalidos('Cada destacado debe indicar su tipo y su id.')
        id_destacado = str(id_destacado).strip()
        if not id_destacado or len(id_destacado) > LARGO_ID:
            raise DestacadosInvalidos('Cada destacado debe indicar su tipo y su id.')

        destacado = {'tipo': tipo.value, 'id': id_destacado}
        if destacado in resultado:
            raise DestacadosInvalidos('No puedes elegir el mismo destacado dos veces.')
        resultado.append(destacado)
    return resultado


def ids_por_tipo(destacados, tipo: TipoDestacado) -> list[str]:
    """Los ids de un tipo, en el orden elegido."""
    return [destacado['id'] for destacado in destacados if destacado['tipo'] == tipo]
