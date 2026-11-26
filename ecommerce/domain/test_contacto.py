from django.test import SimpleTestCase

from ecommerce.domain.contacto import UsuarioInstagramInvalido, direccion_es_publica, normalizar_usuario_instagram


class UsuarioInstagramTests(SimpleTestCase):
    def test_acepta_el_usuario_con_o_sin_arroba_y_el_enlace_al_perfil(self):
        for texto in ('mitienda', '@mitienda', ' @MiTienda ', 'instagram.com/mitienda',
                      'https://www.instagram.com/mitienda/', 'https://instagram.com/MiTienda?hl=es'):
            with self.subTest(texto=texto):
                self.assertEqual(normalizar_usuario_instagram(texto), 'mitienda')

    def test_admite_puntos_guiones_bajos_y_numeros(self):
        self.assertEqual(normalizar_usuario_instagram('taller.mache_2026'), 'taller.mache_2026')

    def test_vacio_quita_el_usuario(self):
        self.assertEqual(normalizar_usuario_instagram('  '), '')
        self.assertEqual(normalizar_usuario_instagram(None), '')

    def test_rechaza_usuarios_que_instagram_no_permite(self):
        for texto in ('mi tienda', 'tienda!', '.tienda', 'tienda.', 'mi..tienda', 'a' * 31,
                      'https://facebook.com/mitienda', '@'):
            with self.subTest(texto=texto), self.assertRaises(UsuarioInstagramInvalido):
                normalizar_usuario_instagram(texto)


class DireccionPublicaTests(SimpleTestCase):
    def test_solo_se_publica_si_hay_retiro_o_el_admin_la_quiere_en_el_pie(self):
        self.assertTrue(direccion_es_publica(retiro_en_local_activo=True, mostrar_direccion_pie=False))
        self.assertTrue(direccion_es_publica(retiro_en_local_activo=False, mostrar_direccion_pie=True))
        self.assertFalse(direccion_es_publica(retiro_en_local_activo=False, mostrar_direccion_pie=False))
