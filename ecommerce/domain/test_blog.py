from django.test import SimpleTestCase

from ecommerce.domain.blog import (
    MAX_FOTOS_PUBLICACION, DatosPublicacion, EstadoPublicacion, LimiteFotosExcedido, NombreBlogInvalido,
    PublicacionInvalida, generar_slug, normalizar_nombre_blog, slug_unico, validar_cantidad_fotos,
)

DATOS = {'titulo': 'Nuestro taller', 'resumen': 'Cómo trabajamos', 'contenido': '<p>Desde 2015.</p>',
         'estado': 'PUBLICADA'}


class DatosPublicacionTests(SimpleTestCase):
    def errores(self, datos, contenido_tiene_texto=True, tiene_portada=False):
        with self.assertRaises(PublicacionInvalida) as error:
            DatosPublicacion.desde(datos, contenido_tiene_texto, tiene_portada)
        return error.exception.errores

    def test_una_publicacion_completa_queda_publicada(self):
        datos = DatosPublicacion.desde({**DATOS, 'titulo': '  Nuestro taller '}, True, False)
        self.assertEqual(datos.titulo, 'Nuestro taller')
        self.assertEqual(datos.contenido, '<p>Desde 2015.</p>')
        self.assertEqual(datos.estado, EstadoPublicacion.PUBLICADA)

    def test_sin_estado_queda_como_borrador(self):
        datos = DatosPublicacion.desde({'titulo': 'Idea'}, False, False)
        self.assertEqual(datos.estado, EstadoPublicacion.BORRADOR)

    def test_un_borrador_puede_quedar_sin_texto_ni_portada(self):
        datos = DatosPublicacion.desde({**DATOS, 'estado': 'BORRADOR', 'contenido': '<p><br></p>'}, False, False)
        self.assertEqual(datos.contenido, '')

    def test_para_publicar_exige_texto_o_portada(self):
        self.assertIn('contenido', self.errores({**DATOS, 'contenido': ''}, contenido_tiene_texto=False))
        datos = DatosPublicacion.desde({**DATOS, 'contenido': ''}, False, tiene_portada=True)
        self.assertEqual(datos.estado, EstadoPublicacion.PUBLICADA)

    def test_el_titulo_es_obligatorio_y_tiene_largo_maximo(self):
        self.assertIn('titulo', self.errores({**DATOS, 'titulo': '   '}))
        self.assertIn('titulo', self.errores({**DATOS, 'titulo': 'a' * 151}))

    def test_el_resumen_tiene_largo_maximo(self):
        self.assertIn('resumen', self.errores({**DATOS, 'resumen': 'a' * 301}))

    def test_rechaza_un_estado_desconocido(self):
        self.assertIn('estado', self.errores({**DATOS, 'estado': 'ARCHIVADA'}))

    def test_publicacion_con_video_de_youtube(self):
        datos = DatosPublicacion.desde({**DATOS, 'youtube': 'https://youtu.be/dQw4w9WgXcQ'}, True, False)
        self.assertEqual(datos.youtube_id, 'dQw4w9WgXcQ')

    def test_rechaza_enlace_youtube_invalido(self):
        self.assertIn('youtube', self.errores({**DATOS, 'youtube': 'https://vimeo.com/123'}))

    def test_publicar_con_video_sin_texto_ni_portada(self):
        datos = DatosPublicacion.desde({**DATOS, 'contenido': '', 'youtube': 'https://youtu.be/dQw4w9WgXcQ'}, False, False)
        self.assertEqual(datos.estado, EstadoPublicacion.PUBLICADA)
        self.assertEqual(datos.youtube_id, 'dQw4w9WgXcQ')


class SlugTests(SimpleTestCase):
    def test_quita_tildes_y_signos(self):
        self.assertEqual(generar_slug('Nuestro taller en Ñuñoa: ¡2026!'), 'nuestro-taller-en-nunoa-2026')

    def test_un_titulo_sin_letras_usa_un_slug_generico(self):
        self.assertEqual(generar_slug('¡¡!!'), 'publicacion')

    def test_se_corta_a_un_largo_maximo(self):
        self.assertLessEqual(len(generar_slug('palabra ' * 30)), 80)

    def test_un_titulo_repetido_recibe_un_sufijo(self):
        self.assertEqual(slug_unico('Taller', set()), 'taller')
        self.assertEqual(slug_unico('Taller', {'taller'}), 'taller-2')
        self.assertEqual(slug_unico('Taller', {'taller', 'taller-2'}), 'taller-3')


class NombreBlogTests(SimpleTestCase):
    def test_vacio_vuelve_al_nombre_por_defecto(self):
        self.assertEqual(normalizar_nombre_blog('  '), 'Nosotros')
        self.assertEqual(normalizar_nombre_blog(None), 'Nosotros')

    def test_conserva_el_nombre_elegido_sin_espacios_de_mas(self):
        self.assertEqual(normalizar_nombre_blog('  Mis   trabajos '), 'Mis trabajos')

    def test_rechaza_un_nombre_demasiado_largo(self):
        with self.assertRaises(NombreBlogInvalido):
            normalizar_nombre_blog('a' * 31)


class CantidadFotosTests(SimpleTestCase):
    def test_permite_hasta_el_maximo(self):
        validar_cantidad_fotos(MAX_FOTOS_PUBLICACION - 3, 3)

    def test_rechaza_pasarse_del_maximo(self):
        with self.assertRaises(LimiteFotosExcedido):
            validar_cantidad_fotos(MAX_FOTOS_PUBLICACION - 2, 3)
