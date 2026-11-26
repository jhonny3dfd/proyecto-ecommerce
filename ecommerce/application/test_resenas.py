from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from ecommerce.application.resenas import (
    EnviarResena, ModerarResena, PedidoNoEncontrado, PedidoParaResenar, PedidosParaResenar,
    PrepararFormularioResena, RepositorioResenas, ResenaNoEncontrada, ResenaPublica, ResenasDeLaTienda,
    ResenasDeProducto, ResenasDesactivadas,
)
from ecommerce.domain.resenas import (
    EstadoResena, ModeracionNoPermitida, PedidoNoEntregado, PlazoResenaVencido, ProductoDelPedido, ResenaInvalida,
    ResenaYaEnviada,
)

AHORA = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)
PRODUCTOS = [ProductoDelPedido('taza', 'Taza de cerámica'), ProductoDelPedido('plato', 'Plato hondo')]
DATOS = {'estrellas': 5, 'comentario': 'Todo perfecto', 'nombre_publico': 'Ana P.', 'acepta_publicacion': True,
         'productos': [{'producto_id': 'taza', 'estrellas': 4, 'comentario': 'Linda'}]}


def pedido(orden_id=1, estado='ENTREGADO', entregado_en=AHORA - timedelta(days=3), tiene_resena=False):
    return PedidoParaResenar(orden_id=orden_id, estado=estado, entregado_en=entregado_en,
                             nombre_comprador='Ana Pérez Soto', productos=PRODUCTOS, tiene_resena=tiene_resena)


class PedidosFalsos(PedidosParaResenar):
    def __init__(self, *pedidos):
        self.pedidos = {p.orden_id: p for p in pedidos}

    def obtener(self, orden_id):
        return self.pedidos.get(orden_id)


class RepositorioResenasFalso(RepositorioResenas):
    def __init__(self):
        self.resenas = {}

    def guardar(self, orden_id, datos):
        if any(r['orden_id'] == orden_id for r in self.resenas.values()):
            return None
        resena_id = len(self.resenas) + 1
        self.resenas[resena_id] = {'orden_id': orden_id, 'datos': datos, 'estado': EstadoResena.PENDIENTE,
                                   'fecha': AHORA + timedelta(minutes=resena_id)}
        return resena_id

    def estado(self, resena_id):
        resena = self.resenas.get(resena_id)
        return resena['estado'] if resena else None

    def cambiar_estado(self, resena_id, estado):
        self.resenas[resena_id]['estado'] = estado

    def _aprobadas(self):
        aprobadas = [r for r in self.resenas.values() if r['estado'] == EstadoResena.APROBADA]
        return sorted(aprobadas, key=lambda r: r['fecha'], reverse=True)

    def estrellas_tienda(self):
        return [r['datos'].estrellas_tienda for r in self._aprobadas()]

    def recientes_tienda(self, cantidad):
        return [ResenaPublica(r['datos'].nombre_publico, r['datos'].estrellas_tienda, r['datos'].comentario_tienda,
                              r['fecha']) for r in self._aprobadas() if r['datos'].comentario_tienda][:cantidad]

    def _del_producto(self, producto_id):
        return [(r, c) for r in self._aprobadas() for c in r['datos'].productos if c.producto_id == producto_id]

    def estrellas_producto(self, producto_id):
        return [c.estrellas for _, c in self._del_producto(producto_id)]

    def recientes_producto(self, producto_id, cantidad):
        return [ResenaPublica(r['datos'].nombre_publico, c.estrellas, c.comentario, r['fecha'])
                for r, c in self._del_producto(producto_id) if c.comentario][:cantidad]


class PrepararFormularioResenaTests(SimpleTestCase):
    def test_muestra_los_productos_del_pedido_y_sugiere_el_nombre(self):
        formulario = PrepararFormularioResena(PedidosFalsos(pedido())).ejecutar(1, resenas_activas=True, ahora=AHORA)
        self.assertEqual(formulario.productos, PRODUCTOS)
        self.assertEqual(formulario.nombre_sugerido, 'Ana P.')

    def test_con_las_resenas_desactivadas_no_se_ofrece(self):
        with self.assertRaises(ResenasDesactivadas):
            PrepararFormularioResena(PedidosFalsos(pedido())).ejecutar(1, resenas_activas=False, ahora=AHORA)

    def test_pedido_inexistente_no_entregado_ya_resenado_o_fuera_de_plazo(self):
        casos = (
            (PedidosFalsos(), PedidoNoEncontrado),
            (PedidosFalsos(pedido(estado='ENVIADO')), PedidoNoEntregado),
            (PedidosFalsos(pedido(tiene_resena=True)), ResenaYaEnviada),
            (PedidosFalsos(pedido(entregado_en=AHORA - timedelta(days=61))), PlazoResenaVencido),
        )
        for pedidos, error in casos:
            with self.subTest(error=error.__name__), self.assertRaises(error):
                PrepararFormularioResena(pedidos).ejecutar(1, resenas_activas=True, ahora=AHORA)


class EnviarResenaTests(SimpleTestCase):
    def setUp(self):
        self.repositorio = RepositorioResenasFalso()
        self.caso = EnviarResena(PedidosFalsos(pedido()), self.repositorio)

    def test_la_resena_queda_pendiente_con_la_tienda_y_los_productos(self):
        resena_id = self.caso.ejecutar(1, DATOS, resenas_activas=True, ahora=AHORA)

        guardada = self.repositorio.resenas[resena_id]
        self.assertEqual(guardada['estado'], EstadoResena.PENDIENTE)
        self.assertEqual(guardada['datos'].estrellas_tienda, 5)
        self.assertEqual([c.producto_nombre for c in guardada['datos'].productos], ['Taza de cerámica'])

    def test_con_las_resenas_desactivadas_no_guarda(self):
        with self.assertRaises(ResenasDesactivadas):
            self.caso.ejecutar(1, DATOS, resenas_activas=False, ahora=AHORA)
        self.assertEqual(self.repositorio.resenas, {})

    def test_datos_invalidos_no_guardan(self):
        with self.assertRaises(ResenaInvalida):
            self.caso.ejecutar(1, {**DATOS, 'acepta_publicacion': False}, resenas_activas=True, ahora=AHORA)
        self.assertEqual(self.repositorio.resenas, {})

    def test_un_pedido_no_entregado_no_guarda(self):
        caso = EnviarResena(PedidosFalsos(pedido(estado='EN_PREPARACION')), self.repositorio)
        with self.assertRaises(PedidoNoEntregado):
            caso.ejecutar(1, DATOS, resenas_activas=True, ahora=AHORA)
        self.assertEqual(self.repositorio.resenas, {})

    def test_si_otro_envio_se_adelanto_se_rechaza(self):
        # El pedido se leyó sin reseña, pero otro envío la guardó antes
        self.caso.ejecutar(1, DATOS, resenas_activas=True, ahora=AHORA)
        with self.assertRaises(ResenaYaEnviada):
            self.caso.ejecutar(1, DATOS, resenas_activas=True, ahora=AHORA)
        self.assertEqual(len(self.repositorio.resenas), 1)


class ModerarResenaTests(SimpleTestCase):
    def setUp(self):
        self.repositorio = RepositorioResenasFalso()
        self.resena_id = EnviarResena(PedidosFalsos(pedido()), self.repositorio).ejecutar(
            1, DATOS, resenas_activas=True, ahora=AHORA)
        self.caso = ModerarResena(self.repositorio)

    def test_aprueba_y_despues_oculta(self):
        self.assertEqual(self.caso.ejecutar(self.resena_id, 'APROBADA'), EstadoResena.APROBADA)
        self.assertEqual(self.caso.ejecutar(self.resena_id, 'OCULTA'), EstadoResena.OCULTA)
        self.assertEqual(self.repositorio.resenas[self.resena_id]['estado'], EstadoResena.OCULTA)

    def test_no_vuelve_a_pendiente_ni_existe_otra(self):
        self.caso.ejecutar(self.resena_id, 'APROBADA')
        with self.assertRaises(ModeracionNoPermitida):
            self.caso.ejecutar(self.resena_id, 'PENDIENTE')
        self.assertEqual(self.repositorio.resenas[self.resena_id]['estado'], EstadoResena.APROBADA)
        with self.assertRaises(ResenaNoEncontrada):
            self.caso.ejecutar(99, 'APROBADA')


class ResenasPublicasTests(SimpleTestCase):
    def setUp(self):
        self.repositorio = RepositorioResenasFalso()
        pedidos = PedidosFalsos(*(pedido(orden_id=n) for n in (1, 2, 3)))
        enviar = EnviarResena(pedidos, self.repositorio)
        moderar = ModerarResena(self.repositorio)
        enviar.ejecutar(1, DATOS, resenas_activas=True, ahora=AHORA)
        enviar.ejecutar(2, {**DATOS, 'estrellas': 4, 'comentario': '', 'productos': [
            {'producto_id': 'taza', 'estrellas': 3}]}, resenas_activas=True, ahora=AHORA)
        # La tercera queda pendiente: no se ve ni cuenta en el promedio
        enviar.ejecutar(3, {**DATOS, 'estrellas': 1}, resenas_activas=True, ahora=AHORA)
        moderar.ejecutar(1, 'APROBADA')
        moderar.ejecutar(2, 'APROBADA')

    def test_la_landing_muestra_el_promedio_de_las_aprobadas_y_las_que_tienen_comentario(self):
        resumen = ResenasDeLaTienda(self.repositorio).ejecutar(resenas_activas=True)
        self.assertEqual((resumen.promedio, resumen.total), (4.5, 2))
        self.assertEqual([r.comentario for r in resumen.resenas], ['Todo perfecto'])

    def test_la_ficha_muestra_el_promedio_del_producto(self):
        resumen = ResenasDeProducto(self.repositorio).ejecutar('taza', resenas_activas=True)
        self.assertEqual((resumen.promedio, resumen.total), (3.5, 2))
        self.assertEqual([(r.nombre_publico, r.comentario) for r in resumen.resenas], [('Ana P.', 'Linda')])

    def test_un_producto_sin_resenas_aprobadas_no_tiene_promedio(self):
        resumen = ResenasDeProducto(self.repositorio).ejecutar('plato', resenas_activas=True)
        self.assertEqual((resumen.promedio, resumen.total, resumen.resenas), (None, 0, []))

    def test_con_las_resenas_desactivadas_no_se_muestra_nada(self):
        for resumen in (ResenasDeLaTienda(self.repositorio).ejecutar(resenas_activas=False),
                        ResenasDeProducto(self.repositorio).ejecutar('taza', resenas_activas=False)):
            self.assertEqual((resumen.promedio, resumen.total, resumen.resenas), (None, 0, []))

    def test_sin_aprobadas_no_hay_seccion(self):
        resumen = ResenasDeLaTienda(RepositorioResenasFalso()).ejecutar(resenas_activas=True)
        self.assertEqual((resumen.promedio, resumen.total, resumen.resenas), (None, 0, []))
