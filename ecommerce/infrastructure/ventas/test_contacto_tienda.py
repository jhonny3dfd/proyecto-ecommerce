"""Contacto y redes de la tienda: correo, horario, dirección del local en el pie e Instagram de la landing."""

import shutil
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from ecommerce.infrastructure.usuarios.tests.factories import create_user

from .models import ConfiguracionGlobal
from .test_identidad_tienda import imagen_png

CAMPOS_DIRECCION = ('calle_origen', 'numero_origen', 'dpto_casa_origen', 'comuna_origen', 'region_origen')


class ContactoTiendaTests(APITestCase):
    def setUp(self):
        # Las fotos se guardan en una carpeta temporal, nunca en el media/ de desarrollo
        carpeta = settings.BASE_DIR / '.tmp'
        carpeta.mkdir(exist_ok=True)
        self.media_root = (carpeta / f'contacto-test-{uuid4().hex}').resolve()
        self.media_root.mkdir()
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        media = override_settings(MEDIA_ROOT=str(self.media_root), MEDIA_URL='/media/')
        media.enable()
        self.addCleanup(media.disable)

        ConfiguracionGlobal.objects.create(
            pk=1, nombre_tienda='Tienda QA', calle_origen='Los Aromos', numero_origen='1550',
            comuna_origen='Ñuñoa', region_origen='Metropolitana', retiro_en_local_activo=False,
        )
        self.client.force_authenticate(create_user('admin-contacto@example.test', rol='ADMIN'))
        self.url = reverse('configuracion-negocio')

    def editar(self, **datos):
        return self.client.patch(self.url, datos, format='json')

    def publica(self):
        self.client.force_authenticate(None)
        return self.client.get(reverse('configuracion-global')).data

    def test_el_admin_edita_el_contacto_y_la_tienda_lo_publica(self):
        respuesta = self.editar(correo_contacto='hola@tienda.cl',
                                horario_atencion='Lunes a viernes, 10:00 a 19:00\nSábado, 10:00 a 14:00',
                                instagram_usuario='@MiTienda')

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        publica = self.publica()
        self.assertEqual(publica['correo_contacto'], 'hola@tienda.cl')
        self.assertEqual(publica['horario_atencion'], 'Lunes a viernes, 10:00 a 19:00\nSábado, 10:00 a 14:00')
        self.assertEqual(publica['instagram_usuario'], 'mitienda')

    def test_el_enlace_al_perfil_se_guarda_como_usuario(self):
        self.editar(instagram_usuario='https://www.instagram.com/taller.mache/?hl=es')

        self.assertEqual(ConfiguracionGlobal.objects.get(pk=1).instagram_usuario, 'taller.mache')

    def test_rechaza_un_usuario_de_instagram_o_un_correo_invalidos(self):
        respuesta = self.editar(instagram_usuario='mi tienda!', correo_contacto='no-es-un-correo')

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('instagram_usuario', respuesta.data)
        self.assertIn('correo_contacto', respuesta.data)

    def test_los_textos_de_contacto_tienen_un_maximo(self):
        self.assertEqual(self.editar(horario_atencion='x' * 501).status_code, 400)

    def test_sin_retiro_ni_permiso_la_direccion_no_es_publica(self):
        publica = self.publica()

        for campo in CAMPOS_DIRECCION:
            with self.subTest(campo=campo):
                self.assertNotIn(campo, publica)

    def test_la_direccion_se_publica_si_el_admin_la_muestra_en_el_pie(self):
        self.editar(mostrar_direccion_pie=True)

        publica = self.publica()
        self.assertTrue(publica['mostrar_direccion_pie'])
        self.assertEqual(publica['calle_origen'], 'Los Aromos')
        self.assertEqual(publica['comuna_origen'], 'Ñuñoa')

    def test_con_retiro_en_local_la_direccion_sigue_publica_para_el_checkout(self):
        ConfiguracionGlobal.objects.filter(pk=1).update(retiro_en_local_activo=True)

        publica = self.publica()
        self.assertEqual(publica['calle_origen'], 'Los Aromos')
        self.assertFalse(publica['mostrar_direccion_pie'])

    def test_el_admin_siempre_ve_la_direccion_para_editarla(self):
        self.assertEqual(self.client.get(self.url).data['calle_origen'], 'Los Aromos')

    def test_sube_y_reemplaza_fotos_de_instagram_borrando_la_anterior(self):
        self.client.patch(self.url, {'instagram_foto_1': imagen_png('uno.png'),
                                     'instagram_foto_6': imagen_png('seis.png')}, format='multipart')
        primera = Path(ConfiguracionGlobal.objects.get(pk=1).instagram_foto_1.path)

        publica = self.publica()
        self.assertTrue(publica['instagram_foto_1'].startswith('http://testserver/media/negocio/instagram/'))
        self.assertTrue(publica['instagram_foto_6'])
        self.assertIsNone(publica['instagram_foto_2'])

        self.client.force_authenticate(create_user('admin-contacto-2@example.test', rol='ADMIN'))
        self.client.patch(self.url, {'instagram_foto_1': imagen_png('otra.png', color='red')}, format='multipart')
        self.assertFalse(primera.exists())

    def test_un_comprador_no_puede_cambiar_el_contacto(self):
        self.client.force_authenticate(create_user('comprador-contacto@example.test'))

        self.assertIn(self.editar(correo_contacto='falso@example.test').status_code, (401, 403))
        self.assertEqual(ConfiguracionGlobal.objects.get(pk=1).correo_contacto, '')

    def test_el_admin_guarda_telefono_y_redes_sociales(self):
        respuesta = self.editar(
            telefono_comercial='9 1234 5678',
            facebook_url='https://www.facebook.com/mitienda',
            x_url='https://x.com/mitienda',
            youtube_url='https://www.youtube.com/@mitienda',
            tiktok_url='https://www.tiktok.com/@mitienda',
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        publica = self.publica()

        self.assertEqual(publica['telefono_comercial'], '+56912345678')
        self.assertEqual(publica['facebook_url'], 'https://www.facebook.com/mitienda')
        self.assertEqual(publica['x_url'], 'https://x.com/mitienda')
        self.assertEqual(publica['youtube_url'], 'https://www.youtube.com/@mitienda')
        self.assertEqual(publica['tiktok_url'], 'https://www.tiktok.com/@mitienda')

    def test_rechaza_telefono_comercial_invalido(self):
        respuesta = self.editar(telefono_comercial='123')

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('telefono_comercial', respuesta.data)

    def test_rechaza_enlaces_de_redes_sociales_incorrectos(self):
        casos = {
            'facebook_url': 'https://www.tiktok.com/@mitienda',
            'x_url': 'https://www.facebook.com/mitienda',
            'youtube_url': 'https://youtube.com.ejemplo.cl/@mitienda',
            'tiktok_url': 'http://www.tiktok.com/@mitienda',
        }

        for campo, enlace in casos.items():
            with self.subTest(campo=campo):
                respuesta = self.editar(**{campo: enlace})

                self.assertEqual(respuesta.status_code, 400)
                self.assertIn(campo, respuesta.data)

    def test_los_nuevos_campos_son_opcionales(self):
        respuesta = self.editar(
            telefono_comercial='',
            facebook_url='',
            x_url='',
            youtube_url='',
            tiktok_url='',
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        publica = self.publica()

        for campo in (
            'telefono_comercial',
            'facebook_url',
            'x_url',
            'youtube_url',
            'tiktok_url',
        ):
            with self.subTest(campo=campo):
                self.assertEqual(publica[campo], '')
