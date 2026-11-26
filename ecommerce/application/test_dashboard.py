from datetime import date, datetime, timedelta, timezone

from django.test import SimpleTestCase

from ecommerce.application.dashboard import (
    CausaCancelacion, ConteoPendientes, Grupo, MetricasVentas, PendientesTienda, ProductoVendido, PuntoSerie,
    ResumenClientes, ResumenDashboard, ResumenVentas, StockCatalogo, Tarea, TareaPendiente, TareasPendientes,
    UsoCupon, VariantePocoStock, causa_cancelacion,
)
from ecommerce.application.pagos import MOTIVO_PAGO_REEMBOLSADO
from ecommerce.application.ventas import (
    MOTIVO_CANCELACION_ADMIN, MOTIVO_PAGO_ANULADO, MOTIVO_PAGO_RECHAZADO, MOTIVO_PAGO_VENCIDO,
)
from ecommerce.domain.dashboard import resolver_periodo

HOY = date(2026, 11, 5)
NOVIEMBRE = resolver_periodo('ESTE_MES', HOY)


class MetricasFalsas(MetricasVentas):
    """Ventas por periodo (clave: (desde, hasta)); lo demás, fijo."""

    def __init__(self, ventas=None, calificaciones=None, **datos):
        self.ventas = ventas or {}
        self.estrellas = calificaciones
        self.datos = datos
        self.limites = {}

    def resumen(self, periodo):
        return self.ventas.get((periodo.desde, periodo.hasta), ResumenVentas(0, 0))

    def serie(self, periodo):
        return self.datos.get('serie', [])

    def mas_vendidos(self, periodo, limite):
        self.limites['mas_vendidos'] = limite
        return self.datos.get('mas_vendidos', [])[:limite]

    def por_medio_pago(self, periodo):
        return self.datos.get('medios_pago', [])

    def por_entrega(self, periodo):
        return self.datos.get('entregas', [])

    def por_comuna(self, periodo, limite):
        return self.datos.get('comunas', [])[:limite]

    def cancelaciones(self, periodo):
        return self.datos.get('cancelaciones', [])

    def cupones(self, periodo):
        return self.datos.get('cupones', [])

    def clientes(self, periodo):
        return self.datos.get('clientes', ResumenClientes(0, 0, 0, 0))

    def calificaciones(self):
        return self.estrellas


def resumen(metricas, periodo=NOVIEMBRE):
    return ResumenDashboard(metricas).ejecutar(periodo)


class TarjetasTests(SimpleTestCase):
    """RF-03.1: ventas, pedidos, ticket promedio y clientes nuevos, contra el mismo tramo del mes anterior."""

    def test_compara_contra_el_mismo_tramo_del_mes_anterior(self):
        metricas = MetricasFalsas(ventas={
            (date(2026, 11, 1), HOY): ResumenVentas(112_000, 4),
            (date(2026, 10, 1), date(2026, 10, 5)): ResumenVentas(100_000, 5),
        }, clientes=ResumenClientes(nuevos=3, recurrentes=1, registrados=2, invitados=2))

        tarjetas = resumen(metricas).tarjetas

        self.assertEqual((tarjetas.ventas, tarjetas.variacion_ventas), (112_000, 12))
        self.assertEqual((tarjetas.pedidos, tarjetas.diferencia_pedidos), (4, -1))
        self.assertEqual((tarjetas.ticket_promedio, tarjetas.variacion_ticket), (28_000, 40))
        self.assertEqual(tarjetas.clientes_nuevos, 3)

    def test_sin_ventas_en_el_periodo_anterior_no_hay_variacion(self):
        metricas = MetricasFalsas(ventas={(date(2026, 11, 1), HOY): ResumenVentas(50_000, 2)})

        tarjetas = resumen(metricas).tarjetas

        self.assertIsNone(tarjetas.variacion_ventas)
        self.assertIsNone(tarjetas.variacion_ticket)
        # Los pedidos sí se comparan: antes hubo 0
        self.assertEqual(tarjetas.diferencia_pedidos, 2)

    def test_desde_el_inicio_no_se_compara(self):
        metricas = MetricasFalsas(ventas={(None, HOY): ResumenVentas(900_000, 30)})

        dashboard = resumen(metricas, resolver_periodo('DESDE_INICIO', HOY))

        self.assertIsNone(dashboard.anterior)
        self.assertIsNone(dashboard.tarjetas.variacion_ventas)
        self.assertIsNone(dashboard.tarjetas.diferencia_pedidos)
        self.assertEqual(dashboard.tarjetas.ventas, 900_000)


class DetallesTests(SimpleTestCase):
    def test_mas_vendidos_y_serie_tal_como_llegan(self):
        vendidos = [ProductoVendido(str(i), f'Producto {i}', 10 - i, 1000) for i in range(8)]
        serie = [PuntoSerie(date(2026, 11, 2), 20_000, 1)]

        dashboard = resumen(MetricasFalsas(mas_vendidos=vendidos, serie=serie))

        self.assertEqual(len(dashboard.mas_vendidos), 5)
        self.assertEqual(dashboard.serie, serie)

    def test_las_barras_van_de_mayor_a_menor_con_su_porcentaje(self):
        metricas = MetricasFalsas(medios_pago=[
            Grupo('TRANSFERENCIA', 'Transferencia', 38_000, 2), Grupo('TRANSBANK', 'Webpay', 62_000, 3)])

        barras = resumen(metricas).medios_pago

        self.assertEqual([(b.nombre, b.porcentaje) for b in barras], [('Webpay', 62), ('Transferencia', 38)])

    def test_las_comunas_se_miden_contra_todo_lo_vendido(self):
        metricas = MetricasFalsas(ventas={(date(2026, 11, 1), HOY): ResumenVentas(200_000, 8)}, comunas=[
            Grupo('MAIPU', 'MAIPU', 50_000, 2), Grupo('SANTIAGO', 'SANTIAGO', 100_000, 4)])

        barras = resumen(metricas).comunas

        self.assertEqual([(b.nombre, b.porcentaje) for b in barras], [('SANTIAGO', 50), ('MAIPU', 25)])

    def test_las_cancelaciones_se_agrupan_por_causa(self):
        metricas = MetricasFalsas(cancelaciones=[
            (MOTIVO_PAGO_RECHAZADO, 3), (MOTIVO_PAGO_ANULADO, 2), (MOTIVO_PAGO_VENCIDO, 4), ('', 1)])

        self.assertEqual(resumen(metricas).cancelaciones, [
            (CausaCancelacion.PAGO_RECHAZADO, 5), (CausaCancelacion.PAGO_VENCIDO, 4), (CausaCancelacion.OTRO, 1)])

    def test_los_cupones_mas_usados_primero(self):
        metricas = MetricasFalsas(cupones=[UsoCupon('VERANO', 2, 4000), UsoCupon('BIENVENIDA', 7, 14_000)])

        self.assertEqual([c.codigo for c in resumen(metricas).cupones], ['BIENVENIDA', 'VERANO'])

    def test_la_calificacion_solo_con_resenas_activas_y_aprobadas(self):
        self.assertIsNone(resumen(MetricasFalsas(calificaciones=None)).calificacion)
        self.assertIsNone(resumen(MetricasFalsas(calificaciones=[])).calificacion)
        calificacion = resumen(MetricasFalsas(calificaciones=[5, 4, 4, 4])).calificacion
        self.assertEqual((calificacion.promedio, calificacion.cantidad), (4.3, 4))


class CausaCancelacionTests(SimpleTestCase):
    def test_cada_motivo_conocido(self):
        casos = {
            MOTIVO_PAGO_RECHAZADO: CausaCancelacion.PAGO_RECHAZADO,
            MOTIVO_PAGO_ANULADO: CausaCancelacion.PAGO_RECHAZADO,
            MOTIVO_PAGO_VENCIDO: CausaCancelacion.PAGO_VENCIDO,
            MOTIVO_PAGO_REEMBOLSADO.format(referencia='MP-123'): CausaCancelacion.PAGO_DEVUELTO,
            MOTIVO_CANCELACION_ADMIN: CausaCancelacion.TIENDA,
            'El cliente se arrepintió': CausaCancelacion.OTRO,
            '': CausaCancelacion.OTRO,
        }
        for motivo, causa in casos.items():
            with self.subTest(motivo=motivo):
                self.assertEqual(causa_cancelacion(motivo), causa)


class PendientesFalsos(PendientesTienda):
    def __init__(self, conteo):
        self.conteo = conteo
        self.por_vencer_antes = None

    def contar(self, por_vencer_antes):
        self.por_vencer_antes = por_vencer_antes
        return self.conteo


class StockFalso(StockCatalogo):
    def __init__(self, variantes=()):
        self.variantes = list(variantes)
        self.umbral = None

    def con_poco_stock(self, umbral):
        self.umbral = umbral
        return [v for v in self.variantes if v.stock <= umbral]


AHORA = datetime(2026, 11, 5, 15, tzinfo=timezone.utc)


def variante(sku, stock, producto='Polerón'):
    return VariantePocoStock('p1', producto, sku, 'Talla M', stock)


class TareasPendientesTests(SimpleTestCase):
    """RF-03.1: "Para hoy" muestra solo lo que no está en cero."""

    def test_solo_las_tareas_con_algo_y_en_su_orden(self):
        pendientes = PendientesFalsos(ConteoPendientes(
            resenas=2, por_preparar=3, transferencias=1, transferencias_por_vencer=1, documentos=0))

        para_hoy = TareasPendientes(pendientes, StockFalso()).ejecutar(AHORA)

        self.assertEqual(para_hoy.tareas, [
            TareaPendiente(Tarea.POR_PREPARAR, 3), TareaPendiente(Tarea.TRANSFERENCIAS, 1, por_vencer=1),
            TareaPendiente(Tarea.RESENAS, 2)])
        self.assertFalse(para_hoy.al_dia)

    def test_las_transferencias_vencen_pronto_si_les_quedan_24_horas(self):
        pendientes = PendientesFalsos(ConteoPendientes())

        TareasPendientes(pendientes, StockFalso()).ejecutar(AHORA)

        self.assertEqual(pendientes.por_vencer_antes, AHORA + timedelta(hours=24))

    def test_stock_agotado_y_bajo_con_el_umbral_de_5(self):
        stock = StockFalso([variante('S', 0), variante('M', 5), variante('L', 6), variante('XL', 2)])

        para_hoy = TareasPendientes(PendientesFalsos(ConteoPendientes()), stock).ejecutar(AHORA)

        self.assertEqual(stock.umbral, 5)
        self.assertEqual([v.sku for v in para_hoy.agotadas], ['S'])
        # Los que tienen menos, primero
        self.assertEqual([v.sku for v in para_hoy.stock_bajo], ['XL', 'M'])

    def test_sin_nada_pendiente_esta_al_dia(self):
        para_hoy = TareasPendientes(PendientesFalsos(ConteoPendientes()), StockFalso([variante('L', 9)])).ejecutar(
            AHORA)

        self.assertEqual(para_hoy.tareas, [])
        self.assertTrue(para_hoy.al_dia)
