from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase, override_settings
from django.urls import reverse
from pymongo.errors import ServerSelectionTimeoutError

SALUD = 'ecommerce.infrastructure.salud'


class SaludTests(TestCase):
    def test_con_las_dos_bases_arriba_responde_200(self):
        response = self.client.get(reverse('salud'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'estado': 'ok', 'postgres': 'ok', 'mongo': 'ok'})
        # El monitor siempre consulta el estado actual
        self.assertIn('no-cache', response['Cache-Control'])

    def test_sin_mongo_responde_503_sin_detalles_del_error(self):
        with patch(f'{SALUD}.get_db', side_effect=ServerSelectionTimeoutError('mongo:27017 sin respuesta')), \
                self.assertLogs(SALUD, 'ERROR'), self.assertLogs('django.request', 'ERROR'):
            response = self.client.get(reverse('salud'))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'estado': 'error', 'postgres': 'ok', 'mongo': 'error'})
        self.assertNotIn('27017', response.content.decode())

    def test_sin_postgres_responde_503(self):
        with patch(f'{SALUD}.connection.cursor', side_effect=OperationalError('sin conexión')), \
                self.assertLogs(SALUD, 'ERROR'), self.assertLogs('django.request', 'ERROR'):
            response = self.client.get(reverse('salud'))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['postgres'], 'error')

    def test_solo_se_consulta(self):
        self.assertEqual(self.client.post(reverse('salud')).status_code, 405)

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_con_https_obligatorio_el_chequeo_interno_no_se_redirige(self):
        self.assertEqual(self.client.get(reverse('salud')).status_code, 200)
        self.assertEqual(self.client.get('/api/configuracion/').status_code, 301)
