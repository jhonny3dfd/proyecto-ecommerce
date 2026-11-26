from copy import deepcopy
from unittest import TestCase

from ecommerce.domain.menu import (
    MAXIMO_NOMBRE_CATALOGO, ORDEN_MENU,
    MenuInvalido, normalizar_menu_principal,
)


class MenuTests(TestCase):
    def assert_invalido(self, valor, mensaje, menu_anterior=None):
        with self.assertRaises(MenuInvalido) as error:
            normalizar_menu_principal(valor, menu_anterior)
        self.assertEqual(str(error.exception), mensaje)

    def test_configuracion_vacia_no_agrega_campos_ausentes(self):
        self.assertEqual(normalizar_menu_principal({}), {})
        self.assertEqual(normalizar_menu_principal({'nombres': {}}), {'nombres': {}})
        self.assertEqual(normalizar_menu_principal({'ocultos': []}), {'ocultos': []})

    def test_rechaza_estructura_y_claves_desconocidas(self):
        for valor in [None, [], '', 1, True, {'ruta': '/'}, {'orden': [], 'extra': True}]:
            with self.subTest(valor=valor):
                self.assert_invalido(valor, 'La configuración debe contener solo orden, nombres y ocultos.')

    def test_completa_orden_vacio_o_incompleto_y_conserva_el_completo(self):
        casos = [
            ([], list(ORDEN_MENU)),
            (['catalogo', 'inicio'], ['catalogo', 'inicio', 'nosotros', 'sobre_mi', 'cotizar', 'suscripcion']),
            (['cotizar'], ['cotizar', 'inicio', 'catalogo', 'nosotros', 'sobre_mi', 'suscripcion']),
            (list(ORDEN_MENU), list(ORDEN_MENU)),
            (list(reversed(ORDEN_MENU)), list(reversed(ORDEN_MENU))),
        ]
        for orden, esperado in casos:
            with self.subTest(orden=orden):
                self.assertEqual(normalizar_menu_principal({'orden': orden}), {'orden': esperado})

    def test_rechaza_orden_invalido_con_el_mensaje_original(self):
        for orden in [None, {}, 'inicio', ('inicio',), 1, True, ['inicio', 'inicio'],
                      ['otro'], ['inicio', 'otro'], [1], [None], [True], [{}], [[]]]:
            with self.subTest(orden=orden):
                self.assert_invalido({'orden': orden}, 'El orden debe contener enlaces conocidos, de texto y sin duplicados.')

    def test_normaliza_espacios_y_omite_nombres_vacios(self):
        resultado = normalizar_menu_principal({'nombres': {'catalogo': '  Mis\tproductos  '}})
        self.assertEqual(resultado, {'nombres': {'catalogo': 'Mis productos'}})
        self.assertEqual(normalizar_menu_principal({'nombres': {'catalogo': ' \t\n '}}), {'nombres': {}})

    def test_rechaza_nombres_invalidos_con_los_mensajes_originales(self):
        for nombres in [None, [], 'Inicio', {'otro': 'Nombre'}]:
            with self.subTest(nombres=nombres):
                self.assert_invalido({'nombres': nombres}, 'Los nombres contienen enlaces desconocidos.')
        for nombre in [None, 1, True, [], {}]:
            with self.subTest(nombre=nombre):
                self.assert_invalido({'nombres': {'catalogo': nombre}}, 'Cada nombre debe ser texto.')

    def test_solo_se_renombra_catalogo(self):
        # El blog y Sobre mí se nombran en su propio módulo; Inicio y Cotizar son fijos
        for clave in [clave for clave in ORDEN_MENU if clave != 'catalogo']:
            with self.subTest(clave=clave):
                self.assert_invalido({'nombres': {clave: 'Otro nombre'}}, 'Solo se puede cambiar el nombre de Catálogo.')
                self.assert_invalido({'nombres': {'catalogo': 'Productos', clave: 'Otro nombre'}},
                                     'Solo se puede cambiar el nombre de Catálogo.')

    def test_conserva_nombres_antiguos_de_otros_botones_si_no_cambian(self):
        anterior = {'nombres': {'sobre_mi': '  Historia   antigua ', 'inicio': 'Portada'}}
        resultado = normalizar_menu_principal(
            {'nombres': {'sobre_mi': 'Historia antigua', 'inicio': 'Portada', 'catalogo': 'Productos'}}, anterior)
        self.assertEqual(resultado, {'nombres': {
            'sobre_mi': '  Historia   antigua ', 'inicio': 'Portada', 'catalogo': 'Productos'}})
        self.assert_invalido({'nombres': {'inicio': 'Otra portada'}}, 'Solo se puede cambiar el nombre de Catálogo.',
                             anterior)

    def test_limite_del_nombre_de_catalogo(self):
        datos = {'nombres': {'catalogo': 'x' * MAXIMO_NOMBRE_CATALOGO}}
        self.assertEqual(normalizar_menu_principal(datos), datos)
        self.assert_invalido({'nombres': {'catalogo': 'x' * (MAXIMO_NOMBRE_CATALOGO + 1)}},
                             f'El nombre no puede superar los {MAXIMO_NOMBRE_CATALOGO} caracteres.')

    def test_preserva_exactamente_catalogo_antiguo_largo_si_no_cambia(self):
        antiguo = '  Nuestra   colección especial  '
        menu_anterior = {'nombres': {'catalogo': antiguo}}
        for nombre in [antiguo, 'Nuestra colección especial']:
            with self.subTest(nombre=nombre):
                resultado = normalizar_menu_principal({'nombres': {'catalogo': nombre}}, menu_anterior)
                self.assertEqual(resultado, menu_anterior)
        self.assertEqual(normalizar_menu_principal({'nombres': {'catalogo': ' Productos '}}, menu_anterior),
                         {'nombres': {'catalogo': 'Productos'}})

    def test_excepcion_antigua_no_permite_nombres_largos_nuevos(self):
        valor = {'nombres': {'catalogo': 'Una colección nueva demasiado larga'}}
        self.assert_invalido(valor, 'El nombre no puede superar los 20 caracteres.')
        self.assert_invalido(valor, 'El nombre no puede superar los 20 caracteres.',
                             {'nombres': {'catalogo': 'Nuestra colección especial'}})

    def test_conserva_ocultos_por_compatibilidad(self):
        for ocultos in [[], ['cotizar'], ['nosotros', 'sobre_mi', 'cotizar']]:
            with self.subTest(ocultos=ocultos):
                self.assertEqual(normalizar_menu_principal({'ocultos': ocultos}), {'ocultos': ocultos})

    def test_rechaza_ocultos_invalidos_con_el_mensaje_original(self):
        for ocultos in [None, {}, 'cotizar', ('cotizar',), [1], [None], [{}], [[]],
                        ['inicio'], ['catalogo'], ['otro'], ['cotizar', 'cotizar']]:
            with self.subTest(ocultos=ocultos):
                self.assert_invalido({'ocultos': ocultos}, 'Solo se pueden ocultar enlaces opcionales, sin duplicados.')

    def test_no_modifica_entradas_y_conserva_la_estructura_completa(self):
        valor = {'orden': ['catalogo'], 'nombres': {'catalogo': ' Productos '}, 'ocultos': ['sobre_mi']}
        anterior = {'nombres': {'catalogo': 'Nuestra colección especial'}}
        copia_valor, copia_anterior = deepcopy(valor), deepcopy(anterior)
        resultado = normalizar_menu_principal(valor, anterior)
        self.assertEqual(resultado, {
            'orden': ['catalogo', 'inicio', 'nosotros', 'sobre_mi', 'cotizar', 'suscripcion'],
            'nombres': {'catalogo': 'Productos'}, 'ocultos': ['sobre_mi'],
        })
        self.assertEqual(valor, copia_valor)
        self.assertEqual(anterior, copia_anterior)
