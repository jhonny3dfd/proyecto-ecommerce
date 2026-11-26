"""API de suscripciones (pedido de un cliente, opcional): planes, suscribirse, ciclos, Mis suscripciones y panel.

El catálogo usa una base Mongo temporal (usar_mongo_de_prueba): nunca la de desarrollo.
"""
from datetime import datetime, timedelta, timezone as tz
from unittest.mock import patch

from django.core import mail
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from ecommerce.domain.suscripciones import EstadoSuscripcion
from ecommerce.infrastructure.usuarios.tests.factories import create_user

from ..catalogo.documents import Producto, Variante
from ..catalogo.tests import usar_mongo_de_prueba
from .models import ConfiguracionGlobal, OrdenCompra, PlanSuscripcion, Suscripcion
from .repositorio_suscripciones import DjangoPedidosSuscripcion, DjangoRepositorioSuscripciones
from .servicio_suscripciones import catalogo_suscripciones
from .tests import DESTINATARIO, habilitar_medios_pago
from .views import confirmar_pago

INICIAR_TRANSBANK = 'ecommerce.infrastructure.ventas.adapters.transbank_adapter.TransbankWebpayAdapter.iniciar_transaccion'
PLAN = {'nombre': 'Café del mes', 'precio': 14990, 'frecuencia_semanas': 4, 'categorias': ['cafés'],
        'beneficios': ['Café recién tostado', 'Envío gratis']}


class SuscripcionesAPIBase(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        usar_mongo_de_prueba(cls)

    def setUp(self):
        Producto._get_collection().delete_many({})
        self.config = ConfiguracionGlobal.objects.create(pk=1, nombre_tienda='Lumière', suscripciones_activas=True,
                                                         retiro_en_local_activo=True)
        habilitar_medios_pago('TRANSFERENCIA', 'TRANSBANK')
        ahora = datetime.now(tz.utc)
        self.cafe = Producto(nombre='Catuai Amarillo', categoria='Cafés', activo=True, publicado=True,
                             fecha_creacion=ahora, variantes=[
                                 Variante(sku='CAT-GRANO', precio=12990, stock=10,
                                          atributos_variables={'molienda': 'Grano'}),
                                 Variante(sku='CAT-MOLIDO', precio=12990, stock=0,
                                          atributos_variables={'molienda': 'Molido'})])
        self.cafe.save()
        self.taza = Producto(nombre='Taza', categoria='Accesorios', activo=True, publicado=True, fecha_creacion=ahora,
                             variantes=[Variante(sku='TAZA-1', precio=5990, stock=5)])
        self.taza.save()
        self.oculto = Producto(nombre='Bourbon', categoria='Cafés', activo=True, publicado=False,
                               fecha_creacion=ahora, variantes=[Variante(sku='BOU-1', precio=16490, stock=5)])
        self.oculto.save()
        self.plan = PlanSuscripcion.objects.create(**PLAN, orden=1)
        self.admin = create_user('admin-sus@example.test', rol='ADMIN')
        self.ana = create_user('ana-sus@example.test', nombre='Ana', apellido_paterno='Pérez')
        self.beto = create_user('beto-sus@example.test')

    def solicitud(self, **cambios):
        return {'plan_id': self.plan.id, 'producto_mongo_id': str(self.cafe.id), 'variante_sku': 'CAT-GRANO',
                'proveedor_logistico': 'RETIRO_LOCAL', 'direccion_envio_snapshot': {}, 'metodo_pago': 'TRANSFERENCIA',
                'acepta_terminos': True, **DESTINATARIO, **cambios}

    def suscribir(self, usuario=None, **cambios):
        self.client.force_authenticate(usuario or self.ana)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse('suscripciones'), self.solicitud(**cambios), format='json')

    def pagar(self, orden_id):
        """La tienda valida la transferencia: pasa por ConfirmarPago, como cualquier pago."""
        with self.captureOnCommitCallbacks(execute=True):
            return confirmar_pago().aprobar(orden_id)


class ModuloApagadoTests(SuscripcionesAPIBase):
    def test_apagado_no_hay_pagina_ni_se_puede_suscribir(self):
        self.config.suscripciones_activas = False
        self.config.save()
        self.assertEqual(self.client.get(reverse('suscripciones-planes')).status_code, 404)
        self.assertEqual(self.client.get(reverse('suscripciones-plan-opciones', args=[self.plan.id])).status_code, 404)
        self.assertEqual(self.suscribir().status_code, 404)
        self.assertFalse(Suscripcion.objects.exists())
        self.assertFalse(self.client.get(reverse('configuracion-global')).data['suscripciones_activas'])

    def test_por_defecto_viene_apagado(self):
        self.assertFalse(ConfiguracionGlobal(nombre_tienda='Nueva').suscripciones_activas)


class PlanesTests(SuscripcionesAPIBase):
    def test_el_admin_crea_un_segundo_plan_y_la_pagina_muestra_solo_los_activos_en_su_orden(self):
        self.client.force_authenticate(self.admin)
        respuesta = self.client.post(reverse('admin-suscripciones-planes'), {
            **PLAN, 'nombre': 'Café doble', 'precio': 26990, 'unidades': 2, 'descuento': 10}, format='json')
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        segundo = respuesta.data['id']
        self.client.post(reverse('admin-suscripciones-planes'), {**PLAN, 'nombre': 'Inactivo', 'activo': False},
                         format='json')
        orden = [segundo, self.plan.id, PlanSuscripcion.objects.get(nombre='Inactivo').id]
        self.assertEqual(self.client.put(reverse('admin-suscripciones-planes-orden'), {'ids': orden},
                                         format='json').status_code, 200)
        self.client.force_authenticate(None)
        planes = self.client.get(reverse('suscripciones-planes')).data['planes']
        self.assertEqual([p['nombre'] for p in planes], ['Café doble', 'Café del mes'])
        self.assertEqual(planes[0]['frecuencia_texto'], 'Cada 4 semanas')
        # El público no ve qué productos elige el admin ni cuántos suscriptores hay
        self.assertNotIn('categorias', planes[0])
        self.assertNotIn('suscripciones', planes[0])

    def test_el_plan_se_valida_con_las_reglas_del_dominio(self):
        self.client.force_authenticate(self.admin)
        respuesta = self.client.post(reverse('admin-suscripciones-planes'),
                                     {**PLAN, 'precio': 0, 'categorias': [], 'productos': []}, format='json')
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(set(respuesta.data['errores']), {'precio', 'productos'})

    def test_un_plan_con_suscripciones_no_se_borra(self):
        self.suscribir()
        self.client.force_authenticate(self.admin)
        respuesta = self.client.delete(reverse('admin-suscripciones-plan', args=[self.plan.id]))
        self.assertEqual(respuesta.status_code, 409)
        self.assertIn('desactívalo', respuesta.data['detail'])
        libre = PlanSuscripcion.objects.create(**{**PLAN, 'nombre': 'Libre'})
        self.assertEqual(self.client.delete(reverse('admin-suscripciones-plan', args=[libre.id])).status_code, 204)

    def test_solo_el_admin_gestiona_planes_y_ve_suscriptores(self):
        for usuario, codigo in ((None, 401), (self.ana, 403)):
            self.client.force_authenticate(usuario)
            with self.subTest(usuario=usuario):
                self.assertEqual(self.client.post(reverse('admin-suscripciones-planes'), PLAN,
                                                  format='json').status_code, codigo)
                self.assertEqual(self.client.get(reverse('admin-suscripciones')).status_code, codigo)

    def test_opciones_por_categoria_sin_distinguir_mayusculas_y_por_producto_puntual(self):
        opciones = self.client.get(reverse('suscripciones-plan-opciones', args=[self.plan.id])).data['productos']
        # Bourbon no está publicado; la taza no es de la categoría
        self.assertEqual([p['nombre'] for p in opciones], ['Catuai Amarillo'])
        self.assertEqual([(v['sku'], v['disponible']) for v in opciones[0]['variantes']],
                         [('CAT-GRANO', True), ('CAT-MOLIDO', False)])
        self.plan.productos = [str(self.taza.id)]
        self.plan.save()
        opciones = self.client.get(reverse('suscripciones-plan-opciones', args=[self.plan.id])).data['productos']
        self.assertEqual([p['nombre'] for p in opciones], ['Catuai Amarillo', 'Taza'])


class SuscribirseTests(SuscripcionesAPIBase):
    def test_un_invitado_debe_iniciar_sesion(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(reverse('suscripciones'), self.solicitud(), format='json').status_code, 401)

    def test_queda_pendiente_con_el_pedido_del_primer_ciclo_y_los_datos_para_transferir(self):
        respuesta = self.suscribir(estado='ACTIVA', proxima_entrega='2020-01-01')
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        suscripcion = Suscripcion.objects.get(pk=respuesta.data['suscripcion_id'])
        # El navegador no fija el estado ni las fechas
        self.assertEqual(suscripcion.estado, EstadoSuscripcion.PENDIENTE.value)
        ciclo = timezone.localdate() + timedelta(days=3)
        self.assertEqual(suscripcion.proxima_entrega, ciclo)
        self.assertEqual(suscripcion.nombre_producto, 'Catuai Amarillo - Grano')
        orden = OrdenCompra.objects.get(pk=respuesta.data['orden_id'])
        self.assertEqual((orden.suscripcion_id, orden.ciclo_fecha, orden.estado), (suscripcion.id, ciclo, 'PENDIENTE'))
        self.assertEqual((orden.subtotal, orden.costo_envio, orden.total_final), (14990, 0, 14990))
        self.assertEqual(orden.detalles.get().cantidad, 1)
        # El plazo para transferir es el día de la entrega, no las 48 h de una compra normal
        self.assertEqual(timezone.localtime(respuesta.data['instrucciones_pago']['vence']).date(), ciclo)
        self.assertIsNone(orden.fecha_limite_pago)

    def test_rechaza_variante_sin_stock_no_elegible_no_publicada_y_sin_terminos(self):
        casos = [({'variante_sku': 'CAT-MOLIDO'}, 'No hay stock suficiente'),
                 ({'producto_mongo_id': str(self.taza.id), 'variante_sku': 'TAZA-1'}, 'no es parte del plan'),
                 ({'producto_mongo_id': str(self.oculto.id), 'variante_sku': 'BOU-1'}, 'no está disponible'),
                 ({'acepta_terminos': False}, 'Términos y Condiciones'),
                 ({'metodo_pago': 'PAYPAL'}, ''),
                 ({'telefono_destinatario': '123'}, 'teléfono chileno')]
        for cambios, mensaje in casos:
            with self.subTest(cambios=cambios):
                respuesta = self.suscribir(**cambios)
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertIn(mensaje, respuesta.data['detail'])
        self.assertFalse(Suscripcion.objects.exists())
        self.assertFalse(OrdenCompra.objects.exists())

    @patch(INICIAR_TRANSBANK, return_value={'exito': True, 'url_pago': 'https://webpay.test/pago', 'token': 'tbk-1'})
    def test_con_webpay_devuelve_la_url_de_pago(self, _iniciar):
        respuesta = self.suscribir(metodo_pago='TRANSBANK')
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.data['url_pago'], 'https://webpay.test/pago?token_ws=tbk-1')
        self.assertEqual(OrdenCompra.objects.get(pk=respuesta.data['orden_id']).id_transaccion_pasarela, 'tbk-1')

    @patch(INICIAR_TRANSBANK, return_value={'exito': False, 'error': 'Webpay no responde'})
    def test_si_la_pasarela_falla_no_queda_nada_a_medias(self, _iniciar):
        respuesta = self.suscribir(metodo_pago='TRANSBANK')
        self.assertEqual(respuesta.status_code, 502)
        self.assertFalse(Suscripcion.objects.exists())
        self.assertFalse(OrdenCompra.objects.exists())


class CicloTests(SuscripcionesAPIBase):
    def test_el_primer_pago_activa_y_avanza_n_semanas_una_sola_vez(self):
        respuesta = self.suscribir()
        orden_id, sid = respuesta.data['orden_id'], respuesta.data['suscripcion_id']
        ciclo = Suscripcion.objects.get(pk=sid).proxima_entrega
        mail.outbox.clear()
        self.assertEqual(self.pagar(orden_id), 'PAGADO')
        suscripcion = Suscripcion.objects.get(pk=sid)
        self.assertEqual(suscripcion.estado, EstadoSuscripcion.ACTIVA.value)
        self.assertEqual(suscripcion.proxima_entrega, ciclo + timedelta(weeks=4))
        self.assertIsNotNone(suscripcion.fecha_activacion)
        asuntos = [correo.subject for correo in mail.outbox]
        self.assertIn('Tu suscripción Café del mes está activa | Lumière', asuntos)
        # Un pago confirmado dos veces no avanza otra vez ni reenvía el correo
        mail.outbox.clear()
        self.assertEqual(self.pagar(orden_id), 'REPETIDO')
        self.assertEqual(Suscripcion.objects.get(pk=sid).proxima_entrega, ciclo + timedelta(weeks=4))
        self.assertEqual(mail.outbox, [])

    def test_un_ciclo_tiene_un_solo_pedido_vigente(self):
        sid = self.suscribir().data['suscripcion_id']
        suscripcion = DjangoRepositorioSuscripciones().obtener(sid)
        pedidos = DjangoPedidosSuscripcion(catalogo_suscripciones())
        self.assertIsNone(pedidos.crear(suscripcion, suscripcion.proxima_entrega, 0))
        self.assertEqual(OrdenCompra.objects.filter(suscripcion_id=sid).count(), 1)
        # Cancelado (no pagado o saltado), el ciclo queda libre
        orden = OrdenCompra.objects.get(suscripcion_id=sid)
        pedidos.cancelar(orden.id, 'prueba')
        self.assertIsNotNone(pedidos.crear(suscripcion, suscripcion.proxima_entrega, 0))

    @patch(INICIAR_TRANSBANK, return_value={'exito': True, 'url_pago': 'https://webpay.test/pago', 'token': 'tbk-2'})
    def test_pagar_un_pedido_pendiente_propio(self, _iniciar):
        orden_id = self.suscribir(metodo_pago='TRANSBANK').data['orden_id']
        self.client.force_authenticate(self.beto)
        self.assertEqual(self.client.post(reverse('pagar-pedido', args=[orden_id])).status_code, 404)
        self.client.force_authenticate(self.ana)
        respuesta = self.client.post(reverse('pagar-pedido', args=[orden_id]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['url_pago'], 'https://webpay.test/pago?token_ws=tbk-2')
        self.pagar(orden_id)
        self.assertEqual(self.client.post(reverse('pagar-pedido', args=[orden_id])).status_code, 409)

    def test_el_panel_distingue_los_pedidos_de_suscripcion(self):
        respuesta = self.suscribir()
        self.client.force_authenticate(self.admin)
        pedidos = self.client.get(reverse('admin-ordenes-list')).data
        pedidos = pedidos['results'] if isinstance(pedidos, dict) else pedidos
        pedido = next(p for p in pedidos if p['id'] == respuesta.data['orden_id'])
        self.assertEqual(pedido['suscripcion'], respuesta.data['suscripcion_id'])
        self.assertIsNotNone(pedido['ciclo_fecha'])


class MisSuscripcionesTests(SuscripcionesAPIBase):
    def test_cada_cliente_ve_y_cambia_solo_las_suyas(self):
        sid = self.suscribir().data['suscripcion_id']
        self.client.force_authenticate(self.beto)
        self.assertEqual(self.client.get(reverse('suscripciones-mias')).data['suscripciones'], [])
        for metodo, url in (('get', reverse('suscripcion', args=[sid])),
                            ('post', reverse('suscripcion-accion', args=[sid, 'cancelar'])),
                            ('patch', reverse('suscripcion', args=[sid]))):
            with self.subTest(metodo=metodo):
                self.assertEqual(getattr(self.client, metodo)(url, {}, format='json').status_code, 404)
        self.assertEqual(Suscripcion.objects.get(pk=sid).estado, EstadoSuscripcion.PENDIENTE.value)

    def test_pausar_reanudar_y_cancelar_desde_la_cuenta(self):
        respuesta = self.suscribir()
        sid = respuesta.data['suscripcion_id']
        self.pagar(respuesta.data['orden_id'])
        self.client.force_authenticate(self.ana)
        mias = self.client.get(reverse('suscripciones-mias')).data['suscripciones']
        self.assertEqual(mias[0]['acciones'], ['PAUSAR', 'SALTAR', 'ADELANTAR', 'CANCELAR', 'CAMBIAR'])
        with self.captureOnCommitCallbacks(execute=True):
            pausada = self.client.post(reverse('suscripcion-accion', args=[sid, 'pausar']))
        self.assertEqual(pausada.data['estado'], 'PAUSADA')
        self.assertIn('Pausaste tu suscripción Café del mes | Lumière', [c.subject for c in mail.outbox])
        self.assertEqual(self.client.post(reverse('suscripcion-accion', args=[sid, 'pausar'])).status_code, 400)
        self.assertEqual(self.client.post(reverse('suscripcion-accion', args=[sid, 'reanudar'])).data['estado'],
                         'ACTIVA')
        cancelada = self.client.post(reverse('suscripcion-accion', args=[sid, 'cancelar']))
        self.assertEqual(cancelada.data['estado'], 'CANCELADA')
        self.assertEqual(cancelada.data['acciones'], [])
        self.assertEqual(self.client.post(reverse('suscripcion-accion', args=[sid, 'otra'])).status_code, 404)

    def test_adelantar_crea_el_pedido_del_ciclo_para_hoy(self):
        respuesta = self.suscribir()
        sid = respuesta.data['suscripcion_id']
        self.pagar(respuesta.data['orden_id'])
        self.client.force_authenticate(self.ana)
        with self.captureOnCommitCallbacks(execute=True):
            datos = self.client.post(reverse('suscripcion-accion', args=[sid, 'adelantar'])).data
        self.assertEqual(datos['proxima_entrega'], timezone.localdate())
        self.assertEqual(datos['pedido_pendiente']['ciclo_fecha'], timezone.localdate())
        self.assertTrue(any(c.subject.startswith('Paga tu próxima entrega') for c in mail.outbox))

    def test_cambiar_la_variante_valida_el_stock(self):
        sid = self.suscribir().data['suscripcion_id']
        url = reverse('suscripcion', args=[sid])
        self.assertEqual(self.client.patch(url, {'variante_sku': 'CAT-MOLIDO'}, format='json').status_code, 400)
        self.cafe.variantes[1].stock = 5
        self.cafe.save()
        self.assertEqual(self.client.patch(url, {'variante_sku': 'CAT-MOLIDO'}, format='json').data['producto'],
                         'Catuai Amarillo - Molido')


class PanelSuscriptoresTests(SuscripcionesAPIBase):
    def test_filtra_por_estado_plan_y_pago_pendiente(self):
        pendiente = self.suscribir().data
        activa = self.suscribir(self.beto).data
        self.pagar(activa['orden_id'])
        self.client.force_authenticate(self.admin)
        url = reverse('admin-suscripciones')
        todas = self.client.get(url).data
        self.assertEqual(todas['count'], 2)
        self.assertEqual({s['cliente']['email'] for s in todas['results']},
                         {'ana-sus@example.test', 'beto-sus@example.test'})
        self.assertEqual([s['id'] for s in self.client.get(url, {'estado': 'ACTIVA'}).data['results']],
                         [activa['suscripcion_id']])
        self.assertEqual([s['id'] for s in self.client.get(url, {'pago_pendiente': '1'}).data['results']],
                         [pendiente['suscripcion_id']])
        self.assertEqual(self.client.get(url, {'plan': self.plan.id + 99}).data['count'], 0)
        self.assertEqual(self.client.get(url, {'estado': 'INVENTADO'}).status_code, 400)


HOY_COMANDO = 'ecommerce.infrastructure.ventas.management.commands.procesar_suscripciones.hoy_local'


class ProcesarSuscripcionesComandoTests(SuscripcionesAPIBase):
    def correr(self, dia):
        from io import StringIO
        from django.core.management import call_command
        salida = StringIO()
        with patch(HOY_COMANDO, return_value=dia), self.captureOnCommitCallbacks(execute=True):
            call_command('procesar_suscripciones', stdout=salida)
        return salida.getvalue()

    def activa(self):
        respuesta = self.suscribir()
        self.pagar(respuesta.data['orden_id'])
        mail.outbox.clear()
        return Suscripcion.objects.get(pk=respuesta.data['suscripcion_id'])

    def test_con_el_modulo_apagado_no_hace_nada(self):
        suscripcion = self.activa()
        self.config.suscripciones_activas = False
        self.config.save()
        self.assertIn('no están activas', self.correr(suscripcion.proxima_entrega))
        self.assertEqual(OrdenCompra.objects.filter(suscripcion=suscripcion).count(), 1)

    def test_avisa_el_cobro_dias_antes_con_el_enlace_y_los_datos_para_transferir_sin_repetir(self):
        suscripcion = self.activa()
        ciclo = suscripcion.proxima_entrega
        self.assertIn('No hay ciclos', self.correr(ciclo - timedelta(days=4)))
        self.assertIn(f'Avisos de cobro enviados (suscripciones): #{suscripcion.id}.', self.correr(ciclo - timedelta(days=3)))
        orden = OrdenCompra.objects.get(suscripcion=suscripcion, ciclo_fecha=ciclo)
        correo, = mail.outbox
        self.assertEqual(correo.subject, 'Paga tu próxima entrega de Café del mes | Lumière')
        self.assertEqual(correo.to, ['ana-sus@example.test'])
        self.assertIn(f'/mis-suscripciones/pagar/{orden.id}', correo.body)
        self.assertIn('$14.990', correo.body)
        self.assertIn('DATOS PARA TRANSFERIR', correo.body.upper())
        self.assertIn(f'/mis-suscripciones/pagar/{orden.id}', correo.alternatives[0][0])
        # Correrla otra vez el mismo día o al siguiente no crea otro pedido ni reenvía el aviso
        self.correr(ciclo - timedelta(days=3))
        self.correr(ciclo - timedelta(days=2))
        self.assertEqual(OrdenCompra.objects.filter(suscripcion=suscripcion, ciclo_fecha=ciclo).count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_sin_pago_el_ciclo_se_cancela_avanza_y_se_avisa_una_vez(self):
        suscripcion = self.activa()
        ciclo = suscripcion.proxima_entrega
        self.correr(ciclo - timedelta(days=3))
        mail.outbox.clear()
        self.assertIn('Ciclos no pagados a tiempo (suscripciones)', self.correr(ciclo + timedelta(days=1)))
        orden = OrdenCompra.objects.get(suscripcion=suscripcion, ciclo_fecha=ciclo)
        self.assertEqual((orden.estado, orden.motivo_cancelacion), ('CANCELADO', 'Ciclo de suscripción no pagado'))
        suscripcion.refresh_from_db()
        self.assertEqual((suscripcion.estado, suscripcion.proxima_entrega), ('ACTIVA', ciclo + timedelta(weeks=4)))
        self.assertEqual([c.subject for c in mail.outbox],
                         ['No recibimos el pago de tu entrega de Café del mes | Lumière'])
        self.correr(ciclo + timedelta(days=1))
        self.assertEqual(len(mail.outbox), 1)

    def test_sin_el_primer_pago_la_suscripcion_no_se_activa(self):
        respuesta = self.suscribir()
        suscripcion = Suscripcion.objects.get(pk=respuesta.data['suscripcion_id'])
        mail.outbox.clear()
        self.correr(suscripcion.proxima_entrega + timedelta(days=1))
        suscripcion.refresh_from_db()
        self.assertEqual((suscripcion.estado, suscripcion.motivo_cancelacion),
                         ('CANCELADA', 'No se recibió el pago del primer ciclo'))
        self.assertEqual(OrdenCompra.objects.get(pk=respuesta.data['orden_id']).estado, 'CANCELADO')
        self.assertEqual([c.subject for c in mail.outbox], ['Tu suscripción Café del mes no se activó | Lumière'])

    def test_los_pedidos_de_suscripcion_no_los_cancela_el_plazo_de_las_transferencias(self):
        from django.core.management import call_command
        from io import StringIO
        respuesta = self.suscribir()
        OrdenCompra.objects.filter(pk=respuesta.data['orden_id']).update(
            fecha_creacion=timezone.now() - timedelta(days=5))
        call_command('cancelar_pagos_vencidos', stdout=StringIO())
        self.assertEqual(OrdenCompra.objects.get(pk=respuesta.data['orden_id']).estado, 'PENDIENTE')


class BeneficiosCheckoutTests(APITestCase):
    """El suscriptor con una suscripción activa recibe en sus compras el descuento y el envío gratis de su plan."""

    def setUp(self):
        from .test_promociones import CheckoutPromocionTests
        CheckoutPromocionTests.setUp(self)
        ConfiguracionGlobal.objects.filter(pk=1).update(suscripciones_activas=True, modo_autenticacion='MIXTO')
        self.cliente = create_user('cliente-beneficios@example.test')
        self.plan = PlanSuscripcion.objects.create(**{**PLAN, 'descuento': 10, 'envio_gratis': True,
                                                      'envio_gratis_compras': True})
        self.suscripcion = Suscripcion.objects.create(
            usuario=self.cliente, plan=self.plan, estado=EstadoSuscripcion.ACTIVA.value, producto_mongo_id='prod1',
            variante_sku='SKU-1', nombre_producto='Producto 1', proveedor_logistico='RETIRO_LOCAL',
            metodo_pago='TRANSFERENCIA', proxima_entrega=timezone.localdate())
        self.client.force_authenticate(self.cliente)

    def comprar(self):
        datos = {**self.payload_base}
        datos.pop('email_invitado')
        respuesta = self.client.post(self.url, datos, format='json')
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        return OrdenCompra.objects.get(pk=respuesta.data['orden_id'])

    def test_activa_descuenta_y_no_cobra_el_envio(self):
        self.assertEqual(self.client.get(reverse('suscripciones-beneficios')).data,
                         {'descuento': 10, 'envio_gratis': True})
        orden = self.comprar()
        # 20.000 - 10 % = 18.000 y el envío de 3.000 queda en 0
        self.assertEqual((orden.costo_envio, orden.total_final), (0.0, 18000.0))

    def test_pausada_o_con_el_modulo_apagado_no_hay_beneficios(self):
        for preparar in (lambda: Suscripcion.objects.update(estado=EstadoSuscripcion.PAUSADA.value),
                         lambda: ConfiguracionGlobal.objects.filter(pk=1).update(suscripciones_activas=False)):
            with self.subTest(preparar=preparar):
                preparar()
                self.assertEqual(self.client.get(reverse('suscripciones-beneficios')).data,
                                 {'descuento': 0, 'envio_gratis': False})
                orden = self.comprar()
                self.assertEqual((orden.costo_envio, orden.total_final), (3000.0, 23000.0))

    def test_se_suma_al_cupon_sobre_lo_que_queda_y_el_total_nunca_es_negativo(self):
        # Cupón del 10 %: 20.000 - 2.000 = 18.000; el del suscriptor, sobre eso: 18.000 - 1.800 = 16.200
        datos = {**self.payload_base, 'codigo_promocion': 'REINTENTO'}
        datos.pop('email_invitado')
        respuesta = self.client.post(self.url, datos, format='json')
        orden = OrdenCompra.objects.get(pk=respuesta.data['orden_id'])
        self.assertEqual(orden.total_final, 16200.0)
        self.plan.descuento = 90
        self.plan.save()
        orden = self.comprar()
        self.assertGreaterEqual(orden.total_final, 0)
        self.assertEqual(orden.total_final, 2000.0)
