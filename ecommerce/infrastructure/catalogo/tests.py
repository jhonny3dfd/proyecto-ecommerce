"""Real MongoDB/storage integration and signed-JWT API tests for SCRUM-125."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from io import BytesIO, StringIO
import os
import shutil
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import uuid4

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings, TestCase
from django.urls import reverse
from PIL import Image, PngImagePlugin
from pymongo import MongoClient
from pymongo.errors import OperationFailure
from rest_framework.test import APITestCase, APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status

from ecommerce.domain.imagenes import GaleriaEnConflicto
from ecommerce.infrastructure.usuarios.tests.factories import create_user
from .documents import ImagenPendienteBorrado, Producto, Variante
from .image_adapters import RepositorioGaleriaMongo, servicio_galeria
from .images import GaleriaUploadSerializer, es_imagen_gestionada
from .permissions import LecturaPublicaEscrituraAdmin
from .serializers import ProductoSerializer
from .views import ProductoListCreateView


def imagen_archivo(nombre='foto.png', formato='PNG', mime='image/png', size=(12, 8)):
    contenido = BytesIO()
    with Image.new('RGB', size, color='green') as imagen:
        imagen.save(contenido, format=formato)
    return SimpleUploadedFile(nombre, contenido.getvalue(), content_type=mime)


class ValidacionImagenTests(SimpleTestCase):
    def validar(self, archivo):
        serializer = GaleriaUploadSerializer(data={'imagenes': [archivo]})
        serializer.is_valid()
        return serializer

    def test_admite_jpeg_png_webp_y_genera_extension_canonica(self):
        for formato, nombre, mime, extension in [
            ('JPEG', 'foto.JPEG', 'image/jpeg', 'jpg'),
            ('PNG', 'foto.png', 'image/png', 'png'),
            ('WEBP', 'foto.webp', 'image/webp', 'webp'),
        ]:
            with self.subTest(formato=formato):
                serializer = self.validar(imagen_archivo(nombre, formato, mime))
                self.assertFalse(serializer.errors)
                self.assertEqual(serializer.validated_data['imagenes'][0].extension, extension)

    def test_regenera_pixeles_sin_metadatos_ni_contenido_adjuntado(self):
        buffer = BytesIO()
        info = PngImagePlugin.PngInfo()
        info.add_text('secreto', 'metadato-privado')
        with Image.new('RGB', (12, 8)) as imagen:
            imagen.save(buffer, format='PNG', pnginfo=info)
        archivo = SimpleUploadedFile('foto.png', buffer.getvalue() + b'<script>evil</script>', content_type='image/png')
        serializer = self.validar(archivo)
        self.assertFalse(serializer.errors)
        procesada = serializer.validated_data['imagenes'][0].contenido
        self.assertNotIn(b'metadato-privado', procesada)
        self.assertNotIn(b'<script>', procesada)
        with Image.open(BytesIO(procesada)) as imagen:
            self.assertEqual(imagen.size, (12, 8))

    def test_rechaza_contenido_falso_mime_extension_svg_y_archivo_vacio(self):
        archivos = [
            SimpleUploadedFile('foto.png', b'not an image', content_type='image/png'),
            imagen_archivo(mime='image/jpeg'),
            imagen_archivo(nombre='foto.jpg'),
            SimpleUploadedFile('foto.svg', b'<svg/>', content_type='image/svg+xml'),
            SimpleUploadedFile('foto.png', b'', content_type='image/png'),
            imagen_archivo('foto.gif', 'GIF', 'image/gif'),
        ]
        for archivo in archivos:
            with self.subTest(nombre=archivo.name, mime=archivo.content_type):
                self.assertTrue(self.validar(archivo).errors)

    @override_settings(CATALOGO_IMAGEN_MAX_BYTES=20)
    def test_rechaza_tamano_excesivo(self):
        self.assertTrue(self.validar(imagen_archivo()).errors)

    @override_settings(CATALOGO_IMAGEN_MAX_PIXELES=50)
    def test_rechaza_dimensiones_excesivas_antes_de_decodificar(self):
        self.assertTrue(self.validar(imagen_archivo()).errors)

    def test_rechaza_bomba_de_descompresion(self):
        archivo = imagen_archivo()
        with patch.object(Image, 'MAX_IMAGE_PIXELS', 50):
            self.assertTrue(self.validar(archivo).errors)

    def test_rechaza_imagen_animada(self):
        buffer = BytesIO()
        with Image.new('RGB', (12, 8), 'green') as uno, Image.new('RGB', (12, 8), 'red') as dos:
            uno.save(buffer, format='WEBP', save_all=True, append_images=[dos], duration=100, loop=0)
        archivo = SimpleUploadedFile('foto.webp', buffer.getvalue(), content_type='image/webp')
        self.assertTrue(self.validar(archivo).errors)

    def test_orienta_jpeg_y_elimina_exif(self):
        buffer = BytesIO()
        with Image.new('RGB', (12, 8)) as imagen:
            exif = imagen.getexif()
            exif[274] = 6
            exif[315] = 'private author'
            imagen.save(buffer, format='JPEG', exif=exif)
        archivo = SimpleUploadedFile('foto.jpg', buffer.getvalue(), content_type='image/jpeg')
        serializer = self.validar(archivo)
        self.assertFalse(serializer.errors)
        with Image.open(BytesIO(serializer.validated_data['imagenes'][0].contenido)) as imagen:
            self.assertEqual(imagen.size, (8, 12))
            self.assertFalse(imagen.getexif())

    def test_conserva_transparencia_png(self):
        buffer = BytesIO()
        with Image.new('RGBA', (12, 8), (10, 20, 30, 40)) as imagen:
            imagen.save(buffer, format='PNG')
        archivo = SimpleUploadedFile('foto.png', buffer.getvalue(), content_type='image/png')
        serializer = self.validar(archivo)
        self.assertFalse(serializer.errors)
        with Image.open(BytesIO(serializer.validated_data['imagenes'][0].contenido)) as imagen:
            self.assertEqual(imagen.getpixel((0, 0)), (10, 20, 30, 40))


class GaleriaAPITests(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Only bind MongoEngine's collections to a newly named test database.
        # All queries, array filters and persistence still use real MongoDB.
        cls.mongo_client = MongoClient(
            os.environ.get('MONGO_TEST_URI', settings.MONGO_URI), serverSelectionTimeoutMS=5000,
        )
        cls.addClassCleanup(cls.mongo_client.close)
        cls.mongo_client.admin.command('ping')
        cls.mongo_db_name = f'test_ecode_catalogo_{uuid4().hex}'
        cls.addClassCleanup(cls.mongo_client.drop_database, cls.mongo_db_name)
        cls.mongo_db = cls.mongo_client[cls.mongo_db_name]
        for documento in (Producto, ImagenPendienteBorrado):
            collection = cls.mongo_db[documento._meta['collection']]
            binding = patch.object(documento, '_get_collection', return_value=collection)
            binding.start()
            cls.addClassCleanup(binding.stop)
        ImagenPendienteBorrado._get_collection().create_index('clave', unique=True)

    @classmethod
    def setUpTestData(cls):
        cls.admin = create_user('catalogo-admin@example.test', rol='ADMIN')
        cls.comprador = create_user('catalogo-comprador@example.test')

    def setUp(self):
        Producto._get_collection().delete_many({})
        ImagenPendienteBorrado._get_collection().delete_many({})
        task_tmp = settings.BASE_DIR / '.tmp'
        task_tmp.mkdir(exist_ok=True)
        # Inherit the workspace ACL on Windows. tempfile's mode 0700 excludes
        # the restricted execution identity used by the desktop test runner.
        self.media_root = (task_tmp / f'catalogo-test-{uuid4().hex}').resolve()
        self.media_root.mkdir()
        self.addCleanup(self.limpiar_media, task_tmp.resolve())
        self.media_settings = override_settings(
            MEDIA_ROOT=str(self.media_root), MEDIA_URL='/media/',
            STORAGES={
                'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
            },
        )
        self.media_settings.enable()
        self.addCleanup(self.media_settings.disable)
        self.producto = Producto(
            nombre='Polera', categoria='Ropa', fecha_creacion=datetime.now(timezone.utc),
            atributos_globales={'material': 'algodón'},
            variantes=[Variante(sku='POL-VERDE', precio='10990.00', stock=7,
                                atributos_variables={'color': 'verde'})],
        ).save()
        self.url = reverse('imagenes_producto', kwargs={'id': str(self.producto.id)})
        self.detalle = reverse('detalle_producto', kwargs={'id': str(self.producto.id)})
        self.autorizar(self.admin)

    def autorizar(self, usuario):
        token = str(RefreshToken.for_user(usuario).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def subir(self, *archivos):
        return self.client.post(self.url, {'imagenes': list(archivos or [imagen_archivo()])}, format='multipart')

    def url_borrado(self, imagen_id, producto_id=None):
        return reverse('detalle_imagen_producto', kwargs={
            'id': str(producto_id or self.producto.id), 'imagen_id': imagen_id,
        })

    def archivos_guardados(self):
        return [path for path in self.media_root.rglob('*') if path.is_file()]

    def limpiar_media(self, raiz_temporal):
        self.assertEqual(self.media_root.parent, raiz_temporal)
        self.assertTrue(self.media_root.name.startswith('catalogo-test-'))
        shutil.rmtree(self.media_root)

    def test_subida_individual_devuelve_url_absoluta_y_clave_segura_en_mongo(self):
        response = self.subir(imagen_archivo('../../nombre-privado.png'))
        self.assertEqual(response.status_code, 201, response.data)
        self.producto.reload()
        clave, = self.producto.imagenes
        self.assertTrue(es_imagen_gestionada(clave, self.producto.id))
        self.assertNotIn('nombre-privado', clave)
        self.assertEqual(response.data['imagenes'], [f'http://testserver/media/{clave}'])
        self.assertEqual(response.data['subidas'], response.data['archivos'])
        with default_storage.open(clave) as archivo, Image.open(archivo) as imagen:
            self.assertEqual(imagen.format, 'PNG')
            self.assertEqual(imagen.size, (12, 8))
        self.assertEqual(self.producto.variantes[0].stock, 7)
        self.assertEqual(self.producto.variantes[0].sku, 'POL-VERDE')

    def test_lote_conserva_orden_y_galeria_previa(self):
        self.producto.imagenes = ['https://example.test/legacy.jpg']
        self.producto.save()
        response = self.subir(imagen_archivo(), imagen_archivo('foto.jpg', 'JPEG', 'image/jpeg'))
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(len(response.data['subidas']), 2)
        self.assertEqual(response.data['imagenes'][0], 'https://example.test/legacy.jpg')
        self.assertTrue(response.data['imagenes'][1].endswith('.png'))
        self.assertTrue(response.data['imagenes'][2].endswith('.jpg'))
        get = self.client.get(self.url)
        self.assertEqual(get.data['archivos'], response.data['archivos'])
        # El público solo ve productos publicados
        Producto.objects(id=self.producto.id).update(set__publicado=True)
        self.client.credentials()
        public = self.client.get(self.detalle)
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public.data['imagenes'], response.data['imagenes'])
        listado = self.client.get(reverse('lista_productos'))
        items = listado.data.get('results', listado.data) if isinstance(listado.data, dict) else listado.data
        self.assertEqual(items[0]['imagenes'], public.data['imagenes'])

    def test_urls_del_storage_externo_y_round_trip(self):
        with override_settings(STORAGES={'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
            'OPTIONS': {'base_url': 'https://cdn.example.test/assets/'},
        }}):
            response = self.subir()
            self.assertEqual(response.status_code, 201)
            self.assertTrue(response.data['imagenes'][0].startswith('https://cdn.example.test/assets/'))
            updated = self.client.patch(self.detalle, {'imagenes': response.data['imagenes']}, format='json')
            self.assertEqual(updated.status_code, 200, updated.data)
            self.producto.reload()
            self.assertTrue(es_imagen_gestionada(self.producto.imagenes[0]))

    def test_conserva_urls_externas_con_rutas_parecidas_al_storage(self):
        referencia = 'https://external.example.test/catalogo/productos/externo/foto.png'
        response = self.client.patch(self.detalle, {'imagenes': [referencia]}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['imagenes'], [referencia])

    def test_edicion_variantes_actualiza_precio_minimo_vigente_en_mongo(self):
        """SCRUM-179 / E01: La API de edición persiste precio_minimo_vigente en MongoDB."""
        self.producto.actualizar_precio_minimo_vigente()
        self.assertEqual(float(self.producto.precio_minimo_vigente), 10990.0)
        nuevas_variantes = [{
            'sku': 'POL-VERDE',
            'precio': '10990.00',
            'precio_oferta': '2990.00',
            'stock': 7,
        }]
        response = self.client.patch(self.detalle, {'variantes': nuevas_variantes}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.producto.reload()
        self.assertEqual(float(self.producto.precio_minimo_vigente), 2990.0)

    def test_lote_invalido_no_asocia_ni_guarda_archivos(self):
        response = self.subir(imagen_archivo(), SimpleUploadedFile('falsa.png', b'bad', content_type='image/png'))
        self.assertEqual(response.status_code, 400)
        self.producto.reload()
        self.assertEqual(self.producto.imagenes, [])
        self.assertEqual(self.archivos_guardados(), [])

    def test_campo_ausente_formato_incorrecto_y_campos_extra(self):
        self.assertEqual(self.client.post(self.url, {}, format='multipart').status_code, 400)
        self.assertEqual(self.client.post(self.url, {'imagenes': []}, format='json').status_code, 415)
        response = self.client.post(self.url, {'imagenes': imagen_archivo(), 'otro': 'dato'}, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.archivos_guardados(), [])

    @override_settings(CATALOGO_IMAGEN_MAX_BYTES=20)
    def test_limite_de_bytes_se_interrumpe_en_parser(self):
        response = self.subir()
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.archivos_guardados(), [])

    @override_settings(CATALOGO_IMAGEN_MAX_ARCHIVOS=1)
    def test_limite_de_archivos_se_interrumpe_en_parser(self):
        self.assertEqual(self.subir(imagen_archivo(), imagen_archivo()).status_code, 413)
        self.assertEqual(self.archivos_guardados(), [])

    @override_settings(CATALOGO_IMAGEN_MAX_GALERIA=1)
    def test_limite_de_galeria_cuenta_imagenes_existentes(self):
        self.assertEqual(self.subir().status_code, 201)
        self.assertEqual(self.subir().status_code, 400)
        self.assertEqual(len(self.archivos_guardados()), 1)

    def test_imagen_y_producto_inexistentes_retornan_404(self):
        for id in ['invalid-id', '0' * 24]:
            response = self.client.post(reverse('imagenes_producto', kwargs={'id': id}),
                                        {'imagenes': imagen_archivo()}, format='multipart')
            self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.delete(self.url_borrado('0' * 32)).status_code, 404)
        self.assertEqual(self.archivos_guardados(), [])

    def test_solo_admin_activo_puede_gestionar_imagenes_y_escribir_productos(self):
        for usuario, esperado in [(None, 401), (self.comprador, 403)]:
            if usuario is None:
                self.client.credentials()
            else:
                self.autorizar(usuario)
            with self.subTest(usuario=usuario):
                self.assertEqual(self.subir().status_code, esperado)
                self.assertEqual(self.client.get(self.url).status_code, esperado)
                self.assertEqual(self.client.delete(self.url_borrado('0' * 32)).status_code, esperado)
                self.assertEqual(self.client.post(reverse('lista_productos'), {}, format='json').status_code, esperado)
                self.assertEqual(self.client.put(self.detalle, {}, format='json').status_code, esperado)
                self.assertEqual(self.client.patch(self.detalle, {}, format='json').status_code, esperado)
                self.assertEqual(self.client.delete(self.detalle).status_code, esperado)
        self.assertEqual(self.archivos_guardados(), [])

    def test_token_invalido_y_admin_degradado_o_inactivo(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer token-invalido')
        self.assertEqual(self.subir().status_code, 401)
        self.autorizar(self.admin)
        type(self.admin).objects.filter(pk=self.admin.pk).update(rol='COMPRADOR')
        self.assertEqual(self.subir().status_code, 403)
        type(self.admin).objects.filter(pk=self.admin.pk).update(rol='ADMIN', is_active=False)
        self.assertEqual(self.subir().status_code, 401)

    def test_asociacion_de_variante_y_borrado_preservan_stock_concurrente(self):
        response = self.subir()
        imagen_id = response.data['subidas'][0]['id']
        url = response.data['imagenes'][0]
        payload = {'variantes': [{'sku': 'POL-VERDE', 'precio': '10990.00', 'stock': 7,
                                 'atributos_variables': {'color': 'verde'}, 'imagen_especifica': url}]}
        update = self.client.patch(self.detalle, payload, format='json')
        self.assertEqual(update.status_code, 200, update.data)
        self.assertEqual(update.data['variantes'][0]['imagen_especifica'], url)
        self.producto.reload()
        clave = self.producto.imagenes[0]
        # Simulate a sale after the gallery snapshot was loaded.
        Producto.objects(id=self.producto.id).update_one(__raw__={'$inc': {'variantes.0.stock': -1}})
        servicio_galeria().eliminar(str(self.producto.id), list(self.producto.imagenes), clave)
        self.producto.reload()
        self.assertEqual(self.producto.imagenes, [])
        self.assertIsNone(self.producto.variantes[0].imagen_especifica)
        self.assertEqual(self.producto.variantes[0].stock, 6)
        self.assertEqual(self.producto.variantes[0].sku, 'POL-VERDE')
        self.assertEqual(self.producto.variantes[0].atributos_variables, {'color': 'verde'})
        self.assertFalse(default_storage.exists(clave))
        self.assertEqual(self.client.delete(self.url_borrado(imagen_id)).status_code, 404)

    def test_no_permite_asociar_o_borrar_imagen_de_otro_producto(self):
        response = self.subir()
        otro = Producto(nombre='Otro', categoria='Ropa', fecha_creacion=datetime.now(timezone.utc)).save()
        detail = reverse('detalle_producto', kwargs={'id': str(otro.id)})
        self.assertEqual(self.client.patch(detail, {'imagenes': response.data['imagenes']}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(self.url_borrado(response.data['archivos'][0]['id'], otro.id)).status_code, 404)
        self.assertEqual(len(self.archivos_guardados()), 1)

    def test_rechaza_rutas_locales_esquemas_peligrosos_y_duplicados(self):
        for referencias in [['../archivo.png'], ['javascript:alert(1)'], ['data:image/png;base64,abcd'],
                            ['https://example.test/a.png', 'https://example.test/a.png']]:
            with self.subTest(referencias=referencias):
                self.assertEqual(self.client.patch(self.detalle, {'imagenes': referencias}, format='json').status_code, 400)

    def test_round_trip_reordena_y_eliminar_por_patch_limpia_storage(self):
        response = self.subir(imagen_archivo(), imagen_archivo('dos.jpg', 'JPEG', 'image/jpeg'))
        urls = response.data['imagenes']
        updated = self.client.patch(self.detalle, {'imagenes': urls[::-1]}, format='json')
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(updated.data['imagenes'], urls[::-1])
        response = self.client.patch(self.detalle, {'imagenes': [urls[0]]}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.archivos_guardados()), 1)
        # Omission on PUT preserves the current gallery.
        response = self.client.put(self.detalle, {'nombre': 'Polera nueva', 'categoria': 'Ropa'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['imagenes'], [urls[0]])

    def test_eliminar_producto_limpia_solo_sus_archivos(self):
        self.subir()
        self.producto.reload()
        self.producto.imagenes.append('https://example.test/external.png')
        self.producto.save()
        self.assertEqual(self.client.delete(self.detalle).status_code, 204)
        self.assertIsNone(Producto.objects(id=self.producto.id).first())
        self.assertEqual(self.archivos_guardados(), [])
        self.assertEqual(ImagenPendienteBorrado.objects.count(), 0)

    def test_fallo_del_segundo_archivo_revierte_primero(self):
        guardar = default_storage.save
        def fallo(nombre, contenido, *args, **kwargs):
            if nombre.endswith('.jpg'):
                raise OSError('storage unavailable')
            return guardar(nombre, contenido, *args, **kwargs)
        with patch.object(default_storage, 'save', side_effect=fallo), self.assertLogs(level='ERROR'):
            response = self.subir(imagen_archivo(), imagen_archivo('dos.jpg', 'JPEG', 'image/jpeg'))
        self.assertEqual(response.status_code, 503)
        self.producto.reload()
        self.assertEqual(self.producto.imagenes, [])
        self.assertEqual(self.archivos_guardados(), [])

    def test_fallo_de_mongo_no_expone_detalles_y_revierte_archivos(self):
        with patch.object(RepositorioGaleriaMongo, 'asociar', side_effect=OperationFailure('sensitive-details')), self.assertLogs(level='ERROR'):
            response = self.subir()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('sensitive-details', str(response.data))
        self.assertEqual(self.archivos_guardados(), [])

    def test_conflicto_de_galeria_revierte_solo_lote_nuevo(self):
        asociar = RepositorioGaleriaMongo.asociar
        def concurrente(repo, producto_id, anteriores, nuevas):
            Producto.objects(id=producto_id).update_one(push__imagenes='https://example.test/concurrente.png')
            return asociar(repo, producto_id, anteriores, nuevas)
        with patch.object(RepositorioGaleriaMongo, 'asociar', new=concurrente):
            response = self.subir()
        self.assertEqual(response.status_code, 409)
        self.producto.reload()
        self.assertEqual(self.producto.imagenes, ['https://example.test/concurrente.png'])
        self.assertEqual(self.archivos_guardados(), [])

    def test_patch_con_galeria_desactualizada_no_pierde_subida(self):
        self.producto.reload()
        serializer = ProductoSerializer(self.producto, data={'imagenes': []}, partial=True)
        serializer.is_valid(raise_exception=True)
        self.subir()
        with self.assertRaises(GaleriaEnConflicto):
            serializer.save()
        self.assertEqual(len(self.archivos_guardados()), 1)

    def test_borrado_fallido_persiste_y_comando_reintenta(self):
        response = self.subir()
        self.producto.reload()
        clave = self.producto.imagenes[0]
        with patch.object(default_storage, 'delete', side_effect=OSError('storage unavailable')), self.assertLogs(level='ERROR'):
            response = self.client.delete(self.url_borrado(response.data['archivos'][0]['id']))
        self.assertEqual(response.status_code, 204)
        self.producto.reload()
        self.assertEqual(self.producto.imagenes, [])
        self.assertTrue(default_storage.exists(clave))
        self.assertEqual(ImagenPendienteBorrado.objects.get().clave, clave)
        call_command('limpiar_imagenes_catalogo', stdout=StringIO())
        self.assertFalse(default_storage.exists(clave))
        self.assertEqual(ImagenPendienteBorrado.objects.count(), 0)

    def test_comando_no_borra_archivos_que_siguen_asociados(self):
        self.subir()
        self.producto.reload()
        clave = self.producto.imagenes[0]
        RepositorioGaleriaMongo().programar_borrado([clave])
        call_command('limpiar_imagenes_catalogo', stdout=StringIO())
        self.assertTrue(default_storage.exists(clave))
        self.assertEqual(ImagenPendienteBorrado.objects.count(), 1)

    def test_documento_antiguo_sin_galeria_o_variantes(self):
        Producto._get_collection().update_one(
            {'_id': self.producto.id}, {'$unset': {'imagenes': 1, 'variantes': 1}},
        )
        response = self.subir()
        self.assertEqual(response.status_code, 201, response.data)
        borrado = self.client.delete(self.url_borrado(response.data['archivos'][0]['id']))
        self.assertEqual(borrado.status_code, 204, borrado.data)
        self.assertEqual(self.archivos_guardados(), [])

    def test_fallo_despues_de_escribir_archivo_tambien_lo_limpia(self):
        guardar = default_storage.save
        def fallo(nombre, contenido, *args, **kwargs):
            guardar(nombre, contenido, *args, **kwargs)
            raise OSError('failure after partial write')
        with patch.object(default_storage, 'save', side_effect=fallo), self.assertLogs(level='ERROR'):
            response = self.subir()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.archivos_guardados(), [])
        self.assertEqual(ImagenPendienteBorrado.objects.count(), 0)

    def test_timeout_despues_de_asociar_no_borra_imagen_confirmada(self):
        asociar = RepositorioGaleriaMongo.asociar
        def fallo(repo, producto_id, anteriores, nuevas):
            asociar(repo, producto_id, anteriores, nuevas)
            raise OperationFailure('timeout after commit')
        with patch.object(RepositorioGaleriaMongo, 'asociar', new=fallo), self.assertLogs(level='ERROR'):
            response = self.subir()
        self.assertEqual(response.status_code, 503)
        self.producto.reload()
        self.assertEqual(len(self.producto.imagenes), 1)
        self.assertTrue(default_storage.exists(self.producto.imagenes[0]))

    def test_borrado_por_patch_limpia_referencia_sin_reemplazar_variantes(self):
        response = self.subir()
        self.producto.reload()
        self.producto.variantes[0].imagen_especifica = self.producto.imagenes[0]
        self.producto.save()
        response = self.client.patch(self.detalle, {'imagenes': []}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.producto.reload()
        self.assertIsNone(self.producto.variantes[0].imagen_especifica)
        self.assertEqual(self.producto.variantes[0].stock, 7)

    def test_borrado_por_url_del_endpoint_elimina_el_archivo(self):
        response = self.subir()
        borrado = self.client.delete(self.url_borrado(response.data['archivos'][0]['id']))
        self.assertEqual(borrado.status_code, 204)
        self.assertEqual(self.archivos_guardados(), [])

    def quitar_enlace(self, url):
        ruta = reverse('enlace_imagen_producto', kwargs={'id': str(self.producto.id)})
        return self.client.delete(f"{ruta}?{urlencode({'url': url})}")

    def test_quitar_enlace_externo_solo_lo_saca_de_la_galeria(self):
        enlace = 'https://example.test/img/camisa-azul.jpg'
        subida = self.subir().data['imagenes'][0]
        self.assertEqual(self.client.patch(self.detalle, {'imagenes': [enlace, subida]}, format='json').status_code, 200)
        self.producto.reload()
        self.producto.variantes[0].imagen_especifica = enlace
        self.producto.save()

        self.assertEqual(self.quitar_enlace(enlace).status_code, 204)

        self.producto.reload()
        self.assertEqual(len(self.producto.imagenes), 1)
        self.assertTrue(es_imagen_gestionada(self.producto.imagenes[0], self.producto.id))
        self.assertIsNone(self.producto.variantes[0].imagen_especifica)
        # La foto subida y su archivo siguen intactos
        self.assertEqual(len(self.archivos_guardados()), 1)

    def test_quitar_enlace_no_borra_fotos_subidas_ni_enlaces_ajenos(self):
        respuesta = self.subir().data
        self.producto.reload()
        for url in (respuesta['imagenes'][0], self.producto.imagenes[0], 'https://example.test/otra.jpg', ''):
            with self.subTest(url=url):
                self.assertEqual(self.quitar_enlace(url).status_code, 404)
        self.producto.reload()
        self.assertEqual(len(self.producto.imagenes), 1)
        self.assertEqual(len(self.archivos_guardados()), 1)

    def test_quitar_enlace_es_solo_para_el_admin(self):
        enlace = 'https://example.test/img/camisa-azul.jpg'
        Producto.objects(id=self.producto.id).update_one(set__imagenes=[enlace])
        self.autorizar(self.comprador)
        self.assertEqual(self.quitar_enlace(enlace).status_code, 403)
        self.producto.reload()
        self.assertEqual(self.producto.imagenes, [enlace])


def usar_mongo_de_prueba(cls):
    """Liga Producto a una base Mongo temporal, que se borra al terminar la clase de tests."""
    cliente = MongoClient(
        os.environ.get('MONGO_TEST_URI', settings.MONGO_URI), serverSelectionTimeoutMS=5000,
    )
    cls.addClassCleanup(cliente.close)
    nombre_base = f'test_ecode_{uuid4().hex}'
    cls.addClassCleanup(cliente.drop_database, nombre_base)
    binding = patch.object(Producto, '_get_collection', return_value=cliente[nombre_base]['productos'])
    binding.start()
    cls.addClassCleanup(binding.stop)


class ReducirStockVarianteTests(SimpleTestCase):
    """RN-03: el descuento de stock es atómico y condicional."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        usar_mongo_de_prueba(cls)

    def setUp(self):
        Producto._get_collection().delete_many({})
        self.producto = Producto(
            nombre='Polera', categoria='Ropa', fecha_creacion=datetime.now(timezone.utc),
            variantes=[Variante(sku='POLERA-S', precio=10000, stock=3),
                       Variante(sku='POLERA-M', precio=10000, stock=5)],
        ).save()

    def stock(self, sku):
        self.producto.reload()
        return next(v.stock for v in self.producto.variantes if v.sku == sku)

    def reducir(self, sku, cantidad, producto_id=None):
        return Producto.reducir_stock_variante(str(producto_id or self.producto.id), sku, cantidad)

    def test_descuenta_solo_la_variante_indicada(self):
        self.assertTrue(self.reducir('POLERA-S', 2))
        self.assertEqual(self.stock('POLERA-S'), 1)
        self.assertEqual(self.stock('POLERA-M'), 5)

    def test_stock_insuficiente_no_modifica_nada(self):
        self.assertFalse(self.reducir('POLERA-S', 4))
        self.assertEqual(self.stock('POLERA-S'), 3)

    def test_sku_o_producto_inexistente_devuelve_false(self):
        self.assertFalse(self.reducir('NO-EXISTE', 1))
        self.assertFalse(self.reducir('POLERA-S', 1, producto_id='64b000000000000000000000'))
        self.assertFalse(self.reducir('POLERA-S', 1, producto_id='no-es-un-id'))
        self.assertEqual(self.stock('POLERA-S'), 3)

    def test_cantidad_no_positiva_no_descuenta(self):
        for cantidad in (0, -2):
            with self.subTest(cantidad=cantidad):
                self.assertFalse(self.reducir('POLERA-S', cantidad))
        self.assertEqual(self.stock('POLERA-S'), 3)

    def test_compras_simultaneas_de_la_ultima_unidad_producen_una_sola_venta(self):
        self.assertTrue(self.reducir('POLERA-S', 2))
        with ThreadPoolExecutor(max_workers=10) as pool:
            resultados = list(pool.map(lambda _: self.reducir('POLERA-S', 1), range(10)))
        self.assertEqual(resultados.count(True), 1)
        self.assertEqual(self.stock('POLERA-S'), 0)

    def test_reponer_devuelve_stock_solo_a_la_variante_indicada(self):
        self.assertTrue(Producto.reponer_stock_variante(str(self.producto.id), 'POLERA-S', 2))
        self.assertEqual(self.stock('POLERA-S'), 5)
        self.assertEqual(self.stock('POLERA-M'), 5)
        for producto_id, sku, cantidad in ((self.producto.id, 'NO-EXISTE', 1),
                                           ('no-es-un-id', 'POLERA-S', 1),
                                           (self.producto.id, 'POLERA-S', 0)):
            with self.subTest(sku=sku, cantidad=cantidad):
                self.assertFalse(Producto.reponer_stock_variante(str(producto_id), sku, cantidad))
        self.assertEqual(self.stock('POLERA-S'), 5)


class CatalogoPublicoTests(APITestCase):
    """El público solo ve productos activos y publicados; el admin también ve los borradores."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        usar_mongo_de_prueba(cls)

    @classmethod
    def setUpTestData(cls):
        cls.admin = create_user('catalogo-admin@example.test', rol='ADMIN')
        cls.comprador = create_user('catalogo-comprador@example.test')

    def setUp(self):
        Producto._get_collection().delete_many({})
        self.productos = {
            nombre: Producto(nombre=nombre, categoria='Ropa', fecha_creacion=datetime.now(timezone.utc),
                             activo=activo, publicado=publicado).save()
            for nombre, activo, publicado in (
                ('Publicado', True, True), ('Borrador', True, False), ('Inactivo', False, True),
            )
        }

    def autenticar(self, usuario):
        token = RefreshToken.for_user(usuario).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def listado(self):
        response = self.client.get(reverse('lista_productos'))
        self.assertEqual(response.status_code, 200)
        items = response.data.get('results', response.data) if isinstance(response.data, dict) else response.data
        return sorted(producto['nombre'] for producto in items)

    def detalle(self, nombre):
        return self.client.get(reverse('detalle_producto', args=[self.productos[nombre].id]))

    def test_publico_y_compradores_solo_ven_productos_publicados(self):
        for usuario in (None, self.comprador):
            with self.subTest(usuario=usuario and usuario.rol):
                if usuario:
                    self.autenticar(usuario)
                self.assertEqual(self.listado(), ['Publicado'])
                self.assertEqual(self.detalle('Publicado').status_code, 200)
                for nombre in ('Borrador', 'Inactivo'):
                    self.assertEqual(self.detalle(nombre).status_code, 404)

    def test_admin_ve_los_borradores_en_el_inventario(self):
        self.autenticar(self.admin)
        self.assertEqual(self.listado(), ['Borrador', 'Publicado'])
        self.assertEqual(self.detalle('Borrador').status_code, 200)


class VarianteDatosImposiblesTests(SimpleTestCase):
    """RN-03 y RF-02.3: stock, precio, peso y medidas que no pueden existir no se guardan."""

    def test_rechaza_cada_valor_imposible_en_su_campo(self):
        from .serializers import VarianteSerializer
        base = {'sku': 'QA-1', 'precio': '10000', 'stock': 5, 'peso_kg': 0.5,
                'alto_cm': 10, 'ancho_cm': 10, 'largo_cm': 10}
        for campo, valor in (('stock', -5), ('peso_kg', 0), ('peso_kg', -1), ('alto_cm', 0), ('ancho_cm', -3),
                             ('largo_cm', 5000), ('precio', '990.75'), ('precio_oferta', '8000.50'),
                             ('sku', 'X' * 65)):
            with self.subTest(campo=campo, valor=valor):
                serializer = VarianteSerializer(data={**base, campo: valor})
                self.assertFalse(serializer.is_valid())
                self.assertIn(campo, serializer.errors)

    def test_acepta_stock_cero_y_precios_enteros_con_ceros_decimales(self):
        from .serializers import VarianteSerializer
        serializer = VarianteSerializer(data={'sku': 'QA-2', 'precio': '19990.00', 'precio_oferta': '15990',
                                              'stock': 0})
        self.assertTrue(serializer.is_valid(), serializer.errors)


class VariantePrecioOfertaTests(SimpleTestCase):
    """Pruebas para E01 de SCRUM-136: validación de límites de precio_oferta."""

    def test_variante_acepta_precio_oferta_valido(self):
        from .serializers import VarianteSerializer
        serializer = VarianteSerializer(data={
            'sku': 'QA-VALIDO',
            'precio': '10000.00',
            'precio_oferta': '8000.00',
            'stock': 5,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(float(serializer.validated_data['precio_oferta']), 8000.0)

    def test_variante_rechaza_precio_oferta_cero(self):
        from .serializers import VarianteSerializer
        serializer = VarianteSerializer(data={
            'sku': 'QA-CERO',
            'precio': '10000.00',
            'precio_oferta': '0.00',
            'stock': 5,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('precio_oferta', serializer.errors)

    def test_variante_rechaza_precio_oferta_negativo(self):
        from .serializers import VarianteSerializer
        serializer = VarianteSerializer(data={
            'sku': 'QA-NEGATIVO',
            'precio': '10000.00',
            'precio_oferta': '-500.00',
            'stock': 5,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('precio_oferta', serializer.errors)

    def test_variante_rechaza_precio_oferta_mayor_o_igual_a_precio(self):
        from .serializers import VarianteSerializer
        serializer_mayor = VarianteSerializer(data={
            'sku': 'QA-MAYOR',
            'precio': '10000.00',
            'precio_oferta': '12000.00',
            'stock': 5,
        })
        self.assertFalse(serializer_mayor.is_valid())
        self.assertIn('precio_oferta', serializer_mayor.errors)

        serializer_igual = VarianteSerializer(data={
            'sku': 'QA-IGUAL',
            'precio': '10000.00',
            'precio_oferta': '10000.00',
            'stock': 5,
        })
        self.assertFalse(serializer_igual.is_valid())
        self.assertIn('precio_oferta', serializer_igual.errors)

    def test_producto_rechaza_skus_duplicados_en_variantes(self):
        from .serializers import ProductoSerializer
        serializer = ProductoSerializer(data={
            'nombre': 'Consola Test',
            'categoria': 'Videojuegos',
            'variantes': [
                {'sku': 'SKU-DUP', 'precio': '10000.00', 'stock': 5},
                {'sku': 'SKU-DUP', 'precio': '20000.00', 'stock': 2},
            ]
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('variantes', serializer.errors)

class ColeccionesBackendTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # 1. Usar BD de prueba (Requisito crítico del feedback)
        usar_mongo_de_prueba(cls)

    def setUp(self):
        self.client = APIClient()
        Producto._get_collection().delete_many({})
        self.comprobar_permisos_originales()
        self.addCleanup(self.comprobar_permisos_originales)
        self.admin = create_user(rol='ADMIN')
        refresh = RefreshToken.for_user(self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    def comprobar_permisos_originales(self):
        self.assertEqual(ProductoListCreateView.permission_classes, [LecturaPublicaEscrituraAdmin])

    def test_comprador_no_puede_crear_productos(self):
        comprador = create_user('colecciones-comprador@example.test', rol='COMPRADOR')
        refresh = RefreshToken.for_user(comprador)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        response = self.client.post('/api/catalogo/productos/', {
            'nombre': 'Producto no autorizado', 'categoria': 'Electronica',
            'colecciones': ['Cyber'],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Producto.objects.count(), 0)

    def test_guardar_colecciones_normalizadas(self):
        """Verifica que se eliminen espacios extra y duplicados case-insensitive al guardar."""
        payload = {
            "nombre": "Teclado Mecánico",
            "precio": 50000,
            "activo": True,
            "publicado": True,
            "categoria": "Electronica",
            # Enviamos colecciones sucias y repetidas
            "colecciones": [" Cyber ", "cyber", "VERANO", "Verano  "]
        }
        
        # Ajusta '/api/productos/' a la URL real de creación de productos en tu API
        response = self.client.post('/api/catalogo/productos/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        producto = Producto.objects.get(id=response.data['id'])
        
        # Debe normalizarse conservando el primer formato encontrado y omitiendo duplicados
        self.assertEqual(len(producto.colecciones), 2)
        self.assertIn("Cyber", producto.colecciones)
        self.assertIn("VERANO", producto.colecciones)

    def test_filtro_coleccion_combina_con_categoria_y_paginacion(self):
        """Verifica que ?coleccion= busque case-insensitive y se combine correctamente."""
        # Producto que debe coincidir
        Producto.objects.create(
            nombre="Producto A", categoria="Electronica",
            colecciones=["Cyber"], activo=True, publicado=True,
            fecha_creacion=datetime.now()
        )
        # Producto con otra categoría
        Producto.objects.create(
            nombre="Producto B", categoria="Ropa",
            colecciones=["Cyber"], activo=True, publicado=True,
            fecha_creacion=datetime.now()
        )
        # Producto con otra colección
        Producto.objects.create(
            nombre="Producto C", categoria="Electronica",
            colecciones=["Navidad"], activo=True, publicado=True,
            fecha_creacion=datetime.now()
        )

        # Filtramos por coleccion 'cyber' (minúscula) y categoria 'Electronica' en la página 1
        url = '/api/catalogo/productos/?coleccion=cyber&categoria=Electronica&page=1'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Solo "Producto A" cumple ambas condiciones
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['nombre'], "Producto A")

    def test_producto_despublicado_no_cuenta_en_colecciones_disponibles(self):
        """Garantiza que productos inactivos/despublicados no muestren sus colecciones."""
        # Producto válido
        Producto.objects.create(
            nombre="Teclado", colecciones=["Navidad"],
            categoria="Electronica",
            activo=True, publicado=True,
            fecha_creacion=datetime.now()
        )
        # Producto inválido (despublicado)
        Producto.objects.create(
            nombre="Mouse", colecciones=["BlackFriday"],
            categoria="Electronica",
            activo=True, publicado=False,
            fecha_creacion=datetime.now()
        )

        # Ajusta esta URL a la ruta real de tu API que devuelve los filtros disponibles
        response = self.client.get('/api/catalogo/filtros/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        colecciones_disponibles = response.data.get('colecciones', [])
        
        # La colección del producto publicado debe estar
        self.assertIn("Navidad", colecciones_disponibles)
        # La colección del producto despublicado NO debe estar
        self.assertNotIn("BlackFriday", colecciones_disponibles)
