from unittest import TestCase

from ecommerce.domain.banner import (
    DESTINO_POR_DEFECTO,
    LARGO_ANTETITULO,
    LARGO_TEXTO,
    LARGO_TITULO,
    TextosFoto,
    TextosFotoInvalidos,
    normalizar_textos_foto,
    MAX_VIDEO_BANNER_BYTES,
    LimiteVideosBannerExcedido,
    VideoBannerInvalido,
    validar_cantidad_videos_banner,
    validar_video_banner,
)



class TextosFotoTests(TestCase):
    def test_normaliza_espacios_y_conserva_el_destino(self):
        textos = normalizar_textos_foto({'antetitulo': ' Nuevo ', 'titulo': ' Murales ', 'texto': ' Hechos a mano ',
                                         'destino': 'BLOG'})
        self.assertEqual(textos, TextosFoto('Nuevo', 'Murales', 'Hechos a mano', 'BLOG'))

    def test_sin_destino_el_boton_lleva_al_catalogo(self):
        for datos in [{'titulo': 'Murales'}, {'titulo': 'Murales', 'destino': ''}, {'titulo': 'Murales', 'destino': None}]:
            with self.subTest(datos=datos):
                self.assertEqual(normalizar_textos_foto(datos).destino, DESTINO_POR_DEFECTO)

    def test_el_antetitulo_y_el_texto_son_opcionales(self):
        textos = normalizar_textos_foto({'titulo': 'Murales', 'antetitulo': None})
        self.assertEqual((textos.antetitulo, textos.texto), ('', ''))

    def test_el_titulo_es_obligatorio(self):
        for titulo in [None, '', '   ']:
            with self.subTest(titulo=titulo), self.assertRaises(TextosFotoInvalidos):
                normalizar_textos_foto({'titulo': titulo})

    def test_respeta_los_largos_de_la_portada(self):
        maximos = {'antetitulo': LARGO_ANTETITULO, 'titulo': LARGO_TITULO, 'texto': LARGO_TEXTO}
        for campo, largo in maximos.items():
            with self.subTest(campo=campo):
                datos = {'titulo': 'Murales', campo: 'x' * largo}
                self.assertEqual(getattr(normalizar_textos_foto(datos), campo), 'x' * largo)
                with self.assertRaises(TextosFotoInvalidos):
                    normalizar_textos_foto({'titulo': 'Murales', campo: 'x' * (largo + 1)})

    def test_rechaza_destinos_y_formatos_invalidos(self):
        for datos in [{'titulo': 'Murales', 'destino': 'SOBRE_MI'}, {'titulo': 'Murales', 'destino': 'catalogo'},
                      {'titulo': 5}, 'Murales', None]:
            with self.subTest(datos=datos), self.assertRaises(TextosFotoInvalidos):
                normalizar_textos_foto(datos)

class VideoBannerTests(TestCase):
    def setUp(self):
        self.nombre = 'presentacion.mp4'
        self.mime = 'video/mp4'
        self.tamano = 5 * 1024 * 1024
        self.firma = b'\x00\x00\x00\x18ftyp'

    def test_acepta_video_mp4_valido(self):
        validar_video_banner(self.nombre, self.mime, self.tamano, self.firma)

    def test_acepta_video_de_exactamente_10_mb(self):
        validar_video_banner(
            self.nombre, self.mime, MAX_VIDEO_BANNER_BYTES, self.firma
        )

    def test_rechaza_video_mayor_a_10_mb(self):
        with self.assertRaises(VideoBannerInvalido):
            validar_video_banner(
                self.nombre, self.mime, MAX_VIDEO_BANNER_BYTES + 1, self.firma
            )

    def test_rechaza_extension_que_no_es_mp4(self):
        with self.assertRaises(VideoBannerInvalido):
            validar_video_banner('video.avi', self.mime, self.tamano, self.firma)

    def test_rechaza_mime_que_no_es_mp4(self):
        with self.assertRaises(VideoBannerInvalido):
            validar_video_banner(
                self.nombre, 'video/avi', self.tamano, self.firma
            )

    def test_rechaza_archivo_sin_firma_mp4(self):
        with self.assertRaises(VideoBannerInvalido):
            validar_video_banner(
                self.nombre, self.mime, self.tamano, b'no-es-mp4'
            )

    def test_rechaza_archivo_vacio(self):
        with self.assertRaises(VideoBannerInvalido):
            validar_video_banner(self.nombre, self.mime, 0, self.firma)

    def test_rechaza_dos_videos(self):
        with self.assertRaises(LimiteVideosBannerExcedido):
            validar_cantidad_videos_banner(2)

    def test_acepta_un_video(self):
        validar_cantidad_videos_banner(1)
