"""Adaptador Django para la persistencia del carrusel de banner (SCRUM-194)."""

from django.db import transaction
from rest_framework import serializers

from ecommerce.application.banner import RepositorioBanners, es_identificador_legacy
from ecommerce.domain.banner import (LARGO_ANTETITULO, LARGO_TEXTO, LARGO_TITULO, TextosFoto,
    validar_cantidad_videos_banner, validar_video_banner, LimiteVideosBannerExcedido, VideoBannerInvalido)
from ecommerce.infrastructure.ventas.models import ConfiguracionGlobal, FotoBanner

# El título por defecto de la portada (models.ConfiguracionGlobal.texto_bienvenida)
TITULO_PORTADA_POR_DEFECTO = 'Bienvenido a nuestra tienda'
from ecommerce.infrastructure.ventas.serializers import ImagenNegocioField


def _ubicaciones(archivos):
    return [(archivo.storage, archivo.name) for archivo in archivos if archivo and getattr(archivo, 'name', None)]


def _borrar_al_confirmar(archivos):
    pendientes = _ubicaciones(archivos)
    if pendientes:
        transaction.on_commit(lambda: [storage.delete(nombre) for storage, nombre in pendientes])


def textos_de_la_portada(config) -> TextosFoto:
    """Los textos generales de la portada: los toma una foto que llega sin los suyos."""
    return TextosFoto(
        antetitulo=(config.subtitulo_bienvenida or '').strip()[:LARGO_ANTETITULO],
        titulo=((config.texto_bienvenida or '').strip() or TITULO_PORTADA_POR_DEFECTO)[:LARGO_TITULO],
        texto=(config.texto_landing or '').strip()[:LARGO_TEXTO],
    )


def _aplicar(foto, orden, textos: TextosFoto | None) -> None:
    """Guarda el orden y, si llegaron, los textos de una foto; solo escribe si algo cambió."""
    cambios = {'orden': orden}
    if textos is not None:
        cambios.update(antetitulo=textos.antetitulo, titulo=textos.titulo, texto=textos.texto,
                       destino=textos.destino)
    distintos = [campo for campo, valor in cambios.items() if getattr(foto, campo) != valor]
    for campo in distintos:
        setattr(foto, campo, cambios[campo])
    if distintos:
        foto.save(update_fields=distintos)


class DjangoRepositorioBanners(RepositorioBanners):
    def __init__(self, campo_imagen=None):
        self.campo_imagen = campo_imagen or ImagenNegocioField()

    def guardar_banners(self, configuracion_id: int, orden_list: list, nuevos_archivos: list,
                        textos: list | None = None, nuevos_videos=None, asociaciones=None) -> None:
        config = ConfiguracionGlobal.objects.get(pk=configuracion_id)
        textos = list(textos) if textos is not None else [None] * len(orden_list)
        portada = textos_de_la_portada(config)
        nuevos_videos = list(nuevos_videos or [])
        asociaciones = asociaciones or {}
        # El archivo se valida antes de tocar la base de datos.
        for archivo in nuevos_videos:
            posicion = archivo.tell()
            try:
                encabezado = archivo.read(12)
            finally:
                archivo.seek(posicion)
            validar_video_banner(archivo.name, getattr(archivo, 'content_type', ''), archivo.size, encabezado)
        videos_existentes = sum(bool(foto.video) for foto in config.fotos_banner.all()
                                if f'id:{foto.id}' in orden_list or foto.id in orden_list)
        validar_cantidad_videos_banner(videos_existentes + len(nuevos_videos))

        # Parsear índices nuevos e IDs pedidos
        nuevos_indices = []
        ids_existentes_pedidos = []
        tiene_legacy = False

        for item in orden_list:
            if es_identificador_legacy(item):
                tiene_legacy = True
            elif isinstance(item, str) and item.startswith('id:'):
                ids_existentes_pedidos.append(int(item.split(':')[1]))
            elif isinstance(item, str) and item.startswith('nuevo:'):
                nuevos_indices.append(int(item.split(':')[1]))
            elif isinstance(item, int):
                ids_existentes_pedidos.append(item)

        # Validar y procesar archivos nuevos (con mensaje legible para el admin)
        archivos_procesados = {}
        for idx in set(nuevos_indices):
            archivo = nuevos_archivos[idx]
            try:
                archivos_procesados[idx] = self.campo_imagen.to_internal_value(archivo)
            except serializers.ValidationError:
                raise
            except Exception as exc:
                raise serializers.ValidationError({
                    'banner_fotos': [f'El archivo {archivo.name} no es una imagen válida o está dañado.']
                }) from exc

        # Ejecución atómica
        with transaction.atomic():
            fotos_actuales = {f.id: f for f in config.fotos_banner.all()}
            archivos_a_borrar = []

            legacy_foto = None
            if tiene_legacy and config.banner:
                # Migrar banner antiguo a FotoBanner
                legacy_foto = FotoBanner.objects.create(
                    configuracion=config,
                    imagen=config.banner,
                    orden=0,
                    antetitulo=portada.antetitulo, titulo=portada.titulo, texto=portada.texto,
                )
                fotos_actuales[legacy_foto.id] = legacy_foto
            elif not tiene_legacy and config.banner:
                # Si el banner antiguo ya no se incluye en el manifiesto, se descarta físicamente
                archivos_a_borrar.append(config.banner)
                config.banner = None
                config.save(update_fields=['banner'])

            ids_a_conservar = set(ids_existentes_pedidos)
            if legacy_foto is not None:
                ids_a_conservar.add(legacy_foto.id)

            # Eliminar fotos del carrusel que no están en el nuevo orden
            for foto_id, foto in list(fotos_actuales.items()):
                if foto_id not in ids_a_conservar:
                    archivos_a_borrar.append(foto.imagen)
                    if foto.video:
                        archivos_a_borrar.append(foto.video)
                    foto.delete()
                    fotos_actuales.pop(foto_id, None)

            # Reordenar y crear fotos nuevas en el orden exacto, con los textos que trae cada una
            for nuevo_orden, (item, textos_foto) in enumerate(zip(orden_list, textos)):
                if es_identificador_legacy(item):
                    if legacy_foto is not None:
                        _aplicar(legacy_foto, nuevo_orden, textos_foto)
                elif isinstance(item, str) and item.startswith('id:'):
                    foto_id = int(item.split(':')[1])
                    if foto_id in fotos_actuales:
                        _aplicar(fotos_actuales[foto_id], nuevo_orden, textos_foto)
                elif isinstance(item, int):
                    if item in fotos_actuales:
                        _aplicar(fotos_actuales[item], nuevo_orden, textos_foto)
                elif isinstance(item, str) and item.startswith('nuevo:'):
                    file_idx = int(item.split(':')[1])
                    procesado = archivos_procesados[file_idx]
                    # Sin textos propios, la foto nueva parte con los de la portada (el título es obligatorio)
                    textos_nueva = textos_foto or portada
                    nueva_foto = FotoBanner.objects.create(
                        configuracion=config,
                        imagen=procesado,
                        video=nuevos_videos[asociaciones[item]] if item in asociaciones else None,
                        orden=nuevo_orden,
                        antetitulo=textos_nueva.antetitulo, titulo=textos_nueva.titulo, texto=textos_nueva.texto,
                        destino=textos_nueva.destino,
                    )
                    fotos_actuales[nueva_foto.id] = nueva_foto

            # Limpiar config.banner si ya se migraron o existen fotos en FotoBanner
            if config.banner and (orden_list or FotoBanner.objects.filter(configuracion=config).exists()):
                config.banner = None
                config.save(update_fields=['banner'])

            # Los textos generales de la portada siguen a la primera foto: los usan el pie de página y el
            # título de la página (decidido el 2026-11-09)
            primera = FotoBanner.objects.filter(configuracion=config).order_by('orden', 'id').first()
            if primera is not None:
                generales = {'subtitulo_bienvenida': primera.antetitulo, 'texto_bienvenida': primera.titulo,
                             'texto_landing': primera.texto}
                distintos = [campo for campo, valor in generales.items() if getattr(config, campo) != valor]
                for campo in distintos:
                    setattr(config, campo, generales[campo])
                if distintos:
                    config.save(update_fields=distintos)

            # Borrar archivos del disco al confirmar
            _borrar_al_confirmar(archivos_a_borrar)

