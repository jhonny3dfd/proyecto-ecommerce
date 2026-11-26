import base64
import os
from decimal import Decimal
from unittest.mock import Mock, patch

import requests

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from ecommerce.domain.logistica import (
    CredencialesCourier, CredencialesInvalidas, CourierNoDisponible, EnvioSolicitado, ErrorOrdenTransporte, Paquete,
)
from ecommerce.infrastructure.usuarios.tests.factories import create_user

from .couriers import DjangoCouriers, DjangoRepositorioCredencialesCourier
from .couriers.chilexpress import ChilexpressCourier
from .cifrado import descifrar_json
from .models import ConfiguracionGlobal, OrdenCompra, ProveedorEnvio

ADAPTADOR = 'ecommerce.infrastructure.ventas.couriers.chilexpress'
COTIZADOR = 'llave-cotizador-secreta-0001'
ENVIOS = 'llave-envios-secreta-0002'


def credenciales(**llaves):
    return CredencialesCourier.con(ChilexpressCourier.CAMPOS, llaves)


def guardar_credenciales(**llaves):
    DjangoRepositorioCredencialesCourier().guardar('CHILEXPRESS', credenciales(**llaves))


def chilexpress():
    """El adaptador con las llaves guardadas, como lo arma el registro (aunque falten las obligatorias)."""
    return DjangoCouriers().obtener('CHILEXPRESS', solo_activos=False)


def sin_llaves_guardadas():
    # La migración 0022 copia a la base de pruebas las llaves que tenga el .env de quien corre los tests
    ProveedorEnvio.objects.all().delete()


class AdminCouriersAPITests(APITestCase):
    """RNF-03: el admin carga las llaves de cada courier desde el panel, cifradas y nunca devueltas completas."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_token = Token.objects.create(user=create_user('admin@example.test', rol='ADMIN'))
        cls.buyer_token = Token.objects.create(user=create_user())

    def setUp(self):
        sin_llaves_guardadas()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')

    def guardar(self, datos):
        return self.client.put(reverse('admin-courier', args=['CHILEXPRESS']), {'datos': datos}, format='json')

    def test_sin_configurar_informa_los_campos_y_lo_que_falta(self):
        response = self.client.get(reverse('admin-couriers'))
        self.assertEqual(response.status_code, 200)
        chilexpress, = response.data
        self.assertEqual((chilexpress['codigo'], chilexpress['nombre']), ('CHILEXPRESS', 'Chilexpress'))
        self.assertEqual((chilexpress['configuradas'], chilexpress['faltantes']), (False, ['cotizador']))
        self.assertEqual([(c['nombre'], c['obligatorio']) for c in chilexpress['campos']],
                         [('ambiente', False), ('cotizador', True), ('coberturas', False), ('envios', False),
                          ('tcc', True), ('rut', True), ('contenido', False)])

    def test_guarda_cifrado_devuelve_enmascarado_y_conserva_al_reenviar(self):
        response = self.guardar({'cotizador': COTIZADOR, 'envios': ENVIOS})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['datos'], {
            'ambiente': 'PRUEBAS', 'cotizador': '••••0001', 'coberturas': '', 'envios': '••••0002', 'tcc': '',
            'rut': '', 'contenido': 'Otros'})
        self.assertTrue(response.data['configuradas'])
        for llave in (COTIZADOR, ENVIOS):
            self.assertNotIn(llave, response.content.decode())
            self.assertNotIn(llave, ProveedorEnvio.objects.get(codigo='CHILEXPRESS').credenciales_cifradas)

        # El panel reenvía lo que mostró: no debe pisar las llaves con los puntos
        self.guardar(response.data['datos'])
        self.assertEqual(chilexpress().credenciales, credenciales(cotizador=COTIZADOR, envios=ENVIOS))

    def test_campo_desconocido_es_400(self):
        response = self.guardar({'cotizador': COTIZADOR, 'otra': '18578680'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('otra', response.data['datos'])
        self.assertFalse(ProveedorEnvio.objects.exists())

    def test_un_courier_desconocido_es_404(self):
        response = self.client.put(reverse('admin-courier', args=['NOEXISTE']), {'datos': {}}, format='json')
        self.assertEqual(response.status_code, 404)

    def test_solo_el_admin_ve_y_carga_las_llaves(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.buyer_token.key}')
        self.assertEqual(self.client.get(reverse('admin-couriers')).status_code, 403)
        self.assertEqual(self.guardar({'cotizador': COTIZADOR}).status_code, 403)
        self.client.credentials()
        self.assertEqual(self.client.get(reverse('admin-couriers')).status_code, 401)


class AdaptadorChilexpressCredencialesTests(TestCase):
    """El adaptador toma las llaves del panel; sin ellas no consulta a Chilexpress."""

    def setUp(self):
        sin_llaves_guardadas()
        ChilexpressCourier._CACHE_COBERTURAS = {}
        self.addCleanup(setattr, ChilexpressCourier, '_CACHE_COBERTURAS', {})

    @patch(f'{ADAPTADOR}.requests.get')
    def test_sin_llaves_no_llama_a_chilexpress(self, get):
        with self.assertRaisesMessage(CourierNoDisponible, 'Servicio de coberturas no disponible en este momento.'):
            chilexpress().comunas()
        get.assert_not_called()

    @patch(f'{ADAPTADOR}.requests.get')
    def test_coberturas_usa_la_llave_del_cotizador_si_no_hay_una_propia(self, get):
        guardar_credenciales(cotizador=COTIZADOR)
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {'regions': []}
        with self.assertRaises(CourierNoDisponible):
            chilexpress().comunas()
        self.assertEqual(get.call_args.kwargs['headers']['Ocp-Apim-Subscription-Key'], COTIZADOR)

    @patch(f'{ADAPTADOR}.requests.post')
    def test_la_orden_de_transporte_usa_la_llave_de_envios(self, post):
        guardar_credenciales(cotizador=COTIZADOR, envios=ENVIOS)
        post.return_value = Mock(status_code=500, text='error')
        chilexpress()._solicitar_orden_transporte({'referencia': 'ORDEN-1'})
        self.assertEqual(post.call_args.kwargs['headers']['Ocp-Apim-Subscription-Key'], ENVIOS)


class DescargarEtiquetaTests(APITestCase):
    """El admin descarga la etiqueta de la OT con la llave de envíos cargada en el panel."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_token = Token.objects.create(user=create_user('admin@example.test', rol='ADMIN'))
        cls.orden = OrdenCompra.objects.create(
            email_invitado='cliente@example.test', metodo_pago='TRANSBANK', estado='PAGADO',
            direccion_envio_snapshot={}, subtotal=10000, costo_envio=3500, total_final=13500,
            proveedor_logistico='CHILEXPRESS', id_transaccion_pasarela='token-tbk | OT: 712678903156')

    def setUp(self):
        sin_llaves_guardadas()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')

    def descargar(self):
        return self.client.get(reverse('descargar-etiqueta', args=[self.orden.id]))

    @patch(f'{ADAPTADOR}.requests.post')
    def test_descarga_el_pdf_por_https_con_la_llave_de_envios(self, post):
        guardar_credenciales(cotizador=COTIZADOR, envios=ENVIOS)
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {
            'statusCode': 0, 'data': {'detail': [{'label': {'labelData': base64.b64encode(b'%PDF-1').decode()}}]}}

        response = self.descargar()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response.content, b'%PDF-1')
        self.assertTrue(post.call_args.args[0].startswith('https://'))
        self.assertEqual(post.call_args.kwargs['headers']['Ocp-Apim-Subscription-Key'], ENVIOS)
        self.assertEqual(post.call_args.kwargs['json']['transportOrderNumber'], 712678903156)

    @patch(f'{ADAPTADOR}.requests.post')
    def test_la_etiqueta_del_sandbox_viene_como_imagen_y_se_descarga_como_jpg(self, post):
        # Formato real del sandbox: data.label.labelData con un JPEG, y data.detail como objeto
        guardar_credenciales(cotizador=COTIZADOR, envios=ENVIOS)
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {'statusCode': 0, 'data': {
            'detail': {'transportOrderNumber': 712678903156.0},
            'label': {'labelData': base64.b64encode(b'\xff\xd8\xff\xe0JPEG').decode()}}}

        response = self.descargar()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')
        self.assertIn('Etiqueta_OT_712678903156.jpg', response['Content-Disposition'])

    @patch(f'{ADAPTADOR}.requests.post')
    def test_sin_llaves_avisa_sin_llamar_a_chilexpress(self, post):
        response = self.descargar()
        self.assertEqual(response.status_code, 400)
        post.assert_not_called()


# El entorno sin ninguna variable de Chilexpress (las del .env de quien corre los tests no cuentan)
ENTORNO_SIN_CHILEXPRESS = {k: v for k, v in os.environ.items() if not k.startswith('CHILEXPRESS_')}


class MigracionCredencialesChilexpressTests(TransactionTestCase):
    """0022 copia una sola vez las llaves de Chilexpress del .env a la base, cifradas."""

    ANTERIOR = [('ventas', '0021_proveedor_envio')]
    COPIA = [('ventas', '0022_copiar_credenciales_chilexpress')]

    def migrar(self, destino):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(destino)
        return executor.loader.project_state(destino).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def copiar(self):
        self.migrar(self.ANTERIOR).get_model('ventas', 'ProveedorEnvio').objects.all().delete()
        return self.migrar(self.COPIA).get_model('ventas', 'ProveedorEnvio').objects.all()

    @patch.dict('os.environ', {**ENTORNO_SIN_CHILEXPRESS, 'CHILEXPRESS_API_KEY_COTIZADOR': COTIZADOR,
                               'CHILEXPRESS_API_KEY_GEO': 'llave-geo-0003', 'CHILEXPRESS_API_KEY_ENVIOS': ENVIOS},
                clear=True)
    def test_copia_las_llaves_cifradas_y_la_de_sucursales_como_coberturas(self):
        fila, = self.copiar()
        self.assertEqual(fila.codigo, 'CHILEXPRESS')
        self.assertEqual(descifrar_json(fila.credenciales_cifradas),
                         {'cotizador': COTIZADOR, 'coberturas': 'llave-geo-0003', 'envios': ENVIOS})
        self.assertNotIn(COTIZADOR, fila.credenciales_cifradas)

    @patch.dict('os.environ', ENTORNO_SIN_CHILEXPRESS, clear=True)
    def test_sin_llaves_en_el_env_no_crea_nada(self):
        self.assertFalse(self.copiar().exists())


def respuesta_tracking(estado, status_code=200, codigo=0):
    respuesta = Mock(status_code=status_code)
    respuesta.json.return_value = {
        'statusCode': codigo, 'statusDescription': 'Extraccion exitosa',
        'data': {'transportOrderData': {'transportOrderNumber': '712678906520', 'status': estado}, 'trackingEvents': []},
    }
    if status_code >= 400:
        respuesta.raise_for_status.side_effect = requests.HTTPError(f'{status_code} Client Error')
    return respuesta


@patch(f'{ADAPTADOR}.requests.post')
class SeguimientoChilexpressTests(TestCase):
    """RF-02.4: el estado de la OT se consulta al tracking del sandbox y se traduce a la línea de tiempo estándar."""

    def setUp(self):
        sin_llaves_guardadas()
        guardar_credenciales(cotizador=COTIZADOR, envios=ENVIOS)

    def consultar(self):
        return chilexpress().consultar_estado('712678906520')

    def test_consulta_por_post_con_la_ot_el_rut_y_la_llave_de_envios(self, post):
        post.return_value = respuesta_tracking('EN PRE-RECEPCION')
        self.assertEqual(self.consultar(), 'En origen')
        url = post.call_args.args[0]
        self.assertEqual(url, 'https://testservices.wschilexpress.com/transport-orders/api/v1.0/tracking')
        self.assertEqual(post.call_args.kwargs['headers']['Ocp-Apim-Subscription-Key'], ENVIOS)
        cuerpo = post.call_args.kwargs['json']
        self.assertEqual((cuerpo['transportOrderNumber'], cuerpo['rut']), (712678906520, 96756430))

    def test_traduce_los_estados_a_la_linea_de_tiempo(self, post):
        for estado_api, esperado in (('EN PRE-RECEPCION', 'En origen'), ('RECEPCIONADO', 'En origen'),
                                     ('EN TRÁNSITO', 'En tránsito'), ('EN REPARTO', 'En reparto'),
                                     ('ENTREGADO', 'Entregado')):
            with self.subTest(estado_api=estado_api):
                post.return_value = respuesta_tracking(estado_api)
                self.assertEqual(self.consultar(), esperado)

    def test_un_estado_sin_equivalencia_se_informa_tal_cual_sin_avanzar_la_linea(self, post):
        for estado_api in ('PARA RETIRO EN SUCURSAL', 'NO ENTREGADO'):
            with self.subTest(estado_api=estado_api), self.assertLogs(ADAPTADOR, level='WARNING') as logs:
                post.return_value = respuesta_tracking(estado_api)
                self.assertEqual(self.consultar(), estado_api.capitalize())
                self.assertIn(estado_api, logs.output[0])

    def test_un_error_de_chilexpress_muestra_no_disponible_sin_la_llave_en_el_log(self, post):
        for respuesta in (respuesta_tracking('', status_code=400, codigo=-41), respuesta_tracking('', codigo=-41),
                          requests.ConnectionError('sin conexión')):
            with self.subTest(respuesta=respuesta), self.assertLogs(ADAPTADOR, level='ERROR') as logs:
                if isinstance(respuesta, Exception):
                    post.side_effect = respuesta
                else:
                    post.side_effect, post.return_value = None, respuesta
                self.assertEqual(self.consultar(), 'Estado no disponible temporalmente')
                self.assertNotIn(ENVIOS, '\n'.join(logs.output))

    def test_sin_llaves_no_consulta_a_chilexpress(self, post):
        sin_llaves_guardadas()
        self.assertEqual(self.consultar(), 'Estado no disponible temporalmente')
        post.assert_not_called()

    def test_el_invitado_ve_el_estado_traducido_en_el_portal(self, post):
        post.return_value = respuesta_tracking('EN PRE-RECEPCION')
        orden = OrdenCompra.objects.create(
            email_invitado='invitado@example.test', metodo_pago='TRANSBANK', estado='PAGADO',
            direccion_envio_snapshot={}, subtotal=10000, costo_envio=3500, total_final=13500,
            proveedor_logistico='CHILEXPRESS', numero_seguimiento_tracking='712678906520')
        response = self.client.post(reverse('tracking-envio'),
                                    {'numero_orden': orden.id, 'email': 'invitado@example.test'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['estado_actual'], 'En origen')
        self.assertIn(response.data['estado_actual'], response.data['linea_tiempo_estandar'])


def respuesta_json(cuerpo, status_code=200):
    respuesta = Mock(status_code=status_code, text='error de Chilexpress')
    respuesta.json.return_value = cuerpo
    return respuesta


EXPRESS = {'serviceTypeCode': 3, 'serviceDescription': 'EXPRESS', 'serviceValue': '3500'}
PRIORITARIO = {'serviceTypeCode': 2, 'serviceDescription': 'PRIORITARIO', 'serviceValue': '8569'}
EXTENDIDO = {'serviceTypeCode': 4, 'serviceDescription': 'EXTENDIDO', 'serviceValue': '5200'}
PAQUETE = Paquete(Decimal('1.5'), Decimal('30'), Decimal('30'), Decimal('30'))


def api_chilexpress(servicios=(PRIORITARIO, EXPRESS)):
    """Responde cada API de Chilexpress según la URL, como lo hacen el cotizador, las OT y el seguimiento."""
    def post(url, **kwargs):
        if url.endswith('/rates/business'):
            return respuesta_json({'data': {'courierServiceOptions': list(servicios)}})
        if url.endswith('/transport-orders'):
            return respuesta_json({'data': {'detail': [{'transportOrderNumber': 712678903156.0}]}})
        if url.endswith('/tracking'):
            return respuesta_tracking('EN PRE-RECEPCION')
        raise AssertionError(f'URL inesperada: {url}')
    return post


def envio_solicitado(**cambios):
    datos = dict(orden_id=7, proveedor='CHILEXPRESS', comuna='Santiago', calle='Uno', numero='123', complemento='',
                 destinatario='Ana Pérez', email='ana@example.test', valor_declarado=25000, telefono='+56912345678')
    return EnvioSolicitado(**{**datos, **cambios})


PRODUCCION = dict(ambiente='PRODUCCION', cotizador=COTIZADOR, envios=ENVIOS, tcc='12345678', rut='76.123.456-0')


@patch(f'{ADAPTADOR}.requests.post')
class AmbientesChilexpressTests(TestCase):
    """Con las llaves del sandbox se usa el ambiente de pruebas; con las del contrato de la tienda, el de
    producción, con su TCC, su RUT y sus datos de contacto como remitente."""

    def setUp(self):
        sin_llaves_guardadas()
        ConfiguracionGlobal.objects.create(
            id=1, nombre_tienda='Tienda de Alan', comuna_origen='Santiago', calle_origen='Los Aromos',
            numero_origen='450', dpto_casa_origen='Local 2', telefono_comercial='+56987654321',
            correo_contacto='ventas@alan.test')
        catalogo = patch(f'{ADAPTADOR}.ChilexpressCourier._obtener_catalogo_dinamico',
                         return_value={'SANTIAGO': 'STGO'})
        catalogo.start()
        self.addCleanup(catalogo.stop)

    @staticmethod
    def llamada(post, sufijo):
        return next(c for c in post.call_args_list if c.args[0].endswith(sufijo))

    @staticmethod
    def hubo_orden(post):
        return any(c.args[0].endswith('/transport-orders') for c in post.call_args_list)

    def test_sin_elegir_ambiente_cotiza_y_despacha_en_el_sandbox(self, post):
        guardar_credenciales(cotizador=COTIZADOR, envios=ENVIOS)
        post.side_effect = api_chilexpress()

        chilexpress().cotizar('Santiago', 'Santiago', PAQUETE)
        chilexpress().generar_orden_transporte(envio_solicitado())

        cotizacion = self.llamada(post, '/rates/business')
        self.assertEqual(cotizacion.args[0], 'https://testservices.wschilexpress.com/rating/api/v1.0/rates/business')
        self.assertEqual(cotizacion.kwargs['json']['customerCardNumber'], '0')
        orden = self.llamada(post, '/transport-orders')
        self.assertTrue(orden.args[0].startswith('https://testservices.wschilexpress.com/'))
        cabecera = orden.kwargs['json']['header']
        self.assertEqual((cabecera['customerCardNumber'], cabecera['marketplaceRut']), ('18578680', '96756430'))

    def test_en_produccion_usa_la_tcc_y_el_rut_de_la_tienda(self, post):
        guardar_credenciales(**PRODUCCION)
        post.side_effect = api_chilexpress()

        chilexpress().cotizar('Santiago', 'Santiago', PAQUETE)
        chilexpress().generar_orden_transporte(envio_solicitado())
        chilexpress().consultar_estado('712678903156')

        cotizacion = self.llamada(post, '/rates/business')
        self.assertEqual(cotizacion.args[0], 'https://services.wschilexpress.com/rating/api/v1.0/rates/business')
        # Con la TCC, Chilexpress cotiza con las tarifas del contrato
        self.assertEqual(cotizacion.kwargs['json']['customerCardNumber'], '12345678')
        orden = self.llamada(post, '/transport-orders')
        self.assertEqual(orden.args[0], 'https://services.wschilexpress.com/transport-orders/api/v1.0/transport-orders')
        cabecera = orden.kwargs['json']['header']
        self.assertEqual((cabecera['customerCardNumber'], cabecera['marketplaceRut']), ('12345678', '76123456'))
        # El seguimiento se consulta con el mismo RUT con que se generó la OT
        seguimiento = self.llamada(post, '/tracking')
        self.assertEqual(seguimiento.args[0], 'https://services.wschilexpress.com/transport-orders/api/v1.0/tracking')
        self.assertEqual(seguimiento.kwargs['json']['rut'], 76123456)

    def test_el_remitente_y_la_devolucion_son_los_de_la_tienda(self, post):
        guardar_credenciales(**PRODUCCION)
        post.side_effect = api_chilexpress()

        chilexpress().generar_orden_transporte(envio_solicitado())

        detalle = self.llamada(post, '/transport-orders').kwargs['json']['details'][0]
        remitente = next(c for c in detalle['contacts'] if c['contactType'] == 'R')
        self.assertEqual((remitente['name'], remitente['phoneNumber'], remitente['mail']),
                         ('Tienda de Alan', '987654321', 'ventas@alan.test'))
        devolucion = next(d for d in detalle['addresses'] if d['addressType'] == 'DEV')
        self.assertEqual((devolucion['countyCoverageCode'], devolucion['streetName'], devolucion['streetNumber'],
                          devolucion['supplement']), ('STGO', 'Los Aromos', '450', 'Local 2'))

    def test_en_produccion_sin_los_datos_de_la_tienda_no_se_genera_la_ot(self, post):
        guardar_credenciales(**PRODUCCION)
        ConfiguracionGlobal.objects.filter(pk=1).update(telefono_comercial='', correo_contacto='')
        post.side_effect = api_chilexpress()

        with self.assertRaisesMessage(ErrorOrdenTransporte, 'falta el teléfono comercial, el correo de contacto'):
            chilexpress().generar_orden_transporte(envio_solicitado())
        self.assertFalse(self.hubo_orden(post))

    def test_en_pruebas_lo_que_falta_de_la_tienda_se_completa_con_datos_del_sandbox(self, post):
        guardar_credenciales(cotizador=COTIZADOR, envios=ENVIOS)
        ConfiguracionGlobal.objects.filter(pk=1).update(telefono_comercial='', correo_contacto='')
        post.side_effect = api_chilexpress()

        chilexpress().generar_orden_transporte(envio_solicitado())

        detalle = self.llamada(post, '/transport-orders').kwargs['json']['details'][0]
        remitente = next(c for c in detalle['contacts'] if c['contactType'] == 'R')
        self.assertEqual((remitente['name'], remitente['phoneNumber'], remitente['mail']),
                         ('Tienda de Alan', '999999999', 'contacto@tu-tienda.cl'))

    def test_la_ot_pide_el_servicio_que_se_cobro_en_el_checkout(self, post):
        guardar_credenciales(cotizador=COTIZADOR, envios=ENVIOS)
        # Sin Express para esa comuna, se cobra y se despacha el primero que ofrece Chilexpress
        post.side_effect = api_chilexpress(servicios=(EXTENDIDO, PRIORITARIO))

        cotizacion = chilexpress().cotizar('Santiago', 'Santiago', PAQUETE)
        chilexpress().generar_orden_transporte(envio_solicitado(paquete=PAQUETE))

        self.assertEqual((cotizacion.precio, cotizacion.tiempo_estimado), (5200, 'EXTENDIDO'))
        paquete = self.llamada(post, '/transport-orders').kwargs['json']['details'][0]['packages'][0]
        self.assertEqual(paquete['serviceDeliveryCode'], 4)

    def test_con_express_disponible_se_despacha_express(self, post):
        guardar_credenciales(cotizador=COTIZADOR, envios=ENVIOS)
        post.side_effect = api_chilexpress(servicios=(PRIORITARIO, EXPRESS))

        chilexpress().generar_orden_transporte(envio_solicitado())

        paquete = self.llamada(post, '/transport-orders').kwargs['json']['details'][0]['packages'][0]
        self.assertEqual(paquete['serviceDeliveryCode'], 3)

    def test_sin_respuesta_del_cotizador_no_se_genera_una_ot_con_otro_servicio(self, post):
        guardar_credenciales(cotizador=COTIZADOR, envios=ENVIOS)
        post.return_value = respuesta_json({}, status_code=503)

        with self.assertRaisesMessage(ErrorOrdenTransporte, 'No se pudo consultar el servicio de Chilexpress'):
            chilexpress().generar_orden_transporte(envio_solicitado())
        self.assertFalse(self.hubo_orden(post))

    def test_el_contenido_declarado_es_el_que_elige_la_tienda(self, post):
        post.side_effect = api_chilexpress()
        for contenido, codigo in (('', 5), ('Vestuario', 4), ('Tecnología', 7)):
            with self.subTest(contenido=contenido):
                guardar_credenciales(cotizador=COTIZADOR, envios=ENVIOS, contenido=contenido)
                post.reset_mock()
                chilexpress().generar_orden_transporte(envio_solicitado())
                paquete = self.llamada(post, '/transport-orders').kwargs['json']['details'][0]['packages'][0]
                self.assertEqual(paquete['declaredContent'], codigo)

    def test_en_produccion_faltan_la_tcc_y_el_rut_y_un_rut_invalido_se_rechaza(self, post):
        self.assertEqual(credenciales(ambiente='PRODUCCION', cotizador=COTIZADOR).faltantes, ['tcc', 'rut'])
        with self.assertRaises(CredencialesInvalidas) as error:
            credenciales().con_cambios({**PRODUCCION, 'rut': '76.123.456-1'})
        self.assertEqual(set(error.exception.errores), {'rut'})
