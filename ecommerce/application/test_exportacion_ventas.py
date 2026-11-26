from datetime import date, datetime

from django.test import SimpleTestCase

from ecommerce.application.exportacion_ventas import (
    COLUMNAS_PRODUCTOS, COLUMNAS_VENTAS, ExportarVentas, LineaVendida, VentaPeriodo, VentasPeriodo,
)
from ecommerce.domain.dashboard import resolver_periodo
from ecommerce.domain.ventas import EstadoPedido

HOY = date(2026, 11, 17)
NOVIEMBRE = resolver_periodo('ESTE_MES', HOY)


class VentasFalsas(VentasPeriodo):
    def __init__(self, ventas=()):
        self.ventas = list(ventas)
        self.periodos = []

    def listar(self, periodo):
        self.periodos.append(periodo)
        return self.ventas


def venta(numero=10, **cambios):
    datos = dict(
        numero=numero, fecha=datetime(2026, 11, 3, 15, 30), estado=EstadoPedido.ENVIADO,
        cliente='Ana Soto', correo='ana@example.com', telefono='+56911111111', registrado=True,
        destinatario='Luis Soto', telefono_destinatario='+56922222222', entrega='Chilexpress',
        direccion='Av. Siempre Viva 742, Depto 3', comuna='Ñuñoa', numero_seguimiento='OT123',
        medio_pago='Transbank', subtotal=20000, costo_envio=3000, total=21000, cupon='BIENVENIDA',
        lineas=(LineaVendida('Polera', 'POL-M', 2, 8000), LineaVendida('Gorro', 'GOR-U', 1, 4000)),
    )
    datos.update(cambios)
    return VentaPeriodo(**datos)


def fila(hoja, indice=0):
    return dict(zip(hoja.columnas, hoja.filas[indice]))


class ExportarVentasTests(SimpleTestCase):
    def exportar(self, *ventas, periodo=NOVIEMBRE):
        self.repositorio = VentasFalsas(ventas)
        return ExportarVentas(self.repositorio).ejecutar(periodo)

    def test_pide_las_ventas_del_periodo_elegido(self):
        self.exportar()
        self.assertEqual(self.repositorio.periodos, [NOVIEMBRE])

    def test_tiene_la_hoja_de_ventas_y_la_de_productos(self):
        planilla = self.exportar(venta())
        ventas, productos = planilla.hojas
        self.assertEqual((ventas.nombre, ventas.columnas), ('Ventas', COLUMNAS_VENTAS))
        self.assertEqual((productos.nombre, productos.columnas), ('Productos', COLUMNAS_PRODUCTOS))

    def test_cada_fila_tiene_un_valor_por_columna(self):
        for hoja in self.exportar(venta()).hojas:
            for valores in hoja.filas:
                self.assertEqual(len(valores), len(hoja.columnas), hoja.nombre)

    def test_una_fila_por_pedido_con_los_datos_del_cliente(self):
        ventas = self.exportar(venta(10), venta(11)).hojas[0]
        self.assertEqual([valores[0] for valores in ventas.filas], [10, 11])
        datos = fila(ventas)
        self.assertEqual(datos['Fecha de pago'], datetime(2026, 11, 3, 15, 30))
        self.assertEqual(datos['Estado'], 'Despachado')
        self.assertEqual((datos['Cliente'], datos['Correo'], datos['Teléfono']),
                         ('Ana Soto', 'ana@example.com', '+56911111111'))
        self.assertEqual((datos['Recibe'], datos['Teléfono de quien recibe']), ('Luis Soto', '+56922222222'))
        self.assertEqual((datos['Entrega'], datos['Dirección'], datos['Comuna'], datos['N° de seguimiento']),
                         ('Chilexpress', 'Av. Siempre Viva 742, Depto 3', 'Ñuñoa', 'OT123'))
        self.assertEqual((datos['Medio de pago'], datos['Cupón']), ('Transbank', 'BIENVENIDA'))

    def test_los_montos_y_el_descuento(self):
        datos = fila(self.exportar(venta()).hojas[0])
        self.assertEqual((datos['Subtotal'], datos['Descuento'], datos['Envío'], datos['Total']),
                         (20000, 2000, 3000, 21000))

    def test_sin_rebaja_el_descuento_es_cero_y_nunca_negativo(self):
        ventas = self.exportar(venta(subtotal=20000, costo_envio=3000, total=23000),
                               venta(subtotal=20000, costo_envio=3000, total=23500)).hojas[0]
        self.assertEqual([fila(ventas, indice)['Descuento'] for indice in (0, 1)], [0, 0])

    def test_distingue_al_registrado_del_invitado(self):
        ventas = self.exportar(venta(registrado=True), venta(registrado=False)).hojas[0]
        self.assertEqual([fila(ventas, indice)['Tipo de cliente'] for indice in (0, 1)], ['Registrado', 'Invitado'])

    def test_la_compra_como_empresa_trae_sus_datos_y_el_folio(self):
        datos = fila(self.exportar(venta(razon_social='Soto SpA', rut_empresa='76123456-7', giro='Comercio',
                                         folio_documento='1520')).hojas[0])
        self.assertEqual((datos['Razón social'], datos['RUT empresa'], datos['Giro'], datos['Folio boleta o factura']),
                         ('Soto SpA', '76123456-7', 'Comercio', '1520'))

    def test_una_persona_deja_vacios_los_datos_de_empresa(self):
        datos = fila(self.exportar(venta()).hojas[0])
        self.assertEqual((datos['Razón social'], datos['RUT empresa'], datos['Giro']), ('', '', ''))

    def test_una_fila_por_producto_vendido_con_su_pedido(self):
        productos = self.exportar(venta(10), venta(11, lineas=(LineaVendida('Taza', 'TAZ-1', 3, 5000),))).hojas[1]
        self.assertEqual([(valores[0], valores[4]) for valores in productos.filas],
                         [(10, 'Polera'), (10, 'Gorro'), (11, 'Taza')])
        datos = fila(productos)
        self.assertEqual((datos['Cliente'], datos['Correo'], datos['SKU']), ('Ana Soto', 'ana@example.com', 'POL-M'))
        self.assertEqual((datos['Cantidad'], datos['Precio unitario'], datos['Total']), (2, 8000, 16000))

    def test_sin_ventas_quedan_las_dos_hojas_solo_con_sus_columnas(self):
        planilla = self.exportar()
        self.assertEqual([(hoja.nombre, hoja.filas) for hoja in planilla.hojas], [('Ventas', []), ('Productos', [])])

    def test_el_nombre_del_archivo_dice_el_periodo(self):
        self.assertEqual(self.exportar().nombre, 'ventas_2026-11-01_a_2026-11-17')

    def test_desde_el_inicio_el_nombre_solo_dice_hasta_cuando(self):
        planilla = self.exportar(periodo=resolver_periodo('DESDE_INICIO', HOY))
        self.assertEqual(planilla.nombre, 'ventas_hasta_2026-11-17')
