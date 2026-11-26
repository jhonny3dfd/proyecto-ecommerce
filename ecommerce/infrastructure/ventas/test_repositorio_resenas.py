from datetime import datetime, timedelta, timezone

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from ecommerce.domain.resenas import CalificacionProducto, DatosResena, EstadoResena, ProductoDelPedido
from ecommerce.domain.ventas import EstadoPedido

from .models import DetalleOrden, OrdenCompra, Resena, ResenaProducto
from .repositorio_ordenes import DjangoRepositorioOrdenes
from .repositorio_resenas import DjangoPedidosParaResenar, DjangoRepositorioResenas


def crear_orden(estado='ENVIADO'):
    return OrdenCompra.objects.create(
        email_invitado='ana@example.test', metodo_pago='TRANSBANK', estado=estado,
        direccion_envio_snapshot={'comuna': 'SANTIAGO'}, subtotal=10000, costo_envio=0, total_final=10000)


class FechaEntregaTests(TestCase):
    def test_se_registra_al_pasar_a_entregado(self):
        orden = crear_orden('ENVIADO')
        self.assertTrue(DjangoRepositorioOrdenes().cambiar_estado(orden.id, EstadoPedido.ENVIADO,
                                                                  EstadoPedido.ENTREGADO))
        orden.refresh_from_db()
        self.assertIsNotNone(orden.fecha_entrega)

    def test_los_demas_cambios_de_estado_no_la_tocan(self):
        orden = crear_orden('EN_PREPARACION')
        DjangoRepositorioOrdenes().cambiar_estado(orden.id, EstadoPedido.EN_PREPARACION, EstadoPedido.ENVIADO)
        orden.refresh_from_db()
        self.assertIsNone(orden.fecha_entrega)

    def test_un_cambio_rechazado_no_la_registra(self):
        # Otro proceso ya cambió el estado: el UPDATE condicional no aplica nada
        orden = crear_orden('CANCELADO')
        self.assertFalse(DjangoRepositorioOrdenes().cambiar_estado(orden.id, EstadoPedido.ENVIADO,
                                                                   EstadoPedido.ENTREGADO))
        orden.refresh_from_db()
        self.assertIsNone(orden.fecha_entrega)


class ModelosResenaTests(TestCase):
    def setUp(self):
        self.orden = crear_orden('ENTREGADO')

    def crear_resena(self, **campos):
        return Resena.objects.create(**{'orden': self.orden, 'estrellas': 5, 'nombre_publico': 'Ana P.', **campos})

    def test_una_resena_nueva_queda_pendiente(self):
        self.assertEqual(self.crear_resena().estado, 'PENDIENTE')

    def test_una_sola_resena_por_pedido(self):
        self.crear_resena()
        with self.assertRaises(IntegrityError):
            self.crear_resena()

    def test_la_base_rechaza_estrellas_fuera_de_1_a_5(self):
        for estrellas in (0, 6):
            with self.subTest(estrellas=estrellas), self.assertRaises(IntegrityError), transaction.atomic():
                self.crear_resena(estrellas=estrellas)

    def test_cada_producto_una_vez_por_resena_y_con_estrellas_validas(self):
        resena = self.crear_resena()
        ResenaProducto.objects.create(resena=resena, producto_mongo_id='taza', producto_nombre='Taza', estrellas=4)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ResenaProducto.objects.create(resena=resena, producto_mongo_id='taza', producto_nombre='Taza',
                                          estrellas=3)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ResenaProducto.objects.create(resena=resena, producto_mongo_id='plato', producto_nombre='Plato',
                                          estrellas=0)


def agregar_linea(orden, producto_id, sku, nombre):
    DetalleOrden.objects.create(orden=orden, producto_mongo_id=producto_id, variante_sku=sku,
                                nombre_producto_snapshot=f'{nombre} - {sku}', precio_unitario_snapshot=5000,
                                cantidad=1)


def resena(estrellas=5, comentario='Todo perfecto', nombre='Ana P.', productos=()):
    return DatosResena(estrellas_tienda=estrellas, comentario_tienda=comentario, nombre_publico=nombre,
                       productos=tuple(productos))


class PedidosParaResenarTests(TestCase):
    def test_un_invitado_con_los_productos_sin_repetir_y_la_fecha_de_entrega(self):
        orden = crear_orden('ENTREGADO')
        entregado_en = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
        OrdenCompra.objects.filter(id=orden.id).update(nombre_destinatario='Ana Pérez', fecha_entrega=entregado_en)
        agregar_linea(orden, 'taza', 'TAZA-AZUL', 'Taza de cerámica')
        agregar_linea(orden, 'plato', 'PLATO-1', 'Plato hondo')
        # Otra variante del mismo producto
        agregar_linea(orden, 'taza', 'TAZA-ROJA', 'Taza de cerámica')

        pedido = DjangoPedidosParaResenar().obtener(orden.id)

        self.assertEqual((pedido.estado, pedido.entregado_en, pedido.nombre_comprador),
                         ('ENTREGADO', entregado_en, 'Ana Pérez'))
        self.assertEqual(pedido.productos, [ProductoDelPedido('taza', 'Taza de cerámica'),
                                            ProductoDelPedido('plato', 'Plato hondo')])
        self.assertFalse(pedido.tiene_resena)

    def test_un_comprador_registrado_usa_el_nombre_de_su_cuenta(self):
        usuario = get_user_model().objects.create_user(
            email='ana@example.test', password='clave-segura-123', nombre='Ana', apellido_paterno='Pérez',
            apellido_materno='Soto')
        orden = crear_orden('ENTREGADO')
        OrdenCompra.objects.filter(id=orden.id).update(usuario=usuario, email_invitado='',
                                                       nombre_destinatario='Luis Rojas')

        self.assertEqual(DjangoPedidosParaResenar().obtener(orden.id).nombre_comprador, 'Ana Pérez')

    def test_sabe_si_ya_tiene_resena_y_si_no_existe(self):
        orden = crear_orden('ENTREGADO')
        DjangoRepositorioResenas().guardar(orden.id, resena())
        self.assertTrue(DjangoPedidosParaResenar().obtener(orden.id).tiene_resena)
        self.assertIsNone(DjangoPedidosParaResenar().obtener(orden.id + 1))
        self.assertIsNone(DjangoPedidosParaResenar().obtener('abc'))


class RepositorioResenasTests(TestCase):
    def setUp(self):
        self.repositorio = DjangoRepositorioResenas()
        self.ahora = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)

    def guardar(self, datos, estado=EstadoResena.APROBADA, minutos=0):
        resena_id = self.repositorio.guardar(crear_orden('ENTREGADO').id, datos)
        Resena.objects.filter(id=resena_id).update(estado=estado.value,
                                                   fecha_creacion=self.ahora + timedelta(minutes=minutos))
        return resena_id

    def test_guarda_la_tienda_y_los_productos_como_pendiente(self):
        orden = crear_orden('ENTREGADO')
        resena_id = self.repositorio.guardar(orden.id, resena(productos=[
            CalificacionProducto('taza', 'Taza de cerámica', 4, 'Linda')]))

        guardada = Resena.objects.get(id=resena_id)
        self.assertEqual((guardada.orden_id, guardada.estado, guardada.estrellas, guardada.nombre_publico),
                         (orden.id, 'PENDIENTE', 5, 'Ana P.'))
        self.assertEqual(list(guardada.productos.values_list('producto_mongo_id', 'producto_nombre', 'estrellas',
                                                             'comentario')),
                         [('taza', 'Taza de cerámica', 4, 'Linda')])

    def test_un_segundo_envio_del_mismo_pedido_no_guarda_nada(self):
        orden = crear_orden('ENTREGADO')
        self.repositorio.guardar(orden.id, resena())
        self.assertIsNone(self.repositorio.guardar(orden.id, resena(estrellas=1, productos=[
            CalificacionProducto('taza', 'Taza', 1)])))
        self.assertEqual((Resena.objects.count(), ResenaProducto.objects.count()), (1, 0))

    def test_lee_y_cambia_el_estado(self):
        resena_id = self.repositorio.guardar(crear_orden('ENTREGADO').id, resena())
        self.assertEqual(self.repositorio.estado(resena_id), EstadoResena.PENDIENTE)
        self.repositorio.cambiar_estado(resena_id, EstadoResena.APROBADA)
        self.assertEqual(self.repositorio.estado(resena_id), EstadoResena.APROBADA)
        self.assertIsNone(self.repositorio.estado(resena_id + 1))

    def test_la_tienda_solo_cuenta_y_muestra_las_aprobadas(self):
        self.guardar(resena(5, 'La primera'), minutos=1)
        self.guardar(resena(4, ''), minutos=2)
        self.guardar(resena(3, 'La última'), minutos=3)
        self.guardar(resena(1, 'Pendiente'), estado=EstadoResena.PENDIENTE, minutos=4)
        self.guardar(resena(1, 'Oculta'), estado=EstadoResena.OCULTA, minutos=5)

        self.assertCountEqual(self.repositorio.estrellas_tienda(), [5, 4, 3])
        recientes = self.repositorio.recientes_tienda(5)
        self.assertEqual([(r.comentario, r.estrellas) for r in recientes], [('La última', 3), ('La primera', 5)])
        self.assertEqual(recientes[0].nombre_publico, 'Ana P.')
        self.assertEqual(len(self.repositorio.recientes_tienda(1)), 1)

    def test_el_producto_solo_cuenta_y_muestra_las_calificaciones_aprobadas(self):
        def taza(estrellas, comentario):
            return CalificacionProducto('taza', 'Taza', estrellas, comentario)

        self.guardar(resena(nombre='Ana P.', productos=[taza(5, 'Linda')]), minutos=1)
        self.guardar(resena(nombre='Luis R.', productos=[
            taza(3, ''), CalificacionProducto('plato', 'Plato', 1, 'Mal')]), minutos=2)
        self.guardar(resena(nombre='Eva M.', productos=[taza(4, 'Buena')]), minutos=3)
        self.guardar(resena(productos=[taza(1, 'Oculta')]), estado=EstadoResena.OCULTA, minutos=4)

        self.assertCountEqual(self.repositorio.estrellas_producto('taza'), [5, 3, 4])
        self.assertEqual([(r.nombre_publico, r.comentario) for r in self.repositorio.recientes_producto('taza', 5)],
                         [('Eva M.', 'Buena'), ('Ana P.', 'Linda')])
        self.assertEqual(self.repositorio.estrellas_producto('otro'), [])
