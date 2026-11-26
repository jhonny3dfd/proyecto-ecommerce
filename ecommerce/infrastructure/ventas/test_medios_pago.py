from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase
from transbank.common.integration_type import IntegrationType

from ecommerce.domain.medios_pago import CodigoMedioPago, MedioPagoConfigurado
from ecommerce.domain.ventas import VarianteCatalogo
from ecommerce.infrastructure.usuarios.tests.factories import create_user

from .adapters.transbank_adapter import TransbankWebpayAdapter
from ecommerce.application.pagos import PagoIniciado
from .cifrado import CredencialesIlegibles, cifrar_json, descifrar_json
from .models import ConfiguracionGlobal, MedioPago, OrdenCompra
from .repositorio_medios_pago import DjangoRepositorioMediosPago
from .tests import DATOS_MEDIOS_PAGO, DESTINATARIO, habilitar_medios_pago, usar_catalogo_falso

TOKEN_MP = 'APP_USR-1234567890-secreto-abcd'


class CifradoTests(TestCase):
    def test_ida_y_vuelta_y_texto_cifrado_sin_el_secreto(self):
        cifrado = cifrar_json({'access_token': TOKEN_MP})
        self.assertNotIn(TOKEN_MP, cifrado)
        self.assertEqual(descifrar_json(cifrado), {'access_token': TOKEN_MP})
        self.assertEqual((cifrar_json({}), descifrar_json('')), ('', {}))

    def test_otra_clave_no_puede_descifrar(self):
        cifrado = cifrar_json({'access_token': TOKEN_MP}, clave='clave-original')
        with self.assertRaises(CredencialesIlegibles):
            descifrar_json(cifrado, clave='otra-clave')


class RepositorioMediosPagoTests(TestCase):
    def setUp(self):
        self.repo = DjangoRepositorioMediosPago()

    def test_medio_sin_configurar_esta_deshabilitado_y_vacio(self):
        medio = self.repo.obtener('MERCADO_PAGO')
        self.assertEqual((medio.habilitado, medio.datos), (False, {}))

    def test_las_credenciales_se_guardan_cifradas_y_los_datos_visibles_no(self):
        self.repo.guardar(MedioPagoConfigurado(CodigoMedioPago.TRANSBANK, True, {
            'ambiente': 'PRODUCCION', 'commerce_code': '597012345678', 'api_key': TOKEN_MP}))

        fila = MedioPago.objects.get(codigo='TRANSBANK')
        self.assertEqual(fila.datos, {'ambiente': 'PRODUCCION', 'commerce_code': '597012345678'})
        self.assertNotIn(TOKEN_MP, fila.credenciales_cifradas)
        self.assertEqual(self.repo.obtener('TRANSBANK').datos['api_key'], TOKEN_MP)

    def test_si_cambia_la_clave_el_medio_queda_incompleto_y_no_se_ofrece(self):
        self.repo.guardar(MedioPagoConfigurado(CodigoMedioPago.TRANSBANK, True, {
            'ambiente': 'PRODUCCION', 'commerce_code': '597012345678', 'api_key': TOKEN_MP}))
        self.assertTrue(self.repo.obtener('TRANSBANK').disponible)

        with override_settings(CLAVE_CIFRADO_CREDENCIALES='otra-clave'), \
                self.assertLogs('ecommerce.infrastructure.ventas.repositorio_medios_pago', level='ERROR') as logs:
            medio = self.repo.obtener('TRANSBANK')

        self.assertFalse(medio.disponible)
        self.assertEqual(medio.faltantes, ['api_key'])
        # El log no revela credenciales
        self.assertNotIn(TOKEN_MP, '\n'.join(logs.output))


class MigracionMediosPagoTests(TransactionTestCase):
    """0017 copia los medios de api_keys_pagos a MedioPago, con las credenciales cifradas."""

    ANTERIOR = [('ventas', '0015_orden_paquete_error_ot')]
    COPIA = [('ventas', '0017_copiar_medios_pago')]

    def migrar(self, destino):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(destino)
        return executor.loader.project_state(destino).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def crear_config(self, api_keys_pagos):
        apps = self.migrar(self.ANTERIOR)
        apps.get_model('ventas', 'ConfiguracionGlobal').objects.create(
            id=1, nombre_tienda='QA', api_keys_pagos=api_keys_pagos)

    def medio(self, codigo):
        fila = self.migrar(self.COPIA).get_model('ventas', 'MedioPago').objects.get(codigo=codigo)
        return fila, descifrar_json(fila.credenciales_cifradas)

    @patch.dict('os.environ', {'TRANSBANK_ENVIRONMENT': 'INTEGRACION'})
    def test_transbank_de_integracion_respeta_activo_y_no_guarda_credenciales(self):
        self.crear_config({'TRANSBANK': {'activo': False, 'commerce_code': 'x', 'api_key': 'y'},
                           'MERCADO_PAGO': {'activo': True, 'access_token': TOKEN_MP}})

        transbank, secretos = self.medio('TRANSBANK')
        self.assertEqual((transbank.habilitado, transbank.datos, secretos), (False, {'ambiente': 'INTEGRACION'}, {}))
        mercado_pago, secretos = self.medio('MERCADO_PAGO')
        self.assertTrue(mercado_pago.habilitado)
        self.assertEqual(secretos, {'access_token': TOKEN_MP})
        self.assertNotIn(TOKEN_MP, mercado_pago.credenciales_cifradas)

    @patch.dict('os.environ', {'TRANSBANK_ENVIRONMENT': 'PRODUCCION', 'TRANSBANK_WEBPAY_COMMERCE_CODE': '597099999999',
                               'TRANSBANK_WEBPAY_API_KEY': TOKEN_MP})
    def test_transbank_de_produccion_toma_las_credenciales_que_usaba_del_env(self):
        self.crear_config({'TRANSBANK': {'activo': True}})
        transbank, secretos = self.medio('TRANSBANK')
        self.assertEqual(transbank.datos, {'ambiente': 'PRODUCCION', 'commerce_code': '597099999999'})
        self.assertEqual(secretos, {'api_key': TOKEN_MP})

    def test_sin_configuracion_no_crea_medios(self):
        self.migrar(self.ANTERIOR)
        self.assertFalse(self.migrar(self.COPIA).get_model('ventas', 'MedioPago').objects.exists())


class CheckoutRN02Tests(APITestCase):
    """RN-02: solo se ofrecen y aceptan los medios habilitados y configurados."""

    def setUp(self):
        ConfiguracionGlobal.objects.create(id=1, nombre_tienda='QA', modo_autenticacion='INVITADO',
                                           retiro_en_local_activo=True)
        usar_catalogo_falso(self, {
            ('camisa', 'CAMISA-S'): VarianteCatalogo('Camisa - CAMISA-S', Decimal('10000.00'), 5, True)})
        habilitar_medios_pago('TRANSBANK', 'TRANSFERENCIA')

    def checkout(self, metodo_pago):
        return self.client.post(reverse('checkout'), {
            'items': [{'producto_mongo_id': 'camisa', 'variante_sku': 'CAMISA-S', 'cantidad': 1}],
            'email_invitado': 'invitado@example.test', 'metodo_pago': metodo_pago,
            'direccion_envio_snapshot': {}, 'subtotal': 10000, 'proveedor_logistico': 'RETIRO_LOCAL',
            'acepta_terminos': True, **DESTINATARIO,
        }, format='json')

    def test_con_transbank_y_transferencia_no_se_ofrece_ni_acepta_mercado_pago(self):
        self.assertEqual(self.client.get(reverse('configuracion-global')).data['pasarelas_activas'],
                         ['TRANSBANK', 'TRANSFERENCIA'])
        for metodo in ('MERCADO_PAGO', 'PAYPAL', 'LINKIFY'):
            with self.subTest(metodo=metodo):
                response = self.checkout(metodo)
                self.assertEqual(response.status_code, 400)
                self.assertIn('no está disponible', str(response.data['metodo_pago']))
        self.assertFalse(OrdenCompra.objects.exists())
        self.assertEqual(self.checkout('TRANSFERENCIA').status_code, 201)

    def test_medio_deshabilitado_o_incompleto_deja_de_aceptarse(self):
        repo = DjangoRepositorioMediosPago()
        repo.guardar(MedioPagoConfigurado(CodigoMedioPago.TRANSFERENCIA, False, DATOS_MEDIOS_PAGO['TRANSFERENCIA']))
        repo.guardar(MedioPagoConfigurado(CodigoMedioPago.TRANSBANK, True, {'ambiente': 'PRODUCCION'}))
        self.assertEqual(self.client.get(reverse('configuracion-global')).data['pasarelas_activas'], [])
        for metodo in ('TRANSFERENCIA', 'TRANSBANK'):
            with self.subTest(metodo=metodo):
                self.assertEqual(self.checkout(metodo).status_code, 400)

    @patch('ecommerce.infrastructure.ventas.adapters.mercadopago.MercadoPagoAdapter.iniciar',
           return_value=PagoIniciado(referencia='pref-123', url_pago='https://mp.test/pago'))
    def test_mercado_pago_configurado_se_acepta_al_estar_su_integracion_lista(self, _crear):
        habilitar_medios_pago('MERCADO_PAGO')
        self.assertIn('MERCADO_PAGO', self.client.get(reverse('configuracion-global')).data['pasarelas_activas'])
        self.assertEqual(self.checkout('MERCADO_PAGO').status_code, 201)

    def test_medio_con_integracion_no_lista_no_se_acepta(self):
        from ecommerce.domain.medios_pago import DefinicionMedioPago, definicion_medio
        def fake_definicion(codigo):
            d = definicion_medio(codigo)
            return DefinicionMedioPago(d.codigo, d.nombre, d.campos, integracion_lista=False)

        with patch('ecommerce.domain.medios_pago.definicion_medio', side_effect=fake_definicion):
            habilitar_medios_pago('MERCADO_PAGO')
            self.assertNotIn('MERCADO_PAGO', self.client.get(reverse('configuracion-global')).data['pasarelas_activas'])
            self.assertEqual(self.checkout('MERCADO_PAGO').status_code, 400)

    def test_transferencia_entrega_datos_bancarios_monto_y_referencia_en_la_respuesta_y_el_correo(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.checkout('TRANSFERENCIA')

        orden_id = response.data['orden_id']
        instrucciones = response.data['instrucciones_pago']
        self.assertEqual((instrucciones['monto'], instrucciones['referencia']), (10000, f'Pedido #{orden_id}'))
        self.assertIn({'etiqueta': 'Número de cuenta', 'valor': DATOS_MEDIOS_PAGO['TRANSFERENCIA']['numero_cuenta']},
                      instrucciones['datos'])
        correo, = mail.outbox
        self.assertIn('DATOS PARA TRANSFERIR', correo.body)
        self.assertIn('Transfiere $10.000', correo.body)
        self.assertIn(f'Número de cuenta: {DATOS_MEDIOS_PAGO["TRANSFERENCIA"]["numero_cuenta"]}', correo.body)
        self.assertIn('Datos para transferir', correo.alternatives[0][0])
        # Plazo de pago: el comprador sabe hasta cuándo puede transferir (48 h, hora de Chile en el correo)
        vence = OrdenCompra.objects.get(id=orden_id).fecha_creacion + timedelta(hours=48)
        self.assertEqual(instrucciones['vence'], vence)
        self.assertIn(f"Tienes hasta el {timezone.localtime(vence).strftime('%d-%m-%Y a las %H:%M')} para transferir",
                      correo.body)

    @patch('ecommerce.infrastructure.ventas.adapters.transbank_adapter.TransbankWebpayAdapter.iniciar_transaccion',
           return_value={'exito': True, 'url_pago': 'https://webpay.test/pago', 'token': 'tbk-token'})
    def test_otros_medios_no_reciben_datos_bancarios(self, _iniciar):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.checkout('TRANSBANK')
        self.assertNotIn('instrucciones_pago', response.data)
        self.assertNotIn('DATOS PARA TRANSFERIR', mail.outbox[0].body)

    def test_la_configuracion_publica_no_expone_credenciales(self):
        habilitar_medios_pago('MERCADO_PAGO')
        cuerpo = self.client.get(reverse('configuracion-global')).content.decode()
        for secreto in (DATOS_MEDIOS_PAGO['MERCADO_PAGO']['access_token'], 'secreto-webhook', 'numero_cuenta'):
            self.assertNotIn(secreto, cuerpo)


class AdminMediosPagoAPITests(APITestCase):
    """RN-02: el admin configura los medios desde el panel y nunca ve una credencial completa."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_token = Token.objects.create(user=create_user('admin@example.test', rol='ADMIN'))
        cls.buyer_token = Token.objects.create(user=create_user())

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')

    def guardar(self, codigo, cuerpo):
        return self.client.put(reverse('admin-medio-pago', args=[codigo]), cuerpo, format='json')

    def test_lista_los_medios_con_sus_campos_y_lo_que_falta(self):
        medios = self.client.get(reverse('admin-medios-pago')).data
        self.assertEqual([m['codigo'] for m in medios], ['TRANSBANK', 'MERCADO_PAGO', 'TRANSFERENCIA'])
        transbank = medios[0]
        self.assertEqual((transbank['habilitado'], transbank['disponible'], transbank['faltantes']),
                         (False, False, ['ambiente']))
        api_key = next(c for c in transbank['campos'] if c['nombre'] == 'api_key')
        self.assertEqual((api_key['secreto'], api_key['obligatorio_si']), (True, ['ambiente', 'PRODUCCION']))

    def test_guardar_devuelve_credenciales_enmascaradas_y_las_conserva_al_reenviarlas(self):
        response = self.guardar('mercado_pago', {'habilitado': True, 'datos': {
            'access_token': TOKEN_MP, 'webhook_secret': 'secreto-de-webhook-5678'}})
        self.assertEqual(response.status_code, 200)
        # Completo y habilitado: la integración está lista y se ofrece
        self.assertEqual(response.data['faltantes'], [])
        self.assertEqual((response.data['integracion_lista'], response.data['disponible']), (True, True))
        self.assertEqual(response.data['datos'], {'access_token': '••••abcd', 'webhook_secret': '••••5678'})
        self.assertNotIn(TOKEN_MP, response.content.decode())

        # El panel reenvía lo que mostró: no debe pisar la credencial con los puntos
        self.guardar('MERCADO_PAGO', {'habilitado': True, 'datos': response.data['datos']})
        self.assertEqual(DjangoRepositorioMediosPago().obtener('MERCADO_PAGO').datos['access_token'], TOKEN_MP)

    def test_datos_invalidos_son_400_y_medio_inexistente_404(self):
        response = self.guardar('TRANSFERENCIA', {'habilitado': True, 'datos': {'tipo_cuenta': 'Cuenta bitcoin'}})
        self.assertEqual(response.status_code, 400)
        self.assertIn('tipo_cuenta', response.data['datos'])
        self.assertEqual(self.guardar('PAYPAL', {'habilitado': True}).status_code, 404)

    def test_solo_el_admin_configura_medios_de_pago(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.buyer_token.key}')
        self.assertEqual(self.client.get(reverse('admin-medios-pago')).status_code, 403)
        self.assertEqual(self.guardar('TRANSBANK', {'habilitado': True}).status_code, 403)
        self.client.credentials()
        self.assertEqual(self.client.get(reverse('admin-medios-pago')).status_code, 401)


@patch('ecommerce.infrastructure.ventas.adapters.transbank_adapter.Transaction')
class TransbankConfiguracionTests(TestCase):
    """Transbank toma el ambiente y las credenciales del panel, no del .env."""

    def opciones(self, transaction):
        TransbankWebpayAdapter._obtener_instancia()
        return transaction.call_args.kwargs['options']

    def test_integracion_usa_las_llaves_publicas_de_prueba(self, transaction):
        habilitar_medios_pago('TRANSBANK')
        opciones = self.opciones(transaction)
        self.assertEqual((opciones.commerce_code, opciones.integration_type), ('597055555532', IntegrationType.TEST))

    def test_produccion_usa_las_credenciales_guardadas(self, transaction):
        DjangoRepositorioMediosPago().guardar(MedioPagoConfigurado(CodigoMedioPago.TRANSBANK, True, {
            'ambiente': 'PRODUCCION', 'commerce_code': '597012345678', 'api_key': TOKEN_MP}))
        opciones = self.opciones(transaction)
        self.assertEqual((opciones.commerce_code, opciones.api_key, opciones.integration_type),
                         ('597012345678', TOKEN_MP, IntegrationType.LIVE))

    def test_produccion_sin_credenciales_no_inicia_el_pago(self, transaction):
        DjangoRepositorioMediosPago().guardar(
            MedioPagoConfigurado(CodigoMedioPago.TRANSBANK, True, {'ambiente': 'PRODUCCION'}))
        with self.assertLogs('ecommerce.infrastructure.ventas.adapters.transbank_adapter', level='ERROR'):
            resultado = TransbankWebpayAdapter.iniciar_transaccion('1', 1000, 'http://x/retorno/', 's')
        self.assertFalse(resultado['exito'])
        transaction.assert_not_called()
