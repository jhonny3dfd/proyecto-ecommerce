from itertools import product

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from ecommerce.domain.documentos_tributarios import ModeloEmision, documento_por_emitir

from .models import ConfiguracionGlobal, OrdenCompra
from .repositorio_documentos import filtro_documento_pendiente

Usuario = get_user_model()
EMPRESA = {'razon_social': 'Comercial Andes SpA', 'rut': '76.123.456-0', 'giro': 'Regalos',
           'direccion': 'Av. Providencia 1234', 'correo': 'facturas@andes.test'}
URL_LISTA = '/api/ventas/admin/ordenes/'


def crear_orden(estado='PAGADO', metodo_pago='TRANSFERENCIA', datos_empresa=None, folio_documento='',
                folio_nota_credito=''):
    return OrdenCompra.objects.create(
        estado=estado, metodo_pago=metodo_pago, datos_empresa=datos_empresa, folio_documento=folio_documento,
        folio_nota_credito=folio_nota_credito, direccion_envio_snapshot={}, subtotal=10000, costo_envio=0,
        total_final=10000)


def usar_modelo(modelo):
    ConfiguracionGlobal.objects.update_or_create(id=1, defaults={'modelo_emision': modelo})


class BaseDocumentos(APITestCase):
    def setUp(self):
        self.client.force_authenticate(Usuario.objects.create_superuser(email='admin@ecode.test',
                                                                        password='password123'))

    def registrar(self, orden, folio):
        return self.client.post(f'{URL_LISTA}{orden.id}/documento/', {'folio': folio}, format='json')


class FiltroDocumentoPendienteTests(BaseDocumentos):
    def test_el_filtro_de_la_base_da_lo_mismo_que_la_regla_de_dominio_en_todas_las_combinaciones(self):
        estados = ['PENDIENTE', 'PAGADO', 'EN_PREPARACION', 'ENVIADO', 'ENTREGADO', 'CANCELADO']
        medios = ['TRANSBANK', 'MERCADO_PAGO', 'TRANSFERENCIA', 'LINKIFY', 'PAYPAL']
        folios = [('', ''), ('120', ''), ('120', '7')]
        for estado, medio, empresa, (documento, nota) in product(estados, medios, [None, EMPRESA], folios):
            crear_orden(estado, medio, empresa, documento, nota)

        for modelo in ModeloEmision:
            with self.subTest(modelo=modelo):
                esperados = {orden.id for orden in OrdenCompra.objects.all() if documento_por_emitir(
                    orden.estado, orden.metodo_pago, bool(orden.datos_empresa), modelo,
                    orden.folio_documento, orden.folio_nota_credito)}
                filtrados = set(OrdenCompra.objects.filter(filtro_documento_pendiente(modelo))
                                .values_list('id', flat=True))
                self.assertEqual(filtrados, esperados)
                self.assertTrue(esperados)


class ListadoPedidosTests(BaseDocumentos):
    def test_cada_pedido_dice_su_documento_y_lo_que_falta_emitir(self):
        transferencia = crear_orden()
        tarjeta = crear_orden(metodo_pago='TRANSBANK')
        empresa = crear_orden(metodo_pago='TRANSBANK', datos_empresa=EMPRESA, folio_documento='45')
        cancelado = crear_orden('CANCELADO', folio_documento='120')

        pedidos = {p['id']: p for p in self.client.get(URL_LISTA).data['results']}

        self.assertEqual((pedidos[transferencia.id]['documento_requerido'],
                          pedidos[transferencia.id]['documento_por_emitir']), ('BOLETA', 'BOLETA'))
        self.assertEqual((pedidos[tarjeta.id]['documento_requerido'], pedidos[tarjeta.id]['documento_por_emitir']),
                         (None, None))
        self.assertEqual((pedidos[empresa.id]['documento_requerido'], pedidos[empresa.id]['documento_por_emitir'],
                          pedidos[empresa.id]['folio_documento']), ('FACTURA', None, '45'))
        self.assertEqual(pedidos[cancelado.id]['documento_por_emitir'], 'NOTA_CREDITO')

    def test_con_siempre_boleta_la_tarjeta_tambien_pide_boleta(self):
        usar_modelo('SIEMPRE_BOLETA')
        tarjeta = crear_orden(metodo_pago='MERCADO_PAGO')

        pedido = self.client.get(URL_LISTA).data['results'][0]
        self.assertEqual((pedido['id'], pedido['documento_por_emitir']), (tarjeta.id, 'BOLETA'))

    def test_filtro_documento_pendiente_combinado_con_estado(self):
        pendiente = crear_orden('PAGADO')
        crear_orden('PAGADO', folio_documento='1')
        crear_orden('PAGADO', metodo_pago='TRANSBANK')
        entregado = crear_orden('ENTREGADO')

        respuesta = self.client.get(URL_LISTA, {'documento': 'pendiente'})
        self.assertEqual({p['id'] for p in respuesta.data['results']}, {pendiente.id, entregado.id})
        respuesta = self.client.get(URL_LISTA, {'documento': 'pendiente', 'estado': 'ENTREGADO'})
        self.assertEqual([p['id'] for p in respuesta.data['results']], [entregado.id])


class RegistrarFolioTests(BaseDocumentos):
    def test_anota_el_folio_de_la_boleta_y_responde_el_pedido_al_dia(self):
        orden = crear_orden()
        respuesta = self.registrar(orden, ' 123 ')

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual((respuesta.data['folio_documento'], respuesta.data['documento_por_emitir']), ('123', None))
        orden.refresh_from_db()
        self.assertEqual(orden.folio_documento, '123')

    def test_un_folio_ya_anotado_se_corrige(self):
        orden = crear_orden(folio_documento='123')
        self.assertEqual(self.registrar(orden, '132').data['folio_documento'], '132')

    def test_en_un_cancelado_con_boleta_anota_la_nota_de_credito(self):
        orden = crear_orden('CANCELADO', folio_documento='120')
        respuesta = self.registrar(orden, '7')

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual((respuesta.data['folio_documento'], respuesta.data['folio_nota_credito'],
                          respuesta.data['documento_por_emitir']), ('120', '7', None))

    def test_un_pago_con_voucher_no_tiene_folio_que_anotar_salvo_con_siempre_boleta(self):
        orden = crear_orden(metodo_pago='TRANSBANK')
        respuesta = self.registrar(orden, '123')
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('folio', respuesta.data)

        usar_modelo('SIEMPRE_BOLETA')
        self.assertEqual(self.registrar(orden, '123').status_code, status.HTTP_200_OK)

    def test_un_pedido_sin_pagar_o_un_folio_invalido_se_rechazan_sin_guardar(self):
        sin_pagar = crear_orden('PENDIENTE')
        pagado = crear_orden()
        for orden, folio in ((sin_pagar, '123'), (pagado, 'B-123'), (pagado, '')):
            with self.subTest(estado=orden.estado, folio=folio):
                respuesta = self.registrar(orden, folio)
                self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn('folio', respuesta.data)
        self.assertFalse(OrdenCompra.objects.exclude(folio_documento='').exists())

    def test_un_pedido_que_no_existe(self):
        respuesta = self.client.post(f'{URL_LISTA}999/documento/', {'folio': '1'}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_404_NOT_FOUND)

    def test_solo_el_administrador(self):
        orden = crear_orden()
        self.client.force_authenticate(Usuario.objects.create_user(
            'comprador@ecode.test', 'password123', nombre='Ana', apellido_paterno='Pérez', apellido_materno=''))
        self.assertEqual(self.registrar(orden, '1').status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(None)
        self.assertEqual(self.registrar(orden, '1').status_code, status.HTTP_401_UNAUTHORIZED)
        orden.refresh_from_db()
        self.assertEqual(orden.folio_documento, '')


class ModeloEmisionConfiguracionTests(BaseDocumentos):
    def test_el_panel_lo_lee_y_lo_cambia(self):
        self.assertEqual(self.client.get('/api/configuracion/negocio/').data['modelo_emision'], 'VOUCHER')

        respuesta = self.client.patch('/api/configuracion/negocio/', {'modelo_emision': 'SIEMPRE_BOLETA'},
                                      format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(ConfiguracionGlobal.objects.get(id=1).modelo_emision, 'SIEMPRE_BOLETA')

    def test_un_modelo_desconocido_se_rechaza(self):
        respuesta = self.client.patch('/api/configuracion/negocio/', {'modelo_emision': 'NINGUNO'}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_se_publica_en_la_configuracion_de_la_tienda(self):
        usar_modelo('VOUCHER')
        self.client.force_authenticate(None)
        self.assertNotIn('modelo_emision', self.client.get('/api/configuracion/').data)
