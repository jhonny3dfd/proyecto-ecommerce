from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from .models import OrdenCompra

Usuario = get_user_model()


def crear_orden(estado, requiere_revision=False):
    return OrdenCompra.objects.create(
        estado=estado,
        requiere_revision=requiere_revision,
        direccion_envio_snapshot='Dirección de prueba',
        total_final=10000,
        subtotal=10000,
        costo_envio=0
    )


class AdminOrdenCompraListViewTests(APITestCase):
    """Listado de pedidos del panel: de a 20 por página, con filtros por estado y por revisión."""

    def setUp(self):
        self.client.force_authenticate(user=Usuario.objects.create_superuser(
            email='admin@ecode.test', password='password123'
        ))
        self.url = '/api/ventas/admin/ordenes/'
        for _ in range(21):
            crear_orden('PENDIENTE')
        crear_orden('PAGADO')
        crear_orden('ENVIADO', requiere_revision=True)
        crear_orden('PENDIENTE', requiere_revision=True)

    def test_paginacion_devuelve_maximo_20_elementos(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 20)
        self.assertEqual(response.data['count'], 24)

    def test_la_segunda_pagina_trae_el_resto(self):
        response = self.client.get(self.url, {'pagina': 2})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 4)

    def test_una_pagina_que_no_existe_responde_404(self):
        # El panel vuelve a la página anterior cuando la última se queda vacía
        self.assertEqual(self.client.get(self.url, {'pagina': 3}).status_code, status.HTTP_404_NOT_FOUND)

    def test_filtro_individual_por_estado(self):
        response = self.client.get(self.url, {'estado': 'PAGADO'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['estado'], 'PAGADO')

    def test_filtro_individual_requiere_revision(self):
        response = self.client.get(self.url, {'requiere_revision': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        for orden in response.data['results']:
            self.assertTrue(orden['requiere_revision'])

    def test_filtros_combinados_estado_y_revision(self):
        response = self.client.get(self.url, {'estado': 'PENDIENTE', 'requiere_revision': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        orden, = response.data['results']
        self.assertEqual(orden['estado'], 'PENDIENTE')
        self.assertTrue(orden['requiere_revision'])

    def test_filtro_estado_invalido_devuelve_lista_vacia(self):
        response = self.client.get(self.url, {'estado': 'ESTADO_INVENTADO'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'], [])
        self.assertEqual(response.data['count'], 0)
