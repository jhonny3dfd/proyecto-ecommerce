from decimal import Decimal

from django.test import SimpleTestCase

from ecommerce.domain.logistica import (
    AVISO_ENTREGA_COORDINADA, ENTREGA_COORDINADA, RETIRO_LOCAL, EntregaNoHabilitada, EntregasDeLaTienda,
    MedidasEnvio, Paquete, aviso_entrega_coordinada, error_direccion_entrega, estado_entrega_de_la_tienda,
    clave_comuna, paquete_de_envio,
)
from ecommerce.domain.ventas import EstadoPedido


class SeguimientoEntregaDeLaTiendaTests(SimpleTestCase):
    """RF-02.4: sin courier, el comprador ve el avance según el estado del pedido."""

    def test_el_estado_sigue_al_pedido_y_cambia_al_final_segun_la_entrega(self):
        for proveedor, enviado, entregado in (
            (ENTREGA_COORDINADA, 'La tienda coordinará la entrega contigo', 'Entregado'),
            (RETIRO_LOCAL, 'Listo para retirar', 'Retirado'),
        ):
            with self.subTest(proveedor=proveedor):
                self.assertEqual(estado_entrega_de_la_tienda(proveedor, EstadoPedido.PAGADO), 'Pago confirmado')
                self.assertEqual(estado_entrega_de_la_tienda(proveedor, 'EN_PREPARACION'), 'En preparación')
                self.assertEqual(estado_entrega_de_la_tienda(proveedor, EstadoPedido.ENVIADO), enviado)
                self.assertEqual(estado_entrega_de_la_tienda(proveedor, EstadoPedido.ENTREGADO), entregado)
                self.assertEqual(estado_entrega_de_la_tienda(proveedor, 'CANCELADO'), 'Cancelado')

    def test_el_aviso_usa_las_instrucciones_del_admin_o_el_aviso_por_defecto(self):
        self.assertEqual(aviso_entrega_coordinada('  Te escribimos por WhatsApp. '), 'Te escribimos por WhatsApp.')
        self.assertEqual(aviso_entrega_coordinada(''), AVISO_ENTREGA_COORDINADA)
        self.assertEqual(aviso_entrega_coordinada(None), AVISO_ENTREGA_COORDINADA)


class EntregasDeLaTiendaTests(SimpleTestCase):
    def test_el_retiro_en_local_es_gratis(self):
        self.assertEqual(EntregasDeLaTienda(retiro_activo=True).costo(RETIRO_LOCAL), Decimal('0'))

    def test_la_entrega_coordinada_cobra_lo_que_definio_el_admin(self):
        entregas = EntregasDeLaTienda(coordinada_activa=True, costo_coordinada=Decimal('2500'))
        self.assertEqual(entregas.costo(ENTREGA_COORDINADA), Decimal('2500'))

    def test_la_entrega_coordinada_puede_ser_gratis(self):
        self.assertEqual(EntregasDeLaTienda(coordinada_activa=True).costo(ENTREGA_COORDINADA), Decimal('0'))

    def test_rechaza_la_entrega_que_el_admin_no_activo(self):
        # Activar una no habilita la otra
        for entregas, proveedor in (
            (EntregasDeLaTienda(coordinada_activa=True), RETIRO_LOCAL),
            (EntregasDeLaTienda(retiro_activo=True), ENTREGA_COORDINADA),
        ):
            with self.subTest(proveedor=proveedor), self.assertRaises(EntregaNoHabilitada):
                entregas.costo(proveedor)

    def test_un_transportista_no_es_una_entrega_de_la_tienda(self):
        with self.assertRaises(EntregaNoHabilitada):
            EntregasDeLaTienda(retiro_activo=True, coordinada_activa=True).costo('CHILEXPRESS')


class DireccionEntregaTests(SimpleTestCase):
    """RF-02.3: la dirección que pide cada forma de entrega."""

    def test_el_retiro_en_local_no_pide_direccion(self):
        self.assertIsNone(error_direccion_entrega(RETIRO_LOCAL, {}))

    def test_la_entrega_coordinada_puede_ir_sin_direccion(self):
        for direccion in ({}, None, {'calle': ' ', 'comuna': ''}, {'dpto_casa': 'Casa 2'}):
            with self.subTest(direccion=direccion):
                self.assertIsNone(error_direccion_entrega(ENTREGA_COORDINADA, direccion))

    def test_la_entrega_coordinada_con_direccion_exige_calle_y_comuna(self):
        self.assertIsNone(error_direccion_entrega(ENTREGA_COORDINADA, {'calle': 'Los Aromos', 'comuna': 'Ñuñoa'}))
        for direccion in ({'calle': 'Los Aromos'}, {'comuna': 'Ñuñoa'}, {'numero': '1550'}):
            with self.subTest(direccion=direccion):
                self.assertIn('calle y la comuna', error_direccion_entrega(ENTREGA_COORDINADA, direccion))

    def test_un_transportista_exige_la_comuna(self):
        self.assertIsNone(error_direccion_entrega('CHILEXPRESS', {'comuna': 'Ñuñoa'}))
        for direccion in ({}, None, 'Ñuñoa', {'calle': 'Los Aromos'}):
            with self.subTest(direccion=direccion):
                self.assertEqual(error_direccion_entrega('CHILEXPRESS', direccion), 'Se requiere la comuna de destino.')


class PaqueteDeEnvioTests(SimpleTestCase):
    """RF-02.3: la caja que se cotiza y se despacha, armada con las medidas del catálogo."""

    def test_suma_los_pesos_y_el_lado_es_el_mayor_entre_el_cubo_del_volumen_y_el_lado_mas_largo(self):
        polera = MedidasEnvio(Decimal('0.3'), Decimal('5'), Decimal('25'), Decimal('30'))
        taza = MedidasEnvio(Decimal('0.45'), Decimal('12'), Decimal('12'), Decimal('12'))
        # Volumen 2 x 3.750 + 3 x 1.728 = 12.684 cm³: un cubo de 24 cm, menor que el lado de 30 de la polera
        self.assertEqual(paquete_de_envio([(polera, 2), (taza, 3)]),
                         Paquete(Decimal('1.95'), Decimal('30'), Decimal('30'), Decimal('30')))

    def test_muchas_unidades_chicas_forman_un_cubo_mayor_que_cada_una(self):
        caja = MedidasEnvio(Decimal('1'), Decimal('10'), Decimal('10'), Decimal('10'))
        # 27 cajas de 1.000 cm³ = un cubo exacto de 30 cm (sin el error de la potencia 1/3, que daría 31)
        paquete = paquete_de_envio([(caja, 27)])
        self.assertEqual((paquete.peso_kg, paquete.alto_cm), (Decimal('27.00'), Decimal('30')))

    def test_valores_vacios_o_en_cero_usan_el_minimo(self):
        sin_datos = MedidasEnvio(Decimal('0'), Decimal('0'), Decimal('0'), Decimal('-5'))
        self.assertEqual(paquete_de_envio([(sin_datos, 1)]),
                         Paquete(Decimal('0.10'), Decimal('10'), Decimal('10'), Decimal('10')))


class ClaveComunaTests(SimpleTestCase):
    def test_la_misma_comuna_escrita_de_distintas_formas_tiene_la_misma_clave(self):
        for escrita, esperada in (('Ñuñoa', 'NUNOA'), ('  maipú ', 'MAIPU'), ('San  José de Maipo', 'SAN JOSE DE MAIPO'),
                                  ('CONCEPCIÓN', 'CONCEPCION'), (None, '')):
            with self.subTest(escrita=escrita):
                self.assertEqual(clave_comuna(escrita), esperada)
