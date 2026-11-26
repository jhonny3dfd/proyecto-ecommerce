from django.test import SimpleTestCase

from ecommerce.domain.categorias import (
    CategoriaInvalida, Renombre, normalizar_nombre_categoria, planificar_renombre, renombrar_en_orden,
    renombrar_en_plan,
)


class PlanificarRenombreTests(SimpleTestCase):
    def test_un_nombre_nuevo_renombra_sin_espacios_sobrantes(self):
        self.assertEqual(planificar_renombre('Cafes', '  Cafés   de  origen ', ['Cafes', 'Packs']),
                         Renombre('Cafes', 'Cafés de origen', une=False))

    def test_el_nombre_de_otra_categoria_las_une_con_su_escritura(self):
        # El admin escribe "packs" y ya existe "Packs": se unen en "Packs"
        self.assertEqual(planificar_renombre('Promos', 'packs', ['Packs', 'Promos']),
                         Renombre('Promos', 'Packs', une=True))

    def test_la_misma_con_otras_mayusculas_corrige_su_escritura(self):
        self.assertEqual(planificar_renombre('cafés', 'Cafés', ['cafés', 'Packs']),
                         Renombre('cafés', 'Cafés', une=False))

    def test_rechaza_vacio_igual_o_demasiado_largo(self):
        for nuevo, mensaje in (('  ', 'Escribe el nombre nuevo'), ('Cafés', 'distinto al actual'),
                               ('x' * 101, 'hasta 100'), (None, 'Escribe el nombre nuevo')):
            with self.subTest(nuevo=nuevo), self.assertRaisesMessage(CategoriaInvalida, mensaje):
                planificar_renombre('Cafés', nuevo, ['Cafés'])

    def test_normaliza_espacios(self):
        self.assertEqual(normalizar_nombre_categoria(' Té\t verde '), 'Té verde')


class ReferenciasTests(SimpleTestCase):
    def test_el_orden_conserva_la_posicion_y_no_repite_al_unir(self):
        self.assertEqual(renombrar_en_orden(['Promos', 'Cafés', 'Packs'], Renombre('Promos', 'Ofertas', False)),
                         ['Ofertas', 'Cafés', 'Packs'])
        self.assertEqual(renombrar_en_orden(['Cafés', 'Promos', 'Packs'], Renombre('Packs', 'Cafés', True)),
                         ['Cafés', 'Promos'])
        self.assertEqual(renombrar_en_orden(['Cafés'], Renombre('Packs', 'Promos', False)), ['Cafés'])

    def test_el_plan_pasa_a_la_nueva_sin_distinguir_mayusculas(self):
        renombre = Renombre('Cafes', 'Cafés', une=False)
        self.assertEqual(renombrar_en_plan(['cafes', 'Packs'], renombre, ['Cafés', 'Packs']), ['Packs', 'Cafés'])
        self.assertEqual(renombrar_en_plan(['Packs'], renombre, ['Cafés', 'Packs']), ['Packs'])

    def test_el_plan_no_repite_si_ya_tenia_la_nueva(self):
        renombre = Renombre('Promos', 'Packs', une=True)
        self.assertEqual(renombrar_en_plan(['Promos', 'packs'], renombre, ['Packs']), ['packs'])

    def test_el_plan_conserva_la_entrada_si_aun_nombra_otra_categoria(self):
        # "Café" y "café" eran dos categorías; el plan las admitía a ambas
        renombre = Renombre('café', 'Bebidas', une=False)
        self.assertEqual(renombrar_en_plan(['Café'], renombre, ['Café', 'Bebidas']), ['Café', 'Bebidas'])
