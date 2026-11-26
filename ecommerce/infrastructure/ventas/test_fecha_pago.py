from importlib import import_module

from django.apps import apps
from django.test import TestCase

from ecommerce.domain.ventas import EstadoPedido

from .models import OrdenCompra
from .repositorio_ordenes import DjangoRepositorioOrdenes


def crear_orden(estado='PENDIENTE', metodo_pago='TRANSBANK'):
    return OrdenCompra.objects.create(
        email_invitado='ana@example.test', metodo_pago=metodo_pago, estado=estado,
        direccion_envio_snapshot={'comuna': 'SANTIAGO'}, subtotal=10000, costo_envio=0, total_final=10000)


class FechaPagoTests(TestCase):
    """El dashboard cuenta cada venta el día en que se pagó (RF-03.1)."""

    def test_se_registra_al_pasar_a_pagado(self):
        for metodo in ('TRANSBANK', 'TRANSFERENCIA'):
            with self.subTest(metodo=metodo):
                orden = crear_orden(metodo_pago=metodo)
                self.assertTrue(DjangoRepositorioOrdenes().cambiar_estado(orden.id, EstadoPedido.PENDIENTE,
                                                                          EstadoPedido.PAGADO))
                orden.refresh_from_db()
                self.assertIsNotNone(orden.fecha_pago)

    def test_los_cambios_siguientes_la_conservan(self):
        orden = crear_orden()
        repositorio = DjangoRepositorioOrdenes()
        repositorio.cambiar_estado(orden.id, EstadoPedido.PENDIENTE, EstadoPedido.PAGADO)
        orden.refresh_from_db()
        pagada_en = orden.fecha_pago
        repositorio.cambiar_estado(orden.id, EstadoPedido.PAGADO, EstadoPedido.EN_PREPARACION)
        orden.refresh_from_db()
        self.assertEqual(orden.fecha_pago, pagada_en)

    def test_una_cancelacion_no_la_registra(self):
        orden = crear_orden()
        DjangoRepositorioOrdenes().cambiar_estado(orden.id, EstadoPedido.PENDIENTE, EstadoPedido.CANCELADO,
                                                  motivo_cancelacion='Pago rechazado')
        orden.refresh_from_db()
        self.assertIsNone(orden.fecha_pago)

    def test_la_migracion_rellena_solo_los_pagados_con_su_fecha_de_creacion(self):
        pagados = [crear_orden(estado) for estado in ('PAGADO', 'EN_PREPARACION', 'ENVIADO', 'ENTREGADO')]
        sin_pago = [crear_orden(estado) for estado in ('PENDIENTE', 'CANCELADO')]
        migracion = import_module('ecommerce.infrastructure.ventas.migrations.0041_fecha_pago')

        migracion.rellenar_fecha_pago(apps, None)

        for orden in pagados:
            orden.refresh_from_db()
            self.assertEqual(orden.fecha_pago, orden.fecha_creacion)
        for orden in sin_pago:
            orden.refresh_from_db()
            self.assertIsNone(orden.fecha_pago)
