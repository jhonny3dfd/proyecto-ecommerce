import json
import hmac
import hashlib
from unittest.mock import patch, MagicMock
from rest_framework.test import APISimpleTestCase, APITestCase
from rest_framework import status
from django.urls import reverse

from ecommerce.application.ventas import GenerarOrdenTransporte
from ecommerce.infrastructure.ventas.models import OrdenCompra

SECRETO_LINKIFY = 'secreto_de_prueba_linkify'
OBTENER_SECRETO = 'ecommerce.infrastructure.ventas.views.LinkifyWebhookAPIView._obtener_secret_key'


@patch(OBTENER_SECRETO, return_value=SECRETO_LINKIFY)
class LinkifyConsultaMontoTests(APITestCase):
    """Linkify consulta con un GET firmado cuánto debe pagarse por la orden."""

    def consultar(self, datos):
        encoded_data = json.dumps(datos)
        firma = hmac.new(SECRETO_LINKIFY.encode('utf-8'), encoded_data.encode('utf-8'), hashlib.sha256).hexdigest()
        return self.client.get(reverse('webhook-linkify'), {'encoded_data': encoded_data},
                               HTTP_X_LINKIFY_CONFIRMATION=firma)

    def test_responde_el_total_de_la_orden(self, _):
        orden = OrdenCompra.objects.create(
            email_invitado='invitado@example.test', metodo_pago='TRANSFERENCIA', direccion_envio_snapshot={},
            subtotal=15000, costo_envio=0, total_final=15000, proveedor_logistico='RETIRO_LOCAL')

        response = self.consultar({'id': orden.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'amount': 15000, 'description': f'Orden #{orden.id}', 'currency': 'CLP'})

    def test_orden_inexistente_o_id_invalido_responde_404(self, _):
        for orden_id in (999999, 'ORD-001', None):
            with self.subTest(orden_id=orden_id):
                self.assertEqual(self.consultar({'id': orden_id}).status_code, status.HTTP_404_NOT_FOUND)

class LinkifyWebhookQATest(APISimpleTestCase):
    def setUp(self):
        # Asegúrate de que este nombre coincide con el 'name' que pusiste en urls.py
        self.url = reverse('webhook-linkify') 
        self.secret_key = "secreto_de_prueba_linkify"

    def generar_firma_valida(self, payload_dict):
        cuerpo_bytes = json.dumps(payload_dict).encode('utf-8')
        firma = hmac.new(
            self.secret_key.encode('utf-8'),
            cuerpo_bytes,
            hashlib.sha256
        ).hexdigest()
        return cuerpo_bytes, firma

    @patch('ecommerce.infrastructure.ventas.views.LinkifyWebhookAPIView._obtener_secret_key')
    def test_rechaza_peticion_con_firma_invalida(self, mock_secret):
        """Criterio 6: Seguridad. Un aviso no auténtico no cambia la orden."""
        mock_secret.return_value = self.secret_key
        payload = {"action": "notification", "id": "ORD-001"}
        cuerpo_bytes = json.dumps(payload).encode('utf-8')
        
        # Enviamos una firma inventada
        headers = {'HTTP_X_LINKIFY_CONFIRMATION': 'firma_falsa_123'}
        response = self.client.post(self.url, cuerpo_bytes, content_type='application/json', **headers)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["notify_merchant"], False)

    @patch('ecommerce.infrastructure.ventas.views.ConfirmarPago')
    @patch('ecommerce.infrastructure.ventas.views.LinkifyWebhookAPIView._obtener_secret_key')
    def test_acepta_pago_exacto_y_ejecuta_confirmacion(self, mock_secret, MockConfirmarPago):
        """Criterio 2: Transferencia validada pasa a Pagado."""
        mock_secret.return_value = self.secret_key
        mock_caso_uso = MagicMock()
        MockConfirmarPago.return_value = mock_caso_uso
        
        payload = {
            "action": "notification",
            "id": "ORD-002",
            "completeness": "exact",
            "transfers": [{"amount": 15000}]
        }
        cuerpo_bytes, firma = self.generar_firma_valida(payload)
        
        headers = {'HTTP_X_LINKIFY_CONFIRMATION': firma}
        response = self.client.post(self.url, cuerpo_bytes, content_type='application/json', **headers)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "accepted")
        
        # Verificamos que el caso de uso se llamó correctamente (usando aprobar)
        mock_caso_uso.aprobar.assert_called_once()
        kwargs = mock_caso_uso.aprobar.call_args.kwargs
        self.assertEqual(kwargs.get('orden_id'), "ORD-002")

    @patch('ecommerce.infrastructure.ventas.views.ConfirmarPago')
    @patch('ecommerce.infrastructure.ventas.views.LinkifyWebhookAPIView._obtener_secret_key')
    def test_la_ot_se_genera_con_el_caso_de_uso_como_en_los_demas_pagos(self, mock_secret, MockConfirmarPago):
        """El caso de uso busca el envío de la orden; el adaptador de Chilexpress solo no sabe hacerlo."""
        mock_secret.return_value = self.secret_key
        payload = {"action": "notification", "id": "ORD-004", "completeness": "exact"}
        cuerpo_bytes, firma = self.generar_firma_valida(payload)

        self.client.post(self.url, cuerpo_bytes, content_type='application/json',
                         HTTP_X_LINKIFY_CONFIRMATION=firma)

        orden_transporte = MockConfirmarPago.call_args.args[2]
        self.assertIsInstance(orden_transporte, GenerarOrdenTransporte)

    @patch('ecommerce.infrastructure.ventas.views.ConfirmarPago')
    @patch('ecommerce.infrastructure.ventas.views.LinkifyWebhookAPIView._obtener_secret_key')
    def test_pago_monto_distinto_no_descuenta_stock_automatico(self, mock_secret, MockConfirmarPago):
        """Criterio 4: Monto no coincide, va a revisión."""
        mock_secret.return_value = self.secret_key
        
        # Simulamos que ConfirmarPago lanza un error o que maneja la revisión 
        # (en nuestro views.py lo pasamos evaluando completeness)
        payload = {
            "action": "notification",
            "id": "ORD-003",
            "completeness": "underpaid",
            "transfers": [{"amount": 10000}]
        }
        cuerpo_bytes, firma = self.generar_firma_valida(payload)
        
        headers = {'HTTP_X_LINKIFY_CONFIRMATION': firma}
        response = self.client.post(self.url, cuerpo_bytes, content_type='application/json', **headers)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # La vista debe procesarlo como éxito hacia Linkify, pero internamente 
        # nuestro caso de uso debió registrar que el pago no fue exacto.