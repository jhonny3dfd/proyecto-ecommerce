"""Adaptador PostgreSQL del blog: publicaciones, portada y galería, sin dejar archivos huérfanos."""

import shutil
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from uuid import uuid4

from django.conf import settings
from django.db import DatabaseError
from django.test import TestCase, override_settings

from ecommerce.application.blog import SIN_CAMBIO
from ecommerce.domain.blog import DatosPublicacion, EstadoPublicacion
from ecommerce.domain.imagenes import ImagenProcesada

from .models import FotoPublicacion, Publicacion
from .repositorio_blog import DjangoRepositorioPublicaciones

AHORA = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
DESPUES = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
FOTO = ImagenProcesada(contenido=b'imagen', extension='png')


def datos(titulo='Nuestro taller', estado=EstadoPublicacion.PUBLICADA, youtube_id=''):
    return DatosPublicacion(titulo=titulo, resumen='Cómo trabajamos', contenido='<p>Desde 2015.</p>', estado=estado,
                            youtube_id=youtube_id)


class RepositorioPublicacionesTests(TestCase):
    def setUp(self):
        # Las fotos se guardan en una carpeta temporal, nunca en el media/ de desarrollo
        carpeta = settings.BASE_DIR / '.tmp'
        carpeta.mkdir(exist_ok=True)
        self.media_root = (carpeta / f'blog-test-{uuid4().hex}').resolve()
        self.media_root.mkdir()
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        media = override_settings(MEDIA_ROOT=str(self.media_root), MEDIA_URL='/media/')
        media.enable()
        self.addCleanup(media.disable)
        self.repositorio = DjangoRepositorioPublicaciones()

    def archivos(self):
        return sorted(p.relative_to(self.media_root).as_posix() for p in self.media_root.rglob('*') if p.is_file())

    def crear(self, titulo='Nuestro taller', slug='nuestro-taller', fecha=AHORA, portada=None, **kwargs):
        return self.repositorio.guardar(None, datos(titulo, **kwargs), slug, fecha, portada)

    def test_crea_y_actualiza_una_publicacion(self):
        publicacion_id = self.crear(portada=FOTO)
        self.repositorio.guardar(publicacion_id, datos('Otro título'), 'nuestro-taller', AHORA, SIN_CAMBIO)

        publicacion = Publicacion.objects.get(id=publicacion_id)
        self.assertEqual((publicacion.titulo, publicacion.estado), ('Otro título', 'PUBLICADA'))
        self.assertTrue(publicacion.portada.name.startswith('blog/portadas/'))
        self.assertEqual(self.repositorio.obtener(publicacion_id).tiene_portada, True)

    def test_guarda_y_obtiene_youtube_id(self):
        publicacion_id = self.crear(youtube_id='dQw4w9WgXcQ')
        publicacion = Publicacion.objects.get(id=publicacion_id)
        self.assertEqual(publicacion.youtube_id, 'dQw4w9WgXcQ')

        guardada = self.repositorio.obtener(publicacion_id)
        self.assertEqual(guardada.youtube_id, 'dQw4w9WgXcQ')

        # Actualiza quitando el video
        self.repositorio.guardar(publicacion_id, datos(youtube_id=''), 'nuestro-taller', AHORA, SIN_CAMBIO)
        publicacion.refresh_from_db()
        self.assertEqual(publicacion.youtube_id, '')

    def test_obtener_informa_slug_fecha_y_cantidad_de_fotos(self):
        publicacion_id = self.crear()
        self.repositorio.agregar_fotos(publicacion_id, [FOTO, FOTO])

        guardada = self.repositorio.obtener(publicacion_id)
        self.assertEqual((guardada.slug, guardada.fecha_publicacion, guardada.tiene_portada, guardada.cantidad_fotos),
                         ('nuestro-taller', AHORA, False, 2))
        self.assertIsNone(self.repositorio.obtener(999))

    def test_reemplazar_la_portada_borra_la_anterior_al_confirmar(self):
        publicacion_id = self.crear(portada=FOTO)
        anterior = self.archivos()

        with self.captureOnCommitCallbacks(execute=True):
            self.repositorio.guardar(publicacion_id, datos(), 'nuestro-taller', AHORA, FOTO)

        actuales = self.archivos()
        self.assertEqual(len(actuales), 1)
        self.assertNotEqual(actuales, anterior)

    def test_quitar_la_portada_borra_el_archivo(self):
        publicacion_id = self.crear(portada=FOTO)
        with self.captureOnCommitCallbacks(execute=True):
            self.repositorio.guardar(publicacion_id, datos(), 'nuestro-taller', AHORA, None)

        self.assertFalse(Publicacion.objects.get(id=publicacion_id).portada)
        self.assertEqual(self.archivos(), [])

    def test_si_falla_la_base_no_queda_la_portada_nueva_ni_se_borra_la_anterior(self):
        publicacion_id = self.crear(portada=FOTO)
        anterior = self.archivos()

        # Falla el UPDATE, cuando Django ya escribió el archivo nuevo
        with self.captureOnCommitCallbacks(execute=True), \
                mock.patch.object(Publicacion, '_do_update', side_effect=DatabaseError):
            with self.assertRaises(DatabaseError):
                self.repositorio.guardar(publicacion_id, datos(), 'nuestro-taller', AHORA, FOTO)

        self.assertEqual(self.archivos(), anterior)

    def test_slugs_parecidos_excluye_la_propia_publicacion(self):
        primera = self.crear()
        self.crear(slug='nuestro-taller-2')
        self.crear(titulo='Feria', slug='feria')

        self.assertEqual(self.repositorio.slugs_parecidos('nuestro-taller', None),
                         {'nuestro-taller', 'nuestro-taller-2'})
        self.assertEqual(self.repositorio.slugs_parecidos('nuestro-taller', primera), {'nuestro-taller-2'})

    def test_agrega_fotos_al_final_de_la_galeria(self):
        publicacion_id = self.crear()
        primeras = self.repositorio.agregar_fotos(publicacion_id, [FOTO, FOTO])
        [tercera] = self.repositorio.agregar_fotos(publicacion_id, [FOTO])

        ordenes = list(FotoPublicacion.objects.filter(publicacion_id=publicacion_id).values_list('id', 'orden'))
        self.assertEqual(ordenes, [(primeras[0], 0), (primeras[1], 1), (tercera, 2)])
        self.assertTrue(all(nombre.startswith('blog/fotos/') for nombre in self.archivos()))

    def test_si_falla_la_base_no_quedan_las_fotos_nuevas(self):
        publicacion_id = self.crear()
        insertar_original = FotoPublicacion._do_insert
        llamadas = []

        # Falla el INSERT de la segunda foto, cuando Django ya escribió su archivo; la primera vuelve con el rollback
        def fallar_en_la_segunda(foto, *args, **kwargs):
            llamadas.append(foto)
            if len(llamadas) == 2:
                raise DatabaseError
            return insertar_original(foto, *args, **kwargs)

        with mock.patch.object(FotoPublicacion, '_do_insert', fallar_en_la_segunda):
            with self.assertRaises(DatabaseError):
                self.repositorio.agregar_fotos(publicacion_id, [FOTO, FOTO])

        self.assertEqual(FotoPublicacion.objects.count(), 0)
        self.assertEqual(self.archivos(), [])

    def test_quitar_una_foto_borra_su_archivo_y_no_toca_las_de_otra_publicacion(self):
        publicacion_id = self.crear()
        otra = self.crear(titulo='Feria', slug='feria')
        [foto_id] = self.repositorio.agregar_fotos(publicacion_id, [FOTO])
        self.repositorio.agregar_fotos(otra, [FOTO])

        self.assertFalse(self.repositorio.quitar_foto(otra, foto_id))
        with self.captureOnCommitCallbacks(execute=True):
            self.assertTrue(self.repositorio.quitar_foto(publicacion_id, foto_id))

        self.assertEqual(FotoPublicacion.objects.filter(publicacion_id=otra).count(), 1)
        self.assertEqual(len(self.archivos()), 1)

    def test_eliminar_borra_la_portada_y_las_fotos(self):
        publicacion_id = self.crear(portada=FOTO)
        self.repositorio.agregar_fotos(publicacion_id, [FOTO, FOTO])

        with self.captureOnCommitCallbacks(execute=True):
            self.assertTrue(self.repositorio.eliminar(publicacion_id))

        self.assertFalse(Publicacion.objects.exists())
        self.assertEqual(self.archivos(), [])
        self.assertFalse(self.repositorio.eliminar(publicacion_id))

    def test_publicadas_sin_borradores_las_mas_recientes_primero_y_paginadas(self):
        primera = self.crear()
        self.crear(titulo='Idea', slug='idea', fecha=None, estado=EstadoPublicacion.BORRADOR)
        segunda = self.crear(titulo='Feria', slug='feria', fecha=DESPUES)

        pagina = self.repositorio.publicadas(0, 10)
        self.assertEqual((pagina.ids, pagina.total), ([segunda, primera], 2))
        self.assertEqual(self.repositorio.publicadas(1, 1).ids, [primera])

    def test_id_publicada_no_devuelve_borradores(self):
        publicada = self.crear()
        self.crear(titulo='Idea', slug='idea', fecha=None, estado=EstadoPublicacion.BORRADOR)

        self.assertEqual(self.repositorio.id_publicada('nuestro-taller'), publicada)
        self.assertIsNone(self.repositorio.id_publicada('idea'))
        self.assertIsNone(self.repositorio.id_publicada('no-existe'))
