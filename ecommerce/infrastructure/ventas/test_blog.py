"""Blog o portafolio (RF-01.1): el admin lo activa, publica entradas con fotos y el público solo ve las publicadas."""

import shutil
from io import BytesIO
from uuid import uuid4

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APITestCase

from ecommerce.infrastructure.usuarios.tests.factories import create_user

from .models import ConfiguracionGlobal, FotoPublicacion, Publicacion

PUBLICADA = {'titulo': 'Nuestro taller', 'resumen': 'Cómo trabajamos', 'contenido': '<p>Desde 2015.</p>',
             'estado': 'PUBLICADA'}


def imagen_png(nombre='foto.png'):
    contenido = BytesIO()
    with Image.new('RGB', (16, 16), color='green') as imagen:
        imagen.save(contenido, format='PNG')
    return SimpleUploadedFile(nombre, contenido.getvalue(), content_type='image/png')


class BlogTestCase(APITestCase):
    def setUp(self):
        # Las fotos se guardan en una carpeta temporal, nunca en el media/ de desarrollo
        carpeta = settings.BASE_DIR / '.tmp'
        carpeta.mkdir(exist_ok=True)
        self.media_root = (carpeta / f'blog-api-test-{uuid4().hex}').resolve()
        self.media_root.mkdir()
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        media = override_settings(MEDIA_ROOT=str(self.media_root), MEDIA_URL='/media/')
        media.enable()
        self.addCleanup(media.disable)

        self.config = ConfiguracionGlobal.objects.create(pk=1, nombre_tienda='Tienda QA', blog_activo=True)
        self.admin = create_user('admin-blog@example.test', rol='ADMIN')

    def como_admin(self):
        self.client.force_authenticate(self.admin)

    def crear(self, datos=PUBLICADA, formato='json'):
        self.como_admin()
        respuesta = self.client.post(reverse('admin-blog'), datos, format=formato)
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.client.force_authenticate(None)
        return respuesta.data

    def archivos(self):
        return [p for p in self.media_root.rglob('*') if p.is_file()]


class BlogPublicoTests(BlogTestCase):
    def test_lista_solo_las_publicadas_sin_el_texto(self):
        self.crear()
        self.crear({'titulo': 'Idea a medias', 'estado': 'BORRADOR'})

        respuesta = self.client.get(reverse('blog'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['total'], 1)
        self.assertEqual([p['slug'] for p in respuesta.data['resultados']], ['nuestro-taller'])
        self.assertNotIn('contenido', respuesta.data['resultados'][0])

    def test_pagina_de_a_9(self):
        for numero in range(10):
            self.crear({**PUBLICADA, 'titulo': f'Trabajo {numero}'})

        primera = self.client.get(reverse('blog')).data
        segunda = self.client.get(reverse('blog'), {'pagina': 2}).data

        self.assertEqual((len(primera['resultados']), primera['paginas']), (9, 2))
        self.assertEqual([p['titulo'] for p in segunda['resultados']], ['Trabajo 0'])
        self.assertEqual(self.client.get(reverse('blog'), {'pagina': 'x'}).data['pagina'], 1)

    def test_detalle_con_texto_portada_y_galeria(self):
        publicacion = self.crear({**PUBLICADA, 'portada': imagen_png()}, formato='multipart')
        self.como_admin()
        self.client.post(reverse('admin-blog-fotos', args=[publicacion['id']]),
                         {'fotos': [imagen_png('a.png'), imagen_png('b.png')]}, format='multipart')
        self.client.force_authenticate(None)

        respuesta = self.client.get(reverse('blog-publicacion', args=['nuestro-taller']))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['contenido'], '<p>Desde 2015.</p>')
        self.assertTrue(respuesta.data['portada'].startswith('http://testserver/media/blog/portadas/'))
        self.assertEqual(len(respuesta.data['fotos']), 2)
        self.assertEqual(respuesta.data['youtube_id'], '')
        self.assertNotIn('estado', respuesta.data)

    def test_detalle_con_video_de_youtube(self):
        self.crear({**PUBLICADA, 'youtube': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'})
        respuesta = self.client.get(reverse('blog-publicacion', args=['nuestro-taller']))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['youtube_id'], 'dQw4w9WgXcQ')

    def test_un_borrador_responde_igual_que_una_publicacion_inexistente(self):
        self.crear({'titulo': 'Idea a medias', 'estado': 'BORRADOR'})

        borrador = self.client.get(reverse('blog-publicacion', args=['idea-a-medias']))
        inexistente = self.client.get(reverse('blog-publicacion', args=['no-existe']))

        self.assertEqual((borrador.status_code, inexistente.status_code), (404, 404))
        self.assertEqual(borrador.data, inexistente.data)

    def test_con_el_blog_apagado_el_publico_no_ve_nada(self):
        self.crear()
        ConfiguracionGlobal.objects.filter(pk=1).update(blog_activo=False)

        self.assertEqual(self.client.get(reverse('blog')).status_code, 404)
        self.assertEqual(self.client.get(reverse('blog-publicacion', args=['nuestro-taller'])).status_code, 404)

    def test_la_configuracion_publica_informa_si_hay_blog_y_su_nombre(self):
        datos = self.client.get(reverse('configuracion-global')).data
        self.assertEqual((datos['blog_activo'], datos['blog_nombre']), (True, 'Nosotros'))


class BlogPanelTests(BlogTestCase):
    def setUp(self):
        super().setUp()
        self.como_admin()

    def test_solo_el_admin_usa_el_panel_del_blog(self):
        publicacion = self.crear()
        self.client.force_authenticate(create_user('comprador-blog@example.test'))
        urls = [reverse('admin-blog'), reverse('admin-blog-publicacion', args=[publicacion['id']])]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(reverse('admin-blog'), PUBLICADA, format='json').status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(reverse('admin-blog')).status_code, 401)

    def test_crea_un_borrador_y_despues_lo_publica(self):
        borrador = self.crear({'titulo': 'Nuestro taller', 'estado': 'BORRADOR'})
        self.assertEqual((borrador['estado'], borrador['fecha_publicacion']), ('BORRADOR', None))

        self.como_admin()
        respuesta = self.client.put(reverse('admin-blog-publicacion', args=[borrador['id']]), PUBLICADA,
                                    format='json')

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['estado'], 'PUBLICADA')
        self.assertIsNotNone(respuesta.data['fecha_publicacion'])

    def test_el_panel_funciona_con_el_blog_apagado(self):
        ConfiguracionGlobal.objects.filter(pk=1).update(blog_activo=False)
        self.crear()
        self.como_admin()
        self.assertEqual(len(self.client.get(reverse('admin-blog')).data), 1)

    def test_los_borradores_aparecen_primero_en_el_panel(self):
        self.crear()
        self.crear({'titulo': 'Idea', 'estado': 'BORRADOR'})
        self.como_admin()
        self.assertEqual([p['titulo'] for p in self.client.get(reverse('admin-blog')).data],
                         ['Idea', 'Nuestro taller'])

    def test_errores_de_validacion_por_campo(self):
        respuesta = self.client.post(reverse('admin-blog'), {**PUBLICADA, 'titulo': '', 'contenido': '<p><br></p>'},
                                     format='json')

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('titulo', respuesta.data)
        self.assertIn('contenido', respuesta.data)
        self.assertFalse(Publicacion.objects.exists())

    def test_el_texto_se_limpia_antes_de_guardarlo(self):
        contenido = '<p>Hola<script>alert(1)</script></p><img src=x onerror="alert(1)">'
        publicacion = self.crear({**PUBLICADA, 'contenido': contenido})
        self.assertEqual(publicacion['contenido'], '<p>Hola</p>')

    def test_reemplaza_y_quita_la_portada(self):
        publicacion = self.crear({**PUBLICADA, 'portada': imagen_png()}, formato='multipart')
        url = reverse('admin-blog-publicacion', args=[publicacion['id']])
        self.como_admin()

        with self.captureOnCommitCallbacks(execute=True):
            reemplazada = self.client.put(url, {**PUBLICADA, 'portada': imagen_png('otra.png')}, format='multipart')
        self.assertNotEqual(reemplazada.data['portada'], publicacion['portada'])
        self.assertEqual(len(self.archivos()), 1)

        sin_cambio = self.client.put(url, PUBLICADA, format='multipart')
        self.assertEqual(sin_cambio.data['portada'], reemplazada.data['portada'])

        with self.captureOnCommitCallbacks(execute=True):
            quitada = self.client.put(url, {**PUBLICADA, 'quitar_portada': True}, format='multipart')
        self.assertIsNone(quitada.data['portada'])
        self.assertEqual(self.archivos(), [])

    def test_rechaza_un_archivo_que_no_es_imagen(self):
        falso = SimpleUploadedFile('foto.png', b'no soy una imagen', content_type='image/png')
        respuesta = self.client.post(reverse('admin-blog'), {**PUBLICADA, 'portada': falso}, format='multipart')
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('portada', respuesta.data)

    def test_guarda_video_de_youtube_solo_con_el_id(self):
        respuesta = self.client.post(reverse('admin-blog'),
                                     {**PUBLICADA, 'youtube': 'https://youtu.be/dQw4w9WgXcQ'}, format='json')
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.data['youtube_id'], 'dQw4w9WgXcQ')
        pub = Publicacion.objects.get(id=respuesta.data['id'])
        self.assertEqual(pub.youtube_id, 'dQw4w9WgXcQ')

    def test_rechaza_enlace_youtube_invalido(self):
        respuesta = self.client.post(reverse('admin-blog'),
                                     {**PUBLICADA, 'youtube': 'https://vimeo.com/12345678901'}, format='json')
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('youtube', respuesta.data)

    def test_seguridad_ataques_en_campo_youtube_devuelven_400(self):
        self.como_admin()
        ataques = [
            '<script>alert("xss")</script>',
            'javascript:alert(1)',
            'https://youtube.com@attacker.com/watch?v=dQw4w9WgXcQ',
            'https://notyoutube.com/watch?v=dQw4w9WgXcQ',
            'https://youtube.com.attacker.com/watch?v=dQw4w9WgXcQ',
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ"><script>alert(1)</script>',
            'https://www.youtube.com/watch?v=123',
            'https://www.youtube.com/embed/dQw4w9WgXcQ" onload="alert(1)',
        ]
        for payload in ataques:
            respuesta = self.client.post(reverse('admin-blog'),
                                         {**PUBLICADA, 'youtube': payload}, format='json')
            self.assertEqual(respuesta.status_code, 400, f'Payload no bloqueado: {payload}')
            self.assertIn('youtube', respuesta.data)

    def test_contenido_limpia_etiquetas_iframe_peligrosas(self):
        self.como_admin()
        payload = '<p>Texto</p><iframe src="https://malicious.com"></iframe>'
        respuesta = self.client.post(reverse('admin-blog'),
                                     {**PUBLICADA, 'contenido': payload}, format='json')
        self.assertEqual(respuesta.status_code, 201)
        self.assertNotIn('<iframe', respuesta.data['contenido'])
        self.assertIn('<p>Texto</p>', respuesta.data['contenido'])

    def test_galeria_de_hasta_10_fotos(self):
        publicacion = self.crear()
        self.como_admin()
        url = reverse('admin-blog-fotos', args=[publicacion['id']])

        respuesta = self.client.post(url, {'fotos': [imagen_png(f'{n}.png') for n in range(8)]}, format='multipart')
        self.assertEqual((respuesta.status_code, len(respuesta.data['fotos'])), (201, 8))

        demasiadas = self.client.post(url, {'fotos': [imagen_png(f'{n}.png') for n in range(3)]},
                                      format='multipart')
        self.assertEqual(demasiadas.status_code, 400)
        self.assertIn('fotos', demasiadas.data)
        self.assertEqual(FotoPublicacion.objects.count(), 8)

    def test_quitar_una_foto_borra_su_archivo(self):
        publicacion = self.crear()
        self.como_admin()
        subida = self.client.post(reverse('admin-blog-fotos', args=[publicacion['id']]),
                                  {'fotos': [imagen_png()]}, format='multipart')
        foto_id = subida.data['fotos'][0]['id']

        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.delete(reverse('admin-blog-foto', args=[publicacion['id'], foto_id]))

        self.assertEqual((respuesta.status_code, respuesta.data['fotos']), (200, []))
        self.assertEqual(self.archivos(), [])
        self.assertEqual(
            self.client.delete(reverse('admin-blog-foto', args=[publicacion['id'], foto_id])).status_code, 404)

    def test_eliminar_borra_la_publicacion_y_sus_archivos(self):
        publicacion = self.crear({**PUBLICADA, 'portada': imagen_png()}, formato='multipart')
        self.como_admin()
        self.client.post(reverse('admin-blog-fotos', args=[publicacion['id']]), {'fotos': [imagen_png()]},
                         format='multipart')
        url = reverse('admin-blog-publicacion', args=[publicacion['id']])

        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.delete(url).status_code, 204)

        self.assertFalse(Publicacion.objects.exists())
        self.assertEqual(self.archivos(), [])
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_el_admin_activa_el_blog_y_elige_el_nombre_del_menu(self):
        url = reverse('configuracion-negocio')

        respuesta = self.client.patch(url, {'blog_activo': True, 'blog_nombre': '  Mis   trabajos '}, format='json')
        self.assertEqual((respuesta.data['blog_activo'], respuesta.data['blog_nombre']), (True, 'Mis trabajos'))

        vacio = self.client.patch(url, {'blog_nombre': ''}, format='json')
        self.assertEqual(vacio.data['blog_nombre'], 'Nosotros')

        largo = self.client.patch(url, {'blog_nombre': 'a' * 31}, format='json')
        self.assertEqual(largo.status_code, 400)
        self.assertIn('blog_nombre', largo.data)
