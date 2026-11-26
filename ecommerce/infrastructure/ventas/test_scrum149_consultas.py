"""Regresión SQL de las solicitudes públicas iniciales del catálogo."""
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APITestCase

from ecommerce.application.medios_pago import MediosPagoDisponibles
from ecommerce.domain.medios_pago import CodigoMedioPago, MedioPagoConfigurado
from ecommerce.infrastructure.usuarios.tests.factories import create_user
from .cifrado import cifrar_json
from .models import ConfiguracionGlobal, MedioPago, PaginaLegal
from .repositorio_medios_pago import DjangoRepositorioMediosPago


class ConsultasInicialesPostgresTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = create_user('sql149@example.test', rol='ADMIN')
        ConfiguracionGlobal.objects.create(pk=1, nombre_tienda='QA149')

    def test_configuracion_resuelve_pagos_y_envios_en_tres_consultas_sin_filtrar_secretos(self):
        repo = DjangoRepositorioMediosPago()
        repo.guardar(MedioPagoConfigurado(CodigoMedioPago.TRANSBANK, True, {'ambiente': 'INTEGRACION'}))
        repo.guardar(MedioPagoConfigurado(CodigoMedioPago.MERCADO_PAGO, True,
                                        {'access_token': 'qa149-ficticio', 'webhook_secret': 'qa149-firma'}))
        # Configuración, medios de pago en lote, disponibilidad de Chilexpress y carrusel de banner (SCRUM-194).
        with self.assertNumQueries(4):
            response = self.client.get(reverse('configuracion-global'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['pasarelas_activas'], ['TRANSBANK', 'MERCADO_PAGO'])
        self.assertNotIn('qa149-ficticio', str(response.data))
        self.assertNotIn('credenciales', str(response.data))

    def test_lectura_en_lote_conserva_orden_ausentes_e_incompletos(self):
        repo = DjangoRepositorioMediosPago()
        repo.guardar(MedioPagoConfigurado(CodigoMedioPago.TRANSBANK, True, {'ambiente': 'INTEGRACION'}))
        repo.guardar(MedioPagoConfigurado(CodigoMedioPago.MERCADO_PAGO, True, {'access_token': 'incompleto'}))
        with self.assertNumQueries(1):
            medios = MediosPagoDisponibles(repo).listar()
        self.assertEqual([m.codigo for m in medios], list(CodigoMedioPago))
        self.assertEqual([m.disponible for m in medios], [True, False, False])
        self.assertEqual(medios[2].datos, {})

    def test_credenciales_ilegibles_no_se_ofrecen_ni_se_revelan(self):
        MedioPago.objects.create(codigo='MERCADO_PAGO', habilitado=True,
                                 credenciales_cifradas=cifrar_json({'access_token': 'ficticio'}, clave='otra-clave'))
        with self.assertLogs('ecommerce.infrastructure.ventas.repositorio_medios_pago', level='ERROR'):
            response = self.client.get(reverse('configuracion-global'))
        self.assertEqual(response.data['pasarelas_activas'], [])
        self.assertNotIn('ficticio', str(response.data))

    def test_siguiente_lectura_refleja_cambios_del_panel(self):
        self.assertEqual(self.client.get(reverse('configuracion-global')).data['pasarelas_activas'], [])
        self.client.force_authenticate(self.admin)
        response = self.client.put(reverse('admin-medio-pago', args=['TRANSBANK']),
                                   {'habilitado': True, 'datos': {'ambiente': 'INTEGRACION'}}, format='json')
        self.assertEqual(response.status_code, 200)
        self.client.patch(reverse('configuracion-negocio'), {'nombre_tienda': 'Editada QA149'}, format='json')
        self.client.force_authenticate(None)
        with self.assertNumQueries(4):
            response = self.client.get(reverse('configuracion-global'))
        self.assertEqual(response.data['nombre_tienda'], 'Editada QA149')
        self.assertEqual(response.data['pasarelas_activas'], ['TRANSBANK'])

    def test_listado_legal_no_lee_contenido_y_conserva_detalle(self):
        PaginaLegal.objects.create(tipo_pagina='TERMINOS', titulo='QA', contenido='<p>Texto</p>', publicada=True)
        PaginaLegal.objects.create(tipo_pagina='PRIVACIDAD', titulo='Borrador', contenido='<p>Privado</p>')
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(reverse('paginas-legales-publicas'))
        self.assertEqual(len(captured), 1)
        self.assertNotIn('"contenido"', captured[0]['sql'])
        self.assertEqual(len(response.data), 1)
        self.assertNotIn('contenido', response.data[0])
        self.assertEqual(self.client.get(reverse('pagina-legal-detalle', args=['terminos'])).data['contenido'], '<p>Texto</p>')
