from datetime import datetime, timezone

from django.test import SimpleTestCase

from ecommerce.application.blog import (
    SIN_CAMBIO, AgregarFotos, BlogDesactivado, EliminarPublicacion, FotoNoEncontrada, GuardarPublicacion,
    PaginaBlog, PublicacionGuardada, PublicacionNoEncontrada, QuitarFoto, RepositorioPublicaciones, VerBlog,
    VerPublicacion,
)
from ecommerce.domain.blog import EstadoPublicacion, LimiteFotosExcedido, PublicacionInvalida
from ecommerce.domain.imagenes import ImagenProcesada

AHORA = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
DESPUES = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
FOTO = ImagenProcesada(contenido=b'png', extension='png')
PUBLICADA = {'titulo': 'Nuestro taller', 'contenido': '<p>Desde 2015.</p>', 'estado': 'PUBLICADA'}
BORRADOR = {'titulo': 'Idea nueva', 'estado': 'BORRADOR'}


class RepositorioPublicacionesFalso(RepositorioPublicaciones):
    def __init__(self):
        self.publicaciones = {}
        self.fotos = {}
        self.ultimo_id_foto = 0

    def obtener(self, publicacion_id):
        guardada = self.publicaciones.get(publicacion_id)
        if guardada is None:
            return None
        return PublicacionGuardada(
            slug=guardada['slug'], fecha_publicacion=guardada['fecha_publicacion'],
            tiene_portada=guardada['portada'] is not None,
            cantidad_fotos=sum(1 for de_publicacion in self.fotos.values() if de_publicacion == publicacion_id),
            youtube_id=guardada['datos'].youtube_id,
        )

    def slugs_parecidos(self, base, excepto_id):
        return {p['slug'] for i, p in self.publicaciones.items() if i != excepto_id and p['slug'].startswith(base)}

    def guardar(self, publicacion_id, datos, slug, fecha_publicacion, portada):
        if publicacion_id is None:
            publicacion_id = len(self.publicaciones) + 1
            anterior_portada = None
        else:
            anterior_portada = self.publicaciones[publicacion_id]['portada']
        self.publicaciones[publicacion_id] = {
            'datos': datos, 'slug': slug, 'fecha_publicacion': fecha_publicacion,
            'portada': anterior_portada if portada is SIN_CAMBIO else portada,
        }
        return publicacion_id

    def eliminar(self, publicacion_id):
        return self.publicaciones.pop(publicacion_id, None) is not None

    def agregar_fotos(self, publicacion_id, imagenes):
        ids = []
        for _ in imagenes:
            self.ultimo_id_foto += 1
            self.fotos[self.ultimo_id_foto] = publicacion_id
            ids.append(self.ultimo_id_foto)
        return ids

    def quitar_foto(self, publicacion_id, foto_id):
        if self.fotos.get(foto_id) != publicacion_id:
            return False
        del self.fotos[foto_id]
        return True

    def _publicadas(self):
        return sorted((i for i, p in self.publicaciones.items() if p['datos'].estado == EstadoPublicacion.PUBLICADA),
                      key=lambda i: self.publicaciones[i]['fecha_publicacion'], reverse=True)

    def publicadas(self, desde, cantidad):
        ids = self._publicadas()
        return PaginaBlog(ids=ids[desde:desde + cantidad], total=len(ids))

    def id_publicada(self, slug):
        return next((i for i in self._publicadas() if self.publicaciones[i]['slug'] == slug), None)


class GuardarPublicacionTests(SimpleTestCase):
    def setUp(self):
        self.repositorio = RepositorioPublicacionesFalso()
        self.caso = GuardarPublicacion(self.repositorio)

    def guardar(self, datos, publicacion_id=None, texto=True, ahora=AHORA, portada=SIN_CAMBIO):
        return self.caso.ejecutar(publicacion_id, datos, contenido_tiene_texto=texto, ahora=ahora, portada=portada)

    def test_al_publicar_se_fija_la_fecha_y_el_slug_sale_del_titulo(self):
        guardada = self.repositorio.publicaciones[self.guardar(PUBLICADA)]
        self.assertEqual(guardada['slug'], 'nuestro-taller')
        self.assertEqual(guardada['fecha_publicacion'], AHORA)

    def test_un_borrador_no_tiene_fecha_y_su_slug_sigue_al_titulo(self):
        publicacion_id = self.guardar(BORRADOR, texto=False)
        self.assertIsNone(self.repositorio.publicaciones[publicacion_id]['fecha_publicacion'])
        self.guardar({**BORRADOR, 'titulo': 'Idea mejor'}, publicacion_id, texto=False)
        self.assertEqual(self.repositorio.publicaciones[publicacion_id]['slug'], 'idea-mejor')

    def test_despues_de_publicada_el_slug_y_la_fecha_no_cambian(self):
        publicacion_id = self.guardar(PUBLICADA)
        self.guardar({**PUBLICADA, 'titulo': 'Otro título'}, publicacion_id, ahora=DESPUES)
        guardada = self.repositorio.publicaciones[publicacion_id]
        self.assertEqual((guardada['slug'], guardada['fecha_publicacion']), ('nuestro-taller', AHORA))
        self.assertEqual(guardada['datos'].titulo, 'Otro título')

    def test_volver_a_borrador_conserva_el_slug_para_no_romper_enlaces(self):
        publicacion_id = self.guardar(PUBLICADA)
        self.guardar({**PUBLICADA, 'titulo': 'Otro', 'estado': 'BORRADOR'}, publicacion_id)
        self.assertEqual(self.repositorio.publicaciones[publicacion_id]['slug'], 'nuestro-taller')

    def test_guarda_publicacion_con_video_de_youtube(self):
        pub_id = self.guardar({**PUBLICADA, 'youtube': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'})
        guardada = self.repositorio.publicaciones[pub_id]
        self.assertEqual(guardada['datos'].youtube_id, 'dQw4w9WgXcQ')
        obtenida = self.repositorio.obtener(pub_id)
        self.assertEqual(obtenida.youtube_id, 'dQw4w9WgXcQ')

    def test_un_titulo_repetido_no_repite_el_slug(self):
        self.guardar(PUBLICADA)
        segunda = self.guardar(PUBLICADA)
        self.assertEqual(self.repositorio.publicaciones[segunda]['slug'], 'nuestro-taller-2')

    def test_editar_un_borrador_no_choca_con_su_propio_slug(self):
        publicacion_id = self.guardar(BORRADOR, texto=False)
        self.guardar(BORRADOR, publicacion_id, texto=False)
        self.assertEqual(self.repositorio.publicaciones[publicacion_id]['slug'], 'idea-nueva')

    def test_publicar_solo_con_portada_vale_si_la_trae_o_ya_la_tenia(self):
        sin_texto = {**PUBLICADA, 'contenido': ''}
        publicacion_id = self.guardar(sin_texto, texto=False, portada=FOTO)
        self.guardar(sin_texto, publicacion_id, texto=False)
        self.assertIs(self.repositorio.publicaciones[publicacion_id]['portada'], FOTO)

    def test_quitar_la_portada_de_una_publicacion_sin_texto_impide_publicarla(self):
        sin_texto = {**PUBLICADA, 'contenido': ''}
        publicacion_id = self.guardar(sin_texto, texto=False, portada=FOTO)
        with self.assertRaises(PublicacionInvalida):
            self.guardar(sin_texto, publicacion_id, texto=False, portada=None)
        self.assertIs(self.repositorio.publicaciones[publicacion_id]['portada'], FOTO)

    def test_datos_invalidos_no_guardan_nada(self):
        with self.assertRaises(PublicacionInvalida):
            self.guardar({**PUBLICADA, 'titulo': ''})
        self.assertEqual(self.repositorio.publicaciones, {})

    def test_editar_una_publicacion_inexistente(self):
        with self.assertRaises(PublicacionNoEncontrada):
            self.guardar(PUBLICADA, publicacion_id=99)


class VerBlogTests(SimpleTestCase):
    def setUp(self):
        self.repositorio = RepositorioPublicacionesFalso()
        guardar = GuardarPublicacion(self.repositorio)
        self.primera = guardar.ejecutar(None, PUBLICADA, True, AHORA)
        self.borrador = guardar.ejecutar(None, BORRADOR, False, AHORA)
        self.segunda = guardar.ejecutar(None, {**PUBLICADA, 'titulo': 'Feria de primavera'}, True, DESPUES)

    def test_lista_solo_las_publicadas_las_mas_recientes_primero(self):
        pagina = VerBlog(self.repositorio).ejecutar(blog_activo=True)
        self.assertEqual((pagina.ids, pagina.total), ([self.segunda, self.primera], 2))

    def test_pagina(self):
        caso = VerBlog(self.repositorio, por_pagina=1)
        self.assertEqual(caso.ejecutar(blog_activo=True, pagina=2).ids, [self.primera])
        self.assertEqual(caso.ejecutar(blog_activo=True, pagina=0).ids, [self.segunda])

    def test_con_el_blog_apagado_el_publico_no_ve_nada(self):
        with self.assertRaises(BlogDesactivado):
            VerBlog(self.repositorio).ejecutar(blog_activo=False)
        with self.assertRaises(BlogDesactivado):
            VerPublicacion(self.repositorio).ejecutar('nuestro-taller', blog_activo=False)

    def test_una_publicacion_se_abre_por_su_slug(self):
        self.assertEqual(VerPublicacion(self.repositorio).ejecutar('nuestro-taller', blog_activo=True),
                         self.primera)

    def test_un_borrador_responde_igual_que_una_inexistente(self):
        for slug in ('idea-nueva', 'no-existe'):
            with self.subTest(slug=slug), self.assertRaises(PublicacionNoEncontrada):
                VerPublicacion(self.repositorio).ejecutar(slug, blog_activo=True)


class FotosYEliminarTests(SimpleTestCase):
    def setUp(self):
        self.repositorio = RepositorioPublicacionesFalso()
        self.publicacion_id = GuardarPublicacion(self.repositorio).ejecutar(None, PUBLICADA, True, AHORA)

    def test_agrega_fotos_hasta_el_maximo(self):
        ids = AgregarFotos(self.repositorio).ejecutar(self.publicacion_id, [FOTO] * 10)
        self.assertEqual(len(ids), 10)
        with self.assertRaises(LimiteFotosExcedido):
            AgregarFotos(self.repositorio).ejecutar(self.publicacion_id, [FOTO])
        self.assertEqual(len(self.repositorio.fotos), 10)

    def test_quitar_una_foto_libera_espacio(self):
        foto_id, *_ = AgregarFotos(self.repositorio).ejecutar(self.publicacion_id, [FOTO] * 10)
        QuitarFoto(self.repositorio).ejecutar(self.publicacion_id, foto_id)
        AgregarFotos(self.repositorio).ejecutar(self.publicacion_id, [FOTO])
        self.assertEqual(len(self.repositorio.fotos), 10)

    def test_no_se_quita_una_foto_de_otra_publicacion(self):
        otra = GuardarPublicacion(self.repositorio).ejecutar(None, BORRADOR, False, AHORA)
        [foto_id] = AgregarFotos(self.repositorio).ejecutar(otra, [FOTO])
        with self.assertRaises(FotoNoEncontrada):
            QuitarFoto(self.repositorio).ejecutar(self.publicacion_id, foto_id)

    def test_fotos_de_una_publicacion_inexistente(self):
        with self.assertRaises(PublicacionNoEncontrada):
            AgregarFotos(self.repositorio).ejecutar(99, [FOTO])

    def test_eliminar(self):
        EliminarPublicacion(self.repositorio).ejecutar(self.publicacion_id)
        self.assertEqual(self.repositorio.publicaciones, {})
        with self.assertRaises(PublicacionNoEncontrada):
            EliminarPublicacion(self.repositorio).ejecutar(self.publicacion_id)
