from unittest import TestCase

from ecommerce.application.banner import ActualizarBanners, RepositorioBanners
from ecommerce.domain.banner import (
    EstructuraBannerInvalida, LimiteFotosBannerExcedido, TextosFoto, TextosFotoInvalidos,
)


class FakeRepositorioBanners(RepositorioBanners):
    def __init__(self):
        self.llamadas = []

    def guardar_banners(self, configuracion_id: int, orden_list: list, nuevos_archivos: list, textos=None) -> None:
        self.llamadas.append((configuracion_id, orden_list, nuevos_archivos))
        self.textos = textos


class ActualizarBannersApplicationTests(TestCase):
    def setUp(self):
        self.repo = FakeRepositorioBanners()
        self.caso_de_uso = ActualizarBanners(self.repo)

    def test_valida_formato_de_orden_valido(self):
        self.caso_de_uso.ejecutar(1, ['id:legacy', 'nuevo:0'], ['archivo1'])
        self.assertEqual(len(self.repo.llamadas), 1)
        config_id, orden, archivos = self.repo.llamadas[0]
        self.assertEqual(config_id, 1)
        self.assertEqual(orden, ['id:legacy', 'nuevo:0'])
        self.assertEqual(archivos, ['archivo1'])

    def test_valida_orden_en_formato_json_string(self):
        self.caso_de_uso.ejecutar(1, '["id:1", "nuevo:0"]', ['archivo1'])
        self.assertEqual(len(self.repo.llamadas), 1)

    def test_rechaza_formato_no_json(self):
        with self.assertRaises(EstructuraBannerInvalida):
            self.caso_de_uso.ejecutar(1, '{no-es-json', [])

    def test_rechaza_tipo_no_lista(self):
        with self.assertRaises(EstructuraBannerInvalida):
            self.caso_de_uso.ejecutar(1, 123, [])

    def test_rechaza_mas_de_10_fotos(self):
        with self.assertRaises(LimiteFotosBannerExcedido):
            self.caso_de_uso.ejecutar(1, [f'nuevo:{i}' for i in range(11)], ['f'] * 11)

    def test_rechaza_indice_nuevo_fuera_de_rango(self):
        with self.assertRaises(EstructuraBannerInvalida):
            self.caso_de_uso.ejecutar(1, ['nuevo:5'], ['f1'])

    def test_rechaza_id_invalido(self):
        with self.assertRaises(EstructuraBannerInvalida):
            self.caso_de_uso.ejecutar(1, ['id:no-es-numero'], [])

    def test_sin_textos_el_repositorio_recibe_none_por_foto(self):
        self.caso_de_uso.ejecutar(1, ['id:3', 'nuevo:0'], ['f'])
        self.assertEqual(self.repo.textos, [None, None])

    def test_separa_la_referencia_de_los_textos_de_cada_foto(self):
        orden = [{'ref': 'id:3', 'titulo': ' Murales ', 'destino': 'BLOG'}, 'nuevo:0',
                 {'ref': 'id:legacy', 'antetitulo': 'Nuevo', 'titulo': 'Cyber', 'texto': 'Hasta el lunes'}]
        self.caso_de_uso.ejecutar(1, orden, ['f'])
        _, referencias, _ = self.repo.llamadas[0]
        self.assertEqual(referencias, ['id:3', 'nuevo:0', 'id:legacy'])
        self.assertEqual(self.repo.textos, [
            TextosFoto('', 'Murales', '', 'BLOG'), None, TextosFoto('Nuevo', 'Cyber', 'Hasta el lunes', 'CATALOGO'),
        ])

    def test_rechaza_textos_invalidos_sin_llamar_al_repositorio(self):
        for item in [{'ref': 'id:3', 'titulo': ''}, {'ref': 'id:3', 'titulo': 'Murales', 'destino': 'SOBRE_MI'}]:
            with self.subTest(item=item), self.assertRaises(TextosFotoInvalidos):
                self.caso_de_uso.ejecutar(1, [item], [])
        self.assertEqual(self.repo.llamadas, [])

    def test_rechaza_un_objeto_sin_referencia_o_con_referencia_invalida(self):
        for item in [{'titulo': 'Murales'}, {'ref': 'otro', 'titulo': 'Murales'}, {'ref': 'nuevo:4', 'titulo': 'Murales'}]:
            with self.subTest(item=item), self.assertRaises(EstructuraBannerInvalida):
                self.caso_de_uso.ejecutar(1, [item], [])

class VideoEnManifiestoTests(TestCase):
    def test_asocia_video_con_imagen_nueva(self):
        from unittest.mock import Mock
        repo = Mock()
        video = object()
        ActualizarBanners(repo).ejecutar(1, [{'ref': 'nuevo:0', 'titulo': 'Video', 'video_indice': 0}],
                                         [object()], [video])
        self.assertEqual(repo.guardar_banners.call_args.kwargs['nuevos_videos'], [video])
        self.assertEqual(repo.guardar_banners.call_args.kwargs['asociaciones'], {'nuevo:0': 0})

    def test_rechaza_video_sin_imagen_asociada(self):
        from unittest.mock import Mock
        repo = Mock()
        with self.assertRaises(EstructuraBannerInvalida):
            ActualizarBanners(repo).ejecutar(1, [], [], [object()])
        repo.guardar_banners.assert_not_called()

    def test_rechaza_video_asociado_a_foto_existente(self):
        from unittest.mock import Mock
        repo = Mock()
        with self.assertRaises(EstructuraBannerInvalida):
            ActualizarBanners(repo).ejecutar(1, [{'ref': 'id:1', 'titulo': 'Video', 'video_indice': 0}],
                                             [], [object()])
        repo.guardar_banners.assert_not_called()

    def test_rechaza_referencias_repetidas(self):
        casos = [
            ['nuevo:0', 'nuevo:0'],
            ['id:3', 'id:3'],
            ['id:3', 3],
            ['id:legacy', 'legacy'],
            ['nuevo:0', 'nuevo:00'],
        ]

        for orden in casos:
            with self.subTest(orden=orden):
                repositorio = FakeRepositorioBanners()
                caso_uso = ActualizarBanners(repositorio)

                with self.assertRaises(EstructuraBannerInvalida):
                    caso_uso.ejecutar(
                        configuracion_id=1,
                        raw_orden=orden,
                        nuevos_archivos=['archivo1'],
                    )

                self.assertEqual(repositorio.llamadas, [])
