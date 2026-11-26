from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from ecommerce.application.ventas import MOTIVO_PAGO_RECHAZADO, MOTIVO_PAGO_VENCIDO
from ecommerce.infrastructure.catalogo.documents import Producto, Variante
from ecommerce.infrastructure.catalogo.tests import usar_mongo_de_prueba
from ecommerce.infrastructure.usuarios.tests.factories import create_user

from .models import ConfiguracionGlobal, Cotizacion, DetalleOrden, OrdenCompra, Promocion, Resena

SANTIAGO = ZoneInfo('America/Santiago')


def el(dia, mes=11, hora=12):
    return datetime(2026, mes, dia, hora, tzinfo=SANTIAGO)


def crear_orden(estado='PAGADO', total=10000, pagada=None, creada=None, metodo='TRANSBANK', entrega='CHILEXPRESS',
                comuna='SANTIAGO', correo='ana@example.test', usuario=None, **campos):
    orden = OrdenCompra.objects.create(
        email_invitado=None if usuario else correo, usuario=usuario, metodo_pago=metodo, estado=estado,
        proveedor_logistico=entrega, direccion_envio_snapshot={'comuna': comuna},
        subtotal=campos.pop('subtotal', total), costo_envio=campos.pop('costo_envio', 0), total_final=total, **campos)
    OrdenCompra.objects.filter(id=orden.id).update(fecha_creacion=creada or pagada or el(1), fecha_pago=pagada)
    return orden


class DashboardMetricasTests(APITestCase):
    """RF-03.1: las ventas cuentan desde que se pagan, por la fecha del pago y aunque el pedido ya avanzó."""

    def setUp(self):
        self.client.force_authenticate(create_user('admin@example.test', rol='ADMIN'))

    def metricas(self, desde='2026-11-01', hasta='2026-11-07', **parametros):
        parametros = {'periodo': 'PERSONALIZADO', 'desde': desde, 'hasta': hasta, **parametros}
        response = self.client.get(reverse('dashboard_metricas'), parametros)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_un_pedido_que_avanzo_sigue_contando_y_los_no_pagados_no(self):
        for estado in ('PAGADO', 'EN_PREPARACION', 'ENVIADO', 'ENTREGADO'):
            crear_orden(estado, pagada=el(2))
        crear_orden('PENDIENTE', creada=el(2))
        crear_orden('CANCELADO', creada=el(2))

        tarjetas = self.metricas()['tarjetas']

        self.assertEqual((tarjetas['ventas'], tarjetas['pedidos'], tarjetas['ticket_promedio']), (40000, 4, 10000))

    def test_cuenta_por_la_fecha_del_pago_y_no_la_de_creacion(self):
        # Transferencia creada el 31 de octubre y validada el 2 de noviembre
        crear_orden(metodo='TRANSFERENCIA', creada=el(31, mes=10), pagada=el(2))

        self.assertEqual(self.metricas()['tarjetas']['ventas'], 10000)
        self.assertEqual(self.metricas('2026-10-25', '2026-10-31')['tarjetas']['ventas'], 0)

    def test_los_limites_del_periodo_son_dias_de_la_tienda(self):
        crear_orden(pagada=el(7, hora=23))
        crear_orden(pagada=el(8, hora=0))

        self.assertEqual(self.metricas()['tarjetas']['pedidos'], 1)

    def test_compara_contra_los_mismos_dias_justo_antes(self):
        crear_orden(total=20000, pagada=el(3))
        crear_orden(total=10000, pagada=el(28, mes=10))

        data = self.metricas()

        self.assertEqual(data['anterior'], {'desde': el(25, mes=10).date(), 'hasta': el(31, mes=10).date()})
        self.assertEqual((data['tarjetas']['variacion_ventas'], data['tarjetas']['diferencia_pedidos']), (100, 0))

    def test_la_serie_por_dia_y_un_ano_por_mes(self):
        crear_orden(total=5000, pagada=el(2))
        crear_orden(total=7000, pagada=el(2, hora=18))
        crear_orden(total=3000, pagada=el(5))
        crear_orden(total=4000, pagada=el(10, mes=3))

        por_dia = self.metricas()['serie']
        por_mes = self.metricas('2026-01-01', '2026-11-30')['serie']

        self.assertEqual([(p['fecha'].day, p['total'], p['pedidos']) for p in por_dia], [(2, 12000, 2), (5, 3000, 1)])
        self.assertEqual([(p['fecha'].month, p['total']) for p in por_mes], [(3, 4000), (11, 15000)])

    def test_mas_vendidos_por_unidades(self):
        for nombre, cantidad, estado in (('Taza', 2, 'PAGADO'), ('Plato', 5, 'ENTREGADO'), ('Vaso', 9, 'CANCELADO')):
            orden = crear_orden(estado, pagada=el(2) if estado != 'CANCELADO' else None, creada=el(2))
            DetalleOrden.objects.create(orden=orden, producto_mongo_id=nombre.lower(), variante_sku=f'{nombre}-1',
                                        nombre_producto_snapshot=nombre, precio_unitario_snapshot=1000,
                                        cantidad=cantidad)

        vendidos = self.metricas()['mas_vendidos']

        self.assertEqual([(p['nombre'], p['unidades'], p['total']) for p in vendidos],
                         [('Plato', 5, 5000), ('Taza', 2, 2000)])

    def test_como_compran(self):
        crear_orden(total=30000, pagada=el(2), metodo='TRANSBANK', entrega='CHILEXPRESS', comuna='Maipu')
        crear_orden(total=10000, pagada=el(2), metodo='TRANSFERENCIA', entrega='chilexpress', comuna='MAIPU')
        crear_orden(total=60000, pagada=el(3), metodo='TRANSBANK', entrega='RETIRO_LOCAL', comuna='SANTIAGO')

        detalles = self.metricas()['detalles']

        self.assertEqual([(b['nombre'], b['porcentaje']) for b in detalles['medios_pago']],
                         [('Transbank Webpay Plus', 90), ('Transferencia bancaria', 10)])
        self.assertEqual([(b['nombre'], b['pedidos']) for b in detalles['entregas']],
                         [('Retiro en local', 1), ('Chilexpress', 2)])
        # El retiro en el local no es una comuna de despacho
        self.assertEqual([(b['nombre'], b['total'], b['porcentaje']) for b in detalles['comunas']],
                         [('Maipu', 40000, 40)])

    def test_cancelaciones_cupones_y_clientes(self):
        crear_orden('CANCELADO', creada=el(2), motivo_cancelacion=MOTIVO_PAGO_RECHAZADO)
        crear_orden('CANCELADO', creada=el(3), motivo_cancelacion=MOTIVO_PAGO_VENCIDO)
        crear_orden('CANCELADO', creada=el(4), motivo_cancelacion=MOTIVO_PAGO_RECHAZADO)
        cupon = Promocion.objects.create(codigo='BIENVENIDA', tipo_descuento='MONTO_FIJO', valor_descuento=2000)
        crear_orden(total=8000, subtotal=10000, pagada=el(2), promocion=cupon, correo='Ana@Example.test')
        # Ana ya había comprado en octubre: es recurrente; Beto compra por primera vez con su cuenta
        crear_orden(pagada=el(10, mes=10), correo='ana@example.test')
        beto = create_user('beto@example.test')
        crear_orden(pagada=el(3), usuario=beto)

        data = self.metricas()
        detalles = data['detalles']

        self.assertEqual([(c['causa'], c['cantidad']) for c in detalles['cancelaciones']],
                         [('PAGO_RECHAZADO', 2), ('PAGO_VENCIDO', 1)])
        self.assertEqual(detalles['cupones'], [{'codigo': 'BIENVENIDA', 'usos': 1, 'descontado': 2000}])
        self.assertEqual(detalles['clientes'], {'nuevos': 1, 'recurrentes': 1, 'registrados': 1, 'invitados': 1})
        self.assertEqual(data['tarjetas']['clientes_nuevos'], 1)

    def test_la_calificacion_solo_con_las_resenas_activas(self):
        ConfiguracionGlobal.objects.create(pk=1, nombre_tienda='Tienda', resenas_activas=False)
        orden = crear_orden('ENTREGADO', pagada=el(2))
        Resena.objects.create(orden=orden, estrellas=4, nombre_publico='Ana P.', estado='APROBADA')

        self.assertIsNone(self.metricas()['detalles']['calificacion'])
        ConfiguracionGlobal.objects.filter(pk=1).update(resenas_activas=True)
        self.assertEqual(self.metricas()['detalles']['calificacion'], {'promedio': 4.0, 'cantidad': 1})

    def test_sin_periodo_es_este_mes_y_trae_los_ultimos_pedidos(self):
        crear_orden(pagada=timezone.now())

        response = self.client.get(reverse('dashboard_metricas'))

        self.assertEqual(response.data['periodo']['clave'], 'ESTE_MES')
        self.assertEqual(response.data['periodo']['desde'], timezone.localdate().replace(day=1))
        self.assertEqual(response.data['ultimas_ordenes'][0]['cliente'], 'ana@example.test')

    def test_un_periodo_invalido_responde_400(self):
        for parametros in ({'periodo': 'SEMANA'}, {'periodo': 'PERSONALIZADO', 'desde': '2026-11-09',
                                                     'hasta': '2026-11-01'}):
            with self.subTest(parametros=parametros):
                response = self.client.get(reverse('dashboard_metricas'), parametros)
                self.assertEqual(response.status_code, 400)
                self.assertIn('periodo', response.data)

    def test_solo_el_admin(self):
        self.client.force_authenticate(create_user('comprador@example.test'))
        self.assertEqual(self.client.get(reverse('dashboard_metricas')).status_code, 403)
        self.assertEqual(self.client.get(reverse('dashboard_pendientes')).status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(reverse('dashboard_metricas')).status_code, 401)


class DashboardPendientesTests(APITestCase):
    """RF-03.1: "Para hoy" cuenta lo que espera al admin y el stock de 5 unidades o menos."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        usar_mongo_de_prueba(cls)

    def setUp(self):
        Producto._get_collection().delete_many({})
        self.client.force_authenticate(create_user('admin@example.test', rol='ADMIN'))

    def pendientes(self):
        response = self.client.get(reverse('dashboard_pendientes'))
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_sin_nada_pendiente_esta_al_dia(self):
        crear_orden('ENTREGADO', pagada=el(2), metodo='TRANSBANK')

        self.assertEqual(self.pendientes(), {'al_dia': True, 'tareas': [], 'agotadas': [], 'stock_bajo': []})

    def test_cuenta_cada_pendiente(self):
        ahora = timezone.now()
        crear_orden('PAGADO', pagada=ahora)
        crear_orden('PAGADO', pagada=ahora, requiere_revision=True, motivo_revision='Sin stock')
        crear_orden('PENDIENTE', metodo='TRANSFERENCIA', fecha_limite_pago=ahora + timedelta(hours=3))
        crear_orden('PENDIENTE', metodo='TRANSFERENCIA', fecha_limite_pago=ahora + timedelta(hours=40))
        # Un pago en línea pendiente (Webpay abandonado) no es una transferencia por validar
        crear_orden('PENDIENTE', metodo='TRANSBANK')
        crear_orden('EN_PREPARACION', pagada=ahora, error_orden_transporte='Chilexpress no respondió')
        # Cancelado: su error ya no se atiende
        crear_orden('CANCELADO', error_orden_transporte='Chilexpress no respondió')
        Cotizacion.objects.create(nombre='Ana', correo='ana@example.test', telefono='+56911112222', cantidad=3)
        Resena.objects.create(orden=crear_orden('ENTREGADO', pagada=ahora), estrellas=5, nombre_publico='Ana P.')
        # Con el voucher como boleta, Webpay no pide documento; una transferencia vendida sin folio, sí
        crear_orden('ENTREGADO', pagada=ahora, metodo='TRANSFERENCIA')

        tareas = {t['tarea']: (t['cantidad'], t['por_vencer']) for t in self.pendientes()['tareas']}

        self.assertEqual(tareas, {
            'POR_PREPARAR': (1, 0), 'TRANSFERENCIAS': (2, 1), 'REVISION': (1, 0), 'ORDEN_TRANSPORTE': (1, 0),
            'DOCUMENTOS': (1, 0), 'COTIZACIONES': (1, 0), 'RESENAS': (1, 0),
        })

    def test_stock_agotado_y_bajo_de_productos_activos(self):
        Producto(nombre='Polerón', categoria='Ropa', fecha_creacion=timezone.now(), variantes=[
            Variante(sku='POL-S', precio=10000, stock=0, atributos_variables={'Talla': 'S'}),
            Variante(sku='POL-M', precio=10000, stock=5, atributos_variables={'Talla': 'M'}),
            Variante(sku='POL-L', precio=10000, stock=6),
        ]).save()
        Producto(nombre='Gorro viejo', categoria='Ropa', activo=False, fecha_creacion=timezone.now(),
                 variantes=[Variante(sku='GOR-1', precio=5000, stock=0)]).save()

        data = self.pendientes()

        self.assertFalse(data['al_dia'])
        self.assertEqual([(v['sku'], v['detalle'], v['stock']) for v in data['agotadas']], [('POL-S', 'Talla: S', 0)])
        self.assertEqual([v['sku'] for v in data['stock_bajo']], ['POL-M'])


class FiltroOrdenTransporteTests(APITestCase):
    def test_la_lista_de_pedidos_filtra_los_que_fallaron_al_generar_su_orden_de_transporte(self):
        self.client.force_authenticate(create_user('admin@example.test', rol='ADMIN'))
        con_error = crear_orden('PAGADO', pagada=el(2), error_orden_transporte='Sin cobertura')
        crear_orden('PAGADO', pagada=el(2))
        crear_orden('CANCELADO', error_orden_transporte='Sin cobertura')

        response = self.client.get(reverse('admin-ordenes-list'), {'orden_transporte': 'error'})

        self.assertEqual([orden['id'] for orden in response.data['results']], [con_error.id])
