from unittest import TestCase

from ecommerce.domain.sobre_mi import (
    NombreSobreMiInvalido, ProyectosSobreMiInvalidos, SobreMiNoDisponible,
    construir_contacto_sobre_mi, exigir_sobre_mi_disponible, muestra_proyectos_sobre_mi, normalizar_nombre_sobre_mi,
    validar_ids_proyectos_sobre_mi,
)


class SobreMiTests(TestCase):
    def test_los_proyectos_solo_se_muestran_con_el_blog_activo(self):
        self.assertTrue(muestra_proyectos_sobre_mi(True))
        for blog_activo in [False, None]:
            with self.subTest(blog_activo=blog_activo):
                self.assertFalse(muestra_proyectos_sobre_mi(blog_activo))

    def test_pagina_activa_disponible(self):
        self.assertIsNone(exigir_sobre_mi_disponible(True))

    def test_pagina_inactiva_no_disponible(self):
        for activo in [False, None, 0, '']:
            with self.subTest(activo=activo):
                with self.assertRaises(SobreMiNoDisponible) as error:
                    exigir_sobre_mi_disponible(activo)
                self.assertEqual(str(error.exception), 'La página Sobre mí no está disponible.')

    def test_normaliza_nombre_y_usa_el_predeterminado(self):
        for valor, esperado in [('', 'Sobre mí'), (' \t\n ', 'Sobre mí'),
                                ('  Nuestra   historia\n', 'Nuestra historia')]:
            with self.subTest(valor=valor):
                self.assertEqual(normalizar_nombre_sobre_mi(valor), esperado)

    def test_limite_se_aplica_despues_de_normalizar_espacios(self):
        self.assertEqual(normalizar_nombre_sobre_mi(' ' + 'x' * 30 + ' '), 'x' * 30)
        with self.assertRaises(NombreSobreMiInvalido) as error:
            normalizar_nombre_sobre_mi('x' * 31)
        self.assertEqual(str(error.exception), 'El nombre no puede superar los 30 caracteres.')

    def test_contactos_opcionales_omiten_solo_valores_vacios(self):
        self.assertEqual(construir_contacto_sobre_mi(), {})
        self.assertEqual(construir_contacto_sobre_mi('', None, ''), {})
        self.assertEqual(construir_contacto_sobre_mi(telefono='+56912345678'), {'telefono': '+56912345678'})
        self.assertEqual(construir_contacto_sobre_mi(correo='contacto@example.test'), {'correo': 'contacto@example.test'})
        self.assertEqual(construir_contacto_sobre_mi(instagram='tienda'), {'instagram': 'tienda'})
        self.assertEqual(construir_contacto_sobre_mi('+56912345678', 'contacto@example.test', 'tienda'), {
            'telefono': '+56912345678', 'correo': 'contacto@example.test', 'instagram': 'tienda',
        })

    def test_contactos_no_se_normalizan_ni_se_agregan_restricciones(self):
        self.assertEqual(construir_contacto_sobre_mi('  ', ' correo guardado ', '@Cuenta'), {
            'telefono': '  ', 'correo': ' correo guardado ', 'instagram': '@Cuenta',
        })

    def test_ids_positivos_conservan_el_orden_y_aceptan_lista_vacia(self):
        for ids in [[], [3, 1, 2], [2 ** 70]]:
            with self.subTest(ids=ids):
                antes = list(ids)
                self.assertEqual(validar_ids_proyectos_sobre_mi(ids), antes)
                self.assertEqual(ids, antes)

    def test_rechaza_ids_que_no_sean_una_lista(self):
        for ids in [None, '1', (1, 2), {}, 1, True]:
            with self.subTest(ids=ids):
                with self.assertRaises(ProyectosSobreMiInvalidos) as error:
                    validar_ids_proyectos_sobre_mi(ids)
                self.assertEqual(str(error.exception), 'Debes enviar una lista de IDs.')

    def test_rechaza_ids_no_enteros_no_positivos_y_booleanos(self):
        for ids in [[0], [-1], [True], [False], [1.0], ['1'], [None], [{}], [[]], [1, True]]:
            with self.subTest(ids=ids):
                with self.assertRaises(ProyectosSobreMiInvalidos) as error:
                    validar_ids_proyectos_sobre_mi(ids)
                self.assertEqual(str(error.exception), 'Todos los IDs deben ser números enteros positivos.')

    def test_rechaza_ids_duplicados(self):
        with self.assertRaises(ProyectosSobreMiInvalidos) as error:
            validar_ids_proyectos_sobre_mi([2, 1, 2])
        self.assertEqual(str(error.exception), 'No puedes seleccionar una publicación más de una vez.')

    def test_el_error_de_tipo_conserva_precedencia_sobre_duplicados(self):
        with self.assertRaises(ProyectosSobreMiInvalidos) as error:
            validar_ids_proyectos_sobre_mi([0, 0])
        self.assertEqual(str(error.exception), 'Todos los IDs deben ser números enteros positivos.')
