from datetime import timedelta
from unittest.mock import patch
from django.test import SimpleTestCase

from ecommerce.application.medios_pago import ConfigurarMedioPago, MediosPagoDisponibles, RepositorioMediosPago
from ecommerce.domain.medios_pago import (
    CodigoMedioPago, DefinicionMedioPago, DatosMedioPagoInvalidos, MedioPagoConfigurado, MedioPagoNoDisponible, enmascarar,
    plazo_pago_transferencia,
)

C = CodigoMedioPago

DATOS_BANCO = {'banco': 'Banco Estado', 'tipo_cuenta': 'Cuenta vista', 'numero_cuenta': '12345678',
               'rut_titular': '11.111.111-1', 'nombre_titular': 'Tienda QA', 'email': 'pagos@example.test'}


class RepositorioMediosPagoFalso(RepositorioMediosPago):
    def __init__(self):
        self.medios = {}

    def obtener(self, codigo):
        return self.medios.get(CodigoMedioPago(codigo), MedioPagoConfigurado(CodigoMedioPago(codigo)))

    def guardar(self, medio):
        self.medios[medio.codigo] = medio


class ConfigurarMedioPagoTests(SimpleTestCase):
    def setUp(self):
        self.repo = RepositorioMediosPagoFalso()
        self.caso = ConfigurarMedioPago(self.repo)

    def test_las_credenciales_se_muestran_enmascaradas(self):
        medio = self.caso.ejecutar('MERCADO_PAGO', True, {'access_token': 'APP_USR-123456789-abcd',
                                                         'webhook_secret': 'secreto-largo-9876'})
        self.assertEqual(medio.datos_visibles(), {'access_token': '••••abcd', 'webhook_secret': '••••9876'})
        # Una credencial corta no revela su final
        self.assertEqual(enmascarar('abc123'), '••••')

    def test_guardar_sin_tocar_la_credencial_enmascarada_la_conserva(self):
        self.caso.ejecutar('MERCADO_PAGO', True, {'access_token': 'APP_USR-123456789-abcd',
                                                 'webhook_secret': 'secreto-largo-9876'})
        medio = self.caso.ejecutar('MERCADO_PAGO', False, {'access_token': '••••abcd', 'webhook_secret': ''})
        self.assertEqual(medio.datos, {'access_token': 'APP_USR-123456789-abcd'})
        self.assertFalse(medio.habilitado)

    def test_campo_desconocido_u_opcion_invalida_se_rechaza_sin_guardar(self):
        with self.assertRaises(DatosMedioPagoInvalidos) as error:
            self.caso.ejecutar('TRANSFERENCIA', True, {'tipo_cuenta': 'Cuenta bitcoin', 'clave_banco': 'x'})
        self.assertEqual(set(error.exception.errores), {'tipo_cuenta', 'clave_banco'})
        self.assertEqual(self.repo.medios, {})

    def test_los_datos_de_la_transferencia_se_validan_porque_el_comprador_los_copia_para_pagar(self):
        with self.assertRaises(DatosMedioPagoInvalidos) as error:
            self.caso.ejecutar('TRANSFERENCIA', True, {**DATOS_BANCO, 'rut_titular': '11.111.111-2',
                                                      'email': 'pagos@', 'numero_cuenta': 'cuenta 12'})
        self.assertEqual(set(error.exception.errores), {'rut_titular', 'email', 'numero_cuenta'})
        self.assertEqual(self.repo.medios, {})

    def test_el_rut_el_correo_y_la_cuenta_se_guardan_con_un_formato_uniforme(self):
        medio = self.caso.ejecutar('TRANSFERENCIA', True, {**DATOS_BANCO, 'rut_titular': '111111111',
                                                          'email': 'Pagos@Example.TEST', 'numero_cuenta': '000-123  456'})
        self.assertEqual((medio.datos['rut_titular'], medio.datos['email'], medio.datos['numero_cuenta']),
                         ('11.111.111-1', 'pagos@example.test', '000-123 456'))


class MediosPagoDisponiblesTests(SimpleTestCase):
    """RN-02: solo se ofrecen y aceptan los medios habilitados y configurados."""

    def setUp(self):
        self.repo = RepositorioMediosPagoFalso()
        self.casos = MediosPagoDisponibles(self.repo)

    def guardar(self, codigo, habilitado, datos):
        self.repo.guardar(MedioPagoConfigurado(C(codigo), habilitado, datos))

    def test_solo_transbank_y_transferencia_no_ofrecen_ni_aceptan_mercado_pago(self):
        self.guardar('TRANSBANK', True, {'ambiente': 'INTEGRACION'})
        self.guardar('TRANSFERENCIA', True, DATOS_BANCO)
        self.assertEqual(self.casos.disponibles(), [C.TRANSBANK, C.TRANSFERENCIA])
        with self.assertRaises(MedioPagoNoDisponible):
            self.casos.exigir('MERCADO_PAGO')
        self.assertEqual(self.casos.exigir('TRANSFERENCIA').datos['banco'], 'Banco Estado')

    def test_habilitado_pero_incompleto_no_se_ofrece(self):
        self.guardar('MERCADO_PAGO', True, {'access_token': 'APP_USR-123456789-abcd'})
        self.guardar('TRANSFERENCIA', True, {**DATOS_BANCO, 'numero_cuenta': ''})
        self.assertEqual(self.casos.disponibles(), [])
        self.assertEqual(self.repo.obtener('MERCADO_PAGO').faltantes, ['webhook_secret'])

    def test_completo_pero_deshabilitado_no_se_ofrece(self):
        self.guardar('TRANSFERENCIA', False, DATOS_BANCO)
        self.assertEqual(self.casos.disponibles(), [])

    def test_transbank_en_produccion_exige_credenciales_y_en_integracion_no(self):
        self.guardar('TRANSBANK', True, {'ambiente': 'PRODUCCION', 'commerce_code': '597012345678'})
        self.assertEqual(self.repo.obtener('TRANSBANK').faltantes, ['api_key'])
        self.assertEqual(self.casos.disponibles(), [])
        self.guardar('TRANSBANK', True, {'ambiente': 'INTEGRACION'})
        self.assertEqual(self.casos.disponibles(), [C.TRANSBANK])

    def test_mercado_pago_completo_se_ofrece_al_estar_su_integracion_lista(self):
        self.guardar('MERCADO_PAGO', True, {'access_token': 'APP_USR-123456789-abcd',
                                            'webhook_secret': 'secreto-largo-9876'})
        self.assertEqual(self.repo.obtener('MERCADO_PAGO').faltantes, [])
        self.assertEqual(self.casos.disponibles(), [C.MERCADO_PAGO])
        self.casos.exigir('MERCADO_PAGO')

    def test_medio_con_integracion_no_lista_no_se_ofrece(self):
        from ecommerce.domain.medios_pago import definicion_medio
        def fake_definicion(codigo):
            d = definicion_medio(codigo)
            return DefinicionMedioPago(d.codigo, d.nombre, d.campos, integracion_lista=False)

        with patch('ecommerce.domain.medios_pago.definicion_medio', side_effect=fake_definicion):
            self.guardar('MERCADO_PAGO', True, {'access_token': 'APP_USR-123456789-abcd',
                                                'webhook_secret': 'secreto-largo-9876'})
            self.assertEqual(self.casos.disponibles(), [])
            with self.assertRaises(MedioPagoNoDisponible):
                self.casos.exigir('MERCADO_PAGO')

    def test_el_comprador_solo_recibe_los_datos_que_no_son_secretos(self):
        self.guardar('TRANSFERENCIA', True, DATOS_BANCO)
        self.assertEqual(self.repo.obtener('TRANSFERENCIA').datos_para_comprador(), DATOS_BANCO)
        self.guardar('TRANSBANK', True, {'ambiente': 'PRODUCCION', 'commerce_code': '5970', 'api_key': 'llave'})
        self.assertEqual(self.repo.obtener('TRANSBANK').datos_para_comprador(),
                         {'ambiente': 'PRODUCCION', 'commerce_code': '5970'})

    def test_la_transferencia_se_ofrece_sin_linkify_y_su_configuracion_no_llega_al_comprador(self):
        self.guardar('TRANSFERENCIA', True, DATOS_BANCO)
        self.assertEqual(self.casos.exigir('TRANSFERENCIA').codigo, 'TRANSFERENCIA')

        self.guardar('TRANSFERENCIA', True, {**DATOS_BANCO, 'verificar_con_linkify': 'Sí',
                                              'linkify_secret': 'secreto-linkify-1234'})
        self.assertEqual(self.repo.obtener('TRANSFERENCIA').datos_para_comprador(), DATOS_BANCO)

    def test_medio_inexistente_no_esta_disponible(self):
        for codigo in ('PAYPAL', '', 'transbank'):
            with self.subTest(codigo=codigo), self.assertRaises(MedioPagoNoDisponible):
                self.casos.exigir(codigo)


class PlazoPagoTransferenciaTests(SimpleTestCase):
    def transferencia(self, **datos):
        return MedioPagoConfigurado(C.TRANSFERENCIA, True, {**DATOS_BANCO, **datos})

    def test_usa_el_plazo_que_eligio_la_tienda(self):
        for horas in ('12', '24', '48', '72'):
            with self.subTest(horas=horas):
                self.assertEqual(plazo_pago_transferencia(self.transferencia(plazo_pago_horas=horas)),
                                 timedelta(hours=int(horas)))

    def test_sin_elegir_son_48_horas_y_la_transferencia_sigue_disponible(self):
        medio = self.transferencia()
        self.assertEqual(plazo_pago_transferencia(medio), timedelta(hours=48))
        self.assertTrue(medio.disponible)

    def test_un_valor_guardado_fuera_de_las_opciones_vuelve_a_48_horas(self):
        self.assertEqual(plazo_pago_transferencia(self.transferencia(plazo_pago_horas='5')), timedelta(hours=48))

    def test_el_panel_rechaza_un_plazo_que_no_esta_entre_las_opciones(self):
        repositorio = RepositorioMediosPagoFalso()
        with self.assertRaises(DatosMedioPagoInvalidos) as error:
            ConfigurarMedioPago(repositorio).ejecutar(C.TRANSFERENCIA, True, {**DATOS_BANCO, 'plazo_pago_horas': '36'})
        self.assertIn('plazo_pago_horas', error.exception.errores)

    def test_el_comprador_no_recibe_el_plazo_entre_los_datos_bancarios(self):
        self.assertNotIn('plazo_pago_horas', self.transferencia(plazo_pago_horas='24').datos_para_comprador())
