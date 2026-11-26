from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from ecommerce.domain.resenas import (
    CalificacionProducto, DatosResena, EstadoResena, ModeracionNoPermitida, PedidoNoEntregado, PlazoResenaVencido,
    ProductoDelPedido, ResenaInvalida, ResenaYaEnviada, nombre_publico_sugerido, promedio, puede_resenarse,
    validar_moderacion, validar_pedido_para_resena, validar_plazo_resena,
)
from ecommerce.domain.ventas import EstadoPedido

PEDIDO = [ProductoDelPedido('taza', 'Taza de cerámica'), ProductoDelPedido('plato', 'Plato hondo')]
DATOS = {'estrellas': 5, 'comentario': ' Llegó rápido ', 'nombre_publico': 'Ana P.', 'acepta_publicacion': True}


class DatosResenaTests(SimpleTestCase):
    def errores(self, datos):
        with self.assertRaises(ResenaInvalida) as error:
            DatosResena.desde(datos, PEDIDO)
        return error.exception.errores

    def test_una_resena_de_la_tienda_sin_productos(self):
        resena = DatosResena.desde(DATOS, PEDIDO)
        self.assertEqual((resena.estrellas_tienda, resena.comentario_tienda), (5, 'Llegó rápido'))
        self.assertEqual(resena.productos, ())

    def test_califica_productos_del_pedido_con_el_nombre_del_pedido_y_en_su_orden(self):
        resena = DatosResena.desde({**DATOS, 'productos': [
            {'producto_id': 'plato', 'estrellas': 3},
            {'producto_id': 'taza', 'estrellas': 4, 'comentario': 'Linda', 'producto_nombre': 'Otro nombre'},
        ]}, PEDIDO)
        self.assertEqual(resena.productos, (
            CalificacionProducto('taza', 'Taza de cerámica', 4, 'Linda'),
            CalificacionProducto('plato', 'Plato hondo', 3, ''),
        ))

    def test_un_producto_sin_estrellas_ni_comentario_se_omite(self):
        resena = DatosResena.desde({**DATOS, 'productos': [{'producto_id': 'taza', 'comentario': '  '}]}, PEDIDO)
        self.assertEqual(resena.productos, ())

    def test_las_estrellas_de_la_tienda_son_obligatorias_y_de_1_a_5(self):
        for valor in (None, 0, 6, 4.5, '5', True):
            with self.subTest(estrellas=valor):
                self.assertIn('estrellas', self.errores({**DATOS, 'estrellas': valor}))

    def test_el_comentario_tiene_largo_maximo(self):
        self.assertIn('comentario', self.errores({**DATOS, 'comentario': 'a' * 1001}))
        DatosResena.desde({**DATOS, 'comentario': 'a' * 1000}, PEDIDO)

    def test_el_nombre_es_obligatorio_corto_y_no_puede_ser_un_correo(self):
        for valor in ('  ', 'a' * 41, 'ana@example.test'):
            with self.subTest(nombre=valor):
                self.assertIn('nombre_publico', self.errores({**DATOS, 'nombre_publico': valor}))
        self.assertEqual(DatosResena.desde({**DATOS, 'nombre_publico': ' Ana   P. '}, PEDIDO).nombre_publico, 'Ana P.')

    def test_exige_aceptar_que_se_publique(self):
        for valor in (None, False, 'true'):
            with self.subTest(acepta=valor):
                self.assertIn('acepta_publicacion', self.errores({**DATOS, 'acepta_publicacion': valor}))

    def test_errores_por_producto(self):
        errores = self.errores({**DATOS, 'productos': [
            {'producto_id': 'otro', 'estrellas': 5},
            {'producto_id': 'taza', 'estrellas': 9},
            {'producto_id': 'plato', 'comentario': 'Sin estrellas'},
        ]})
        self.assertEqual(set(errores['productos']), {'otro', 'taza', 'plato'})
        self.assertIn('no es parte de tu pedido', errores['productos']['otro'])
        self.assertIn('califícalo', errores['productos']['plato'])

    def test_un_producto_repetido_se_rechaza(self):
        errores = self.errores({**DATOS, 'productos': [{'producto_id': 'taza', 'estrellas': 5}] * 2})
        self.assertIn('repetido', errores['productos']['taza'])

    def test_el_comentario_de_un_producto_tiene_largo_maximo(self):
        errores = self.errores({**DATOS, 'productos': [
            {'producto_id': 'taza', 'estrellas': 5, 'comentario': 'a' * 1001}]})
        self.assertIn('taza', errores['productos'])


class PedidoParaResenaTests(SimpleTestCase):
    def test_solo_un_pedido_entregado(self):
        validar_pedido_para_resena(EstadoPedido.ENTREGADO, ya_tiene_resena=False)
        for estado in set(EstadoPedido) - {EstadoPedido.ENTREGADO}:
            with self.subTest(estado=estado), self.assertRaises(PedidoNoEntregado):
                validar_pedido_para_resena(estado, ya_tiene_resena=False)

    def test_una_sola_vez(self):
        with self.assertRaises(ResenaYaEnviada):
            validar_pedido_para_resena(EstadoPedido.ENTREGADO, ya_tiene_resena=True)


class PlazoResenaTests(SimpleTestCase):
    ENTREGADO_EN = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)

    def test_hasta_60_dias_desde_la_entrega(self):
        validar_plazo_resena(self.ENTREGADO_EN, self.ENTREGADO_EN + timedelta(days=60))
        with self.assertRaises(PlazoResenaVencido):
            validar_plazo_resena(self.ENTREGADO_EN, self.ENTREGADO_EN + timedelta(days=60, seconds=1))

    def test_sin_fecha_de_entrega_no_esta_en_plazo(self):
        with self.assertRaises(PlazoResenaVencido):
            validar_plazo_resena(None, self.ENTREGADO_EN)

    def test_puede_resenarse_solo_entregado_sin_resena_y_en_plazo(self):
        ahora = self.ENTREGADO_EN + timedelta(days=5)
        self.assertTrue(puede_resenarse(EstadoPedido.ENTREGADO, self.ENTREGADO_EN, False, ahora))
        self.assertFalse(puede_resenarse(EstadoPedido.ENVIADO, None, False, ahora))
        self.assertFalse(puede_resenarse(EstadoPedido.ENTREGADO, self.ENTREGADO_EN, True, ahora))
        self.assertFalse(puede_resenarse(EstadoPedido.ENTREGADO, self.ENTREGADO_EN, False,
                                         self.ENTREGADO_EN + timedelta(days=61)))


class ModeracionTests(SimpleTestCase):
    def test_el_admin_aprueba_u_oculta_y_puede_cambiar_de_opinion(self):
        for actual, nuevo in (('PENDIENTE', 'APROBADA'), ('PENDIENTE', 'OCULTA'),
                              ('APROBADA', 'OCULTA'), ('OCULTA', 'APROBADA')):
            with self.subTest(actual=actual, nuevo=nuevo):
                self.assertEqual(validar_moderacion(actual, nuevo), EstadoResena(nuevo))

    def test_una_resena_revisada_no_vuelve_a_pendiente(self):
        for actual in ('APROBADA', 'OCULTA'):
            with self.subTest(actual=actual), self.assertRaises(ModeracionNoPermitida):
                validar_moderacion(actual, 'PENDIENTE')

    def test_rechaza_un_estado_desconocido(self):
        with self.assertRaises(ValueError):
            validar_moderacion('PENDIENTE', 'PUBLICADA')


class NombrePublicoSugeridoTests(SimpleTestCase):
    def test_nombre_e_inicial_del_apellido(self):
        self.assertEqual(nombre_publico_sugerido('  Ana   pérez Soto '), 'Ana P.')

    def test_un_solo_nombre_o_ninguno(self):
        self.assertEqual(nombre_publico_sugerido('Ana'), 'Ana')
        self.assertEqual(nombre_publico_sugerido(''), '')
        self.assertEqual(nombre_publico_sugerido(None), '')

    def test_no_pasa_del_largo_maximo(self):
        self.assertEqual(len(nombre_publico_sugerido('A' * 60)), 40)


class PromedioTests(SimpleTestCase):
    def test_sin_calificaciones_no_hay_promedio(self):
        self.assertIsNone(promedio([]))

    def test_un_decimal_redondeando_la_mitad_hacia_arriba(self):
        self.assertEqual(promedio([5, 4, 4, 4]), 4.3)
        self.assertEqual(promedio([5, 5, 4]), 4.7)
        self.assertEqual(promedio([3]), 3.0)
