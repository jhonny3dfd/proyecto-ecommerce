from decimal import Decimal
from unittest.mock import Mock, patch

from django.urls import reverse
from rest_framework.test import APITestCase

from ecommerce.application.couriers import TransportistaSegunProveedor
from ecommerce.application.test_couriers import CourierFalso, CouriersFalsos
from ecommerce.application.ventas import GenerarOrdenTransporte
from ecommerce.domain.logistica import CourierNoDisponible, MedidasEnvio
from ecommerce.domain.ventas import VarianteCatalogo
from ecommerce.infrastructure.usuarios.tests.factories import create_user

from .cifrado import cifrar_json
from .couriers import DjangoCouriers
from .couriers.chilexpress import ChilexpressCourier
from .models import ConfiguracionGlobal, OrdenCompra, ProveedorEnvio
from .repositorio_ordenes import DjangoRepositorioOrdenes
from .test_chilexpress import guardar_credenciales
from .tests import DESTINATARIO, habilitar_medios_pago, usar_catalogo_falso


PAQUETE = {'peso_kg': '1.50', 'alto_cm': '10', 'ancho_cm': '20', 'largo_cm': '30'}
# Lo que podría mandar un navegador alterado para pagar menos envío: el servidor lo ignora
PAQUETE_MANIPULADO = {'peso_kg': '0.01', 'alto_cm': '1', 'ancho_cm': '1', 'largo_cm': '1'}
ADAPTADOR_CHILEXPRESS = 'ecommerce.infrastructure.ventas.couriers.chilexpress'


def respuesta_chilexpress(servicios, status=200):
    result = Mock(status_code=status, text='provider error')
    result.json.return_value = {'data': {'courierServiceOptions': servicios}}
    return result


TARIFA_OK = [{'serviceValue': 3500, 'serviceDescription': 'EXPRESS'}]
# Un ítem de $25.000, el subtotal que usan las pruebas de checkout
ITEMS = [{'producto_mongo_id': 'polera', 'variante_sku': 'POLERA-M', 'cantidad': 1}]


class CotizacionesAPITests(APITestCase):
    def setUp(self):
        # La llave la carga el admin en el panel (cifrada en la base), no el .env
        guardar_credenciales(cotizador='secreto-chilexpress')
        habilitar_medios_pago('TRANSFERENCIA', 'TRANSBANK')
        self.config = ConfiguracionGlobal.objects.create(
            id=1, nombre_tienda='QA', comuna_origen='Santiago', retiro_en_local_activo=True,
        )
        self.payload = {'destino': 'SANTIAGO', 'items': ITEMS}
        # 1,5 kg y 10 x 20 x 30 cm: el paquete es de 1,5 kg y un cubo de 30 cm (el lado más largo)
        usar_catalogo_falso(self, {
            ('polera', 'POLERA-M'): VarianteCatalogo(
                'Polera - POLERA-M', Decimal('25000'), 5, True,
                MedidasEnvio(Decimal('1.5'), Decimal('10'), Decimal('20'), Decimal('30'))),
        })
        # El catálogo de comunas se descarga por red: en pruebas se fija uno conocido
        catalogo = patch(f'{ADAPTADOR_CHILEXPRESS}.ChilexpressCourier._obtener_catalogo_dinamico',
                         return_value={'SANTIAGO': 'STGO'})
        catalogo.start()
        self.addCleanup(catalogo.stop)

    @patch(f'{ADAPTADOR_CHILEXPRESS}.requests.post')
    def test_cotizacion_entrega_precio_y_oculta_credenciales(self, post):
        post.return_value = respuesta_chilexpress(TARIFA_OK)

        response = self.client.post(reverse('cotizar-envio'), self.payload, format='json')

        self.assertEqual(response.status_code, 200)
        opcion, = response.data['opciones']
        self.assertEqual((opcion['proveedor'], opcion['nombre'], opcion['precio']), ('CHILEXPRESS', 'Chilexpress', 3500))
        self.assertEqual(opcion['tiempo_estimado'], 'EXPRESS')
        self.assertEqual(post.call_args.kwargs['json']['destinationCountyCode'], 'STGO')
        # El paquete sale del catálogo, aunque el navegador mande otro
        self.assertEqual(post.call_args.kwargs['json']['package'],
                         {'weight': '1.5', 'height': '30', 'width': '30', 'length': '30'})
        self.assertEqual(post.call_args.kwargs['headers']['Ocp-Apim-Subscription-Key'],
                         'secreto-chilexpress')
        self.assertNotIn('secreto-chilexpress', str(response.data))

    @patch(f'{ADAPTADOR_CHILEXPRESS}.requests.post')
    def test_el_peso_y_el_origen_del_navegador_se_ignoran(self, post):
        """Un navegador alterado no puede cotizar menos peso ni desde otra comuna (RF-02.3)."""
        post.return_value = respuesta_chilexpress(TARIFA_OK)
        self.config.comuna_origen = 'Puente Alto'
        self.config.save(update_fields=['comuna_origen'])
        payload = {**self.payload, 'peso': 0.01, 'alto': 1, 'ancho': 1, 'largo': 1, 'origen': 'SANTIAGO'}

        with patch(f'{ADAPTADOR_CHILEXPRESS}.ChilexpressCourier._obtener_catalogo_dinamico',
                   return_value={'SANTIAGO': 'STGO', 'PUENTE ALTO': 'PALT'}):
            response = self.client.post(reverse('cotizar-envio'), payload, format='json')

        self.assertEqual(response.status_code, 200, response.data)
        enviado = post.call_args.kwargs['json']
        self.assertEqual(enviado['originCountyCode'], 'PALT')
        self.assertEqual(enviado['package']['weight'], '1.5')

    @patch(f'{ADAPTADOR_CHILEXPRESS}.requests.post')
    def test_las_comunas_se_encuentran_aunque_lleven_tildes_o_ene(self, post):
        # Chilexpress las escribe sin tildes y con N: 'Ñuñoa' es NUNOA
        post.return_value = respuesta_chilexpress(TARIFA_OK)
        self.config.comuna_origen = 'Ñuñoa'
        self.config.save(update_fields=['comuna_origen'])
        with patch(f'{ADAPTADOR_CHILEXPRESS}.ChilexpressCourier._obtener_catalogo_dinamico',
                   return_value={'NUNOA': 'NUNO', 'MAIPU': 'MIPU'}):
            response = self.client.post(reverse('cotizar-envio'), {**self.payload, 'destino': 'Maipú'}, format='json')

        self.assertEqual(response.status_code, 200, response.data)
        enviado = post.call_args.kwargs['json']
        self.assertEqual((enviado['originCountyCode'], enviado['destinationCountyCode']), ('NUNO', 'MIPU'))

    @patch(f'{ADAPTADOR_CHILEXPRESS}.requests.post')
    def test_un_origen_sin_cobertura_no_se_cotiza_desde_santiago(self, post):
        """Antes se usaba Santiago sin avisar y el comprador pagaba el envío desde otra comuna."""
        self.config.comuna_origen = 'Atlántida'
        self.config.save(update_fields=['comuna_origen'])

        response = self.client.post(reverse('cotizar-envio'), self.payload, format='json')

        self.assertEqual(response.status_code, 503)
        post.assert_not_called()

    @patch(f'{ADAPTADOR_CHILEXPRESS}.requests.post')
    def test_rechaza_datos_invalidos_sin_consultar_proveedor(self, post):
        sin_items = {k: v for k, v in self.payload.items() if k != 'items'}
        for payload in (sin_items, {**self.payload, 'items': [{'producto_mongo_id': 'polera'}]},
                        {**self.payload, 'items': [{**ITEMS[0], 'variante_sku': 'NO-EXISTE'}]},
                        {k: v for k, v in self.payload.items() if k != 'destino'}):
            with self.subTest(payload=payload):
                response = self.client.post(reverse('cotizar-envio'), payload, format='json')
                self.assertEqual(response.status_code, 400)
                self.assertIn('error', response.data)
        post.assert_not_called()

    @patch(f'{ADAPTADOR_CHILEXPRESS}.requests.post')
    def test_comuna_sin_cobertura_responde_400(self, post):
        payload = {**self.payload, 'destino': 'ATLANTIDA'}
        response = self.client.post(reverse('cotizar-envio'), payload, format='json')
        self.assertEqual(response.status_code, 400)
        post.assert_not_called()

    @patch(f'{ADAPTADOR_CHILEXPRESS}.requests.post')
    def test_fallo_de_proveedor_no_se_convierte_en_costo_cero(self, post):
        post.return_value = respuesta_chilexpress([], status=500)
        response = self.client.post(reverse('cotizar-envio'), self.payload, format='json')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('precio', response.data)

    @patch(f'{ADAPTADOR_CHILEXPRESS}.requests.post')
    def test_checkout_recalcula_envio_y_total(self, post):
        post.return_value = respuesta_chilexpress(TARIFA_OK)
        payload = {
            'email_invitado': 'cliente@example.test', 'metodo_pago': 'TRANSFERENCIA',
            'acepta_terminos': True, 'items': ITEMS, **DESTINATARIO,
            'direccion_envio_snapshot': {'comuna': 'Santiago', 'calle': 'Uno 123'},
            'subtotal': 25000, 'costo_envio': 1, 'total_final': 1,
            'proveedor_logistico': 'CHILEXPRESS', 'paquete': PAQUETE_MANIPULADO,
        }
        response = self.client.post(reverse('checkout'), payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        orden = OrdenCompra.objects.get()
        self.assertEqual(orden.costo_envio, 3500)
        self.assertEqual(orden.total_final, 28500)
        self.assertEqual(orden.proveedor_logistico, 'CHILEXPRESS')
        # Se cotiza y se despacha el paquete del catálogo, no el que mandó el navegador
        self.assertEqual(post.call_args.kwargs['json']['package']['weight'], '1.5')
        self.assertEqual(orden.paquete, {'peso_kg': '1.50', 'alto_cm': '30', 'ancho_cm': '30', 'largo_cm': '30'})

    def test_checkout_no_permite_retiro_desactivado(self):
        payload = {
            'email_invitado': 'cliente@example.test', 'metodo_pago': 'TRANSFERENCIA',
            'acepta_terminos': True, 'items': ITEMS, **DESTINATARIO,
            'direccion_envio_snapshot': {}, 'subtotal': 25000,
            'proveedor_logistico': 'RETIRO_LOCAL',
        }
        self.config.retiro_en_local_activo = False
        self.config.save(update_fields=['retiro_en_local_activo'])
        response = self.client.post(reverse('checkout'), payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('proveedor_logistico', response.data)
        self.assertFalse(OrdenCompra.objects.exists())

    def test_checkout_retiro_ignora_costo_enviado_por_cliente(self):
        payload = {
            'email_invitado': 'cliente@example.test', 'metodo_pago': 'TRANSFERENCIA',
            'acepta_terminos': True, 'items': ITEMS, **DESTINATARIO,
            'direccion_envio_snapshot': {}, 'subtotal': '25000',
            'costo_envio': 9999, 'total_final': 34999,
            'proveedor_logistico': 'RETIRO_LOCAL',
        }
        response = self.client.post(reverse('checkout'), payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        orden = OrdenCompra.objects.get()
        self.assertEqual(orden.costo_envio, 0)
        self.assertEqual(orden.total_final, 25000)

    def sin_logistica_configurada(self):
        self.config.retiro_en_local_activo = False
        self.config.save(update_fields=['retiro_en_local_activo'])

    def checkout_con_totales_manipulados(self, **cambios):
        payload = {
            'email_invitado': 'cliente@example.test', 'metodo_pago': 'TRANSFERENCIA',
            'acepta_terminos': True, 'items': ITEMS, **DESTINATARIO,
            'direccion_envio_snapshot': {'comuna': 'Santiago', 'calle': 'Uno 123'},
            'subtotal': 25000, 'costo_envio': 0, 'total_final': 1, **cambios,
        }
        return self.client.post(reverse('checkout'), payload, format='json')

    def test_sin_opcion_de_entrega_se_rechaza_aunque_la_tienda_no_tenga_logistica(self):
        self.sin_logistica_configurada()
        response = self.checkout_con_totales_manipulados()
        self.assertEqual(response.status_code, 400)
        self.assertIn('proveedor_logistico', response.data)
        self.assertFalse(OrdenCompra.objects.exists())

    @patch(f'{ADAPTADOR_CHILEXPRESS}.requests.post')
    def test_sin_logistica_activa_el_courier_igual_se_cotiza_en_el_servidor(self, post):
        # Sin paquete en la petición: lo arma el servidor
        post.return_value = respuesta_chilexpress(TARIFA_OK)
        self.sin_logistica_configurada()
        response = self.checkout_con_totales_manipulados(proveedor_logistico='CHILEXPRESS')
        self.assertEqual(response.status_code, 201, response.data)
        orden = OrdenCompra.objects.get()
        self.assertEqual((orden.costo_envio, orden.total_final), (3500, 28500))
        self.assertEqual((response.data['costo_envio'], response.data['total_final']), (3500, 28500))

    @patch(f'{ADAPTADOR_CHILEXPRESS}.requests.post')
    def test_tarifa_sin_precio_valido_no_crea_orden(self, post):
        post.return_value = respuesta_chilexpress(
            [{'serviceValue': '-10', 'serviceDescription': 'EXPRESS'}])
        payload = {
            'email_invitado': 'cliente@example.test', 'metodo_pago': 'TRANSFERENCIA',
            'acepta_terminos': True, 'items': ITEMS, **DESTINATARIO,
            'direccion_envio_snapshot': {'comuna': 'Santiago'},
            'subtotal': '25000', 'proveedor_logistico': 'CHILEXPRESS',
        }
        response = self.client.post(reverse('checkout'), payload, format='json')
        self.assertEqual(response.status_code, 503)
        self.assertFalse(OrdenCompra.objects.exists())


class OrdenTransporteTests(APITestCase):
    def setUp(self):
        guardar_credenciales(cotizador='llave-cotizador', envios='secreto-chilexpress')
        ConfiguracionGlobal.objects.create(id=1, nombre_tienda='QA', comuna_origen='Santiago')
        self.orden = OrdenCompra.objects.create(
            email_invitado='cliente@example.test', metodo_pago='TRANSBANK',
            direccion_envio_snapshot={'comuna': 'SANTIAGO', 'calle': 'Uno', 'numero': '123'},
            subtotal=25000, costo_envio=3500, total_final=28500,
            proveedor_logistico='CHILEXPRESS', id_transaccion_pasarela='token-tbk',
            nombre_destinatario='Ana Pérez', telefono_destinatario='+56912345678',
        )
        catalogo = patch(f'{ADAPTADOR_CHILEXPRESS}.ChilexpressCourier._obtener_catalogo_dinamico',
                         return_value={'SANTIAGO': 'STGO'})
        catalogo.start()
        self.addCleanup(catalogo.stop)
        # El servicio cotizado se consulta antes de la OT; aquí se prueba la OT (ver test_chilexpress)
        servicio = patch(f'{ADAPTADOR_CHILEXPRESS}.ChilexpressCourier._servicio_elegido',
                         return_value={'serviceTypeCode': 3, 'serviceDescription': 'EXPRESS'})
        servicio.start()
        self.addCleanup(servicio.stop)

    @patch(f'{ADAPTADOR_CHILEXPRESS}.requests.post')
    @patch('ecommerce.infrastructure.ventas.adapters.transbank_adapter.TransbankWebpayAdapter.confirmar_transaccion')
    def test_pago_aprobado_guarda_ot_como_codigo_de_seguimiento(self, confirmar, post):
        confirmar.return_value = {
            'exito': True, 'aprobado': True,
            'data_completa': {'buy_order': f'ORD-{self.orden.id}'},
        }
        # Chilexpress devuelve el número de OT como decimal
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {
            'data': {'detail': [{'transportOrderNumber': 712678903156.0, 'label': {}}]}}

        response = self.client.get(reverse('transbank_retorno'), {'token_ws': 'token-tbk'})

        self.assertEqual(response.status_code, 302)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, 'PAGADO')
        self.assertEqual(self.orden.numero_seguimiento_tracking, '712678903156')
        self.assertEqual(self.orden.id_transaccion_pasarela, 'token-tbk | OT: 712678903156')

    def generar_ot(self):
        return GenerarOrdenTransporte(DjangoRepositorioOrdenes(),
                                      TransportistaSegunProveedor(DjangoCouriers())).ejecutar(self.orden.id)

    def test_sin_destinatario_la_ot_usa_el_nombre_de_la_cuenta(self):
        # Pedidos anteriores a pedir el destinatario en el checkout (RF-02.3)
        usuario = create_user('luis@example.test', nombre='Luis', apellido_paterno='Rojas')
        OrdenCompra.objects.filter(id=self.orden.id).update(usuario=usuario, email_invitado='',
                                                            nombre_destinatario='')
        self.assertEqual(DjangoRepositorioOrdenes().obtener_envio(self.orden.id).destinatario, 'Luis Rojas')

        OrdenCompra.objects.filter(id=self.orden.id).update(usuario=None, email_invitado='cliente@example.test')
        self.assertEqual(DjangoRepositorioOrdenes().obtener_envio(self.orden.id).destinatario, 'Cliente')

    @patch(f'{ADAPTADOR_CHILEXPRESS}.requests.post')
    def test_ot_usa_el_paquete_cotizado_y_declara_el_valor_de_los_productos(self, post):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {'data': {'detail': [{'transportOrderNumber': 1.0}]}}
        OrdenCompra.objects.filter(id=self.orden.id).update(paquete=PAQUETE)

        self.assertEqual(self.generar_ot(), '1')

        detalle = post.call_args.kwargs['json']['details'][0]
        paquete = detalle['packages'][0]
        self.assertEqual((paquete['weight'], paquete['height'], paquete['width'], paquete['length']),
                         ('1.50', 10, 20, 30))
        self.assertEqual(paquete['declaredValue'], 25000)
        destino = detalle['addresses'][0]
        self.assertEqual((destino['countyCoverageCode'], destino['deliveryOnCommercialOffice']), ('STGO', False))

    @patch(f'{ADAPTADOR_CHILEXPRESS}.requests.post')
    def test_retiro_en_sucursal_se_entrega_en_la_oficina(self, post):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {'data': {'detail': [{'transportOrderNumber': 1.0}]}}
        OrdenCompra.objects.filter(id=self.orden.id).update(direccion_envio_snapshot={
            'comuna': 'Santiago', 'calle': 'Agencia Chilexpress: Centro', 'numero': 'S/N',
            'codigo_sucursal': 'OF-123'})

        self.generar_ot()

        destino = post.call_args.kwargs['json']['details'][0]['addresses'][0]
        self.assertEqual((destino['deliveryOnCommercialOffice'], destino['commercialOfficeId']), (True, 'OF-123'))

    @patch(f'{ADAPTADOR_CHILEXPRESS}.requests.post')
    def test_ot_lleva_el_nombre_y_telefono_del_destinatario(self, post):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {'data': {'detail': [{'transportOrderNumber': 1.0}]}}

        self.generar_ot()

        destinatario = post.call_args.kwargs['json']['details'][0]['contacts'][0]
        self.assertEqual((destinatario['name'], destinatario['phoneNumber']), ('Ana Pérez', '912345678'))

    @patch(f'{ADAPTADOR_CHILEXPRESS}.requests.post')
    def test_orden_sin_telefono_no_genera_ot_con_datos_inventados(self, post):
        OrdenCompra.objects.filter(id=self.orden.id).update(telefono_destinatario='')

        self.assertIsNone(self.generar_ot())

        post.assert_not_called()
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.error_orden_transporte, 'La orden no tiene teléfono del destinatario.')

    @patch(f'{ADAPTADOR_CHILEXPRESS}.requests.post')
    def test_rechazo_de_chilexpress_queda_en_la_orden_sin_ot(self, post):
        post.return_value = Mock(status_code=400, text='Comuna sin cobertura')

        self.assertIsNone(self.generar_ot())

        self.orden.refresh_from_db()
        self.assertIsNone(self.orden.numero_seguimiento_tracking)
        self.assertIn('Comuna sin cobertura', self.orden.error_orden_transporte)

    @patch(f'{ADAPTADOR_CHILEXPRESS}.requests.post')
    def test_comuna_sin_cobertura_no_llama_a_chilexpress(self, post):
        OrdenCompra.objects.filter(id=self.orden.id).update(direccion_envio_snapshot={'comuna': 'Isla de Pascua'})

        self.assertIsNone(self.generar_ot())

        post.assert_not_called()
        self.orden.refresh_from_db()
        self.assertIn('Isla de Pascua', self.orden.error_orden_transporte)


class CouriersAPITests(APITestCase):
    """RF-02.3: la API ofrece los couriers activos, sin nombrar a ninguno en particular."""

    def setUp(self):
        habilitar_medios_pago('TRANSFERENCIA')
        ConfiguracionGlobal.objects.create(id=1, nombre_tienda='QA', comuna_origen='Santiago')
        self.payload = {'destino': 'MAIPU', 'items': ITEMS}
        usar_catalogo_falso(self, {
            ('polera', 'POLERA-M'): VarianteCatalogo('Polera - POLERA-M', Decimal('25000'), 5, True),
        })

    def con_couriers(self, *couriers):
        for modulo in ('views', 'serializers'):
            parche = patch(f'ecommerce.infrastructure.ventas.{modulo}.couriers', return_value=CouriersFalsos(*couriers))
            parche.start()
            self.addCleanup(parche.stop)

    def checkout(self, proveedor):
        return self.client.post(reverse('checkout'), {
            'email_invitado': 'cliente@example.test', 'metodo_pago': 'TRANSFERENCIA',
            'acepta_terminos': True, 'items': ITEMS, **DESTINATARIO,
            'direccion_envio_snapshot': {'comuna': 'Maipú', 'calle': 'Uno 123'},
            'subtotal': 25000, 'costo_envio': 0, 'total_final': 1,
            'proveedor_logistico': proveedor,
        }, format='json')

    def test_cotiza_con_cada_courier_activo_y_uno_caido_no_tapa_al_otro(self):
        self.con_couriers(CourierFalso('CHILEXPRESS', 3990), CourierFalso('STARKEN', 3500),
                          CourierFalso('OTRO', falla=CourierNoDisponible()))
        response = self.client.post(reverse('cotizar-envio'), self.payload, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([(o['proveedor'], o['precio']) for o in response.data['opciones']],
                         [('CHILEXPRESS', 3990), ('STARKEN', 3500)])

        response = self.client.post(reverse('cotizar-envio'), {**self.payload, 'proveedor': 'STARKEN'}, format='json')
        self.assertEqual([o['proveedor'] for o in response.data['opciones']], ['STARKEN'])

    def test_sin_couriers_activos_no_hay_cotizacion_ni_comunas(self):
        self.con_couriers()
        self.assertEqual(self.client.post(reverse('cotizar-envio'), self.payload, format='json').status_code, 400)
        self.assertEqual(self.client.get(reverse('comunas-cobertura')).status_code, 503)

    def test_las_comunas_son_las_de_todos_los_couriers_activos(self):
        self.con_couriers(CourierFalso('CHILEXPRESS', comunas=['MAIPU', 'SANTIAGO']),
                          CourierFalso('STARKEN', comunas=['ARICA', 'SANTIAGO']))
        response = self.client.get(reverse('comunas-cobertura'))
        self.assertEqual(response.data['comunas'], ['ARICA', 'MAIPU', 'SANTIAGO'])

    def test_el_checkout_cobra_el_envio_del_courier_elegido(self):
        self.con_couriers(CourierFalso('CHILEXPRESS', 3990), CourierFalso('STARKEN', 3500))
        response = self.checkout('STARKEN')
        self.assertEqual(response.status_code, 201, response.data)
        orden = OrdenCompra.objects.get()
        self.assertEqual((orden.proveedor_logistico, orden.costo_envio, orden.total_final), ('STARKEN', 3500, 28500))

    def test_el_checkout_rechaza_un_courier_inactivo(self):
        self.con_couriers()
        response = self.checkout('CHILEXPRESS')
        self.assertEqual(response.status_code, 400)
        self.assertIn('proveedor_logistico', response.data)
        self.assertFalse(OrdenCompra.objects.exists())


class SucursalesAPITests(APITestCase):
    def setUp(self):
        ChilexpressCourier._CACHE_COBERTURAS = {}
        ProveedorEnvio.objects.all().delete()

    def test_sin_courier_con_oficinas_no_hay_retiro_en_sucursal(self):
        response = self.client.get(reverse('sucursales-courier'), {'comuna': 'MAIPU'})
        self.assertEqual(response.status_code, 400)

    @patch(f'{ADAPTADOR_CHILEXPRESS}.requests.get')
    def test_las_oficinas_de_chilexpress_en_la_comuna(self, get):
        guardar_credenciales(cotizador='llave-cotizador', coberturas='llave-coberturas')
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {'offices': [
            {'officeCode': 'OF-1', 'officeName': 'Maipú Centro', 'streetName': 'Pajaritos', 'streetNumber': '100'}]}

        response = self.client.get(reverse('sucursales-courier'), {'comuna': 'Maipu', 'proveedor': 'CHILEXPRESS'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['sucursales'],
                         [{'codigo': 'OF-1', 'nombre': 'Maipú Centro', 'direccion': 'Pajaritos 100'}])
        self.assertIn('CountyName=MAIPU', get.call_args.args[0])
        self.assertEqual(get.call_args.kwargs['headers']['Ocp-Apim-Subscription-Key'], 'llave-coberturas')


class CredencialesGuardadasTests(APITestCase):
    def test_las_llaves_que_ya_cargo_la_tienda_se_siguen_leyendo(self):
        # Mismo formato que guardaba el panel antes de ordenar los couriers (y la migración 0022)
        ProveedorEnvio.objects.all().delete()
        ProveedorEnvio.objects.create(codigo='CHILEXPRESS', credenciales_cifradas=cifrar_json(
            {'cotizador': 'llave-cotizador', 'envios': 'llave-envios'}))

        chilexpress, = DjangoCouriers().activos()

        self.assertEqual(chilexpress.credenciales.como_dict(),
                         {'ambiente': '', 'cotizador': 'llave-cotizador', 'coberturas': '', 'envios': 'llave-envios',
                          'tcc': '', 'rut': '', 'contenido': ''})
        # Sin ambiente guardado siguen en el de pruebas, como antes de poder elegirlo
        self.assertEqual(chilexpress.credenciales.valor('ambiente'), 'PRUEBAS')
        self.assertTrue(chilexpress.credenciales.configuradas)
