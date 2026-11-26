from datetime import datetime, timedelta
from decimal import Decimal

from django.test import SimpleTestCase

from ecommerce.application.ventas import (
    CambiarEstadoPedido, CancelarPagosVencidos, CatalogoVariantes, ConfirmarPago, InventarioVariantes,
    OrdenNoEncontrada,
    GenerarOrdenTransporte, NotificadorPedidos, PaqueteDelPedido, PedidoModificado, PrepararPedido, RepositorioOrdenes,
    RecordarPagosPorVencer, ResolverRevision,
    ResultadoPago, RevisarCarrito, SinRevisionPendiente, TransportistaOrdenes, MOTIVO_PAGO_VENCIDO,
    PagoFueraPlazoNoPermitido, RegistrarPagoFueraPlazo
)
from ecommerce.domain.logistica import EnvioSolicitado, ErrorOrdenTransporte, MedidasEnvio
from ecommerce.domain.ventas import (
    CantidadInvalida, EstadoPedido, EventoPedido, ItemSolicitado, OrdenRegistrada, OrdenTransporteNoPermitida,
    PedidoVacio, ProblemaLinea,
    StockInsuficiente, SubtotalDesactualizado, TransicionNoPermitida, VarianteCatalogo,
    VarianteNoDisponible, plazo_pago,
)


class CatalogoFalso(CatalogoVariantes):
    def __init__(self, variantes):
        self.variantes = variantes

    def obtener(self, producto_id, sku):
        return self.variantes.get((producto_id, sku))


CATALOGO = CatalogoFalso({
    ('camisa', 'CAMISA-S'): VarianteCatalogo('Camisa S', Decimal('20990.00'), 2, True),
    ('camisa', 'CAMISA-M'): VarianteCatalogo('Camisa M', Decimal('20990.00'), 0, True),
    ('gorro', 'GORRO-U'): VarianteCatalogo('Gorro', Decimal('5000.00'), 10, False),
})


def preparar(items, subtotal):
    return PrepararPedido(CATALOGO).ejecutar(
        [ItemSolicitado(*item) for item in items], Decimal(subtotal))


class PrepararPedidoTests(SimpleTestCase):
    def test_usa_nombre_y_precio_del_catalogo(self):
        pedido = preparar([('camisa', 'CAMISA-S', 2)], '41980')
        linea, = pedido.lineas
        self.assertEqual(linea.nombre, 'Camisa S')
        self.assertEqual(linea.precio_unitario, Decimal('20990.00'))
        self.assertEqual(pedido.subtotal, Decimal('41980'))

    def test_variante_sin_stock_se_rechaza_aunque_otra_del_mismo_producto_tenga(self):
        with self.assertRaises(StockInsuficiente) as error:
            preparar([('camisa', 'CAMISA-M', 1)], '20990')
        self.assertEqual(error.exception.disponible, 0)
        self.assertEqual(len(preparar([('camisa', 'CAMISA-S', 1)], '20990').lineas), 1)

    def test_cantidad_mayor_al_stock_se_rechaza(self):
        with self.assertRaises(StockInsuficiente) as error:
            preparar([('camisa', 'CAMISA-S', 3)], '62970')
        self.assertEqual(error.exception.disponible, 2)

    def test_lineas_repetidas_del_mismo_sku_suman_contra_el_stock(self):
        with self.assertRaises(StockInsuficiente):
            preparar([('camisa', 'CAMISA-S', 2), ('camisa', 'CAMISA-S', 1)], '62970')

    def test_variante_inexistente_o_producto_no_publicado_no_se_vende(self):
        for item in (('camisa', 'NO-EXISTE', 1), ('gorro', 'GORRO-U', 1)):
            with self.subTest(item=item), self.assertRaises(VarianteNoDisponible):
                preparar([item], '5000')

    def test_subtotal_distinto_al_vigente_se_rechaza(self):
        with self.assertRaises(SubtotalDesactualizado) as error:
            preparar([('camisa', 'CAMISA-S', 1)], '1')
        self.assertEqual(error.exception.subtotal_vigente, Decimal('20990.00'))
        self.assertEqual(error.exception.lineas[0].precio_unitario, Decimal('20990.00'))

    def test_carrito_vacio_o_cantidad_cero_se_rechaza(self):
        with self.assertRaises(PedidoVacio):
            preparar([], '0')
        with self.assertRaises(CantidadInvalida):
            preparar([('camisa', 'CAMISA-S', 0)], '0')


def revisar(items):
    return RevisarCarrito(CATALOGO).ejecutar([ItemSolicitado(*item) for item in items])


class PaqueteDelPedidoTests(SimpleTestCase):
    """RF-02.3: el paquete del envío sale de las medidas del catálogo, no del navegador."""

    def test_usa_las_medidas_de_cada_variante_y_junta_las_lineas_del_mismo_sku(self):
        catalogo = CatalogoFalso({
            ('camisa', 'CAMISA-S'): VarianteCatalogo(
                'Camisa S', Decimal('20990'), 5, True, MedidasEnvio(Decimal('0.4'), Decimal('3'), Decimal('30'), Decimal('40'))),
        })
        paquete = PaqueteDelPedido(catalogo).ejecutar(
            [ItemSolicitado('camisa', 'CAMISA-S', 1), ItemSolicitado('camisa', 'CAMISA-S', 2)])
        self.assertEqual((paquete.peso_kg, paquete.alto_cm), (Decimal('1.20'), Decimal('40')))

    def test_rechaza_un_carrito_vacio_o_una_variante_que_no_esta_disponible(self):
        with self.assertRaises(PedidoVacio):
            PaqueteDelPedido(CATALOGO).ejecutar([])
        for producto, sku in (('gorro', 'GORRO-U'), ('camisa', 'NO-EXISTE')):
            with self.subTest(sku=sku), self.assertRaises(VarianteNoDisponible):
                PaqueteDelPedido(CATALOGO).ejecutar([ItemSolicitado(producto, sku, 1)])


class RevisarCarritoTests(SimpleTestCase):
    def test_linea_con_stock_suficiente_no_tiene_problema(self):
        linea, = revisar([('camisa', 'CAMISA-S', 2)])
        self.assertIsNone(linea.problema)
        self.assertIsNone(linea.mensaje)
        self.assertEqual(linea.disponible, 2)
        self.assertEqual(linea.precio, Decimal('20990.00'))

    def test_variante_agotada_aunque_otra_del_mismo_producto_tenga_stock(self):
        agotada, con_stock = revisar([('camisa', 'CAMISA-M', 1), ('camisa', 'CAMISA-S', 1)])
        self.assertEqual(agotada.problema, ProblemaLinea.SIN_STOCK)
        self.assertEqual(agotada.disponible, 0)
        self.assertIsNone(con_stock.problema)

    def test_cantidad_mayor_al_stock_informa_lo_disponible(self):
        linea, = revisar([('camisa', 'CAMISA-S', 3)])
        self.assertEqual(linea.problema, ProblemaLinea.STOCK_INSUFICIENTE)
        self.assertEqual(linea.disponible, 2)
        self.assertIn('solo quedan 2', linea.mensaje)

    def test_lineas_repetidas_del_mismo_sku_suman_contra_el_stock(self):
        linea, = revisar([('camisa', 'CAMISA-S', 2), ('camisa', 'CAMISA-S', 1)])
        self.assertEqual(linea.cantidad, 3)
        self.assertEqual(linea.problema, ProblemaLinea.STOCK_INSUFICIENTE)

    def test_variante_inexistente_o_producto_no_publicado_no_esta_disponible(self):
        for item in (('camisa', 'NO-EXISTE', 1), ('gorro', 'GORRO-U', 1)):
            with self.subTest(item=item):
                linea, = revisar([item])
                self.assertEqual(linea.problema, ProblemaLinea.NO_DISPONIBLE)
                self.assertEqual(linea.disponible, 0)
                # No se revelan precio ni nombre de lo que no está a la venta
                self.assertIsNone(linea.precio)


class InventarioFalso(InventarioVariantes):
    def __init__(self, stock):
        self.stock = dict(stock)
        self.falla_en = None
        self.error = ConnectionError('inventario no disponible')

    def descontar(self, producto_id, sku, cantidad):
        if (producto_id, sku) == self.falla_en:
            raise self.error
        if self.stock.get((producto_id, sku), 0) < cantidad:
            return False
        self.stock[(producto_id, sku)] -= cantidad
        return True

    def reponer(self, producto_id, sku, cantidad):
        self.stock[(producto_id, sku)] += cantidad


class RepositorioOrdenesFalso(RepositorioOrdenes):
    def __init__(self):
        self.ordenes = {}
        # Simula que otro proceso cambia la orden entre la lectura y la escritura
        self.cambio_concurrente = None

    def agregar(self, orden_id, estado, items, stock_descontado=False, proveedor='RETIRO_LOCAL',
                metodo_pago='TRANSBANK', creada=datetime(2026, 10, 1, 12, 0), plazo=timedelta(hours=48),
                motivo_cancelacion=''):
        self.ordenes[orden_id] = {
            'estado': EstadoPedido(estado), 'items': tuple(ItemSolicitado(*i) for i in items),
            'stock_descontado': stock_descontado, 'motivo_revision': '', 'motivo_cancelacion': motivo_cancelacion,
            'requiere_revision': False, 'proveedor': proveedor, 'numero_ot': '', 'error_ot': '',
            'metodo_pago': metodo_pago, 'plazo': plazo_pago(creada, plazo), 'recordatorio_pago': False,
        }
        return self.ordenes[orden_id]

    def _pendientes(self, metodo_pago):
        return [(orden_id, datos) for orden_id, datos in self.ordenes.items()
                if datos['estado'] == EstadoPedido.PENDIENTE and datos['metodo_pago'] == metodo_pago]

    def pagos_vencidos(self, metodo_pago, ahora):
        return [orden_id for orden_id, datos in self._pendientes(metodo_pago) if datos['plazo'].vence < ahora]

    def pagos_por_recordar(self, metodo_pago, ahora):
        return [orden_id for orden_id, datos in self._pendientes(metodo_pago)
                if datos['plazo'].recordar < ahora and not datos['recordatorio_pago']]

    def marcar_recordatorio_pago(self, orden_id):
        datos = self.ordenes[orden_id]
        if self.cambio_concurrente:
            datos['estado'], self.cambio_concurrente = self.cambio_concurrente, None
        if datos['estado'] != EstadoPedido.PENDIENTE or datos['recordatorio_pago']:
            return False
        datos['recordatorio_pago'] = True
        return True

    def obtener_envio(self, orden_id):
        datos = self.ordenes.get(orden_id)
        return datos and EnvioSolicitado(
            orden_id=orden_id, proveedor=datos['proveedor'], comuna='Santiago', calle='Uno', numero='1',
            complemento='', destinatario='Cliente', email='c@example.test', valor_declarado=1000,
            numero_ot=datos['numero_ot'])

    def registrar_orden_transporte(self, orden_id, numero_ot='', error=''):
        if numero_ot:
            self.ordenes[orden_id].update(numero_ot=numero_ot, error_ot='')
        else:
            self.ordenes[orden_id]['error_ot'] = error

    def obtener(self, orden_id):
        datos = self.ordenes.get(orden_id)
        return datos and OrdenRegistrada(orden_id, datos['estado'], datos['items'],
                                         datos['stock_descontado'], datos['requiere_revision'],
                                         motivo_cancelacion=datos['motivo_cancelacion'])

    def cambiar_estado(self, orden_id, desde, hacia, motivo_cancelacion='', motivo_revision=''):
        datos = self.ordenes[orden_id]
        if self.cambio_concurrente:
            datos['estado'], self.cambio_concurrente = self.cambio_concurrente, None
        if datos['estado'] != desde:
            return False
        datos['estado'] = EstadoPedido(hacia)
        if motivo_cancelacion:
            datos['motivo_cancelacion'] = motivo_cancelacion
        if motivo_revision:
            datos.update(requiere_revision=True, motivo_revision=motivo_revision)
        return True

    def registrar_stock_descontado(self, orden_id, descontado=True):
        self.ordenes[orden_id]['stock_descontado'] = descontado

    def completar_pago(self, orden_id):
        self.ordenes[orden_id].update(stock_descontado=True, requiere_revision=False, motivo_revision='')

    def marcar_revision(self, orden_id, motivo):
        self.ordenes[orden_id].update(requiere_revision=True, motivo_revision=motivo)

    def resolver_revision(self, orden_id):
        if not self.ordenes[orden_id]['requiere_revision']:
            return False
        self.ordenes[orden_id]['requiere_revision'] = False
        return True


class TransportistaFalso(TransportistaOrdenes):
    def __init__(self):
        self.envios = []
        self.error = None

    def generar_orden_transporte(self, envio):
        if self.error:
            raise self.error
        self.envios.append(envio)
        return f'OT-{len(self.envios)}'


class GenerarOrdenTransporteTests(SimpleTestCase):
    def setUp(self):
        self.ordenes = RepositorioOrdenesFalso()
        self.transportista = TransportistaFalso()
        self.caso = GenerarOrdenTransporte(self.ordenes, self.transportista)
        self.orden = self.ordenes.agregar(1, 'PAGADO', [], proveedor='CHILEXPRESS')

    def test_genera_y_guarda_la_ot(self):
        self.assertEqual(self.caso.ejecutar(1), 'OT-1')
        self.assertEqual(self.orden['numero_ot'], 'OT-1')

    def test_no_genera_otra_si_la_orden_ya_tiene_ot(self):
        self.caso.ejecutar(1)
        self.assertEqual(self.caso.ejecutar(1), 'OT-1')
        self.assertEqual(len(self.transportista.envios), 1)

    def test_retiro_en_local_no_genera_ot(self):
        self.ordenes.agregar(2, 'PAGADO', [], proveedor='RETIRO_LOCAL')
        self.assertIsNone(self.caso.ejecutar(2))
        self.assertEqual(self.transportista.envios, [])

    def test_fallo_del_transportista_queda_registrado_sin_lanzar(self):
        self.transportista.error = ErrorOrdenTransporte('Sin cobertura')
        self.assertIsNone(self.caso.ejecutar(1))
        self.assertEqual((self.orden['numero_ot'], self.orden['error_ot']), ('', 'Sin cobertura'))

    def test_error_inesperado_tambien_queda_registrado(self):
        self.transportista.error = ValueError('respuesta inesperada')
        with self.assertLogs('ecommerce.application.ventas', level='ERROR'):
            self.assertIsNone(self.caso.ejecutar(1))
        self.assertEqual(self.orden['error_ot'], 'Error inesperado al generar la orden de transporte')

    def test_reintento_exitoso_limpia_el_error(self):
        self.transportista.error = ErrorOrdenTransporte('Sin cobertura')
        self.caso.ejecutar(1)
        self.transportista.error = None
        self.assertEqual(self.caso.reintentar(1), 'OT-1')
        self.assertEqual(self.orden['error_ot'], '')

    def test_reintento_fallido_informa_y_guarda_el_error(self):
        self.transportista.error = ErrorOrdenTransporte('Sin cobertura')
        with self.assertRaisesMessage(ErrorOrdenTransporte, 'Sin cobertura'):
            self.caso.reintentar(1)
        self.assertEqual(self.orden['error_ot'], 'Sin cobertura')

    def test_reintento_solo_en_pedidos_que_admiten_ot(self):
        with self.assertRaises(OrdenNoEncontrada):
            self.caso.reintentar(99)
        self.orden['requiere_revision'] = True
        with self.assertRaises(OrdenTransporteNoPermitida):
            self.caso.reintentar(1)
        self.ordenes.agregar(2, 'CANCELADO', [], proveedor='CHILEXPRESS')
        self.ordenes.agregar(3, 'PAGADO', [], proveedor='RETIRO_LOCAL')
        for orden_id in (2, 3):
            with self.subTest(orden_id=orden_id), self.assertRaises(OrdenTransporteNoPermitida):
                self.caso.reintentar(orden_id)
        self.assertEqual(self.transportista.envios, [])


class ConfirmarPagoTests(SimpleTestCase):
    def setUp(self):
        self.ordenes = RepositorioOrdenesFalso()
        self.inventario = InventarioFalso({('camisa', 'CAMISA-S'): 2, ('gorro', 'GORRO-U'): 1})
        self.caso = ConfirmarPago(self.ordenes, self.inventario)
        self.orden = self.ordenes.agregar(1, 'PENDIENTE', [('camisa', 'CAMISA-S', 2),
                                                          ('gorro', 'GORRO-U', 1)])

    def test_pago_aprobado_descuenta_todas_las_lineas(self):
        self.assertEqual(self.caso.aprobar(1), ResultadoPago.PAGADO)
        self.assertEqual(self.orden['estado'], EstadoPedido.PAGADO)
        self.assertTrue(self.orden['stock_descontado'])
        # La marca provisional se quita al terminar
        self.assertFalse(self.orden['requiere_revision'])
        self.assertEqual(self.orden['motivo_revision'], '')
        self.assertEqual(self.inventario.stock, {('camisa', 'CAMISA-S'): 0, ('gorro', 'GORRO-U'): 0})

    def test_solo_el_primer_pago_con_stock_genera_la_ot(self):
        transportista = TransportistaFalso()
        caso = ConfirmarPago(self.ordenes, self.inventario,
                             GenerarOrdenTransporte(self.ordenes, transportista))
        self.orden['proveedor'] = 'CHILEXPRESS'
        sin_stock = self.ordenes.agregar(2, 'PENDIENTE', [('gorro', 'GORRO-U', 5)], proveedor='CHILEXPRESS')

        self.assertEqual(caso.aprobar(1), ResultadoPago.PAGADO)
        self.assertEqual(caso.aprobar(1), ResultadoPago.REPETIDO)
        self.assertEqual(caso.aprobar(2), ResultadoPago.EN_REVISION)
        self.assertEqual([envio.orden_id for envio in transportista.envios], [1])
        self.assertEqual((self.orden['numero_ot'], sin_stock['numero_ot']), ('OT-1', ''))

    def test_si_el_proceso_cae_al_descontar_la_orden_queda_pagada_y_en_revision(self):
        # Una caída del proceso no pasa por los except: solo queda lo que ya se escribió
        class ProcesoInterrumpido(BaseException):
            pass

        self.inventario.falla_en = ('gorro', 'GORRO-U')
        self.inventario.error = ProcesoInterrumpido()
        with self.assertRaises(ProcesoInterrumpido):
            self.caso.aprobar(1)
        self.assertEqual(self.orden['estado'], EstadoPedido.PAGADO)
        self.assertTrue(self.orden['requiere_revision'])
        self.assertIn('la confirmación del stock no terminó', self.orden['motivo_revision'])
        self.assertFalse(self.orden['stock_descontado'])

    def test_confirmacion_repetida_no_descuenta_otra_vez(self):
        self.caso.aprobar(1)
        self.inventario.stock = {('camisa', 'CAMISA-S'): 5, ('gorro', 'GORRO-U'): 5}
        for estado in ('PAGADO', 'EN_PREPARACION', 'ENVIADO', 'ENTREGADO'):
            with self.subTest(estado=estado):
                self.orden['estado'] = EstadoPedido(estado)
                self.assertEqual(self.caso.aprobar(1), ResultadoPago.REPETIDO)
        self.assertEqual(self.inventario.stock, {('camisa', 'CAMISA-S'): 5, ('gorro', 'GORRO-U'): 5})

    def test_sin_stock_en_una_linea_repone_las_demas_y_va_a_revision(self):
        self.inventario.stock[('gorro', 'GORRO-U')] = 0
        self.assertEqual(self.caso.aprobar(1), ResultadoPago.EN_REVISION)
        self.assertEqual(self.orden['estado'], EstadoPedido.PAGADO)
        self.assertFalse(self.orden['stock_descontado'])
        self.assertEqual(self.orden['motivo_revision'], 'Pago confirmado sin stock para GORRO-U')
        self.assertEqual(self.inventario.stock, {('camisa', 'CAMISA-S'): 2, ('gorro', 'GORRO-U'): 0})

    def test_al_pagar_se_avisa_una_sola_vez_aunque_falte_stock_y_no_sobre_una_cancelada(self):
        # Ej. una suscripción avanza al ciclo siguiente cuando se paga el pedido del ciclo
        avisados = []
        caso = ConfirmarPago(self.ordenes, self.inventario, al_pagar=avisados.append)
        sin_stock = self.ordenes.agregar(2, 'PENDIENTE', [('gorro', 'GORRO-U', 5)])
        cancelada = self.ordenes.agregar(3, 'CANCELADO', [('gorro', 'GORRO-U', 1)])
        self.assertEqual(caso.aprobar(1), ResultadoPago.PAGADO)
        self.assertEqual(caso.aprobar(1), ResultadoPago.REPETIDO)
        self.assertEqual(caso.aprobar(2), ResultadoPago.EN_REVISION)
        self.assertEqual(caso.aprobar(3), ResultadoPago.EN_REVISION)
        self.assertEqual(avisados, [1, 2])
        self.assertEqual((sin_stock['estado'], cancelada['estado']), (EstadoPedido.PAGADO, EstadoPedido.CANCELADO))

    def test_pago_aprobado_sobre_orden_cancelada_va_a_revision_sin_tocar_stock(self):
        self.orden['estado'] = EstadoPedido.CANCELADO
        self.assertEqual(self.caso.aprobar(1), ResultadoPago.EN_REVISION)
        self.assertEqual(self.orden['estado'], EstadoPedido.CANCELADO)
        self.assertEqual(self.orden['motivo_revision'], 'Pago aprobado sobre una orden en estado Cancelado')
        self.assertEqual(self.inventario.stock, {('camisa', 'CAMISA-S'): 2, ('gorro', 'GORRO-U'): 1})

    def test_error_del_inventario_repone_lo_descontado_y_va_a_revision(self):
        self.inventario.falla_en = ('gorro', 'GORRO-U')
        with self.assertRaises(ConnectionError):
            self.caso.aprobar(1)
        self.assertEqual(self.inventario.stock[('camisa', 'CAMISA-S')], 2)
        self.assertEqual(self.orden['motivo_revision'], 'No se pudo descontar el stock')
        self.assertFalse(self.orden['stock_descontado'])

    def test_orden_inexistente(self):
        self.assertEqual(self.caso.aprobar(99), ResultadoPago.NO_ENCONTRADA)
        self.assertFalse(self.caso.rechazar(99, 'Pago rechazado'))

    def test_rechazo_cancela_solo_ordenes_pendientes(self):
        self.assertTrue(self.caso.rechazar(1, 'Pago rechazado'))
        self.assertEqual(self.orden['estado'], EstadoPedido.CANCELADO)
        self.assertEqual(self.orden['motivo_cancelacion'], 'Pago rechazado')

        pagada = self.ordenes.agregar(2, 'PAGADO', [])
        self.assertFalse(self.caso.rechazar(2, 'Pago rechazado'))
        self.assertEqual(pagada['estado'], EstadoPedido.PAGADO)


class NotificadorFalso(NotificadorPedidos):
    def __init__(self):
        self.enviados = []

    def notificar(self, orden_id, evento):
        self.enviados.append((orden_id, evento))


class ConfirmarPagoNotificacionesTests(SimpleTestCase):
    """RF-04.2: cada resultado del pago avisa al comprador una sola vez."""

    def setUp(self):
        self.ordenes = RepositorioOrdenesFalso()
        self.inventario = InventarioFalso({('camisa', 'CAMISA-S'): 2})
        self.notificador = NotificadorFalso()
        self.caso = ConfirmarPago(self.ordenes, self.inventario, notificador=self.notificador)
        self.ordenes.agregar(1, 'PENDIENTE', [('camisa', 'CAMISA-S', 1)])

    def test_pago_aprobado_avisa_una_sola_vez_aunque_la_confirmacion_se_repita(self):
        self.caso.aprobar(1)
        self.caso.aprobar(1)
        self.assertEqual(self.notificador.enviados, [(1, EventoPedido.PAGO_APROBADO)])

    def test_pago_sin_stock_o_sobre_orden_cancelada_avisa_revision(self):
        self.ordenes.agregar(2, 'PENDIENTE', [('camisa', 'CAMISA-S', 5)])
        self.ordenes.agregar(3, 'CANCELADO', [('camisa', 'CAMISA-S', 1)])
        self.caso.aprobar(2)
        self.caso.aprobar(3)
        self.assertEqual(self.notificador.enviados,
                         [(2, EventoPedido.PAGO_EN_REVISION), (3, EventoPedido.PAGO_EN_REVISION)])

    def test_error_del_inventario_avisa_revision(self):
        self.inventario.falla_en = ('camisa', 'CAMISA-S')
        with self.assertRaises(ConnectionError):
            self.caso.aprobar(1)
        self.assertEqual(self.notificador.enviados, [(1, EventoPedido.PAGO_EN_REVISION)])

    def test_rechazo_y_anulacion_avisan_distinto(self):
        self.ordenes.agregar(2, 'PENDIENTE', [])
        self.caso.rechazar(1, 'Pago rechazado')
        self.caso.rechazar(2, 'Pago anulado por el comprador')
        self.assertEqual(self.notificador.enviados,
                         [(1, EventoPedido.PAGO_RECHAZADO), (2, EventoPedido.CANCELADO)])

    def test_rechazo_de_una_orden_que_ya_no_esta_pendiente_no_avisa(self):
        self.caso.aprobar(1)
        self.notificador.enviados.clear()
        self.assertFalse(self.caso.rechazar(1, 'Pago rechazado'))
        self.assertEqual(self.notificador.enviados, [])


class CambiarEstadoPedidoNotificacionesTests(SimpleTestCase):
    """RF-04.2: cada cambio del admin que se aplica avisa al comprador."""

    def setUp(self):
        self.ordenes = RepositorioOrdenesFalso()
        self.notificador = NotificadorFalso()
        self.caso = CambiarEstadoPedido(self.ordenes, InventarioFalso({('camisa', 'CAMISA-S'): 5}),
                                        notificador=self.notificador)
        self.orden = self.ordenes.agregar(1, 'PENDIENTE', [('camisa', 'CAMISA-S', 1)])

    def test_flujo_completo_avisa_cada_hito(self):
        for estado in ('PAGADO', 'EN_PREPARACION', 'ENVIADO', 'ENTREGADO'):
            self.caso.ejecutar(1, estado)
        self.assertEqual([evento for _, evento in self.notificador.enviados], [
            EventoPedido.PAGO_APROBADO, EventoPedido.EN_PREPARACION, EventoPedido.DESPACHADO,
            EventoPedido.ENTREGADO])

    def test_cancelacion_del_admin_avisa(self):
        self.caso.ejecutar(1, 'CANCELADO')
        self.assertEqual(self.notificador.enviados, [(1, EventoPedido.CANCELADO)])

    def test_cambio_rechazado_no_avisa(self):
        with self.assertRaises(TransicionNoPermitida):
            self.caso.ejecutar(1, 'ENVIADO')
        self.ordenes.cambio_concurrente = EstadoPedido.CANCELADO
        self.orden['estado'] = EstadoPedido.PAGADO
        with self.assertRaises(PedidoModificado):
            self.caso.ejecutar(1, 'EN_PREPARACION')
        self.assertEqual(self.notificador.enviados, [])


class CambiarEstadoPedidoTests(SimpleTestCase):
    def setUp(self):
        self.ordenes = RepositorioOrdenesFalso()
        self.inventario = InventarioFalso({('camisa', 'CAMISA-S'): 5})
        self.caso = CambiarEstadoPedido(self.ordenes, self.inventario)

    def orden(self, estado, stock_descontado=False):
        return self.ordenes.agregar(1, estado, [('camisa', 'CAMISA-S', 2)], stock_descontado)

    def stock(self):
        return self.inventario.stock[('camisa', 'CAMISA-S')]

    def test_avance_normal_no_toca_el_stock(self):
        orden = self.orden('PAGADO', stock_descontado=True)
        self.assertEqual(self.caso.ejecutar(1, 'EN_PREPARACION'), EstadoPedido.EN_PREPARACION)
        self.assertEqual(orden['estado'], EstadoPedido.EN_PREPARACION)
        self.assertEqual(self.stock(), 5)

    def test_transicion_no_permitida_no_cambia_nada(self):
        orden = self.orden('CANCELADO')
        with self.assertRaises(TransicionNoPermitida):
            self.caso.ejecutar(1, 'PAGADO')
        self.assertEqual(orden['estado'], EstadoPedido.CANCELADO)
        self.assertEqual(self.stock(), 5)

    def test_pagar_a_mano_descuenta_stock_como_un_pago_en_linea(self):
        orden = self.orden('PENDIENTE')
        self.assertEqual(self.caso.ejecutar(1, 'PAGADO'), EstadoPedido.PAGADO)
        self.assertEqual(orden['estado'], EstadoPedido.PAGADO)
        self.assertTrue(orden['stock_descontado'])
        self.assertEqual(self.stock(), 3)

    def test_transferencia_validada_genera_la_ot_como_un_pago_en_linea(self):
        transportista = TransportistaFalso()
        caso = CambiarEstadoPedido(self.ordenes, self.inventario,
                                   GenerarOrdenTransporte(self.ordenes, transportista))
        orden = self.orden('PENDIENTE')
        orden['proveedor'] = 'CHILEXPRESS'
        caso.ejecutar(1, 'PAGADO')
        self.assertEqual(orden['numero_ot'], 'OT-1')

    def test_pagar_a_mano_sin_stock_deja_la_orden_en_revision(self):
        self.inventario.stock[('camisa', 'CAMISA-S')] = 1
        orden = self.orden('PENDIENTE')
        self.caso.ejecutar(1, 'PAGADO')
        self.assertEqual(orden['estado'], EstadoPedido.PAGADO)
        self.assertEqual(orden['motivo_revision'], 'Pago confirmado sin stock para CAMISA-S')
        self.assertEqual(self.stock(), 1)

    def test_cancelar_repone_el_stock_descontado(self):
        for estado in ('PAGADO', 'EN_PREPARACION'):
            with self.subTest(estado=estado):
                self.inventario.stock[('camisa', 'CAMISA-S')] = 3
                orden = self.orden(estado, stock_descontado=True)
                self.caso.ejecutar(1, 'CANCELADO')
                self.assertEqual(orden['estado'], EstadoPedido.CANCELADO)
                self.assertEqual(orden['motivo_cancelacion'], 'Cancelado por el administrador')
                self.assertFalse(orden['stock_descontado'])
                self.assertEqual(self.stock(), 5)

    def test_cancelar_sin_stock_descontado_no_repone(self):
        # PENDIENTE, o PAGADO en revisión porque faltó stock al confirmar
        for estado in ('PENDIENTE', 'PAGADO'):
            with self.subTest(estado=estado):
                self.orden(estado, stock_descontado=False)
                self.caso.ejecutar(1, 'CANCELADO')
                self.assertEqual(self.stock(), 5)

    def test_cambio_concurrente_se_rechaza_sin_reponer_dos_veces(self):
        orden = self.orden('PAGADO', stock_descontado=True)
        self.ordenes.cambio_concurrente = EstadoPedido.CANCELADO
        with self.assertRaises(PedidoModificado):
            self.caso.ejecutar(1, 'CANCELADO')
        self.assertEqual(self.stock(), 5)
        self.assertTrue(orden['stock_descontado'])

    def test_orden_inexistente(self):
        with self.assertRaises(OrdenNoEncontrada):
            self.caso.ejecutar(99, 'CANCELADO')


class CancelarPagosVencidosTests(SimpleTestCase):
    """Plazo de pago: una transferencia no pagada en 48 h se cancela y se avisa al comprador."""

    AHORA = datetime(2026, 10, 14, 12, 0)

    def setUp(self):
        self.ordenes = RepositorioOrdenesFalso()
        self.notificador = NotificadorFalso()
        self.caso = CancelarPagosVencidos(self.ordenes, self.notificador)

    def agregar(self, orden_id, horas, estado='PENDIENTE', metodo_pago='TRANSFERENCIA', plazo=48):
        return self.ordenes.agregar(orden_id, estado, [], metodo_pago=metodo_pago,
                                    creada=self.AHORA - timedelta(hours=horas), plazo=timedelta(hours=plazo))

    def test_cada_orden_vence_con_el_plazo_que_tenia_la_tienda_al_crearla(self):
        self.agregar(1, 13, plazo=12)
        self.agregar(2, 13, plazo=24)
        self.agregar(3, 71, plazo=72)
        self.agregar(4, 73, plazo=72)

        self.assertEqual(self.caso.ejecutar(self.AHORA), [1, 4])

    def test_cancela_y_avisa_solo_las_transferencias_pendientes_con_mas_de_48_horas(self):
        vencida = self.agregar(1, 49)
        a_tiempo = self.agregar(2, 47)
        webpay = self.agregar(3, 72, metodo_pago='TRANSBANK')
        pagada = self.agregar(4, 72, estado='PAGADO')

        self.assertEqual(self.caso.ejecutar(self.AHORA), [1])

        self.assertEqual((vencida['estado'], vencida['motivo_cancelacion']),
                         (EstadoPedido.CANCELADO, 'Pago no recibido a tiempo'))
        for orden in (a_tiempo, webpay):
            self.assertEqual(orden['estado'], EstadoPedido.PENDIENTE)
        self.assertEqual(pagada['estado'], EstadoPedido.PAGADO)
        self.assertEqual(self.notificador.enviados, [(1, EventoPedido.CANCELADO)])

    def test_no_cancela_una_orden_que_el_admin_valido_mientras_tanto(self):
        self.agregar(1, 49)
        self.ordenes.cambio_concurrente = EstadoPedido.PAGADO
        self.assertEqual(self.caso.ejecutar(self.AHORA), [])
        self.assertEqual(self.ordenes.ordenes[1]['estado'], EstadoPedido.PAGADO)
        self.assertEqual(self.notificador.enviados, [])

    def test_volver_a_ejecutar_no_repite_cancelaciones_ni_correos(self):
        self.agregar(1, 49)
        self.caso.ejecutar(self.AHORA)
        self.assertEqual(self.caso.ejecutar(self.AHORA), [])
        self.assertEqual(len(self.notificador.enviados), 1)


class RecordarPagosPorVencerTests(SimpleTestCase):
    """Plazo de pago: a las 24 h sin pagar se le recuerda al comprador la transferencia, una sola vez."""

    AHORA = datetime(2026, 10, 14, 12, 0)

    def setUp(self):
        self.ordenes = RepositorioOrdenesFalso()
        self.notificador = NotificadorFalso()
        self.caso = RecordarPagosPorVencer(self.ordenes, self.notificador)

    def agregar(self, orden_id, horas, estado='PENDIENTE', metodo_pago='TRANSFERENCIA', plazo=48):
        return self.ordenes.agregar(orden_id, estado, [], metodo_pago=metodo_pago,
                                    creada=self.AHORA - timedelta(hours=horas), plazo=timedelta(hours=plazo))

    def test_recuerda_a_la_mitad_del_plazo_de_cada_orden(self):
        self.agregar(1, 7, plazo=12)
        self.agregar(2, 5, plazo=12)
        self.agregar(3, 37, plazo=72)
        self.agregar(4, 35, plazo=72)

        self.assertEqual(self.caso.ejecutar(self.AHORA), [1, 3])

    def test_recuerda_solo_las_transferencias_pendientes_con_mas_de_24_horas(self):
        por_vencer = self.agregar(1, 25)
        reciente = self.agregar(2, 23)
        self.agregar(3, 30, metodo_pago='TRANSBANK')
        self.agregar(4, 30, estado='PAGADO')

        self.assertEqual(self.caso.ejecutar(self.AHORA), [1])

        self.assertTrue(por_vencer['recordatorio_pago'])
        self.assertFalse(reciente['recordatorio_pago'])
        # El recordatorio no cambia el estado: la orden sigue esperando el pago
        self.assertEqual(por_vencer['estado'], EstadoPedido.PENDIENTE)
        self.assertEqual(self.notificador.enviados, [(1, EventoPedido.RECORDATORIO_PAGO)])

    def test_volver_a_ejecutar_no_repite_el_recordatorio(self):
        self.agregar(1, 25)
        self.caso.ejecutar(self.AHORA)
        self.assertEqual(self.caso.ejecutar(self.AHORA + timedelta(hours=1)), [])
        self.assertEqual(len(self.notificador.enviados), 1)

    def test_no_recuerda_una_orden_que_el_admin_valido_mientras_tanto(self):
        self.agregar(1, 25)
        self.ordenes.cambio_concurrente = EstadoPedido.PAGADO
        self.assertEqual(self.caso.ejecutar(self.AHORA), [])
        self.assertEqual(self.notificador.enviados, [])


class ResolverRevisionTests(SimpleTestCase):
    def setUp(self):
        self.ordenes = RepositorioOrdenesFalso()
        self.caso = ResolverRevision(self.ordenes)

    def test_quita_la_marca_y_conserva_el_motivo(self):
        orden = self.ordenes.agregar(1, 'PAGADO', [])
        self.ordenes.marcar_revision(1, 'Pago confirmado sin stock para CAMISA-S')
        self.caso.ejecutar(1)
        self.assertFalse(orden['requiere_revision'])
        self.assertEqual(orden['motivo_revision'], 'Pago confirmado sin stock para CAMISA-S')

    def test_orden_sin_revision_pendiente_o_inexistente(self):
        self.ordenes.agregar(1, 'PAGADO', [])
        with self.assertRaises(SinRevisionPendiente):
            self.caso.ejecutar(1)
        with self.assertRaises(OrdenNoEncontrada):
            self.caso.ejecutar(99)

class RegistrarPagoFueraPlazoTests(SimpleTestCase):
    def setUp(self):
        self.ordenes = RepositorioOrdenesFalso()
        self.caso = RegistrarPagoFueraPlazo(self.ordenes)

    def test_registra_pago_tardio_sin_cambiar_estado_ni_stock(self):
        orden = self.ordenes.agregar(
            1,
            'CANCELADO',
            [],
            motivo_cancelacion=MOTIVO_PAGO_VENCIDO,
        )

        self.caso.ejecutar(1)

        self.assertEqual(orden['estado'], EstadoPedido.CANCELADO)
        self.assertTrue(orden['requiere_revision'])
        self.assertEqual(
            orden['motivo_revision'],
            RegistrarPagoFueraPlazo.MOTIVO_REVISION,
        )
        self.assertFalse(orden['stock_descontado'])

    def test_rechaza_orden_cancelada_por_otro_motivo(self):
        orden = self.ordenes.agregar(
            1,
            'CANCELADO',
            [],
            motivo_cancelacion='Cancelado por el administrador',
        )

        with self.assertRaises(PagoFueraPlazoNoPermitido):
            self.caso.ejecutar(1)

        self.assertFalse(orden['requiere_revision'])
        self.assertEqual(orden['estado'], EstadoPedido.CANCELADO)

    def test_rechaza_orden_que_no_esta_cancelada(self):
        self.ordenes.agregar(
            1,
            'PENDIENTE',
            [],
            motivo_cancelacion=MOTIVO_PAGO_VENCIDO,
        )

        with self.assertRaises(PagoFueraPlazoNoPermitido):
            self.caso.ejecutar(1)

    def test_rechaza_orden_inexistente(self):
        with self.assertRaises(OrdenNoEncontrada):
            self.caso.ejecutar(999)
