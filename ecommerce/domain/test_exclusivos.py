"""Acceso a exclusivos: regla independiente del navegador y de la persistencia."""
from unittest import TestCase

from .suscripciones import permite_producto_exclusivo


class AccesoExclusivosTests(TestCase):
    def test_sin_modulo_o_sin_restriccion_no_exige_suscripcion(self):
        self.assertTrue(permite_producto_exclusivo(False, True, [1], []))
        self.assertTrue(permite_producto_exclusivo(True, False, [1], []))

    def test_sin_planes_vigentes_no_accede(self):
        self.assertFalse(permite_producto_exclusivo(True, True, [], []))
        self.assertFalse(permite_producto_exclusivo(True, True, [1], []))

    def test_planes_permitidos_y_seleccion_de_entrega(self):
        self.assertTrue(permite_producto_exclusivo(True, True, [], [2], 2))
        self.assertTrue(permite_producto_exclusivo(True, True, [1], [1, 2], 1))
        self.assertFalse(permite_producto_exclusivo(True, True, [1], [2]))
        self.assertFalse(permite_producto_exclusivo(True, True, [1], [1], 2))
