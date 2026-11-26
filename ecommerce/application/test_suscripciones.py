from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

from django.test import SimpleTestCase

from ecommerce.application.suscripciones import (
    AccionesSuscripcion, AlPagarPedido, CambiosSuscripcion, CatalogoSuscripciones, CicloYaPagado,
    CompraNoPermitida, CotizadorDespacho, DespachoNoDisponible, DestinatarioIncompleto, Entrega, NotificadorSuscripciones, PedidoCiclo,
    PedidoEnCurso, PedidosSuscripcion, PlanNoDisponible, PlanRegistrado, ProcesarCiclos, ReglasCompra,
    RepositorioPlanes, RepositorioSuscripciones, SinStockSuscripcion, SolicitudSuscripcion, Suscribirse,
    SuscripcionNoEncontrada, SuscripcionRegistrada, TerminosNoAceptados, VarianteElegible, VarianteNoElegible,
    beneficios_de,
)
from ecommerce.domain.suscripciones import (
    MOTIVO_CICLO_NO_PAGADO, MOTIVO_CICLO_SALTADO, MOTIVO_PRIMER_PAGO_NO_RECIBIDO, AccionNoPermitida, DatosPlan,
    EstadoSuscripcion, EventoSuscripcion,
)
from ecommerce.domain.ventas import EstadoPedido

HOY = date(2026, 11, 11)
DIAS = 3
ANA, BETO = 1, 2
E = EstadoSuscripcion


def plan(**cambios):
    datos = {'nombre': 'Café del mes', 'precio': 14990, 'frecuencia_semanas': 4, 'categorias': ['Cafés'],
             'beneficios': ['Café recién tostado'], **cambios}
    return DatosPlan.desde(datos)


# ---------- Fakes de los puertos ----------

class PlanesFalsos(RepositorioPlanes):
    def __init__(self, *planes):
        self.planes = {numero: PlanRegistrado(numero, datos) for numero, datos in enumerate(planes, start=1)}

    def obtener(self, plan_id):
        return self.planes.get(plan_id)


class SuscripcionesFalsas(RepositorioSuscripciones):
    def __init__(self, planes: PlanesFalsos):
        self.planes = planes
        self.filas = {}
        self.motivos = {}

    def crear(self, usuario_id, plan_id, variante, entrega, metodo_pago, proxima_entrega):
        nuevo = len(self.filas) + 1
        self.filas[nuevo] = SuscripcionRegistrada(
            nuevo, usuario_id, self.planes.obtener(plan_id), E.PENDIENTE, variante.producto_id, variante.sku,
            variante.nombre, entrega, metodo_pago, proxima_entrega)
        return nuevo

    def obtener(self, suscripcion_id):
        return self.filas.get(suscripcion_id)

    def cambiar_estado(self, suscripcion_id, desde, hacia, motivo=''):
        fila = self.filas[suscripcion_id]
        if fila.estado != desde:
            return False
        self.filas[suscripcion_id] = replace(fila, estado=hacia)
        self.motivos[suscripcion_id] = motivo
        return True

    def fijar_proxima(self, suscripcion_id, fecha):
        self.filas[suscripcion_id] = replace(self.filas[suscripcion_id], proxima_entrega=fecha)

    def avanzar_si(self, suscripcion_id, ciclo_fecha, nueva):
        fila = self.filas[suscripcion_id]
        if fila.proxima_entrega != ciclo_fecha:
            return False
        self.filas[suscripcion_id] = replace(fila, proxima_entrega=nueva)
        return True

    def cambiar_datos(self, suscripcion_id, variante=None, entrega=None, metodo_pago=None):
        fila = self.filas[suscripcion_id]
        if variante:
            fila = replace(fila, producto_id=variante.producto_id, sku=variante.sku, nombre_producto=variante.nombre)
        if entrega:
            fila = replace(fila, entrega=entrega)
        if metodo_pago:
            fila = replace(fila, metodo_pago=metodo_pago)
        self.filas[suscripcion_id] = fila

    def ids_por_avisar(self, hasta):
        return [s.id for s in self.filas.values() if s.estado == E.ACTIVA and s.proxima_entrega <= hasta]

    def ids_con_ciclo_vencido(self, hoy):
        return [s.id for s in self.filas.values()
                if s.estado in (E.ACTIVA, E.PENDIENTE) and s.proxima_entrega and s.proxima_entrega < hoy]

    def planes_activos_de(self, usuario_id):
        return [s.plan.datos for s in self.filas.values() if s.usuario_id == usuario_id and s.estado == E.ACTIVA]

    # Ayuda de los tests
    def con(self, suscripcion_id, **cambios):
        self.filas[suscripcion_id] = replace(self.filas[suscripcion_id], **cambios)


class PedidosFalsos(PedidosSuscripcion):
    def __init__(self):
        self.pedidos = {}
        self.costos = {}
        self.motivos = {}

    def crear(self, suscripcion, ciclo_fecha, costo_envio):
        if self.del_ciclo(suscripcion.id, ciclo_fecha):
            return None
        nuevo = 100 + len(self.pedidos)
        self.pedidos[nuevo] = PedidoCiclo(nuevo, suscripcion.id, ciclo_fecha, EstadoPedido.PENDIENTE)
        self.costos[nuevo] = costo_envio
        return nuevo

    def del_ciclo(self, suscripcion_id, ciclo_fecha):
        return next((p for p in self.pedidos.values() if p.suscripcion_id == suscripcion_id
                     and p.ciclo_fecha == ciclo_fecha and p.estado != EstadoPedido.CANCELADO), None)

    def pendientes(self, suscripcion_id):
        return [p for p in self.pedidos.values()
                if p.suscripcion_id == suscripcion_id and p.estado == EstadoPedido.PENDIENTE]

    def ciclo_de(self, orden_id):
        return self.pedidos.get(orden_id)

    def cancelar(self, orden_id, motivo):
        pedido = self.pedidos[orden_id]
        if pedido.estado != EstadoPedido.PENDIENTE:
            return False
        self.pedidos[orden_id] = replace(pedido, estado=EstadoPedido.CANCELADO)
        self.motivos[orden_id] = motivo
        return True

    def pagar(self, orden_id):
        self.pedidos[orden_id] = replace(self.pedidos[orden_id], estado=EstadoPedido.PAGADO)


class CatalogoFalso(CatalogoSuscripciones):
    VARIANTES = {
        ('catuai', 'CAT-GRANO'): VarianteElegible('catuai', 'CAT-GRANO', 'Catuai - Grano', 'Cafés', 10, True),
        ('catuai', 'CAT-MOLIDO'): VarianteElegible('catuai', 'CAT-MOLIDO', 'Catuai - Molido', 'Cafés', 0, True),
        ('taza', 'TAZA-1'): VarianteElegible('taza', 'TAZA-1', 'Taza', 'Accesorios', 5, True),
        ('oculto', 'OC-1'): VarianteElegible('oculto', 'OC-1', 'Oculto', 'Cafés', 5, False),
    }

    def variante(self, producto_id, sku):
        return self.VARIANTES.get((producto_id, sku))


class DespachoFalso(CotizadorDespacho):
    def __init__(self, costo=Decimal('3500'), caido=False):
        self.valor, self.caido = costo, caido

    def costo(self, suscripcion):
        if self.caido:
            raise DespachoNoDisponible('El courier no respondió.')
        return self.valor


class ReglasFalsas(ReglasCompra):
    def validar(self, metodo_pago, entrega):
        if metodo_pago not in ('TRANSBANK', 'TRANSFERENCIA'):
            raise CompraNoPermitida('Ese medio de pago no está disponible en esta tienda.')


class NotificadorFalso(NotificadorSuscripciones):
    def __init__(self):
        self.enviados = []

    def notificar(self, suscripcion_id, evento, orden_id=None):
        self.enviados.append((suscripcion_id, evento, orden_id))


ENTREGA = Entrega('CHILEXPRESS', {'comuna': 'Santiago', 'calle': 'Uno', 'numero': '1'}, 'Ana Pérez', '+56912345678')


def solicitud(**cambios):
    datos = dict(plan_id=1, producto_id='catuai', sku='CAT-GRANO', entrega=ENTREGA, metodo_pago='TRANSBANK',
                 acepta_terminos=True)
    return SolicitudSuscripcion(**{**datos, **cambios})


class Base(SimpleTestCase):
    def setUp(self):
        self.planes = PlanesFalsos(plan(), plan(nombre='Inactivo', activo=False),
                                   plan(nombre='Gratis', envio_gratis=True, frecuencia_semanas=2))
        self.suscripciones = SuscripcionesFalsas(self.planes)
        self.pedidos = PedidosFalsos()
        self.despacho = DespachoFalso()
        self.notificador = NotificadorFalso()
        self.catalogo = CatalogoFalso()
        self.reglas = ReglasFalsas()
        comunes = (self.suscripciones, self.pedidos, self.despacho, self.notificador)
        self.suscribirse = Suscribirse(self.planes, self.catalogo, self.reglas, *comunes)
        self.al_pagar = AlPagarPedido(self.suscripciones, self.pedidos, self.notificador)
        self.procesar = ProcesarCiclos(*comunes)
        self.acciones = AccionesSuscripcion(self.catalogo, self.reglas, *comunes)

    def suscribir(self, usuario=ANA, **cambios):
        return self.suscribirse.ejecutar(usuario, solicitud(**cambios), HOY, DIAS)

    def activa(self, usuario=ANA, **cambios):
        """Suscripción con el primer ciclo pagado; devuelve su id."""
        iniciada = self.suscribir(usuario, **cambios)
        self.pedidos.pagar(iniciada.orden_id)
        self.al_pagar.ejecutar(iniciada.orden_id)
        self.notificador.enviados.clear()
        return iniciada.suscripcion_id

    def suscripcion(self, suscripcion_id):
        return self.suscripciones.obtener(suscripcion_id)


class SuscribirseTests(Base):
    def test_queda_pendiente_con_el_pedido_del_primer_ciclo_a_dias_de_aviso(self):
        iniciada = self.suscribir()
        suscripcion = self.suscripcion(iniciada.suscripcion_id)
        self.assertEqual(suscripcion.estado, E.PENDIENTE)
        self.assertEqual(suscripcion.proxima_entrega, HOY + timedelta(days=DIAS))
        self.assertEqual(self.pedidos.ciclo_de(iniciada.orden_id).ciclo_fecha, HOY + timedelta(days=DIAS))
        self.assertEqual(self.pedidos.costos[iniciada.orden_id], Decimal('3500'))

    def test_con_envio_gratis_el_despacho_del_ciclo_es_cero(self):
        iniciada = self.suscribir(plan_id=3)
        self.assertEqual(self.pedidos.costos[iniciada.orden_id], Decimal('0'))

    def test_rechaza_sin_terminos_plan_inactivo_o_inexistente(self):
        with self.assertRaises(TerminosNoAceptados):
            self.suscribir(acepta_terminos=False)
        for plan_id in (2, 99):
            with self.subTest(plan_id=plan_id), self.assertRaises(PlanNoDisponible):
                self.suscribir(plan_id=plan_id)

    def test_exige_el_nombre_y_el_telefono_de_quien_recibe(self):
        # RF-02.3: igual que el checkout, también para retirar en el local
        for entrega in (replace(ENTREGA, destinatario=''), replace(ENTREGA, telefono=' '), Entrega('RETIRO_LOCAL')):
            with self.subTest(entrega=entrega), self.assertRaises(DestinatarioIncompleto):
                self.suscribir(entrega=entrega)

    def test_solo_variantes_elegibles_disponibles_y_con_stock(self):
        with self.assertRaisesMessage(VarianteNoElegible, 'Ese producto no es parte del plan.'):
            self.suscribir(producto_id='taza', sku='TAZA-1')
        for producto_id, sku in (('oculto', 'OC-1'), ('catuai', 'NO-EXISTE')):
            with self.subTest(sku=sku), self.assertRaisesMessage(VarianteNoElegible, 'no está disponible'):
                self.suscribir(producto_id=producto_id, sku=sku)
        with self.assertRaises(SinStockSuscripcion):
            self.suscribir(sku='CAT-MOLIDO')
        self.assertEqual(self.suscripciones.filas, {})

    def test_el_medio_de_pago_debe_estar_habilitado(self):
        with self.assertRaises(CompraNoPermitida):
            self.suscribir(metodo_pago='PAYPAL')


class AlPagarTests(Base):
    def test_el_primer_pago_activa_y_la_proxima_entrega_queda_a_n_semanas_del_ciclo(self):
        iniciada = self.suscribir()
        self.pedidos.pagar(iniciada.orden_id)
        self.al_pagar.ejecutar(iniciada.orden_id)
        suscripcion = self.suscripcion(iniciada.suscripcion_id)
        self.assertEqual(suscripcion.estado, E.ACTIVA)
        self.assertEqual(suscripcion.proxima_entrega, HOY + timedelta(days=DIAS, weeks=4))
        self.assertEqual(self.notificador.enviados,
                         [(iniciada.suscripcion_id, EventoSuscripcion.ACTIVADA, iniciada.orden_id)])

    def test_un_aviso_repetido_no_avanza_dos_veces_ni_reenvia_el_correo(self):
        iniciada = self.suscribir()
        self.pedidos.pagar(iniciada.orden_id)
        self.al_pagar.ejecutar(iniciada.orden_id)
        self.al_pagar.ejecutar(iniciada.orden_id)
        self.assertEqual(self.suscripcion(iniciada.suscripcion_id).proxima_entrega,
                         HOY + timedelta(days=DIAS, weeks=4))
        self.assertEqual(len(self.notificador.enviados), 1)

    def test_un_pedido_que_no_es_de_suscripcion_se_ignora(self):
        self.al_pagar.ejecutar(999)
        self.assertEqual(self.notificador.enviados, [])


class ProcesarCiclosTests(Base):
    def test_crea_el_pedido_y_avisa_dias_antes_y_no_lo_repite(self):
        sid = self.activa()
        ciclo = self.suscripcion(sid).proxima_entrega
        antes = ciclo - timedelta(days=DIAS + 1)
        self.assertEqual(self.procesar.ejecutar(antes, DIAS).avisados, [])
        resumen = self.procesar.ejecutar(ciclo - timedelta(days=DIAS), DIAS)
        self.assertEqual(resumen.avisados, [sid])
        pedido = self.pedidos.del_ciclo(sid, ciclo)
        self.assertEqual(self.notificador.enviados, [(sid, EventoSuscripcion.AVISO_COBRO, pedido.orden_id)])
        # Correrla otra vez (o al día siguiente) no crea otro pedido ni otro aviso
        self.procesar.ejecutar(ciclo - timedelta(days=DIAS), DIAS)
        self.procesar.ejecutar(ciclo - timedelta(days=1), DIAS)
        self.assertEqual(len(self.pedidos.pendientes(sid)), 1)
        self.assertEqual(len(self.notificador.enviados), 1)

    def test_pagado_a_tiempo_pasa_al_ciclo_siguiente(self):
        sid = self.activa()
        ciclo = self.suscripcion(sid).proxima_entrega
        self.procesar.ejecutar(ciclo - timedelta(days=DIAS), DIAS)
        pedido = self.pedidos.del_ciclo(sid, ciclo)
        self.pedidos.pagar(pedido.orden_id)
        self.al_pagar.ejecutar(pedido.orden_id)
        self.assertEqual(self.suscripcion(sid).proxima_entrega, ciclo + timedelta(weeks=4))
        self.assertEqual(self.procesar.ejecutar(ciclo + timedelta(days=1), DIAS).no_pagados, [])

    def test_sin_pago_al_terminar_el_dia_el_ciclo_no_se_entrega_y_se_avisa(self):
        sid = self.activa()
        ciclo = self.suscripcion(sid).proxima_entrega
        self.procesar.ejecutar(ciclo - timedelta(days=DIAS), DIAS)
        pedido = self.pedidos.del_ciclo(sid, ciclo)
        self.notificador.enviados.clear()
        self.assertEqual(self.procesar.ejecutar(ciclo, DIAS).no_pagados, [])  # aún puede pagar ese día
        resumen = self.procesar.ejecutar(ciclo + timedelta(days=1), DIAS)
        self.assertEqual(resumen.no_pagados, [sid])
        self.assertEqual(self.pedidos.pedidos[pedido.orden_id].estado, EstadoPedido.CANCELADO)
        self.assertEqual(self.pedidos.motivos[pedido.orden_id], MOTIVO_CICLO_NO_PAGADO)
        self.assertEqual(self.suscripcion(sid).proxima_entrega, ciclo + timedelta(weeks=4))
        self.assertEqual(self.suscripcion(sid).estado, E.ACTIVA)
        self.assertEqual(self.notificador.enviados, [(sid, EventoSuscripcion.CICLO_NO_PAGADO, None)])
        self.procesar.ejecutar(ciclo + timedelta(days=1), DIAS)
        self.assertEqual(len(self.notificador.enviados), 1)

    def test_si_la_tarea_no_corrio_cierra_todos_los_ciclos_atrasados_con_un_solo_aviso(self):
        sid = self.activa()
        ciclo = self.suscripcion(sid).proxima_entrega
        resumen = self.procesar.ejecutar(ciclo + timedelta(weeks=9), DIAS)
        self.assertEqual(self.suscripcion(sid).proxima_entrega, ciclo + timedelta(weeks=12))
        self.assertEqual(resumen.no_pagados, [sid])
        self.assertEqual([e[1] for e in self.notificador.enviados].count(EventoSuscripcion.CICLO_NO_PAGADO), 1)

    def test_sin_pagar_el_primer_ciclo_la_suscripcion_no_se_activa(self):
        iniciada = self.suscribir()
        ciclo = self.suscripcion(iniciada.suscripcion_id).proxima_entrega
        self.procesar.ejecutar(ciclo, DIAS)
        self.assertEqual(self.suscripcion(iniciada.suscripcion_id).estado, E.PENDIENTE)
        resumen = self.procesar.ejecutar(ciclo + timedelta(days=1), DIAS)
        self.assertEqual(resumen.no_activadas, [iniciada.suscripcion_id])
        self.assertEqual(self.suscripcion(iniciada.suscripcion_id).estado, E.CANCELADA)
        self.assertEqual(self.pedidos.motivos[iniciada.orden_id], MOTIVO_PRIMER_PAGO_NO_RECIBIDO)
        self.assertEqual(self.notificador.enviados, [(iniciada.suscripcion_id, EventoSuscripcion.NO_ACTIVADA, None)])

    def test_si_el_despacho_no_se_puede_cotizar_se_reintenta_al_dia_siguiente(self):
        sid = self.activa()
        ciclo = self.suscripcion(sid).proxima_entrega
        self.despacho.caido = True
        resumen = self.procesar.ejecutar(ciclo - timedelta(days=DIAS), DIAS)
        self.assertEqual((resumen.avisados, resumen.con_error), ([], [sid]))
        self.despacho.caido = False
        self.assertEqual(self.procesar.ejecutar(ciclo - timedelta(days=DIAS - 1), DIAS).avisados, [sid])

    def test_pausadas_y_canceladas_no_reciben_avisos(self):
        sid = self.activa()
        self.acciones.pausar(ANA, sid)
        ciclo = self.suscripcion(sid).proxima_entrega
        self.assertEqual(self.procesar.ejecutar(ciclo - timedelta(days=DIAS), DIAS).avisados, [])
        self.assertEqual(self.procesar.ejecutar(ciclo + timedelta(days=5), DIAS).no_pagados, [])


class AccionesTests(Base):
    def test_solo_el_dueno_actua_sobre_su_suscripcion(self):
        sid = self.activa()
        for accion in (lambda: self.acciones.pausar(BETO, sid), lambda: self.acciones.cancelar(BETO, sid),
                       lambda: self.acciones.saltar(BETO, sid), lambda: self.acciones.pausar(ANA, 999)):
            with self.assertRaises(SuscripcionNoEncontrada):
                accion()
        self.assertEqual(self.suscripcion(sid).estado, E.ACTIVA)

    def test_pausar_cancela_el_pedido_sin_pagar_y_reanudar_recalcula_la_entrega(self):
        sid = self.activa()
        ciclo = self.suscripcion(sid).proxima_entrega
        self.procesar.ejecutar(ciclo - timedelta(days=DIAS), DIAS)
        pedido = self.pedidos.del_ciclo(sid, ciclo)
        self.acciones.pausar(ANA, sid)
        self.assertEqual(self.suscripcion(sid).estado, E.PAUSADA)
        self.assertEqual(self.pedidos.pedidos[pedido.orden_id].estado, EstadoPedido.CANCELADO)
        # Reanuda después de la fecha: la entrega queda para cuando alcanza el aviso
        proxima = self.acciones.reanudar(ANA, sid, ciclo + timedelta(days=10), DIAS)
        self.assertEqual(proxima, ciclo + timedelta(days=10 + DIAS))
        self.assertEqual(self.suscripcion(sid).estado, E.ACTIVA)
        self.assertEqual([e[1] for e in self.notificador.enviados],
                         [EventoSuscripcion.AVISO_COBRO, EventoSuscripcion.PAUSADA, EventoSuscripcion.REANUDADA])
        with self.assertRaises(AccionNoPermitida):
            self.acciones.reanudar(ANA, sid, HOY, DIAS)

    def test_pausar_no_toca_un_ciclo_ya_pagado(self):
        sid = self.activa()
        ciclo = self.suscripcion(sid).proxima_entrega
        self.procesar.ejecutar(ciclo - timedelta(days=DIAS), DIAS)
        pedido = self.pedidos.del_ciclo(sid, ciclo)
        self.pedidos.pagar(pedido.orden_id)
        self.acciones.pausar(ANA, sid)
        self.assertEqual(self.pedidos.pedidos[pedido.orden_id].estado, EstadoPedido.PAGADO)

    def test_saltar_corre_un_ciclo_y_cancela_su_pedido_sin_pagar(self):
        sid = self.activa()
        ciclo = self.suscripcion(sid).proxima_entrega
        self.assertEqual(self.acciones.saltar(ANA, sid), ciclo + timedelta(weeks=4))
        self.procesar.ejecutar(ciclo + timedelta(weeks=4) - timedelta(days=DIAS), DIAS)
        pedido = self.pedidos.del_ciclo(sid, ciclo + timedelta(weeks=4))
        self.assertEqual(self.acciones.saltar(ANA, sid), ciclo + timedelta(weeks=8))
        self.assertEqual(self.pedidos.motivos[pedido.orden_id], MOTIVO_CICLO_SALTADO)

    def test_no_se_salta_un_ciclo_ya_pagado(self):
        sid = self.activa()
        ciclo = self.suscripcion(sid).proxima_entrega
        self.procesar.ejecutar(ciclo - timedelta(days=DIAS), DIAS)
        self.pedidos.pagar(self.pedidos.del_ciclo(sid, ciclo).orden_id)
        with self.assertRaises(CicloYaPagado):
            self.acciones.saltar(ANA, sid)

    def test_adelantar_trae_la_entrega_a_hoy_y_pide_el_pago_al_tiro(self):
        sid = self.activa()
        dia = HOY + timedelta(days=5)
        orden_id = self.acciones.adelantar(ANA, sid, dia)
        self.assertEqual(self.suscripcion(sid).proxima_entrega, dia)
        self.assertEqual(self.pedidos.ciclo_de(orden_id).ciclo_fecha, dia)
        self.assertEqual(self.notificador.enviados, [(sid, EventoSuscripcion.AVISO_COBRO, orden_id)])
        with self.assertRaises(PedidoEnCurso):
            self.acciones.adelantar(ANA, sid, dia)
        # Al pagarlo, el siguiente ciclo se cuenta desde hoy
        self.pedidos.pagar(orden_id)
        self.al_pagar.ejecutar(orden_id)
        self.assertEqual(self.suscripcion(sid).proxima_entrega, dia + timedelta(weeks=4))

    def test_cancelar_es_definitivo_y_cancela_lo_que_no_se_pago(self):
        iniciada = self.suscribir()
        self.acciones.cancelar(ANA, iniciada.suscripcion_id)
        self.assertEqual(self.suscripcion(iniciada.suscripcion_id).estado, E.CANCELADA)
        self.assertEqual(self.pedidos.pedidos[iniciada.orden_id].estado, EstadoPedido.CANCELADO)
        for accion in (lambda: self.acciones.cancelar(ANA, iniciada.suscripcion_id),
                       lambda: self.acciones.pausar(ANA, iniciada.suscripcion_id),
                       lambda: self.acciones.cambiar(ANA, iniciada.suscripcion_id, CambiosSuscripcion(sku='X'))):
            with self.assertRaises(AccionNoPermitida):
                accion()

    def test_cambiar_valida_la_variante_y_el_medio_de_pago(self):
        sid = self.activa()
        with self.assertRaises(SinStockSuscripcion):
            self.acciones.cambiar(ANA, sid, CambiosSuscripcion(sku='CAT-MOLIDO'))
        with self.assertRaises(CompraNoPermitida):
            self.acciones.cambiar(ANA, sid, CambiosSuscripcion(metodo_pago='PAYPAL'))
        with self.assertRaises(DestinatarioIncompleto):
            self.acciones.cambiar(ANA, sid, CambiosSuscripcion(entrega=Entrega('RETIRO_LOCAL')))
        nueva = Entrega('RETIRO_LOCAL', {}, 'Ana Pérez', '+56912345678')
        self.acciones.cambiar(ANA, sid, CambiosSuscripcion(entrega=nueva, metodo_pago='TRANSFERENCIA'))
        suscripcion = self.suscripcion(sid)
        self.assertEqual((suscripcion.entrega, suscripcion.metodo_pago), (nueva, 'TRANSFERENCIA'))
        self.assertEqual(suscripcion.sku, 'CAT-GRANO')


class BeneficiosTests(Base):
    def test_solo_las_activas_dan_beneficios_y_vale_el_mayor_descuento(self):
        self.planes.planes[1] = PlanRegistrado(1, plan(descuento=10))
        self.planes.planes[3] = PlanRegistrado(3, plan(descuento=15, envio_gratis=True, envio_gratis_compras=True))
        self.assertEqual(beneficios_de(self.suscripciones, ANA).descuento, 0)
        self.suscribir()  # pendiente: aún no da beneficios
        self.assertEqual(beneficios_de(self.suscripciones, ANA).descuento, 0)
        self.activa()
        self.assertEqual(beneficios_de(self.suscripciones, ANA).descuento, 10)
        sid = self.activa(plan_id=3)
        beneficios = beneficios_de(self.suscripciones, ANA)
        self.assertEqual((beneficios.descuento, beneficios.envio_gratis), (15, True))
        self.acciones.pausar(ANA, sid)
        self.assertEqual(beneficios_de(self.suscripciones, ANA).envio_gratis, False)
        self.assertEqual(beneficios_de(self.suscripciones, None).descuento, 0)
