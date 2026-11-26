from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from ecommerce.domain.suscripciones import (
    AccionNoPermitida, AccionSuscripcion, DatosPlan, EstadoSuscripcion, PlanInvalido,
    TransicionSuscripcionNoPermitida, ciclo_vencido, descuento_suscriptor, fecha_al_adelantar, fecha_al_reanudar,
    fecha_primer_ciclo,
    fecha_aviso, frecuencia_legible, siguiente_ciclo, toca_avisar, validar_accion, validar_dias_aviso,
    validar_transicion_suscripcion,
)

PLAN = {'nombre': 'Café del mes', 'precio': 14990, 'frecuencia_semanas': 4, 'categorias': ['Cafés'],
        'beneficios': ['Café recién tostado', 'Envío gratis']}


class TransicionesTests(SimpleTestCase):
    def test_el_primer_pago_activa_y_una_activa_se_pausa_reanuda_o_cancela(self):
        E = EstadoSuscripcion
        for actual, nuevo in [(E.PENDIENTE, E.ACTIVA), (E.PENDIENTE, E.CANCELADA), (E.ACTIVA, E.PAUSADA),
                              (E.ACTIVA, E.CANCELADA), (E.PAUSADA, E.ACTIVA), (E.PAUSADA, E.CANCELADA)]:
            with self.subTest(actual=actual, nuevo=nuevo):
                self.assertEqual(validar_transicion_suscripcion(actual, nuevo), nuevo)

    def test_cancelar_es_definitivo_y_no_se_salta_el_primer_pago(self):
        E = EstadoSuscripcion
        for actual, nuevo in [(E.CANCELADA, E.ACTIVA), (E.CANCELADA, E.PAUSADA), (E.PENDIENTE, E.PAUSADA),
                              (E.ACTIVA, E.PENDIENTE), (E.ACTIVA, 'INVENTADO')]:
            with self.subTest(actual=actual, nuevo=nuevo), self.assertRaises(TransicionSuscripcionNoPermitida):
                validar_transicion_suscripcion(actual, nuevo)

    def test_el_mensaje_dice_en_palabras_que_no_se_puede(self):
        with self.assertRaisesMessage(TransicionSuscripcionNoPermitida,
                                      'Una suscripción cancelada no puede pasar a activa.'):
            validar_transicion_suscripcion(EstadoSuscripcion.CANCELADA, EstadoSuscripcion.ACTIVA)


class AccionesTests(SimpleTestCase):
    def test_cada_accion_solo_en_sus_estados(self):
        A, E = AccionSuscripcion, EstadoSuscripcion
        permitidas = {(A.PAUSAR, E.ACTIVA), (A.REANUDAR, E.PAUSADA), (A.SALTAR, E.ACTIVA), (A.ADELANTAR, E.ACTIVA),
                      (A.CANCELAR, E.PENDIENTE), (A.CANCELAR, E.ACTIVA), (A.CANCELAR, E.PAUSADA),
                      (A.CAMBIAR, E.PENDIENTE), (A.CAMBIAR, E.ACTIVA), (A.CAMBIAR, E.PAUSADA)}
        for accion in A:
            for estado in E:
                with self.subTest(accion=accion, estado=estado):
                    if (accion, estado) in permitidas:
                        self.assertEqual(validar_accion(accion, estado), accion)
                    else:
                        with self.assertRaises(AccionNoPermitida):
                            validar_accion(accion, estado)

    def test_el_mensaje_explica_por_que(self):
        with self.assertRaisesMessage(AccionNoPermitida, 'Solo se puede pausar una suscripción activa.'):
            validar_accion(AccionSuscripcion.PAUSAR, EstadoSuscripcion.PAUSADA)


class FechasDeCicloTests(SimpleTestCase):
    def test_el_ciclo_siguiente_se_cuenta_desde_la_fecha_del_anterior(self):
        self.assertEqual(siguiente_ciclo(date(2026, 11, 11), 4), date(2026, 12, 9))
        self.assertEqual(siguiente_ciclo(date(2026, 12, 30), 1), date(2027, 1, 6))

    def test_el_aviso_llega_dias_antes_y_el_ciclo_vence_al_terminar_su_dia(self):
        ciclo = date(2026, 12, 9)
        self.assertEqual(fecha_aviso(ciclo, 3), date(2026, 12, 6))
        self.assertFalse(toca_avisar(ciclo, date(2026, 12, 5), 3))
        self.assertTrue(toca_avisar(ciclo, date(2026, 12, 6), 3))
        self.assertTrue(toca_avisar(ciclo, date(2026, 12, 9), 3))
        self.assertFalse(ciclo_vencido(ciclo, date(2026, 12, 9)))
        self.assertTrue(ciclo_vencido(ciclo, date(2026, 12, 10)))

    def test_reanudar_conserva_la_fecha_si_alcanza_el_aviso_y_si_no_la_corre(self):
        hoy = date(2026, 11, 11)
        self.assertEqual(fecha_al_reanudar(date(2026, 11, 30), hoy, 3), date(2026, 11, 30))
        # La entrega ya pasó durante la pausa: queda para cuando alcanza el aviso de siempre
        self.assertEqual(fecha_al_reanudar(date(2026, 11, 1), hoy, 3), date(2026, 11, 14))
        self.assertEqual(fecha_al_reanudar(date(2026, 11, 12), hoy, 3), date(2026, 11, 14))

    def test_el_primer_ciclo_deja_los_dias_de_aviso_para_pagar(self):
        self.assertEqual(fecha_primer_ciclo(date(2026, 11, 11), 3), date(2026, 11, 14))

    def test_adelantar_trae_la_entrega_a_hoy(self):
        self.assertEqual(fecha_al_adelantar(date(2026, 11, 11)), date(2026, 11, 11))

    def test_dias_de_aviso_entre_1_y_14(self):
        self.assertEqual(validar_dias_aviso('3'), 3)
        for valor in (0, 15, 'tres', None):
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                validar_dias_aviso(valor)


class DescuentoTests(SimpleTestCase):
    def test_porcentaje_en_pesos_enteros_y_nunca_mas_que_el_subtotal(self):
        self.assertEqual(descuento_suscriptor(Decimal('14990'), 10), Decimal('1499'))
        self.assertEqual(descuento_suscriptor(Decimal('14995'), 10), Decimal('1500'))  # 1499,5 redondea arriba
        self.assertEqual(descuento_suscriptor(Decimal('1000'), 0), Decimal('0'))
        self.assertEqual(descuento_suscriptor(Decimal('-5'), 50), Decimal('0'))
        self.assertLessEqual(descuento_suscriptor(Decimal('1'), 90), Decimal('1'))


class PlanTests(SimpleTestCase):
    def errores(self, cambios):
        with self.assertRaises(PlanInvalido) as error:
            DatosPlan.desde({**PLAN, **cambios})
        return error.exception.errores

    def test_un_plan_valido_queda_normalizado(self):
        plan = DatosPlan.desde({**PLAN, 'nombre': '  Café   del mes ', 'precio': '14990', 'beneficios': [
            ' Café recién tostado ', '', 'café recién tostado', 'Envío gratis']})
        self.assertEqual(plan.nombre, 'Café del mes')
        self.assertEqual((plan.precio, plan.frecuencia_semanas, plan.unidades, plan.descuento), (14990, 4, 1, 0))
        # Sin espacios de más, sin vacíos y sin repetidos (sin distinguir mayúsculas)
        self.assertEqual(plan.beneficios, ('Café recién tostado', 'Envío gratis'))
        self.assertTrue(plan.activo)

    def test_campos_obligatorios_y_limites(self):
        self.assertEqual(self.errores({'nombre': ' ', 'precio': None, 'frecuencia_semanas': ''}), {
            'nombre': 'El nombre es obligatorio.', 'precio': 'Este dato es obligatorio.',
            'frecuencia_semanas': 'Este dato es obligatorio.'})
        errores = self.errores({'precio': 0, 'frecuencia_semanas': 13, 'unidades': 21, 'descuento': 91})
        self.assertEqual(set(errores), {'precio', 'frecuencia_semanas', 'unidades', 'descuento'})
        self.assertEqual(self.errores({'precio': '14990.5'}), {'precio': 'Debe ser un número entero.'})
        self.assertEqual(self.errores({'precio': 'mucho'}), {'precio': 'Debe ser un número.'})
        self.assertIn('nombre', self.errores({'nombre': 'x' * 61}))

    def test_beneficios_hasta_10_de_120_caracteres(self):
        self.assertIn('beneficios', self.errores({'beneficios': [f'Beneficio {n}' for n in range(11)]}))
        self.assertIn('beneficios', self.errores({'beneficios': ['x' * 121]}))
        self.assertIn('beneficios', self.errores({'beneficios': 'no es una lista'}))

    def test_exige_algo_que_elegir(self):
        self.assertEqual(self.errores({'categorias': [], 'productos': []}), {
            'productos': 'Elige al menos una categoría o un producto que el cliente pueda recibir.'})
        self.assertEqual(DatosPlan.desde({**PLAN, 'categorias': [], 'productos': ['abc']}).productos, ('abc',))

    def test_envio_gratis_en_todas_las_compras_exige_el_de_la_suscripcion(self):
        self.assertIn('envio_gratis_compras', self.errores({'envio_gratis_compras': True}))
        plan = DatosPlan.desde({**PLAN, 'envio_gratis': True, 'envio_gratis_compras': True, 'descuento': '15'})
        self.assertEqual((plan.envio_gratis, plan.envio_gratis_compras, plan.descuento), (True, True, 15))

    def test_admite_por_producto_o_categoria_sin_distinguir_mayusculas(self):
        plan = DatosPlan.desde({**PLAN, 'categorias': ['Cafés'], 'productos': ['p-1']})
        self.assertTrue(plan.admite('p-9', 'cafés'))
        self.assertTrue(plan.admite('p-1', 'Packs'))
        self.assertFalse(plan.admite('p-9', 'Packs'))
        self.assertFalse(plan.admite('p-9', ''))

    def test_frecuencia_en_palabras(self):
        self.assertEqual(frecuencia_legible(1), 'Cada semana')
        self.assertEqual(frecuencia_legible(4), 'Cada 4 semanas')
