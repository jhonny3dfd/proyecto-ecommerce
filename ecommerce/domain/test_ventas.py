from datetime import datetime, timedelta

from django.test import SimpleTestCase

from ecommerce.domain.ventas import (
    EstadoPedido, NombreInvalido, OrdenTransporteNoPermitida, TelefonoInvalido, TransicionNoPermitida,
    normalizar_nombre_persona, normalizar_telefono_chile, paginas_legales_faltantes, plazo_pago, transiciones_desde,
    validar_generacion_orden_transporte, validar_transicion,
)

E = EstadoPedido

# Máquina de estados del pedido, escrita a mano para no repetir la tabla del dominio
PERMITIDAS = {
    (E.PENDIENTE, E.PAGADO), (E.PENDIENTE, E.CANCELADO),
    (E.PAGADO, E.EN_PREPARACION), (E.PAGADO, E.CANCELADO),
    (E.EN_PREPARACION, E.ENVIADO), (E.EN_PREPARACION, E.CANCELADO),
    (E.ENVIADO, E.ENTREGADO),
}


class MaquinaEstadosPedidoTests(SimpleTestCase):
    def test_solo_se_permiten_las_transiciones_de_la_tabla(self):
        for actual in EstadoPedido:
            for nuevo in EstadoPedido:
                with self.subTest(actual=actual, nuevo=nuevo):
                    if (actual, nuevo) in PERMITIDAS:
                        self.assertEqual(validar_transicion(actual, nuevo), nuevo)
                    else:
                        with self.assertRaises(TransicionNoPermitida):
                            validar_transicion(actual, nuevo)

    def test_transiciones_desde_cada_estado_en_orden_del_flujo(self):
        for actual in EstadoPedido:
            with self.subTest(actual=actual):
                esperadas = [nuevo for nuevo in EstadoPedido if (actual, nuevo) in PERMITIDAS]
                self.assertEqual(transiciones_desde(actual), esperadas)
        self.assertEqual(transiciones_desde('PAGADO'), [E.EN_PREPARACION, E.CANCELADO])
        self.assertEqual(transiciones_desde('RECHAZADO'), [])

    def test_acepta_los_codigos_como_texto(self):
        self.assertIs(validar_transicion('PAGADO', 'EN_PREPARACION'), E.EN_PREPARACION)

    def test_estado_desconocido_se_rechaza(self):
        for actual, nuevo in (('RECHAZADO', 'PAGADO'), ('PENDIENTE', 'RECHAZADO')):
            with self.subTest(actual=actual, nuevo=nuevo):
                with self.assertRaises(TransicionNoPermitida):
                    validar_transicion(actual, nuevo)

    def test_el_mensaje_usa_los_nombres_de_la_interfaz(self):
        with self.assertRaisesMessage(TransicionNoPermitida,
                                      'Un pedido Cancelado no puede pasar a Pagado.'):
            validar_transicion(E.CANCELADO, E.PAGADO)


class TelefonoDestinatarioTests(SimpleTestCase):
    def test_acepta_formatos_chilenos_y_normaliza(self):
        for texto in ('+56 9 1234 5678', '912345678', '56912345678', '(+56) 9-1234-5678'):
            with self.subTest(texto=texto):
                self.assertEqual(normalizar_telefono_chile(texto), '+56912345678')
        # Fijo con código de área (ej. Santiago 2)
        self.assertEqual(normalizar_telefono_chile('+56 2 2345 6789'), '+56223456789')

    def test_rechaza_lo_que_no_es_un_telefono_chileno(self):
        for texto in ('', '12345', '+1 555 123 4567', '012345678', 'no tengo', '+56 9 1234 56789'):
            with self.subTest(texto=texto), self.assertRaises(TelefonoInvalido):
                normalizar_telefono_chile(texto)


class NombrePersonaTests(SimpleTestCase):
    def test_acepta_nombres_con_tildes_guiones_apostrofos_y_puntos(self):
        for texto, esperado in (('María José', 'María José'), ("O'Higgins", "O'Higgins"), ('Juan P.', 'Juan P.'),
                                ('Núñez-Pérez', 'Núñez-Pérez'), ('  Ana   María ', 'Ana María')):
            with self.subTest(texto=texto):
                self.assertEqual(normalizar_nombre_persona(texto), esperado)

    def test_rechaza_numeros_simbolos_o_texto_vacio(self):
        for texto in ('', '   ', '12345', 'Ana2', '<b>Ana</b>', '-Ana', 'Ana_Pérez', '@@@'):
            with self.subTest(texto=texto), self.assertRaises(NombreInvalido):
                normalizar_nombre_persona(texto)


class GeneracionOrdenTransporteTests(SimpleTestCase):
    def test_solo_pedidos_pagados_sin_despachar_y_sin_revision(self):
        for estado in (E.PAGADO, E.EN_PREPARACION):
            validar_generacion_orden_transporte(estado, requiere_revision=False)
        for estado in (E.PENDIENTE, E.ENVIADO, E.ENTREGADO, E.CANCELADO):
            with self.subTest(estado=estado), self.assertRaises(OrdenTransporteNoPermitida):
                validar_generacion_orden_transporte(estado, requiere_revision=False)
        with self.assertRaisesMessage(OrdenTransporteNoPermitida, 'Resuelve la revisión'):
            validar_generacion_orden_transporte(E.PAGADO, requiere_revision=True)


class PaginasLegalesParaVenderTests(SimpleTestCase):
    def test_faltan_terminos_y_privacidad_hasta_publicarlas(self):
        self.assertEqual(paginas_legales_faltantes([]), ['TERMINOS', 'PRIVACIDAD'])
        self.assertEqual(paginas_legales_faltantes(['REEMBOLSOS', 'PRIVACIDAD']), ['TERMINOS'])
        self.assertEqual(paginas_legales_faltantes(['PRIVACIDAD', 'TERMINOS']), [])


class PlazoPagoTests(SimpleTestCase):
    def test_vence_al_terminar_el_plazo_y_recuerda_a_la_mitad(self):
        creada = datetime(2026, 10, 19, 10, 0)
        for horas, recordar in ((12, datetime(2026, 10, 19, 16, 0)), (48, datetime(2026, 10, 20, 10, 0)),
                                (72, datetime(2026, 10, 20, 22, 0))):
            with self.subTest(horas=horas):
                plazo = plazo_pago(creada, timedelta(hours=horas))
                self.assertEqual(plazo.vence, creada + timedelta(hours=horas))
                self.assertEqual(plazo.recordar, recordar)
