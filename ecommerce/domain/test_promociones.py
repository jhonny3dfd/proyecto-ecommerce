from decimal import Decimal

from django.test import SimpleTestCase

from ecommerce.domain.promociones import (
    MONTO_FIJO, PORCENTAJE, PromocionInvalida, ReglaDescuento, elegir_promocion, monto_descuento, validar_promocion,
)


class ValidarPromocionTests(SimpleTestCase):
    """RF-04.1: lo que se puede guardar como código de descuento."""

    def test_normaliza_el_codigo_y_acepta_los_valores_razonables(self):
        self.assertEqual(validar_promocion(' verano-20 ', PORCENTAJE, 100, None), 'VERANO-20')
        self.assertEqual(validar_promocion('PASCUA_5000', MONTO_FIJO, 5000, 30000), 'PASCUA_5000')
        self.assertEqual(validar_promocion('AÑONUEVO', PORCENTAJE, '12.5', None), 'AÑONUEVO')

    def test_cada_error_queda_en_su_campo(self):
        with self.assertRaises(PromocionInvalida) as error:
            validar_promocion('dos palabras', PORCENTAJE, 101, 0)
        self.assertEqual(set(error.exception.errores), {'codigo', 'valor_descuento', 'umbral_envio_gratis'})

    def test_rechaza_codigo_vacio_o_largo_y_montos_imposibles(self):
        for args in (('', PORCENTAJE, 10, None), ('A' * 51, PORCENTAJE, 10, None), ('X', PORCENTAJE, None, None),
                     ('X', MONTO_FIJO, '1000.5', None), ('X', MONTO_FIJO, -1, None)):
            with self.subTest(args=args), self.assertRaises(PromocionInvalida):
                validar_promocion(*args)

    def test_un_automatico_necesita_monto_minimo_y_los_usos_son_al_menos_uno(self):
        with self.assertRaises(PromocionInvalida) as error:
            validar_promocion('AUTO', PORCENTAJE, 10, None, monto_minimo=None, automatica=True, usos_maximos=0)
        self.assertEqual(set(error.exception.errores), {'monto_minimo', 'usos_maximos'})
        self.assertEqual(validar_promocion('AUTO', PORCENTAJE, 10, None, monto_minimo=30000, automatica=True), 'AUTO')


class ElegirPromocionTests(SimpleTestCase):
    """El código escrito y los automáticos no se suman: gana el que más ahorra (envío gratis incluido)."""

    def test_el_monto_minimo_deja_el_descuento_en_cero(self):
        regla = ReglaDescuento(PORCENTAJE, Decimal('10'), monto_minimo=Decimal('30000'))
        self.assertEqual(monto_descuento(regla, Decimal('29999')), 0)
        self.assertEqual(monto_descuento(regla, Decimal('30000')), 3000)
        # Nunca más que el subtotal
        self.assertEqual(monto_descuento(ReglaDescuento(MONTO_FIJO, Decimal('9000')), Decimal('5000')), 5000)

    def test_gana_el_que_mas_ahorra_contando_el_envio(self):
        porcentaje = ReglaDescuento(PORCENTAJE, Decimal('10'))
        envio_gratis = ReglaDescuento(MONTO_FIJO, Decimal('1000'), umbral_envio_gratis=Decimal('15000'))
        # 10 % de 20.000 = 2.000; el otro ahorra 1.000 + 3.990 de envío
        self.assertIs(elegir_promocion([porcentaje, envio_gratis], Decimal('20000'), Decimal('3990'), lambda r: r),
                      envio_gratis)
        self.assertIs(elegir_promocion([porcentaje, envio_gratis], Decimal('20000'), Decimal('0'), lambda r: r),
                      porcentaje)

    def test_con_el_mismo_ahorro_gana_el_primero_y_sin_ahorro_ninguno(self):
        uno, otro = ReglaDescuento(MONTO_FIJO, Decimal('1000')), ReglaDescuento(MONTO_FIJO, Decimal('1000'))
        self.assertIs(elegir_promocion([uno, otro], Decimal('5000'), Decimal('0'), lambda r: r), uno)
        lejano = ReglaDescuento(PORCENTAJE, Decimal('10'), monto_minimo=Decimal('90000'))
        self.assertIsNone(elegir_promocion([lejano], Decimal('5000'), Decimal('0'), lambda r: r))
