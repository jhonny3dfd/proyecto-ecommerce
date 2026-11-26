from datetime import date

from django.test import SimpleTestCase

from ecommerce.application.cotizaciones import (
    CambiarEstadoCotizacion, CotizacionNoEncontrada, FormularioCotizacionDesactivado, NombresProductos,
    NotificadorCotizaciones, RepositorioCotizaciones, SolicitarCotizacion,
)
from ecommerce.domain.cotizaciones import CotizacionInvalida, EstadoCotizacion

HOY = date(2026, 10, 20)
DATOS = {'nombre': 'Ana Pérez', 'correo': 'ana@example.test', 'telefono': '912345678', 'cantidad': 20,
         'producto_id': 'taza', 'personalizacion': 'Con el logo'}


class RepositorioCotizacionesFalso(RepositorioCotizaciones):
    def __init__(self):
        self.cotizaciones = {}

    def guardar(self, solicitud):
        cotizacion_id = len(self.cotizaciones) + 1
        self.cotizaciones[cotizacion_id] = {'solicitud': solicitud, 'estado': EstadoCotizacion.NUEVA}
        return cotizacion_id

    def cambiar_estado(self, cotizacion_id, estado):
        if cotizacion_id not in self.cotizaciones:
            return False
        self.cotizaciones[cotizacion_id]['estado'] = estado
        return True


class NotificadorFalso(NotificadorCotizaciones):
    def __init__(self):
        self.avisadas = []

    def notificar_nueva(self, cotizacion_id):
        self.avisadas.append(cotizacion_id)


class ProductosFalsos(NombresProductos):
    def nombre(self, producto_id):
        return {'taza': 'Taza de cerámica'}.get(producto_id)


class SolicitarCotizacionTests(SimpleTestCase):
    def setUp(self):
        self.repositorio = RepositorioCotizacionesFalso()
        self.notificador = NotificadorFalso()
        self.caso = SolicitarCotizacion(self.repositorio, self.notificador, ProductosFalsos())

    def test_guarda_la_solicitud_como_nueva_con_el_nombre_del_producto_y_avisa(self):
        cotizacion_id = self.caso.ejecutar(DATOS, formulario_activo=True, hoy=HOY)

        guardada = self.repositorio.cotizaciones[cotizacion_id]
        self.assertEqual(guardada['estado'], EstadoCotizacion.NUEVA)
        self.assertEqual(guardada['solicitud'].producto_nombre, 'Taza de cerámica')
        self.assertEqual(self.notificador.avisadas, [cotizacion_id])

    def test_con_el_formulario_desactivado_no_guarda_ni_avisa(self):
        with self.assertRaises(FormularioCotizacionDesactivado):
            self.caso.ejecutar(DATOS, formulario_activo=False, hoy=HOY)
        self.assertEqual((self.repositorio.cotizaciones, self.notificador.avisadas), ({}, []))

    def test_un_producto_que_no_esta_publicado_se_rechaza_sin_guardar(self):
        with self.assertRaises(CotizacionInvalida) as error:
            self.caso.ejecutar({**DATOS, 'producto_id': 'oculto'}, formulario_activo=True, hoy=HOY)
        self.assertIn('producto_id', error.exception.errores)
        self.assertEqual(self.notificador.avisadas, [])


class CambiarEstadoCotizacionTests(SimpleTestCase):
    def setUp(self):
        self.repositorio = RepositorioCotizacionesFalso()
        self.cotizacion_id = SolicitarCotizacion(self.repositorio, NotificadorFalso(), ProductosFalsos()).ejecutar(
            DATOS, formulario_activo=True, hoy=HOY)
        self.caso = CambiarEstadoCotizacion(self.repositorio)

    def test_la_tienda_registra_en_que_quedo(self):
        for estado in ('RESPONDIDA', 'ACEPTADA', 'DESCARTADA', 'NUEVA'):
            with self.subTest(estado=estado):
                self.assertEqual(self.caso.ejecutar(self.cotizacion_id, estado), EstadoCotizacion(estado))
                self.assertEqual(self.repositorio.cotizaciones[self.cotizacion_id]['estado'], estado)

    def test_estado_desconocido_o_cotizacion_inexistente(self):
        with self.assertRaises(ValueError):
            self.caso.ejecutar(self.cotizacion_id, 'PAGADA')
        with self.assertRaises(CotizacionNoEncontrada):
            self.caso.ejecutar(99, 'ACEPTADA')
