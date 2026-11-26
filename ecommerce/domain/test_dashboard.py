from datetime import date

from django.test import SimpleTestCase

from ecommerce.domain.dashboard import (
    Agrupacion, ClavePeriodo, EstadoStock, Periodo, PeriodoInvalido, estado_stock, periodo_anterior, porcentajes,
    resolver_periodo, ticket_promedio, variacion_porcentual,
)

HOY = date(2026, 11, 5)


def rango(periodo):
    return periodo.desde, periodo.hasta


class ResolverPeriodoTests(SimpleTestCase):
    def test_los_periodos_predefinidos(self):
        casos = {
            ClavePeriodo.ESTE_MES: (date(2026, 11, 1), HOY),
            ClavePeriodo.MES_ANTERIOR: (date(2026, 10, 1), date(2026, 10, 31)),
            ClavePeriodo.ULTIMOS_30: (date(2026, 10, 7), HOY),
            ClavePeriodo.ESTE_ANO: (date(2026, 1, 1), HOY),
            ClavePeriodo.DESDE_INICIO: (None, HOY),
        }
        for clave, esperado in casos.items():
            with self.subTest(clave=clave):
                self.assertEqual(rango(resolver_periodo(clave, HOY)), esperado)

    def test_sin_periodo_es_este_mes(self):
        self.assertEqual(resolver_periodo(None, HOY).clave, ClavePeriodo.ESTE_MES)

    def test_el_mes_anterior_en_enero_es_diciembre_del_ano_pasado(self):
        self.assertEqual(rango(resolver_periodo('MES_ANTERIOR', date(2027, 1, 10))),
                         (date(2026, 12, 1), date(2026, 12, 31)))

    def test_personalizado_con_fechas_en_texto(self):
        self.assertEqual(rango(resolver_periodo('PERSONALIZADO', HOY, '2026-10-03', '2026-10-09')),
                         (date(2026, 10, 3), date(2026, 10, 9)))

    def test_personalizado_invalido(self):
        for desde, hasta in [('2026-10-09', '2026-10-03'), ('', '2026-10-03'), ('3/10/2026', '2026-10-09')]:
            with self.subTest(desde=desde, hasta=hasta), self.assertRaises(PeriodoInvalido):
                resolver_periodo('PERSONALIZADO', HOY, desde, hasta)

    def test_un_periodo_que_no_existe(self):
        with self.assertRaises(PeriodoInvalido):
            resolver_periodo('SEMANA', HOY)


class PeriodoAnteriorTests(SimpleTestCase):
    def test_este_mes_contra_el_mismo_tramo_del_mes_anterior(self):
        anterior = periodo_anterior(resolver_periodo('ESTE_MES', HOY))
        self.assertEqual(rango(anterior), (date(2026, 10, 1), date(2026, 10, 5)))

    def test_el_31_de_marzo_se_compara_hasta_el_ultimo_dia_de_febrero(self):
        anterior = periodo_anterior(resolver_periodo('ESTE_MES', date(2027, 3, 31)))
        self.assertEqual(rango(anterior), (date(2027, 2, 1), date(2027, 2, 28)))

    def test_el_mes_anterior_contra_el_mes_completo_previo(self):
        # Octubre (31 días) contra septiembre (30) y diciembre contra noviembre
        self.assertEqual(rango(periodo_anterior(resolver_periodo('MES_ANTERIOR', HOY))),
                         (date(2026, 9, 1), date(2026, 9, 30)))
        self.assertEqual(rango(periodo_anterior(resolver_periodo('MES_ANTERIOR', date(2027, 1, 10)))),
                         (date(2026, 11, 1), date(2026, 11, 30)))

    def test_el_ano_contra_el_mismo_tramo_del_ano_anterior(self):
        self.assertEqual(rango(periodo_anterior(resolver_periodo('ESTE_ANO', HOY))),
                         (date(2025, 1, 1), date(2025, 11, 5)))

    def test_un_rango_contra_los_mismos_dias_justo_antes(self):
        self.assertEqual(rango(periodo_anterior(resolver_periodo('ULTIMOS_30', HOY))),
                         (date(2026, 9, 7), date(2026, 10, 6)))
        self.assertEqual(rango(periodo_anterior(resolver_periodo('PERSONALIZADO', HOY, '2026-10-03', '2026-10-09'))),
                         (date(2026, 9, 26), date(2026, 10, 2)))

    def test_desde_el_inicio_no_tiene_con_que_compararse(self):
        self.assertIsNone(periodo_anterior(resolver_periodo('DESDE_INICIO', HOY)))


class AgrupacionTests(SimpleTestCase):
    def test_hasta_dos_meses_por_dia_y_mas_largo_por_mes(self):
        self.assertEqual(resolver_periodo('ULTIMOS_30', HOY).agrupacion, Agrupacion.DIA)
        self.assertEqual(Periodo(ClavePeriodo.PERSONALIZADO, date(2026, 9, 1), date(2026, 11, 1)).agrupacion,
                         Agrupacion.DIA)
        self.assertEqual(Periodo(ClavePeriodo.PERSONALIZADO, date(2026, 9, 1), date(2026, 11, 2)).agrupacion,
                         Agrupacion.MES)
        self.assertEqual(resolver_periodo('ESTE_ANO', HOY).agrupacion, Agrupacion.MES)
        self.assertEqual(resolver_periodo('DESDE_INICIO', HOY).agrupacion, Agrupacion.MES)


class CalculosTests(SimpleTestCase):
    def test_variacion_porcentual(self):
        self.assertEqual(variacion_porcentual(112_000, 100_000), 12)
        self.assertEqual(variacion_porcentual(50_000, 100_000), -50)
        self.assertEqual(variacion_porcentual(0, 100_000), -100)

    def test_sin_ventas_antes_no_hay_variacion(self):
        self.assertIsNone(variacion_porcentual(100_000, 0))

    def test_ticket_promedio(self):
        self.assertEqual(ticket_promedio(100_000, 3), 33_333)
        self.assertEqual(ticket_promedio(0, 0), 0)

    def test_porcentajes(self):
        self.assertEqual(porcentajes([620, 380]), [62, 38])
        self.assertEqual(porcentajes([0, 0]), [0, 0])


class EstadoStockTests(SimpleTestCase):
    def test_umbral_de_5_unidades(self):
        casos = {0: EstadoStock.AGOTADO, -1: EstadoStock.AGOTADO, 1: EstadoStock.BAJO, 5: EstadoStock.BAJO, 6: None}
        for stock, esperado in casos.items():
            with self.subTest(stock=stock):
                self.assertEqual(estado_stock(stock), esperado)
