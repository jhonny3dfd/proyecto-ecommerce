"""Stop oversized multipart uploads before Django writes the entire file."""

from django.conf import settings
from django.core.files.uploadhandler import FileUploadHandler
from rest_framework.exceptions import APIException


class LimiteSubidaExcedido(APIException):
    status_code = 413
    default_detail = 'La petición supera los límites de subida de imágenes.'
    default_code = 'image_upload_limit'


class CatalogoImageUploadHandler(FileUploadHandler):
    def __init__(self, request=None):
        super().__init__(request)
        self.archivos = 0
        self.bytes_archivo = 0

    def new_file(self, *args, **kwargs):
        super().new_file(*args, **kwargs)
        self.archivos += 1
        self.bytes_archivo = 0
        if self.archivos > settings.CATALOGO_IMAGEN_MAX_ARCHIVOS:
            raise LimiteSubidaExcedido

    def receive_data_chunk(self, raw_data, start):
        self.bytes_archivo += len(raw_data)
        if self.bytes_archivo > settings.CATALOGO_IMAGEN_MAX_BYTES:
            raise LimiteSubidaExcedido
        return raw_data

    def file_complete(self, file_size):
        return None
