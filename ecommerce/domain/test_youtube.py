from django.test import SimpleTestCase

from ecommerce.domain.youtube import extraer_id_youtube


class ExtraerIdYouTubeTests(SimpleTestCase):
    def test_enlace_estandar_watch(self):
        self.assertEqual(extraer_id_youtube('https://www.youtube.com/watch?v=dQw4w9WgXcQ'), 'dQw4w9WgXcQ')
        self.assertEqual(extraer_id_youtube('http://youtube.com/watch?v=dQw4w9WgXcQ&t=42s&feature=share'), 'dQw4w9WgXcQ')

    def test_enlace_corto_youtu_be(self):
        self.assertEqual(extraer_id_youtube('https://youtu.be/dQw4w9WgXcQ'), 'dQw4w9WgXcQ')
        self.assertEqual(extraer_id_youtube('http://youtu.be/dQw4w9WgXcQ?t=10'), 'dQw4w9WgXcQ')

    def test_enlace_shorts(self):
        self.assertEqual(extraer_id_youtube('https://www.youtube.com/shorts/dQw4w9WgXcQ'), 'dQw4w9WgXcQ')
        self.assertEqual(extraer_id_youtube('http://youtube.com/shorts/dQw4w9WgXcQ?feature=share'), 'dQw4w9WgXcQ')

    def test_enlace_movil_y_embebido(self):
        self.assertEqual(extraer_id_youtube('https://m.youtube.com/watch?v=dQw4w9WgXcQ'), 'dQw4w9WgXcQ')
        self.assertEqual(extraer_id_youtube('https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ'), 'dQw4w9WgXcQ')

    def test_id_directo_y_espacios(self):
        self.assertEqual(extraer_id_youtube('  dQw4w9WgXcQ  '), 'dQw4w9WgXcQ')

    def test_vacio_o_none_retorna_vacio(self):
        self.assertEqual(extraer_id_youtube(''), '')
        self.assertEqual(extraer_id_youtube('   '), '')
        self.assertEqual(extraer_id_youtube(None), '')

    def test_rechaza_dominio_ajeno(self):
        with self.assertRaises(ValueError) as ctx:
            extraer_id_youtube('https://vimeo.com/12345678901')
        self.assertIn('El enlace debe ser de YouTube', str(ctx.exception))

    def test_rechaza_enlace_sin_id_o_id_invalido(self):
        with self.assertRaises(ValueError):
            extraer_id_youtube('https://www.youtube.com/watch')
        with self.assertRaises(ValueError):
            extraer_id_youtube('https://youtu.be/')
        with self.assertRaises(ValueError):
            extraer_id_youtube('https://www.youtube.com/watch?v=corto')
