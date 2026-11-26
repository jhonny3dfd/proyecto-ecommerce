"""Exclusivos con SQL y Mongo reales aislados: carrito, checkout y selección de entregas."""
from django.urls import reverse

from .models import Carrito, OrdenCompra, PlanSuscripcion, Suscripcion
from .test_suscripciones import SuscripcionesAPIBase
from .tests import DESTINATARIO
from ..catalogo.documents import Variante


class ExclusivosAPITests(SuscripcionesAPIBase):
    def test_pendiente_cambia_variante_exclusiva_y_lista_coherente_sin_habilitar_carrito(self):
        self.taza.variantes.append(Variante(sku='TAZA-2', precio=5990, stock=5))
        self.taza.planes_suscripcion = [self.plan.id]
        self.taza.save()
        alta = self.suscribir(producto_mongo_id=str(self.taza.id), variante_sku='TAZA-1')
        self.assertEqual(alta.status_code, 201, alta.data)
        identificador = alta.data['suscripcion_id']
        opciones = self.client.get(reverse('suscripciones-plan-opciones', args=[self.plan.id]),
                                   {'suscripcion_id': identificador}).data['productos']
        taza = next(p for p in opciones if p['id'] == str(self.taza.id))
        self.assertTrue(taza['variantes'][1]['disponible'])
        respuesta = self.client.patch(reverse('suscripcion', args=[identificador]),
                                     {'variante_sku': 'TAZA-2'}, format='json')
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(Suscripcion.objects.get(pk=identificador).variante_sku, 'TAZA-2')
        self.assertFalse(self.revisar().data['valido'])
        self.assertEqual(self.checkout().status_code, 400)

    def test_pausada_y_cancelada_bloquean_lista_y_edicion_aunque_exista_otro_plan_activo(self):
        propia = self.activar()
        otra = self.suscribir()
        self.pagar(otra.data['orden_id'])
        for estado in ('PAUSADA', 'CANCELADA'):
            propia.estado = estado
            propia.save()
            opciones = self.client.get(reverse('suscripciones-plan-opciones', args=[self.plan.id]),
                                       {'suscripcion_id': propia.id}).data['productos']
            taza = next(p for p in opciones if p['id'] == str(self.taza.id))
            self.assertTrue(taza['requiere_suscripcion'])
            self.assertFalse(taza['variantes'][0]['disponible'])
            self.assertEqual(self.client.patch(reverse('suscripcion', args=[propia.id]),
                                              self.item, format='json').status_code, 400)

    def test_opciones_de_cambio_solo_admiten_la_suscripcion_propia_y_su_plan(self):
        propia = self.activar()
        url = reverse('suscripciones-plan-opciones', args=[self.plan.id])
        self.client.force_authenticate(self.beto)
        self.assertEqual(self.client.get(url, {'suscripcion_id': propia.id}).status_code, 404)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(url, {'suscripcion_id': propia.id}).status_code, 401)

    def setUp(self):
        super().setUp()
        self.taza.solo_suscriptores = True
        self.taza.save()
        self.item = {'producto_mongo_id': str(self.taza.id), 'variante_sku': 'TAZA-1', 'cantidad': 1}
        self.plan.productos = [str(self.taza.id)]
        self.plan.save()

    def activar(self):
        respuesta = self.suscribir()
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.pagar(respuesta.data['orden_id'])
        return Suscripcion.objects.get(pk=respuesta.data['suscripcion_id'])

    def checkout(self):
        return self.client.post(reverse('checkout'), {
            'items': [self.item], 'subtotal': 5990, 'costo_envio': 0, 'total_final': 5990,
            'metodo_pago': 'TRANSFERENCIA', 'proveedor_logistico': 'RETIRO_LOCAL',
            'direccion_envio_snapshot': {}, 'acepta_terminos': True,
            'email_invitado': 'invitado202@example.test', **DESTINATARIO,
        }, format='json')

    def revisar(self):
        return self.client.post(reverse('carrito-validar'), {'items': [self.item]}, format='json')

    def test_invitado_y_cuenta_sin_suscripcion_no_compran_ni_inyectando_el_carrito(self):
        for usuario in (None, self.ana):
            self.client.force_authenticate(usuario)
            with self.subTest(usuario=usuario):
                revision = self.revisar()
                self.assertEqual(revision.status_code, 200)
                self.assertFalse(revision.data['valido'])
                self.assertEqual(revision.data['items'][0]['problema'], 'SUSCRIPCION_REQUERIDA')
                self.assertEqual(self.checkout().status_code, 400)
        self.assertFalse(OrdenCompra.objects.exists())
        self.assertEqual(self.client.post(reverse('carrito-usuario'), {'items': [self.item]}, format='json').status_code, 400)
        self.assertEqual(Carrito.objects.get(usuario=self.ana).items, [])

    def test_activa_compra_y_pausa_o_cancelacion_revocan_acceso_inmediatamente(self):
        activa = self.activar()
        self.assertTrue(self.revisar().data['valido'])
        self.assertEqual(self.checkout().status_code, 201)
        antes = OrdenCompra.objects.count()
        for accion in ('pausar', 'cancelar'):
            respuesta = self.client.post(reverse('suscripcion-accion', args=[activa.id, accion]))
            self.assertEqual(respuesta.status_code, 200, respuesta.data)
            self.assertFalse(self.revisar().data['valido'])
            self.assertEqual(self.checkout().status_code, 400)
            self.assertEqual(self.client.post(reverse('carrito-usuario'), {'items': [self.item]}, format='json').status_code, 400)
        self.assertEqual(OrdenCompra.objects.count(), antes)
        self.taza.reload()
        self.assertEqual(self.taza.variantes[0].stock, 5)

    def test_solo_planes_permitidos_y_sin_filtrar_los_datos_de_otros_suscriptores(self):
        self.activar()
        otro = PlanSuscripcion.objects.create(nombre='Otro', precio=1000, frecuencia_semanas=4)
        self.taza.planes_suscripcion = [otro.id]
        self.taza.save()
        self.assertFalse(self.revisar().data['valido'])
        self.assertEqual(self.checkout().status_code, 400)
        self.taza.planes_suscripcion = [self.plan.id]
        self.taza.save()
        self.assertTrue(self.revisar().data['valido'])
        self.client.force_authenticate(self.beto)
        self.assertFalse(self.revisar().data['valido'])

    def test_nuevo_suscriptor_elige_exclusivo_del_plan_permitido_sin_abrir_carrito_normal(self):
        self.taza.planes_suscripcion = [self.plan.id]
        self.taza.save()
        respuesta = self.suscribir(producto_mongo_id=str(self.taza.id), variante_sku='TAZA-1')
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(OrdenCompra.objects.get(pk=respuesta.data['orden_id']).estado, 'PENDIENTE')
        self.assertFalse(self.revisar().data['valido'])
        self.assertEqual(self.checkout().status_code, 400)
        opciones = self.client.get(reverse('suscripciones-plan-opciones', args=[self.plan.id])).data['productos']
        taza = next(p for p in opciones if p['id'] == str(self.taza.id))
        self.assertFalse(taza['requiere_suscripcion'])
        self.assertTrue(taza['variantes'][0]['disponible'])

    def test_nuevo_suscriptor_no_contrata_exclusivo_reservado_a_otro_plan(self):
        otro = PlanSuscripcion.objects.create(nombre='Otro', precio=1000, frecuencia_semanas=4)
        self.taza.planes_suscripcion = [otro.id]
        self.taza.save()
        self.assertEqual(self.suscribir(producto_mongo_id=str(self.taza.id), variante_sku='TAZA-1').status_code, 400)
        self.assertFalse(Suscripcion.objects.exists())
        opciones = self.client.get(reverse('suscripciones-plan-opciones', args=[self.plan.id])).data['productos']
        taza = next(p for p in opciones if p['id'] == str(self.taza.id))
        self.assertTrue(taza['requiere_suscripcion'])
        self.assertFalse(taza['variantes'][0]['disponible'])

    def test_suscriptor_activo_elige_exclusivo_y_pausado_no_puede(self):
        activa = self.activar()
        url = reverse('suscripcion', args=[activa.id])
        self.assertEqual(self.client.patch(url, self.item, format='json').status_code, 200)
        self.client.post(reverse('suscripcion-accion', args=[activa.id, 'pausar']))
        self.assertEqual(self.client.patch(url, self.item, format='json').status_code, 400)

    def test_sin_modulo_no_queda_ningun_producto_restringido(self):
        self.config.suscripciones_activas = False
        self.config.save()
        self.assertTrue(self.revisar().data['valido'])
        self.client.force_authenticate(self.ana)
        self.assertEqual(self.checkout().status_code, 201)
        self.client.force_authenticate(None)
        detalle = self.client.get(reverse('detalle_producto', args=[str(self.taza.id)]))
        self.assertFalse(detalle.data['solo_suscriptores'])

    def test_admin_guarda_restricciones_y_rechaza_planes_inexistentes_o_duplicados(self):
        self.client.force_authenticate(self.admin)
        url = reverse('detalle_producto', args=[str(self.cafe.id)])
        for planes in ([999999], [self.plan.id, self.plan.id], [-1]):
            self.assertEqual(self.client.patch(url, {'planes_suscripcion': planes}, format='json').status_code, 400)
        respuesta = self.client.patch(url, {'solo_suscriptores': True, 'planes_suscripcion': [self.plan.id]}, format='json')
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.cafe.reload()
        self.assertTrue(self.cafe.solo_suscriptores)
        self.assertEqual(self.cafe.planes_suscripcion, [self.plan.id])

    def test_otro_plan_no_puede_seleccionar_un_producto_restringido_a_un_plan_distinto(self):
        activa = self.activar()
        otro = PlanSuscripcion.objects.create(nombre='Otro', precio=1000, frecuencia_semanas=4,
                                              productos=[str(self.taza.id)])
        self.taza.planes_suscripcion = [otro.id]
        self.taza.save()
        self.assertEqual(self.client.patch(reverse('suscripcion', args=[activa.id]), self.item, format='json').status_code, 400)
