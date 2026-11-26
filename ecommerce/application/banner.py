"""Casos de uso para el carrusel de banner de la portada (RF-01.1, SCRUM-194).

Independiente de Django y DRF. La capa de infraestructura implementa la persistencia.
"""

from abc import ABC, abstractmethod
import json

from ecommerce.domain.banner import (
    EstructuraBannerInvalida,
    TextosFoto,
    normalizar_textos_foto,
    validar_cantidad_fotos_banner,
)


class RepositorioBanners(ABC):
    """Puerto de salida para persistir las fotos del banner y su orden."""

    @abstractmethod
    def guardar_banners(self, configuracion_id: int, orden_list: list, nuevos_archivos: list,
                        textos: list[TextosFoto | None] | None = None) -> None:
        """textos va alineado con orden_list: los de cada foto, o None si el pedido no los trae (se conservan
        los que tenía; una foto nueva o la antigua toman los de la portada)."""
        raise NotImplementedError


def separar_referencia_y_textos(item):
    """Un elemento del orden es la referencia sola ('id:3', 'nuevo:0', 'id:legacy') o un objeto con la
    referencia en 'ref' y los textos de la foto (SCRUM-194)."""
    if isinstance(item, dict):
        if 'ref' not in item:
            raise EstructuraBannerInvalida('Cada foto del banner debe indicar su referencia (ref).')
        return item['ref'], normalizar_textos_foto(item)
    return item, None


def es_identificador_legacy(item) -> bool:
    """Reconoce 'id:legacy', 'legacy', 'id:0', 0 o '0' como referencia al banner antiguo."""
    return item in ('id:legacy', 'legacy', 'id:0', 0, '0')


class ActualizarBanners:
    """Valida el manifiesto del banner y orquesta la actualización atómica mediante el repositorio."""

    def __init__(self, repositorio: RepositorioBanners):
        self.repositorio = repositorio

    def ejecutar(self, configuracion_id: int, raw_orden, nuevos_archivos: list, nuevos_videos=None) -> None:
        nuevos_videos = list(nuevos_videos or [])
        # 1. Parsear y validar formato de banner_orden
        if isinstance(raw_orden, str):
            try:
                orden_list = json.loads(raw_orden)
            except (json.JSONDecodeError, ValueError, TypeError) as exc:
                raise EstructuraBannerInvalida('El formato de banner_orden no es un JSON válido.') from exc
        elif isinstance(raw_orden, list):
            orden_list = raw_orden
        else:
            raise EstructuraBannerInvalida('banner_orden debe ser una lista.')

        if not isinstance(orden_list, list):
            raise EstructuraBannerInvalida('banner_orden debe ser una lista.')

        # 2. Validar límite de fotos (domain/banner.py)
        validar_cantidad_fotos_banner(len(orden_list))

        # 3. Separar la referencia de cada foto de sus textos; los textos se validan en el dominio
        asociaciones = {}
        for item in orden_list:
            if isinstance(item, dict) and 'video_indice' in item:
                ref = item.get('ref')
                indice = item['video_indice']
                if not isinstance(ref, str) or not ref.startswith('nuevo:') or not isinstance(indice, int) or isinstance(indice, bool) or indice < 0 or indice >= len(nuevos_videos):
                    raise EstructuraBannerInvalida('La referencia del video es inválida.')
                if indice in asociaciones.values():
                    raise EstructuraBannerInvalida('Un video no puede asignarse a varias diapositivas.')
                asociaciones[ref] = indice
        if len(asociaciones) != len(nuevos_videos):
            raise EstructuraBannerInvalida('Cada video debe tener una diapositiva con imagen de portada.')
        separados = [separar_referencia_y_textos(item) for item in orden_list]
        orden_list = [referencia for referencia, _ in separados]
        textos = [textos_foto for _, textos_foto in separados]

        # 4. Validar sintaxis y rangos de los elementos del manifiesto
        nuevos_indices = []
        for item in orden_list:
            if isinstance(item, str):
                if es_identificador_legacy(item):
                    continue
                elif item.startswith('id:'):
                    try:
                        int(item.split(':')[1])
                    except (IndexError, ValueError) as exc:
                        raise EstructuraBannerInvalida(f'ID de banner inválido: {item}') from exc
                elif item.startswith('nuevo:'):
                    try:
                        idx = int(item.split(':')[1])
                        if idx < 0 or idx >= len(nuevos_archivos):
                            raise EstructuraBannerInvalida(f'Índice de archivo nuevo fuera de rango: {idx}')
                        nuevos_indices.append(idx)
                    except (IndexError, ValueError) as exc:
                        raise EstructuraBannerInvalida(f'Índice de nuevo banner inválido: {item}') from exc
                else:
                    raise EstructuraBannerInvalida(f'Elemento inválido en banner_orden: {item}')
            elif isinstance(item, int):
                pass
            else:
                raise EstructuraBannerInvalida(f'Tipo de dato inválido en banner_orden: {type(item)}')

        # 5. Rechazar referencias repetidas en el manifiesto.
        referencias_vistas = set()

        for referencia in orden_list:
            if es_identificador_legacy(referencia):
                clave = 'id:legacy'
            elif isinstance(referencia, int):
                clave = f'id:{referencia}'
            elif referencia.startswith('id:'):
                clave = f'id:{int(referencia.split(":")[1])}'
            elif referencia.startswith('nuevo:'):
                clave = f'nuevo:{int(referencia.split(":")[1])}'
            else:
                raise EstructuraBannerInvalida(
                    f'Referencia inválida: {referencia}'
                )

            if clave in referencias_vistas:
                raise EstructuraBannerInvalida(
                    f'Referencia repetida en banner_orden: {referencia}'
                )

            referencias_vistas.add(clave)

        # 6. Delegar la persistencia atómica y validación de archivos al puerto
        if nuevos_videos:
            self.repositorio.guardar_banners(configuracion_id, orden_list, nuevos_archivos, textos,
                                             nuevos_videos=nuevos_videos, asociaciones=asociaciones)
        else:
            self.repositorio.guardar_banners(configuracion_id, orden_list, nuevos_archivos, textos)
