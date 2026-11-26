"""Pedido de un cliente: fotos en la página Sobre mí y textos del editor sin palabras cortadas."""

import shutil
from importlib import import_module
from pathlib import Path
from uuid import uuid4

from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from ecommerce.domain.sobre_mi import fotos_sobre_mi
from ecommerce.infrastructure.usuarios.tests.factories import create_user

from .html_seguro import espacios_normales, limpiar_html
from .models import ConfiguracionGlobal, PaginaLegal, Publicacion
from .test_identidad_tienda import imagen_png

PEGADO = '<h2><span>Alan&nbsp;Zárate,&nbsp;muralista</span></h2><p><span>Soy&nbsp;un&nbsp;artista</span></p>'


class EspaciosNormalesTests(SimpleTestCase):
    def test_cambia_los_nbsp_del_texto_pegado(self):
        self.assertEqual(espacios_normales(PEGADO),
                         '<h2><span>Alan Zárate, muralista</span></h2><p><span>Soy un artista</span></p>')

    def test_conserva_un_parrafo_vacio_y_junta_dos_seguidos(self):
        self.assertEqual(espacios_normales('<p>&nbsp;</p><p>a&nbsp;&nbsp;b</p>'), '<p>&nbsp;</p><p>a  b</p>')

    def test_limpiar_html_tambien_los_cambia_y_el_caracter_u00a0(self):
        self.assertEqual(limpiar_html('<p>Hola mundo <strong>en</strong>&nbsp;negrita</p>'),
                         '<p>Hola mundo <strong>en</strong> negrita</p>')


class FotosSobreMiDominioTests(SimpleTestCase):
    def test_solo_las_subidas_en_su_orden_y_hasta_dos(self):
        self.assertEqual(fotos_sobre_mi([(None, 'x'), ('/b.jpg', ' Taller ')]), [{'url': '/b.jpg', 'alt': 'Taller'}])
        self.assertEqual(len(fotos_sobre_mi([('/a', ''), ('/b', ''), ('/c', '')])), 2)


class MigracionEspaciosTests(TestCase):
    def test_arregla_los_textos_ya_guardados(self):
        ConfiguracionGlobal.objects.create(pk=1, sobre_mi_biografia=PEGADO)
        publicacion = Publicacion.objects.create(titulo='Obra', slug='obra', contenido='<p>Un&nbsp;mural</p>')
        legal = PaginaLegal.objects.create(tipo_pagina='TERMINOS', titulo='T', contenido='<p>&nbsp;</p><p>Al&nbsp;comprar</p>')

        import_module('ecommerce.infrastructure.ventas.migrations.0052_sobre_mi_fotos').espacios_normales(apps, None)

        self.assertNotIn('&nbsp;', ConfiguracionGlobal.objects.get(pk=1).sobre_mi_biografia)
        publicacion.refresh_from_db()
        legal.refresh_from_db()
        self.assertEqual(publicacion.contenido, '<p>Un mural</p>')
        self.assertEqual(legal.contenido, '<p>&nbsp;</p><p>Al comprar</p>')


class FotosSobreMiApiTests(APITestCase):
    def setUp(self):
        # Las imágenes se guardan en una carpeta temporal, nunca en el media/ de desarrollo
        carpeta = settings.BASE_DIR / '.tmp'
        carpeta.mkdir(exist_ok=True)
        self.media_root = (carpeta / f'sobre-mi-test-{uuid4().hex}').resolve()
        self.media_root.mkdir()
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        media = override_settings(MEDIA_ROOT=str(self.media_root), MEDIA_URL='/media/')
        media.enable()
        self.addCleanup(media.disable)

        ConfiguracionGlobal.objects.create(pk=1, nombre_tienda='Tienda QA', sobre_mi_activo=True)
        self.client.force_authenticate(create_user('admin-sobre-mi@example.test', rol='ADMIN'))
        self.url = reverse('configuracion-negocio')
        self.publica = reverse('sobre-mi-publico')

    def test_sube_fotos_con_su_texto_alternativo_y_la_pagina_las_muestra(self):
        respuesta = self.client.patch(self.url, {'sobre_mi_foto_2': imagen_png('mural.png')}, format='multipart')
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        respuesta = self.client.patch(self.url, {'sobre_mi_foto_2_alt': '  Mural en Valparaíso '}, format='json')
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        fotos = self.client.get(self.publica).data['fotos']
        self.assertEqual(len(fotos), 1)
        self.assertTrue(fotos[0]['url'].startswith('http://testserver/media/negocio/sobre_mi/'))
        self.assertEqual(fotos[0]['alt'], 'Mural en Valparaíso')
        guardada = ConfiguracionGlobal.objects.get(pk=1).sobre_mi_foto_2
        # El nombre lo pone el servidor, no el navegador
        self.assertNotIn('mural', Path(guardada.name).stem)

    def test_quitar_una_foto_borra_su_archivo(self):
        self.client.patch(self.url, {'sobre_mi_foto_1': imagen_png()}, format='multipart')
        archivo = Path(ConfiguracionGlobal.objects.get(pk=1).sobre_mi_foto_1.path)
        self.assertTrue(archivo.is_file())

        respuesta = self.client.patch(self.url, {'sobre_mi_foto_1': None}, format='json')

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertFalse(archivo.exists())
        self.assertEqual(self.client.get(self.publica).data['fotos'], [])

    def test_rechaza_un_archivo_que_no_es_imagen_y_un_texto_alternativo_largo(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        falso = SimpleUploadedFile('foto.png', b'no soy una imagen', content_type='image/png')
        self.assertEqual(self.client.patch(self.url, {'sobre_mi_foto_1': falso}, format='multipart').status_code, 400)
        largo = self.client.patch(self.url, {'sobre_mi_foto_1_alt': 'x' * 151}, format='json')
        self.assertEqual(largo.status_code, 400)
        self.assertIn('sobre_mi_foto_1_alt', largo.data)

    def test_la_biografia_pegada_se_guarda_con_espacios_normales(self):
        respuesta = self.client.patch(self.url, {'sobre_mi_biografia': PEGADO}, format='json')

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertNotIn('&nbsp;', self.client.get(self.publica).data['biografia'])
