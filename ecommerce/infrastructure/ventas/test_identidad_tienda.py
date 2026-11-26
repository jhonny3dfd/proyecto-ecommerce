"""RF-01.1 y RF-01.2: el admin cambia el logo, el favicon y la landing desde el panel, sin el equipo."""

import shutil
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APITestCase

from ecommerce.infrastructure.usuarios.tests.factories import create_user

from .models import ConfiguracionGlobal


def imagen_png(nombre='logo.png', color='green'):
    contenido = BytesIO()
    with Image.new('RGB', (16, 16), color=color) as imagen:
        imagen.save(contenido, format='PNG')
    return SimpleUploadedFile(nombre, contenido.getvalue(), content_type='image/png')


class IdentidadTiendaTests(APITestCase):
    def setUp(self):
        # Las imágenes se guardan en una carpeta temporal, nunca en el media/ de desarrollo
        carpeta = settings.BASE_DIR / '.tmp'
        carpeta.mkdir(exist_ok=True)
        self.media_root = (carpeta / f'identidad-test-{uuid4().hex}').resolve()
        self.media_root.mkdir()
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        media = override_settings(MEDIA_ROOT=str(self.media_root), MEDIA_URL='/media/')
        media.enable()
        self.addCleanup(media.disable)

        ConfiguracionGlobal.objects.create(pk=1, nombre_tienda='Tienda QA')
        self.client.force_authenticate(create_user('admin-identidad@example.test', rol='ADMIN'))
        self.url = reverse('configuracion-negocio')

    def subir(self, **archivos):
        return self.client.patch(self.url, archivos, format='multipart')

    def archivo(self, campo):
        return getattr(ConfiguracionGlobal.objects.get(pk=1), campo)

    def test_sube_logo_favicon_portada_y_foto_de_nosotros_y_la_tienda_los_recibe_como_url(self):
        response = self.subir(logo=imagen_png(), favicon=imagen_png('icono.png'), banner=imagen_png('portada.png'),
                              nosotros_imagen=imagen_png('taller.png'))

        self.assertEqual(response.status_code, 200, response.data)
        publica = self.client.get(reverse('configuracion-global')).data
        for campo in ('logo', 'favicon', 'banner', 'nosotros_imagen'):
            with self.subTest(campo=campo):
                guardado = self.archivo(campo)
                self.assertTrue(Path(guardado.path).is_file())
                # El nombre lo pone el servidor, no el navegador
                self.assertNotIn(campo, Path(guardado.name).stem)
                self.assertTrue(publica[campo].startswith('http://testserver/media/negocio/'))

    def test_rechaza_archivos_que_no_son_imagenes(self):
        falso = SimpleUploadedFile('logo.png', b'<svg onload="alert(1)"></svg>', content_type='image/png')

        response = self.subir(logo=falso)

        self.assertEqual(response.status_code, 400)
        self.assertIn('logo', response.data)
        self.assertFalse(self.archivo('logo'))

    @override_settings(CATALOGO_IMAGEN_MAX_BYTES=20)
    def test_rechaza_imagenes_demasiado_grandes(self):
        self.assertEqual(self.subir(logo=imagen_png()).status_code, 400)
        self.assertFalse(self.archivo('logo'))

    def test_reemplazar_o_quitar_una_imagen_borra_el_archivo_anterior(self):
        self.subir(logo=imagen_png())
        primero = Path(self.archivo('logo').path)

        self.subir(logo=imagen_png(color='red'))
        segundo = Path(self.archivo('logo').path)
        self.assertFalse(primero.exists())
        self.assertTrue(segundo.is_file())

        response = self.client.patch(self.url, {'logo': None}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.archivo('logo'))
        self.assertFalse(segundo.exists())

    def test_edita_los_campos_fijos_de_la_landing(self):
        datos = {'nombre_tienda': 'Murales Alan', 'texto_bienvenida': 'Murales de Alan',
                 'subtitulo_bienvenida': 'Arte para tus paredes',
                 'texto_landing': 'Pintamos murales a pedido en todo Chile.', 'texto_boton_ingreso': 'Ver obras',
                 'nosotros_titulo': 'Nuestro taller', 'nosotros_texto': 'Desde 2015 pintamos en Valparaíso.'}

        self.assertEqual(self.client.patch(self.url, datos, format='json').status_code, 200)

        publica = self.client.get(reverse('configuracion-global')).data
        self.assertEqual({campo: publica[campo] for campo in datos}, datos)

    def test_los_textos_largos_de_la_landing_tienen_un_maximo(self):
        for campo, maximo in (('texto_bienvenida', 300), ('texto_landing', 1000), ('nosotros_texto', 2000)):
            with self.subTest(campo=campo):
                response = self.client.patch(self.url, {campo: 'x' * (maximo + 1)}, format='json')
                self.assertEqual(response.status_code, 400)
                self.assertIn(campo, response.data)

    def test_rn01_el_admin_elige_donde_va_el_logo_de_la_universidad_pero_no_puede_ocultarlo(self):
        # Por defecto en el header, junto al del negocio
        self.assertEqual(self.client.get(reverse('configuracion-global')).data['ubicacion_logo_universidad'], 'HEADER')

        self.assertEqual(self.client.patch(self.url, {'ubicacion_logo_universidad': 'FOOTER'}, format='json').status_code, 200)
        self.assertEqual(self.client.get(reverse('configuracion-global')).data['ubicacion_logo_universidad'], 'FOOTER')

        # Solo esas dos ubicaciones: ningún valor lo oculta
        for valor in ('OCULTO', 'NINGUNO', '', None):
            with self.subTest(valor=valor):
                response = self.client.patch(self.url, {'ubicacion_logo_universidad': valor}, format='json')
                self.assertEqual(response.status_code, 400)
                self.assertIn('ubicacion_logo_universidad', response.data)

    def test_el_admin_elige_la_tipografia_y_la_tienda_la_recibe(self):
        self.assertEqual(self.client.get(reverse('configuracion-global')).data['tipografia_seleccionada'], 1)

        self.assertEqual(self.client.patch(self.url, {'tipografia_seleccionada': 4}, format='json').status_code, 200)

        self.assertEqual(self.client.get(reverse('configuracion-global')).data['tipografia_seleccionada'], 4)

    def test_rechaza_una_tipografia_que_no_existe(self):
        for valor in (0, 6, 'serif'):
            with self.subTest(valor=valor):
                response = self.client.patch(self.url, {'tipografia_seleccionada': valor}, format='json')
                self.assertEqual(response.status_code, 400)
                self.assertIn('tipografia_seleccionada', response.data)
        self.assertEqual(ConfiguracionGlobal.objects.get(pk=1).tipografia_seleccionada, 1)

    def test_un_comprador_no_puede_cambiar_la_identidad(self):
        self.client.force_authenticate(create_user('comprador-identidad@example.test'))
        self.assertEqual(self.subir(logo=imagen_png()).status_code, 403)
        self.assertFalse(self.archivo('logo'))

    def test_sube_varias_fotos_del_banner_las_reordena_y_las_borra(self):
        import json
        from .models import FotoBanner

        # Sube 3 fotos nuevas al banner
        f1 = imagen_png('foto1.png', color='red')
        f2 = imagen_png('foto2.png', color='blue')
        f3 = imagen_png('foto3.png', color='yellow')
        datos = {
            'banner_fotos': [f1, f2, f3],
            'banner_orden': json.dumps(['nuevo:0', 'nuevo:1', 'nuevo:2']),
        }
        resp = self.client.patch(self.url, datos, format='multipart')
        self.assertEqual(resp.status_code, 200)

        banners_resp = resp.data.get('banners', [])
        self.assertEqual(len(banners_resp), 3)
        self.assertEqual(FotoBanner.objects.filter(configuracion_id=1).count(), 3)

        id1 = banners_resp[0]['id']
        id2 = banners_resp[1]['id']
        id3 = banners_resp[2]['id']

        # Reordena e invierte el orden, y elimina la del medio (id2)
        resp_reorden = self.client.patch(self.url, {
            'banner_orden': json.dumps([f'id:{id3}', f'id:{id1}']),
        }, format='json')
        self.assertEqual(resp_reorden.status_code, 200)
        banners_reorden = resp_reorden.data.get('banners', [])
        self.assertEqual(len(banners_reorden), 2)
        self.assertEqual(banners_reorden[0]['id'], id3)
        self.assertEqual(banners_reorden[0]['orden'], 0)
        self.assertEqual(banners_reorden[1]['id'], id1)
        self.assertEqual(banners_reorden[1]['orden'], 1)
        self.assertEqual(FotoBanner.objects.filter(configuracion_id=1).count(), 2)

        # La vista pública también las entrega ordenadas
        publica = self.client.get(reverse('configuracion-global')).data
        self.assertEqual(len(publica['banners']), 2)
        self.assertEqual(publica['banners'][0]['id'], id3)

        # Borra todas las fotos del banner
        resp_borrar = self.client.patch(self.url, {'banner_orden': json.dumps([])}, format='json')
        self.assertEqual(resp_borrar.status_code, 200)
        self.assertEqual(FotoBanner.objects.filter(configuracion_id=1).count(), 0)

    def test_migra_banner_existente_cuando_recibe_id_legacy_y_agrega_segunda_foto(self):
        import json
        from .models import FotoBanner

        # Caso de Alan y Daniela: la tienda ya tenía un banner antiguo
        self.subir(banner=imagen_png('banner_existente.png'))
        config = ConfiguracionGlobal.objects.get(pk=1)
        self.assertTrue(bool(config.banner))

        # Obtenemos lo que la API entrega (como hace el front)
        publica = self.client.get(reverse('configuracion-global')).data
        banner_inicial = publica['banners'][0]
        id_inicial = banner_inicial['id']

        # El front manda la foto actual según el ID que le dio la API y sube una segunda foto
        f2 = imagen_png('foto2.png', color='blue')
        datos = {
            'banner_fotos': [f2],
            'banner_orden': json.dumps([f'id:{id_inicial}', 'nuevo:0']),
        }
        resp = self.client.patch(self.url, datos, format='multipart')
        self.assertEqual(resp.status_code, 200)

        banners = resp.data.get('banners', [])
        self.assertEqual(len(banners), 2)
        self.assertEqual(FotoBanner.objects.filter(configuracion_id=1).count(), 2)
        # Se limpió config.banner para no tener dos fuentes de verdad
        config.refresh_from_db()
        self.assertFalse(bool(config.banner))

    def test_quitar_banner_antiguo_lo_elimina_y_borra_su_archivo(self):
        import json

        self.subir(banner=imagen_png('banner_antiguo.png'))
        config = ConfiguracionGlobal.objects.get(pk=1)
        ruta_archivo = Path(config.banner.path)
        self.assertTrue(ruta_archivo.is_file())

        # El admin quita la foto antigua dejando el carrusel vacío
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.patch(self.url, {'banner_orden': json.dumps([])}, format='json')
        self.assertEqual(resp.status_code, 200)

        config.refresh_from_db()
        self.assertFalse(bool(config.banner))
        self.assertFalse(ruta_archivo.is_file())

    def test_banner_orden_mal_formado_responde_400_y_no_borra_fotos(self):
        import json
        from .models import FotoBanner

        # Sube 1 foto
        f1 = imagen_png('foto1.png')
        self.client.patch(self.url, {'banner_fotos': [f1], 'banner_orden': json.dumps(['nuevo:0'])}, format='multipart')
        self.assertEqual(FotoBanner.objects.filter(configuracion_id=1).count(), 1)

        # Manda banner_orden corrupto
        resp = self.client.patch(self.url, {'banner_orden': '{bad-json'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('banner_orden', resp.data)
        # No se borraron las fotos existentes
        self.assertEqual(FotoBanner.objects.filter(configuracion_id=1).count(), 1)

    def test_archivo_invalido_en_banner_responde_400_y_no_guarda_a_medias(self):
        import json
        from .models import FotoBanner

        falso = SimpleUploadedFile('malicioso.png', b'<svg onload="alert(1)"></svg>', content_type='image/png')
        resp = self.client.patch(self.url, {
            'banner_fotos': [falso],
            'banner_orden': json.dumps(['nuevo:0']),
            'texto_bienvenida': 'Nuevo Titulo',
        }, format='multipart')

        self.assertEqual(resp.status_code, 400)
        # La transacción atómica revirtió también el cambio de texto
        config = ConfiguracionGlobal.objects.get(pk=1)
        self.assertNotEqual(config.texto_bienvenida, 'Nuevo Titulo')
        self.assertEqual(FotoBanner.objects.filter(configuracion_id=1).count(), 0)

    def test_limite_maximo_10_fotos_en_banner(self):
        import json

        # Intenta pasar 11 fotos en banner_orden
        orden_excedido = [f'nuevo:{i}' for i in range(11)]
        resp = self.client.patch(self.url, {'banner_orden': json.dumps(orden_excedido)}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('banner_fotos', resp.data)

    def test_al_quitar_fotos_se_borran_del_disco(self):
        import json
        from .models import FotoBanner

        f1 = imagen_png('foto_a_borrar.png')
        resp = self.client.patch(self.url, {'banner_fotos': [f1], 'banner_orden': json.dumps(['nuevo:0'])}, format='multipart')
        self.assertEqual(resp.status_code, 200)

        foto = FotoBanner.objects.filter(configuracion_id=1).first()
        ruta_archivo = Path(foto.imagen.path)
        self.assertTrue(ruta_archivo.is_file())

        # Quita la foto
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.patch(self.url, {'banner_orden': json.dumps([])}, format='json')
        self.assertEqual(resp.status_code, 200)
        # El archivo físico se borró del disco al confirmar la transacción
        self.assertFalse(ruta_archivo.is_file())

    # Textos y botón propios de cada foto (decidido el 2026-11-09: los textos viajan con su foto)

    def subir_con_textos(self):
        import json
        orden = [{'ref': 'nuevo:0', 'antetitulo': 'Hecho a mano', 'titulo': 'Murales', 'texto': 'Para tu casa'},
                 {'ref': 'nuevo:1', 'titulo': 'Cyber', 'destino': 'COTIZAR'}]
        return self.client.patch(self.url, {'banner_fotos': [imagen_png('a.png'), imagen_png('b.png', color='blue')],
                                            'banner_orden': json.dumps(orden)}, format='multipart')

    def test_cada_foto_guarda_sus_textos_y_su_destino(self):
        resp = self.subir_con_textos()
        self.assertEqual(resp.status_code, 200, resp.data)
        banners = [{campo: foto[campo] for campo in ('antetitulo', 'titulo', 'texto', 'destino')}
                   for foto in resp.data['banners']]
        self.assertEqual(banners, [
            {'antetitulo': 'Hecho a mano', 'titulo': 'Murales', 'texto': 'Para tu casa', 'destino': 'CATALOGO'},
            {'antetitulo': '', 'titulo': 'Cyber', 'texto': '', 'destino': 'COTIZAR'},
        ])
        # La tienda pública recibe lo mismo
        publica = self.client.get(reverse('configuracion-global')).data['banners']
        self.assertEqual([(foto['titulo'], foto['destino']) for foto in publica],
                         [('Murales', 'CATALOGO'), ('Cyber', 'COTIZAR')])

    def test_los_textos_viajan_con_su_foto_y_los_generales_siguen_a_la_primera(self):
        import json
        banners = self.subir_con_textos().data['banners']
        config = ConfiguracionGlobal.objects.get(pk=1)
        self.assertEqual((config.subtitulo_bienvenida, config.texto_bienvenida, config.texto_landing),
                         ('Hecho a mano', 'Murales', 'Para tu casa'))

        # Al invertir el orden sin mandar textos, cada foto conserva los suyos y la portada sigue a la nueva primera
        resp = self.client.patch(self.url, {'banner_orden': json.dumps([f"id:{banners[1]['id']}",
                                                                        f"id:{banners[0]['id']}"])}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([foto['titulo'] for foto in resp.data['banners']], ['Cyber', 'Murales'])
        config.refresh_from_db()
        self.assertEqual((config.subtitulo_bienvenida, config.texto_bienvenida, config.texto_landing),
                         ('', 'Cyber', ''))

    def test_una_foto_nueva_sin_textos_parte_con_los_de_la_portada(self):
        import json
        ConfiguracionGlobal.objects.filter(pk=1).update(subtitulo_bienvenida='Hola', texto_bienvenida='Bienvenidos',
                                                        texto_landing='Texto de la portada')
        resp = self.client.patch(self.url, {'banner_fotos': [imagen_png()], 'banner_orden': json.dumps(['nuevo:0'])},
                                 format='multipart')
        self.assertEqual(resp.status_code, 200)
        foto = resp.data['banners'][0]
        self.assertEqual((foto['antetitulo'], foto['titulo'], foto['texto'], foto['destino']),
                         ('Hola', 'Bienvenidos', 'Texto de la portada', 'CATALOGO'))

    def test_la_portada_antigua_se_entrega_con_sus_textos_y_los_conserva_al_pasar_al_carrusel(self):
        import json
        ConfiguracionGlobal.objects.filter(pk=1).update(texto_bienvenida='Bienvenidos', texto_landing='Hecho en Chile')
        self.subir(banner=imagen_png('antigua.png'))
        antigua = self.client.get(self.url).data['banners'][0]
        self.assertEqual((antigua['id'], antigua['titulo'], antigua['texto'], antigua['destino']),
                         ('legacy', 'Bienvenidos', 'Hecho en Chile', 'CATALOGO'))

        resp = self.client.patch(self.url, {'banner_fotos': [imagen_png('nueva.png')], 'banner_orden': json.dumps(
            ['id:legacy', {'ref': 'nuevo:0', 'titulo': 'Cyber', 'destino': 'BLOG'}])}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual([(foto['titulo'], foto['texto'], foto['destino']) for foto in resp.data['banners']],
                         [('Bienvenidos', 'Hecho en Chile', 'CATALOGO'), ('Cyber', '', 'BLOG')])

    def test_textos_invalidos_responden_400_y_no_cambian_nada(self):
        import json
        banners = self.subir_con_textos().data['banners']
        for item in [{'ref': f"id:{banners[0]['id']}", 'titulo': '   '},
                     {'ref': f"id:{banners[0]['id']}", 'titulo': 'Murales', 'destino': 'SOBRE_MI'},
                     {'ref': f"id:{banners[0]['id']}", 'titulo': 'x' * 301}]:
            with self.subTest(item=item):
                resp = self.client.patch(self.url, {'texto_landing': 'No debe guardarse',
                                                    'banner_orden': json.dumps([item])}, format='json')
                self.assertEqual(resp.status_code, 400)
                self.assertIn('banner_orden', resp.data)
        config = ConfiguracionGlobal.objects.get(pk=1)
        self.assertEqual(config.texto_landing, 'Para tu casa')
        self.assertEqual([foto.titulo for foto in config.fotos_banner.all()], ['Murales', 'Cyber'])


class PresentacionTiendaTests(APITestCase):
    """Pedido de un cliente: fotos sin recorte, ficha con la foto horizontal y logo más grande. Apagadas por defecto."""

    def setUp(self):
        ConfiguracionGlobal.objects.create(pk=1, nombre_tienda='Tienda QA')
        self.url = reverse('configuracion-negocio')
        self.opciones = {'fotos_completas': True, 'ficha_horizontal': True, 'logo_grande': True}

    def publica(self):
        datos = self.client.get(reverse('configuracion-global')).data
        return {campo: datos[campo] for campo in self.opciones}

    def test_por_defecto_la_tienda_se_ve_como_antes(self):
        self.assertEqual(self.publica(), {campo: False for campo in self.opciones})

    def test_el_admin_activa_cada_opcion_por_separado_y_la_tienda_la_recibe(self):
        self.client.force_authenticate(create_user('admin-presentacion@example.test', rol='ADMIN'))

        respuesta = self.client.patch(self.url, {'ficha_horizontal': True}, format='json')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.publica(), {'fotos_completas': False, 'ficha_horizontal': True, 'logo_grande': False})

        self.assertEqual(self.client.patch(self.url, self.opciones, format='json').status_code, 200)
        self.assertEqual(self.publica(), self.opciones)

    def test_solo_el_admin_puede_cambiarlas(self):
        self.assertEqual(self.client.patch(self.url, self.opciones, format='json').status_code, 401)
        self.client.force_authenticate(create_user('comprador-presentacion@example.test'))
        self.assertEqual(self.client.patch(self.url, self.opciones, format='json').status_code, 403)
        self.assertEqual(self.publica(), {campo: False for campo in self.opciones})
