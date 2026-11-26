from datetime import datetime
from io import BytesIO

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook
from rest_framework.test import APITestCase

from ecommerce.application.exportacion_ventas import COLUMNAS_PRODUCTOS, COLUMNAS_VENTAS, LineaVendida
from ecommerce.domain.dashboard import resolver_periodo
from ecommerce.domain.ventas import EstadoPedido
from ecommerce.infrastructure.usuarios.tests.factories import create_user

from .models import DetalleOrden, Promocion
from .planilla_xlsx import TIPO_XLSX
from .repositorio_dashboard import DjangoVentasPeriodo
from .test_dashboard import crear_orden, el

SEMANA = resolver_periodo('PERSONALIZADO', el(7).date(), '2026-11-01', '2026-11-07')


def agregar_producto(orden, nombre, cantidad=1, precio=1000):
    return DetalleOrden.objects.create(
        orden=orden, producto_mongo_id=nombre.lower(), variante_sku=f'{nombre.upper()}-1',
        nombre_producto_snapshot=nombre, precio_unitario_snapshot=precio, cantidad=cantidad)


class DjangoVentasPeriodoTests(TestCase):
    """RF-03.1: la planilla trae las mismas ventas que cuenta el dashboard, con los datos de cada comprador."""

    def listar(self, periodo=SEMANA):
        return DjangoVentasPeriodo().listar(periodo)

    def test_solo_los_pedidos_pagados_del_periodo_del_mas_antiguo_al_mas_nuevo(self):
        tercero = crear_orden('ENTREGADO', pagada=el(5))
        primero = crear_orden('PAGADO', pagada=el(2))
        segundo = crear_orden('ENVIADO', pagada=el(3))
        crear_orden('PENDIENTE', creada=el(2))
        crear_orden('CANCELADO', creada=el(2))
        crear_orden('PAGADO', pagada=el(8))
        crear_orden('PAGADO', pagada=el(31, mes=10))

        ventas = self.listar()

        self.assertEqual([venta.numero for venta in ventas], [primero.id, segundo.id, tercero.id])
        self.assertEqual([venta.estado for venta in ventas],
                         [EstadoPedido.PAGADO, EstadoPedido.ENVIADO, EstadoPedido.ENTREGADO])

    def test_cuenta_por_la_fecha_del_pago_en_la_hora_de_la_tienda(self):
        # Transferencia creada en octubre y validada el 2 de noviembre a las 15:00 de Santiago
        crear_orden(metodo='TRANSFERENCIA', creada=el(31, mes=10), pagada=el(2, hora=15))

        venta, = self.listar()

        self.assertEqual(venta.fecha, datetime(2026, 11, 2, 15, 0))
        self.assertEqual(venta.medio_pago, 'Transferencia bancaria')

    def test_los_datos_de_un_comprador_registrado(self):
        ana = create_user('ana@example.test', nombre='Ana', apellido_paterno='Soto', apellido_materno='Rojas',
                          telefono='+56911111111')
        crear_orden(pagada=el(2), usuario=ana, nombre_destinatario='Luis Soto', telefono_destinatario='+56922222222')

        venta, = self.listar()

        self.assertEqual((venta.cliente, venta.correo, venta.telefono, venta.registrado),
                         ('Ana Soto Rojas', 'ana@example.test', '+56911111111', True))
        self.assertEqual((venta.destinatario, venta.telefono_destinatario), ('Luis Soto', '+56922222222'))

    def test_un_invitado_queda_con_el_nombre_y_el_telefono_de_quien_recibe(self):
        crear_orden(pagada=el(2), correo='beto@example.test', nombre_destinatario='Beto Paz',
                    telefono_destinatario='+56933333333')

        venta, = self.listar()

        self.assertEqual((venta.cliente, venta.correo, venta.telefono, venta.registrado),
                         ('Beto Paz', 'beto@example.test', '+56933333333', False))

    def test_la_direccion_del_despacho(self):
        orden = crear_orden(pagada=el(2), numero_seguimiento_tracking='OT123')
        orden.direccion_envio_snapshot = {'calle': 'Av. Siempre Viva', 'numero': 742, 'dpto_casa': 'Depto 3',
                                          'comuna': 'Ñuñoa'}
        orden.save(update_fields=['direccion_envio_snapshot'])

        venta, = self.listar()

        self.assertEqual((venta.entrega, venta.direccion, venta.comuna, venta.numero_seguimiento),
                         ('Chilexpress', 'Av. Siempre Viva 742, Depto 3', 'Ñuñoa', 'OT123'))

    def test_un_retiro_en_el_local_no_lleva_direccion(self):
        crear_orden(pagada=el(2), entrega='RETIRO_LOCAL', comuna='SANTIAGO')

        venta, = self.listar()

        self.assertEqual((venta.entrega, venta.direccion, venta.comuna, venta.numero_seguimiento),
                         ('Retiro en local', '', '', ''))

    def test_los_montos_y_el_cupon(self):
        cupon = Promocion.objects.create(codigo='BIENVENIDA', tipo_descuento='MONTO_FIJO', valor_descuento=2000)
        crear_orden(pagada=el(2), subtotal=20000, costo_envio=3000, total=21000, promocion=cupon)
        crear_orden(pagada=el(3))

        con_cupon, sin_cupon = self.listar()

        self.assertEqual((con_cupon.subtotal, con_cupon.costo_envio, con_cupon.total, con_cupon.cupon),
                         (20000, 3000, 21000, 'BIENVENIDA'))
        self.assertEqual(sin_cupon.cupon, '')

    def test_la_compra_como_empresa_y_el_folio(self):
        crear_orden(pagada=el(2), folio_documento='1520',
                    datos_empresa={'razon_social': 'Soto SpA', 'rut': '76123456-7', 'giro': 'Comercio'})
        crear_orden(pagada=el(3))

        empresa, persona = self.listar()

        self.assertEqual((empresa.razon_social, empresa.rut_empresa, empresa.giro, empresa.folio_documento),
                         ('Soto SpA', '76123456-7', 'Comercio', '1520'))
        self.assertEqual((persona.razon_social, persona.rut_empresa, persona.giro, persona.folio_documento),
                         ('', '', '', ''))

    def test_los_productos_de_cada_pedido(self):
        orden = crear_orden(pagada=el(2))
        agregar_producto(orden, 'Polera', cantidad=2, precio=8000)
        agregar_producto(orden, 'Gorro', precio=4000)
        crear_orden(pagada=el(3))

        con_productos, sin_productos = self.listar()

        self.assertEqual(con_productos.lineas,
                         (LineaVendida('Polera', 'POLERA-1', 2, 8000), LineaVendida('Gorro', 'GORRO-1', 1, 4000)))
        self.assertEqual(sin_productos.lineas, ())

    def test_no_hace_una_consulta_por_cada_pedido(self):
        for dia in (2, 3, 4):
            agregar_producto(crear_orden(pagada=el(dia), usuario=create_user(f'cliente{dia}@example.test')), 'Taza')

        # Los pedidos (con su comprador y su cupón) y sus productos
        with self.assertNumQueries(2):
            self.listar()


class DashboardExportarVentasTests(APITestCase):
    """RF-03.1: el dueño de la tienda descarga en Excel las ventas del periodo que eligió en el dashboard."""

    def setUp(self):
        self.client.force_authenticate(create_user('admin@example.test', rol='ADMIN'))

    def exportar(self, desde='2026-11-01', hasta='2026-11-07', **parametros):
        parametros = {'periodo': 'PERSONALIZADO', 'desde': desde, 'hasta': hasta, **parametros}
        response = self.client.get(reverse('dashboard_exportar'), parametros)
        self.assertEqual(response.status_code, 200)
        return response, load_workbook(BytesIO(response.content))

    def test_descarga_un_excel_con_el_nombre_del_periodo(self):
        response, libro = self.exportar()

        self.assertEqual(response['Content-Type'], TIPO_XLSX)
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="ventas_2026-11-01_a_2026-11-07.xlsx"')
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(libro.sheetnames, ['Ventas', 'Productos'])

    def test_las_hojas_traen_las_ventas_y_sus_productos(self):
        orden = crear_orden(pagada=el(2, hora=15), total=16000, correo='beto@example.test',
                            nombre_destinatario='Beto Paz')
        agregar_producto(orden, 'Polera', cantidad=2, precio=8000)
        crear_orden('PENDIENTE', creada=el(2))

        _, libro = self.exportar()
        ventas, productos = (list(libro[nombre].iter_rows(values_only=True)) for nombre in libro.sheetnames)

        self.assertEqual(ventas[0], COLUMNAS_VENTAS)
        self.assertEqual(len(ventas), 2)
        venta = dict(zip(*ventas))
        self.assertEqual((venta['N° pedido'], venta['Fecha de pago'], venta['Estado'], venta['Cliente'],
                          venta['Correo'], venta['Total']),
                         (orden.id, datetime(2026, 11, 2, 15, 0), 'Pagado', 'Beto Paz', 'beto@example.test', 16000))
        self.assertEqual(productos[0], COLUMNAS_PRODUCTOS)
        self.assertEqual(productos[1:], [(orden.id, datetime(2026, 11, 2, 15, 0), 'Beto Paz', 'beto@example.test',
                                          'Polera', 'POLERA-1', 2, 8000, 16000)])

    def test_el_total_coincide_con_las_ventas_del_dashboard(self):
        for dia, total in ((2, 12000), (5, 30000), (9, 99000)):
            crear_orden(pagada=el(dia), total=total)

        _, libro = self.exportar()
        totales = [fila[COLUMNAS_VENTAS.index('Total')] for fila in libro['Ventas'].iter_rows(min_row=2, values_only=True)]
        metricas = self.client.get(reverse('dashboard_metricas'),
                                   {'periodo': 'PERSONALIZADO', 'desde': '2026-11-01', 'hasta': '2026-11-07'}).data

        self.assertEqual(sum(totales), metricas['tarjetas']['ventas'])
        self.assertEqual(len(totales), metricas['tarjetas']['pedidos'])

    def test_un_texto_del_comprador_que_parece_formula_queda_como_texto(self):
        crear_orden(pagada=el(2), nombre_destinatario='=HYPERLINK("http://malo.example","Ver")')

        _, libro = self.exportar()
        celda = libro['Ventas'].cell(row=2, column=COLUMNAS_VENTAS.index('Cliente') + 1)

        self.assertEqual((celda.data_type, celda.value), ('s', '=HYPERLINK("http://malo.example","Ver")'))

    def test_sin_ventas_descarga_las_hojas_solo_con_sus_titulos(self):
        _, libro = self.exportar()

        self.assertEqual([libro[nombre].max_row for nombre in libro.sheetnames], [1, 1])

    def test_sin_periodo_es_este_mes(self):
        response = self.client.get(reverse('dashboard_exportar'))

        hoy = timezone.localdate()
        self.assertEqual(response['Content-Disposition'],
                         f'attachment; filename="ventas_{hoy.replace(day=1).isoformat()}_a_{hoy.isoformat()}.xlsx"')

    def test_un_periodo_invalido_responde_400(self):
        response = self.client.get(reverse('dashboard_exportar'), {'periodo': 'PERSONALIZADO', 'desde': '2026-11-05'})

        self.assertEqual(response.status_code, 400)
        self.assertIn('periodo', response.data)

    def test_solo_el_admin(self):
        crear_orden(pagada=el(2))
        self.client.force_authenticate(create_user('comprador@example.test'))
        self.assertEqual(self.client.get(reverse('dashboard_exportar')).status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(reverse('dashboard_exportar')).status_code, 401)
