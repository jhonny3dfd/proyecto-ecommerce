"""Validación del día y mes sin depender de un año de nacimiento."""
from unittest import TestCase

from .cumpleanos import validar_cumpleanos


class CumpleanosTests(TestCase):
    def test_opcional_y_29_de_febrero(self):
        self.assertEqual(validar_cumpleanos(None, None), (None, None))
        self.assertEqual(validar_cumpleanos(29, 2), (29, 2))

    def test_rechaza_fechas_inexistentes_y_pares_incompletos(self):
        for dia, mes in [(31, 4), (30, 2), (1, 13), (0, 1), (None, 1), (1, None), (True, 1), ('1', 1)]:
            with self.subTest(dia=dia, mes=mes), self.assertRaises(ValueError):
                validar_cumpleanos(dia, mes)
