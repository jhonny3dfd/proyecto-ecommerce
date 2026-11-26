"""Image decoding and references at the Django/storage boundary."""

from io import BytesIO
from pathlib import PurePosixPath
import re
from urllib.parse import unquote, urlsplit
import warnings

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.storage import default_storage
from django.core.validators import URLValidator
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework import serializers

from ecommerce.domain.imagenes import ImagenProcesada


FORMATOS = {
    'JPEG': ('image/jpeg', 'jpg', {'.jpg', '.jpeg'}),
    'PNG': ('image/png', 'png', {'.png'}),
    'WEBP': ('image/webp', 'webp', {'.webp'}),
}
CLAVE_IMAGEN = re.compile(
    r'catalogo/productos/(?P<producto>[0-9a-f]{24})/'
    r'(?P<id>[0-9a-f]{32}(?:_[A-Za-z0-9]{7})*)\.(?:jpg|png|webp)'
)


def es_imagen_gestionada(clave, producto_id=None):
    match = CLAVE_IMAGEN.fullmatch(clave)
    return bool(match and (producto_id is None or match['producto'] == str(producto_id)))


def url_imagen(clave, request=None):
    if not es_imagen_gestionada(clave):
        return clave
    url = default_storage.url(clave)
    return request.build_absolute_uri(url) if request is not None else url


def descriptor_imagen(clave, request=None):
    return {'id': CLAVE_IMAGEN.fullmatch(clave)['id'], 'url': url_imagen(clave, request)}


def normalizar_referencia_imagen(valor, producto=None, request=None):
    """Accept existing owned images or external HTTP(S) URLs, never arbitrary keys."""
    if producto is not None:
        for clave in producto.imagenes:
            if not es_imagen_gestionada(clave, producto.id):
                continue
            # Ignore a storage URL's temporary signature when round-tripping it.
            referencias = (clave, url_imagen(clave), url_imagen(clave, request))
            if valor.split('?', 1)[0] in {ref.split('?', 1)[0] for ref in referencias}:
                return clave
    try:
        URLValidator(schemes=['http', 'https'])(valor)
        if producto is not None and valor in producto.imagenes:
            return valor
        referencia = urlsplit(valor)
        path = unquote(referencia.path)
        if 'catalogo/productos/' in path:
            prefijo = default_storage.url('catalogo/productos/')
            prefijos = [prefijo]
            if request is not None:
                prefijos.append(request.build_absolute_uri(prefijo))
            for base in map(urlsplit, prefijos):
                if referencia.netloc.lower() == base.netloc.lower() and path.startswith(unquote(base.path)):
                    raise serializers.ValidationError('La imagen no pertenece a la galería de este producto.')
    except (DjangoValidationError, ValueError) as exc:
        raise serializers.ValidationError('Se requiere una URL HTTP(S) de imagen válida.') from exc
    return valor


class ReferenciaImagenField(serializers.CharField):
    def to_representation(self, value):
        return url_imagen(value, self.context.get('request')) if value else value


class ArchivoImagenField(serializers.FileField):
    """Decode fully, cap resource use and re-encode only raster pixels."""

    def to_internal_value(self, data):
        archivo = super().to_internal_value(data)
        max_bytes = settings.CATALOGO_IMAGEN_MAX_BYTES
        if archivo.size > max_bytes:
            raise serializers.ValidationError(f'El archivo supera el límite de {max_bytes} bytes.')
        archivo.seek(0)
        contenido = archivo.read(max_bytes + 1)
        if len(contenido) > max_bytes:
            raise serializers.ValidationError(f'El archivo supera el límite de {max_bytes} bytes.')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(BytesIO(contenido)) as imagen:
                    formato = imagen.format
                    if formato not in FORMATOS:
                        raise serializers.ValidationError('Solo se admiten imágenes JPEG, PNG y WebP.')
                    mime, extension, sufijos = FORMATOS[formato]
                    if (archivo.content_type or '').lower() != mime or PurePosixPath(archivo.name).suffix.lower() not in sufijos:
                        raise serializers.ValidationError('El MIME, la extensión y el contenido de la imagen deben coincidir.')
                    if imagen.width * imagen.height > settings.CATALOGO_IMAGEN_MAX_PIXELES:
                        raise serializers.ValidationError('La imagen supera el límite de píxeles permitido.')
                    if getattr(imagen, 'n_frames', 1) != 1:
                        raise serializers.ValidationError('No se admiten imágenes animadas.')
                    imagen.verify()
                with Image.open(BytesIO(contenido)) as imagen:
                    imagen.load()
                    orientada = ImageOps.exif_transpose(imagen)
                    modo = 'RGBA' if formato != 'JPEG' and (
                        'A' in orientada.getbands() or 'transparency' in orientada.info
                    ) else 'RGB'
                    with orientada.convert(modo) as limpia:
                        limpia.info.clear()
                        salida = BytesIO()
                        opciones = {'quality': 90} if formato in ('JPEG', 'WEBP') else {}
                        limpia.save(salida, format=formato, **opciones)
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError,
                Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise serializers.ValidationError('El archivo no contiene una imagen válida o está dañado.') from exc
        contenido_seguro = salida.getvalue()
        if len(contenido_seguro) > max_bytes:
            raise serializers.ValidationError('La imagen procesada supera el tamaño máximo permitido.')
        return ImagenProcesada(contenido=contenido_seguro, extension=extension)


class GaleriaUploadSerializer(serializers.Serializer):
    imagenes = serializers.ListField(child=ArchivoImagenField(), allow_empty=False)

    def validate_imagenes(self, imagenes):
        if len(imagenes) > settings.CATALOGO_IMAGEN_MAX_ARCHIVOS:
            raise serializers.ValidationError('Se ha superado el número máximo de archivos por petición.')
        return imagenes
