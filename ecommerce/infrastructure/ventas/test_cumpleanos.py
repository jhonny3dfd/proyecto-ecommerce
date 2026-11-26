"""Privacidad del cumpleaños y regalo anual con PostgreSQL real de pruebas."""
from datetime import date
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework.test import APITestCase

from ecommerce.infrastructure.usuarios.tests.factories import create_user
from .models import ConfiguracionGlobal, PlanSuscripcion, RegaloCumpleanos, Suscripcion


class CumpleanosAPITests(APITestCase):
    def setUp(self):
        self.admin = create_user('admin-cumpleanos@example.test', rol='ADMIN')
        self.ana = create_user('ana-cumpleanos@example.test', nombre='Ana', cumpleanos_dia=29, cumpleanos_mes=2)
        self.beto = create_user('beto-cumpleanos@example.test')
        self.config = ConfiguracionGlobal.objects.create(pk=1, nombre_tienda='QA', suscripciones_activas=True)
        self.plan = PlanSuscripcion.objects.create(nombre='Mensual', precio=1000, frecuencia_semanas=4)
        self.suscripcion = Suscripcion.objects.create(
            usuario=self.ana, plan=self.plan, estado='ACTIVA', producto_mongo_id='producto-de-prueba',
            variante_sku='SKU-QA', nombre_producto='Ejemplo', proveedor_logistico='ENTREGA_COORDINADA',
            direccion_envio={'calle': 'Calle de ejemplo', 'numero': '202', 'dpto_casa': 'Depto. 4',
                             'comuna': 'Santiago', 'region': 'Metropolitana'},
            nombre_destinatario='Ana', metodo_pago='TRANSFERENCIA', proxima_entrega=date(2026, 2, 28))
        self.url = reverse('mi-cumpleanos')
        self.panel = reverse('admin-cumpleanos')
        self.regalo = reverse('admin-regalo-cumpleanos', args=[self.ana.pk])

    def test_propietario_guarda_sin_anio_consulta_corrige_y_elimina(self):
        self.client.force_authenticate(self.ana)
        self.assertEqual(self.client.get(self.url).data, {'dia': 29, 'mes': 2})
        for datos in ({'dia': 11, 'mes': 5}, {'dia': None, 'mes': None}):
            respuesta = self.client.patch(self.url, datos, format='json')
            self.assertEqual(respuesta.status_code, 200, respuesta.data)
            self.assertEqual(self.client.get(self.url).data, datos)
        self.ana.refresh_from_db()
        self.assertIsNone(self.ana.cumpleanos_mes)

    def test_modulo_apagado_oculta_fecha_y_rechaza_cambios_sin_borrar_datos(self):
        self.config.suscripciones_activas = False
        self.config.save()
        self.client.force_authenticate(self.ana)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.patch(self.url, {'dia': 1, 'mes': 1}, format='json').status_code, 404)
        self.ana.refresh_from_db()
        self.assertEqual((self.ana.cumpleanos_dia, self.ana.cumpleanos_mes), (29, 2))

    def test_no_permite_fecha_invalida_y_no_sobrescribe_la_guardada(self):
        self.client.force_authenticate(self.ana)
        for datos in ({'dia': 31, 'mes': 4}, {'dia': 30, 'mes': 2}, {'dia': None, 'mes': 1},
                      {'dia': 1}, {'dia': 1, 'mes': 13}):
            self.assertEqual(self.client.patch(self.url, datos, format='json').status_code, 400)
        self.ana.refresh_from_db()
        self.assertEqual((self.ana.cumpleanos_dia, self.ana.cumpleanos_mes), (29, 2))

    def test_otra_cuenta_solo_ve_y_edita_su_propia_fecha(self):
        self.client.force_authenticate(self.beto)
        self.assertEqual(self.client.get(self.url, {'usuario_id': self.ana.id}).data, {'dia': None, 'mes': None})
        self.client.patch(self.url, {'dia': 3, 'mes': 7, 'usuario_id': self.ana.pk}, format='json')
        self.ana.refresh_from_db()
        self.beto.refresh_from_db()
        self.assertEqual(self.ana.cumpleanos_mes, 2)
        self.assertEqual(self.beto.cumpleanos_mes, 7)
        self.assertNotIn('cumpleanos_dia', self.client.get(reverse('usuario_actual')).data)
        self.assertEqual(self.client.get(self.panel).status_code, 403)
        self.assertEqual(self.client.post(self.regalo).status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(self.client.patch(self.url, {'dia': 1, 'mes': 1}, format='json').status_code, 401)

    @patch('ecommerce.infrastructure.ventas.views_cumpleanos.hoy_local', return_value=date(2026, 2, 1))
    def test_panel_elige_mes_y_solo_lista_vigentes_una_vez_con_la_proxima_direccion(self, _hoy):
        self.client.force_authenticate(self.admin)
        Suscripcion.objects.create(usuario=self.ana, plan=self.plan, estado='ACTIVA',
                                    proxima_entrega=date(2026, 3, 28), proveedor_logistico='RETIRO_LOCAL')
        respuesta = self.client.get(self.panel)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual((respuesta.data['mes'], respuesta.data['anio'], respuesta.data['count']), (2, 2026, 1))
        fila = respuesta.data['results'][0]
        self.assertEqual(fila['direccion_envio']['dpto_casa'], 'Depto. 4')
        self.assertEqual(fila['proxima_entrega'], date(2026, 2, 28))
        self.assertFalse(fila['regalo_enviado'])
        self.assertEqual(self.client.get(self.panel, {'mes': 3}).data['count'], 0)
        self.assertEqual(self.client.get(self.panel, {'mes': 'febrero'}).status_code, 400)
        Suscripcion.objects.filter(usuario=self.ana).update(estado='PAUSADA')
        self.assertEqual(self.client.get(self.panel).data['count'], 0)
        self.assertEqual(self.client.post(self.regalo).status_code, 404)

    @patch('ecommerce.infrastructure.ventas.views_cumpleanos.hoy_local')
    def test_regalo_idempotente_y_otro_anio_puede_volver_a_marcarse(self, hoy):
        hoy.return_value = date(2026, 2, 1)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(self.regalo, {'anio': 2000}).status_code, 201)
        self.assertEqual(self.client.post(self.regalo).status_code, 200)
        self.assertEqual(RegaloCumpleanos.objects.count(), 1)
        self.assertTrue(self.client.get(self.panel).data['results'][0]['regalo_enviado'])
        regalo = RegaloCumpleanos.objects.get()
        self.assertEqual((regalo.anio, regalo.enviado_por_id), (2026, self.admin.id))
        hoy.return_value = date(2027, 2, 1)
        self.assertFalse(self.client.get(self.panel).data['results'][0]['regalo_enviado'])
        self.assertEqual(self.client.post(self.regalo).status_code, 201)
        self.assertEqual(RegaloCumpleanos.objects.count(), 2)

    def test_sin_modulo_no_expone_listado_ni_registra_regalos(self):
        self.client.force_authenticate(self.admin)
        self.config.suscripciones_activas = False
        self.config.save()
        self.assertEqual(self.client.get(self.panel).status_code, 404)
        self.assertEqual(self.client.post(self.regalo).status_code, 404)
        self.assertFalse(RegaloCumpleanos.objects.exists())

    def test_base_de_datos_impide_fechas_invalidas_y_regalo_duplicado(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            type(self.ana).objects.filter(pk=self.ana.id).update(cumpleanos_dia=31, cumpleanos_mes=4)
        RegaloCumpleanos.objects.create(usuario=self.ana, anio=2026)
        with self.assertRaises(IntegrityError), transaction.atomic():
            RegaloCumpleanos.objects.create(usuario=self.ana, anio=2026)
