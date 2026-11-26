from decimal import Decimal

from django.test import SimpleTestCase

from ecommerce.application.couriers import (
    ComunasConCobertura, ConfigurarCourier, CotizarEnvio, Courier, CourierNoActivo, Couriers,
    RepositorioCredencialesCourier, TransportistaSegunProveedor,
)
from ecommerce.domain.logistica import (
    AMBIENTE_PRODUCCION, AMBIENTE_PRUEBAS, FORMATO_DIGITOS, FORMATO_RUT, CampoCredencial, CotizacionEnvio,
    CourierNoDisponible, CredencialesCourier, CredencialesInvalidas, EnvioSolicitado, ErrorOrdenTransporte, Paquete,
    SinCobertura, rut_sin_digito,
)

PAQUETE = Paquete(Decimal('1'), Decimal('10'), Decimal('10'), Decimal('10'))
CAMPOS = (CampoCredencial('llave', 'API key', obligatorio=True), CampoCredencial('cuenta', 'N° de cuenta'))


class CourierFalso(Courier):
    CAMPOS = CAMPOS
    con_sucursales = True

    def __init__(self, codigo, precio=None, comunas=(), falla=None, ot='OT-1'):
        self.codigo, self.nombre = codigo, codigo.capitalize()
        self.precio, self._comunas, self.falla, self.ot = precio, comunas, falla, ot
        self.envios = []

    def _fallar(self):
        if self.falla:
            raise self.falla

    def comunas(self):
        self._fallar()
        return list(self._comunas)

    def cotizar(self, origen, destino, paquete):
        self._fallar()
        return CotizacionEnvio(self.codigo, self.nombre, self.precio, 'EXPRESS')

    def sucursales(self, comuna):
        return []

    def etiqueta(self, numero_ot):
        return 'base64'

    def consultar_estado(self, codigo_seguimiento):
        return 'En tránsito'

    def generar_orden_transporte(self, envio):
        self.envios.append(envio)
        return self.ot


class CouriersFalsos(Couriers):
    def __init__(self, *activos, inactivos=()):
        self._activos, self._inactivos = list(activos), list(inactivos)

    def activos(self):
        return self._activos

    def obtener(self, codigo, solo_activos=True):
        candidatos = self._activos + ([] if solo_activos else self._inactivos)
        for courier in candidatos:
            if courier.codigo == codigo:
                return courier
        raise CourierNoActivo()


class RepositorioFalso(RepositorioCredencialesCourier):
    def __init__(self):
        self.guardadas = {}

    def obtener(self, codigo, campos):
        return self.guardadas.get(codigo, CredencialesCourier.con(campos))

    def guardar(self, codigo, credenciales):
        self.guardadas[codigo] = credenciales


def envio(proveedor):
    return EnvioSolicitado(orden_id=7, proveedor=proveedor, comuna='Maipú', calle='Calle', numero='1', complemento='',
                           destinatario='Ana', email='ana@example.test', valor_declarado=1000)


class CotizarEnvioTests(SimpleTestCase):
    """RF-02.3: cada courier activo cotiza; uno caído no deja al comprador sin opciones."""

    def test_sin_proveedor_cotizan_todos_los_activos(self):
        casos = CotizarEnvio(CouriersFalsos(CourierFalso('CHILEXPRESS', 3990), CourierFalso('STARKEN', 3500)))
        opciones = casos.ejecutar('Santiago', 'Maipú', PAQUETE)
        self.assertEqual([(o.proveedor, o.precio) for o in opciones], [('CHILEXPRESS', 3990), ('STARKEN', 3500)])

    def test_un_courier_caido_o_sin_cobertura_no_tapa_a_los_demas(self):
        couriers = CouriersFalsos(CourierFalso('CHILEXPRESS', falla=CourierNoDisponible()),
                                  CourierFalso('STARKEN', 3500), CourierFalso('OTRO', falla=SinCobertura()))
        self.assertEqual([o.proveedor for o in CotizarEnvio(couriers).ejecutar('Santiago', 'Maipú', PAQUETE)],
                         ['STARKEN'])

    def test_si_ninguno_llega_a_la_comuna_es_sin_cobertura_y_si_alguno_fallo_no_disponible(self):
        sin_cobertura = CouriersFalsos(CourierFalso('A', falla=SinCobertura('No llega')),
                                       CourierFalso('B', falla=SinCobertura('Tampoco')))
        with self.assertRaisesMessage(SinCobertura, 'No llega'):
            CotizarEnvio(sin_cobertura).ejecutar('Santiago', 'Isla de Pascua', PAQUETE)
        mixto = CouriersFalsos(CourierFalso('A', falla=SinCobertura()), CourierFalso('B', falla=CourierNoDisponible()))
        with self.assertRaises(CourierNoDisponible):
            CotizarEnvio(mixto).ejecutar('Santiago', 'Maipú', PAQUETE)

    def test_sin_couriers_activos_no_se_cotiza(self):
        with self.assertRaises(CourierNoActivo):
            CotizarEnvio(CouriersFalsos()).ejecutar('Santiago', 'Maipú', PAQUETE)

    def test_con_proveedor_se_cobra_ese_y_sus_errores_llegan_tal_cual(self):
        couriers = CouriersFalsos(CourierFalso('CHILEXPRESS', 3990), CourierFalso('STARKEN', falla=SinCobertura()))
        casos = CotizarEnvio(couriers)
        self.assertEqual(casos.precio('Santiago', 'Maipú', PAQUETE, 'CHILEXPRESS'), Decimal('3990'))
        with self.assertRaises(SinCobertura):
            casos.ejecutar('Santiago', 'Maipú', PAQUETE, 'STARKEN')
        with self.assertRaises(CourierNoActivo):
            casos.ejecutar('Santiago', 'Maipú', PAQUETE, 'INEXISTENTE')


class ComunasConCoberturaTests(SimpleTestCase):
    def test_une_las_comunas_de_los_activos_sin_repetir(self):
        couriers = CouriersFalsos(CourierFalso('A', comunas=['MAIPU', 'SANTIAGO']),
                                  CourierFalso('B', comunas=['SANTIAGO', 'ARICA']),
                                  CourierFalso('C', falla=CourierNoDisponible()))
        self.assertEqual(ComunasConCobertura(couriers).ejecutar(), ['ARICA', 'MAIPU', 'SANTIAGO'])

    def test_si_ninguno_responde_no_esta_disponible(self):
        with self.assertRaises(CourierNoDisponible):
            ComunasConCobertura(CouriersFalsos(CourierFalso('A', falla=CourierNoDisponible()))).ejecutar()
        with self.assertRaises(CourierNoActivo):
            ComunasConCobertura(CouriersFalsos()).ejecutar()


class ConfigurarCourierTests(SimpleTestCase):
    """RNF-03: las llaves se cargan en el panel, también las de un courier aún inactivo."""

    def setUp(self):
        self.repositorio = RepositorioFalso()
        self.caso = ConfigurarCourier(self.repositorio, CouriersFalsos(inactivos=[CourierFalso('STARKEN')]))

    def test_guarda_los_campos_del_courier_y_queda_configurado(self):
        credenciales = self.caso.ejecutar('STARKEN', {'llave': 'llave-starken-1234'})
        self.assertTrue(credenciales.configuradas)
        self.assertEqual(self.repositorio.guardadas['STARKEN'].como_dict(),
                         {'llave': 'llave-starken-1234', 'cuenta': ''})

    def test_un_campo_que_el_courier_no_declara_se_rechaza(self):
        with self.assertRaises(CredencialesInvalidas) as error:
            self.caso.ejecutar('STARKEN', {'secreto': 'x'})
        self.assertEqual(error.exception.errores, {'secreto': 'Campo desconocido.'})

    def test_un_courier_desconocido_se_rechaza(self):
        with self.assertRaises(CourierNoActivo):
            self.caso.ejecutar('INEXISTENTE', {'llave': 'x'})


class CredencialesCourierTests(SimpleTestCase):
    def test_faltan_las_obligatorias_y_el_panel_ve_solo_los_ultimos_4(self):
        vacias = CredencialesCourier.con(CAMPOS)
        self.assertEqual(vacias.faltantes, ['llave'])
        llenas = CredencialesCourier.con(CAMPOS, {'llave': 'llave-0001-abcd', 'otra': 'se descarta'})
        self.assertTrue(llenas.configuradas)
        self.assertEqual(llenas.como_dict(), {'llave': 'llave-0001-abcd', 'cuenta': ''})
        self.assertEqual(llenas.visibles()['llave'][-4:], 'abcd')
        self.assertNotIn('llave-0001', llenas.visibles()['llave'])

    def test_una_llave_enmascarada_se_conserva_y_una_vacia_se_borra(self):
        guardadas = CredencialesCourier.con(CAMPOS, {'llave': 'llave-0001-abcd', 'cuenta': '123456'})
        cambios = guardadas.con_cambios({'llave': guardadas.visibles()['llave'], 'cuenta': ''})
        self.assertEqual(cambios.como_dict(), {'llave': 'llave-0001-abcd', 'cuenta': ''})


# Como los declara un courier con ambiente de pruebas y de producción (ej. Chilexpress)
CAMPOS_CON_AMBIENTE = (
    CampoCredencial('ambiente', 'Ambiente', secreto=False, opciones=(AMBIENTE_PRUEBAS, AMBIENTE_PRODUCCION),
                    por_defecto=AMBIENTE_PRUEBAS),
    CampoCredencial('llave', 'API key', obligatorio=True),
    CampoCredencial('numero_cliente', 'Número de cliente', secreto=False, formato=FORMATO_DIGITOS, obligatorio=True,
                    obligatorio_si=('ambiente', AMBIENTE_PRODUCCION)),
    CampoCredencial('rut', 'RUT de la empresa', secreto=False, formato=FORMATO_RUT, obligatorio=True,
                    obligatorio_si=('ambiente', AMBIENTE_PRODUCCION)),
)


class CredencialesConAmbienteTests(SimpleTestCase):
    """Las llaves de producción de un courier traen datos del contrato de la tienda, que en pruebas no se piden."""

    def test_sin_cargar_el_ambiente_es_el_de_pruebas_y_no_pide_los_datos_del_contrato(self):
        credenciales = CredencialesCourier.con(CAMPOS_CON_AMBIENTE, {'llave': 'llave-0001-abcd'})
        self.assertEqual(credenciales.valor('ambiente'), AMBIENTE_PRUEBAS)
        self.assertTrue(credenciales.configuradas)
        # El valor por defecto no se guarda: si cambia, las tiendas que no lo eligieron siguen el nuevo
        self.assertNotIn(AMBIENTE_PRUEBAS, credenciales.como_dict().values())

    def test_en_produccion_faltan_el_numero_de_cliente_y_el_rut(self):
        credenciales = CredencialesCourier.con(CAMPOS_CON_AMBIENTE,
                                               {'ambiente': AMBIENTE_PRODUCCION, 'llave': 'llave-0001-abcd'})
        self.assertEqual(credenciales.faltantes, ['numero_cliente', 'rut'])
        completas = credenciales.con_cambios({'numero_cliente': '18578680', 'rut': '76.123.456-0'})
        self.assertTrue(completas.configuradas)

    def test_el_panel_ve_completos_los_datos_que_no_son_llaves(self):
        credenciales = CredencialesCourier.con(CAMPOS_CON_AMBIENTE, {
            'ambiente': AMBIENTE_PRODUCCION, 'llave': 'llave-0001-abcd', 'numero_cliente': '18578680',
            'rut': '76.123.456-0'})
        visibles = credenciales.visibles()
        self.assertEqual((visibles['ambiente'], visibles['numero_cliente'], visibles['rut']),
                         (AMBIENTE_PRODUCCION, '18578680', '76.123.456-0'))
        self.assertNotIn('llave-0001', visibles['llave'])

    def test_un_dato_visible_igual_a_la_mascara_no_se_confunde_con_una_llave(self):
        guardadas = CredencialesCourier.con(CAMPOS_CON_AMBIENTE, {'llave': 'llave-0001-abcd'})
        cambios = guardadas.con_cambios({'numero_cliente': '12345678', 'ambiente': AMBIENTE_PRODUCCION})
        self.assertEqual(cambios.valor('numero_cliente'), '12345678')
        self.assertEqual(cambios.valor('llave'), 'llave-0001-abcd')

    def test_el_rut_se_guarda_con_formato_y_se_rechaza_si_el_digito_no_cuadra(self):
        guardadas = CredencialesCourier.con(CAMPOS_CON_AMBIENTE)
        self.assertEqual(guardadas.con_cambios({'rut': '761234560'}).valor('rut'), '76.123.456-0')
        with self.assertRaises(CredencialesInvalidas) as error:
            guardadas.con_cambios({'rut': '76.123.456-1'})
        self.assertIn('rut', error.exception.errores)

    def test_se_rechazan_un_ambiente_desconocido_y_un_numero_con_letras(self):
        with self.assertRaises(CredencialesInvalidas) as error:
            CredencialesCourier.con(CAMPOS_CON_AMBIENTE).con_cambios(
                {'ambiente': 'STAGING', 'numero_cliente': '1857-868A'})
        self.assertEqual(set(error.exception.errores), {'ambiente', 'numero_cliente'})

    def test_vaciar_el_ambiente_vuelve_al_de_pruebas(self):
        guardadas = CredencialesCourier.con(CAMPOS_CON_AMBIENTE, {'ambiente': AMBIENTE_PRODUCCION})
        self.assertEqual(guardadas.con_cambios({'ambiente': ''}).valor('ambiente'), AMBIENTE_PRUEBAS)

    def test_el_valor_por_defecto_que_reenvia_el_panel_no_se_guarda(self):
        guardadas = CredencialesCourier.con(CAMPOS_CON_AMBIENTE, {'ambiente': AMBIENTE_PRODUCCION})
        cambios = guardadas.con_cambios({'ambiente': AMBIENTE_PRUEBAS})
        self.assertEqual((cambios.valor('ambiente'), cambios.como_dict()['ambiente']), (AMBIENTE_PRUEBAS, ''))

    def test_el_rut_va_sin_puntos_ni_digito_verificador(self):
        self.assertEqual(rut_sin_digito('76.123.456-0'), '76123456')
        self.assertEqual(rut_sin_digito('9.876.543-K'), '9876543')
        self.assertEqual(rut_sin_digito(''), '')


class TransportistaSegunProveedorTests(SimpleTestCase):
    """RF-02.3: la OT la genera el courier que eligió el comprador."""

    def test_la_orden_va_al_courier_del_pedido(self):
        chilexpress, starken = CourierFalso('CHILEXPRESS', ot='CX-1'), CourierFalso('STARKEN', ot='ST-1')
        transportista = TransportistaSegunProveedor(CouriersFalsos(chilexpress, starken))
        self.assertEqual(transportista.generar_orden_transporte(envio('STARKEN')), 'ST-1')
        self.assertEqual((len(chilexpress.envios), len(starken.envios)), (0, 1))

    def test_un_courier_inactivo_es_un_error_de_la_orden_de_transporte(self):
        with self.assertRaises(ErrorOrdenTransporte):
            TransportistaSegunProveedor(CouriersFalsos()).generar_orden_transporte(envio('CHILEXPRESS'))

    def test_solo_las_entregas_con_courier_requieren_orden_de_transporte(self):
        self.assertTrue(envio('CHILEXPRESS').requiere_orden_transporte)
        self.assertTrue(envio('STARKEN').requiere_orden_transporte)
        for proveedor in ('RETIRO_LOCAL', 'ENTREGA_COORDINADA', '', None):
            self.assertFalse(envio(proveedor).requiere_orden_transporte)
