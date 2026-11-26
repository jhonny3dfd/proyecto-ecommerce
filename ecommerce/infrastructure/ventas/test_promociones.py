from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from django.urls import reverse

from ecommerce.infrastructure.usuarios.tests.factories import create_user

from .models import OrdenCompra, Promocion


class ValidarPromocionTests(APITestCase):
    def setUp(self):
        self.url = reverse('validar-promocion')
        self.ahora = timezone.now()

        # Cupón activo vigente
        self.promo_vigente = Promocion.objects.create(
            codigo='VERANO20',
            tipo_descuento='PORCENTAJE',
            valor_descuento=20.0,
            umbral_envio_gratis=50000.0,
            fecha_expiracion=self.ahora + timedelta(days=7),
            is_active=True,
        )

        # Cupón expirado
        self.promo_expirada = Promocion.objects.create(
            codigo='EXPIRADO',
            tipo_descuento='MONTO_FIJO',
            valor_descuento=5000.0,
            fecha_expiracion=self.ahora - timedelta(days=1),
            is_active=True,
        )

        # Cupón inactivo
        self.promo_inactiva = Promocion.objects.create(
            codigo='INACTIVO',
            tipo_descuento='MONTO_FIJO',
            valor_descuento=3000.0,
            fecha_expiracion=self.ahora + timedelta(days=10),
            is_active=False,
        )

    def test_valida_cupon_porcentaje_exitosamente(self):
        response = self.client.post(self.url, {'codigo': 'VERANO20', 'subtotal': 100000})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['descuento'], 20000)
        self.assertEqual(response.data['umbral_envio_gratis'], 50000.0)

    def test_valida_cupon_monto_fijo_tope_subtotal(self):
        promo_fija = Promocion.objects.create(
            codigo='FIJO5000',
            tipo_descuento='MONTO_FIJO',
            valor_descuento=5000.0,
            is_active=True,
        )
        # Subtotal menor al descuento: no debe generar totales negativos
        response = self.client.post(self.url, {'codigo': 'FIJO5000', 'subtotal': 3000})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['descuento'], 3000)

    def test_rechaza_cupon_expirado(self):
        response = self.client.post(self.url, {'codigo': 'EXPIRADO', 'subtotal': 50000})
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND])
        self.assertIn('error', response.data)

    def test_rechaza_cupon_inactivo(self):
        response = self.client.post(self.url, {'codigo': 'INACTIVO', 'subtotal': 50000})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_rechaza_codigo_vacio(self):
        response = self.client.post(self.url, {'codigo': '', 'subtotal': 50000})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_propiedad_esta_vigente(self):
        self.assertTrue(self.promo_vigente.esta_vigente)
        self.assertFalse(self.promo_expirada.esta_vigente)
        self.assertFalse(self.promo_inactiva.esta_vigente)


class CheckoutPromocionTests(APITestCase):
    def setUp(self):
        from decimal import Decimal
        from unittest.mock import patch
        from .models import ConfiguracionGlobal, OrdenCompra
        from .tests import DESTINATARIO, habilitar_medios_pago, usar_catalogo_falso
        from ecommerce.domain.ventas import VarianteCatalogo

        self.url = reverse('checkout')
        self.ahora = timezone.now()
        ConfiguracionGlobal.objects.update_or_create(
            pk=1, defaults={'nombre_tienda': 'Tienda QA', 'modo_autenticacion': 'INVITADO', 'retiro_en_local_activo': False}
        )
        habilitar_medios_pago('TRANSFERENCIA', 'TRANSBANK')
        usar_catalogo_falso(self, {
            ('prod1', 'SKU-1'): VarianteCatalogo('Producto 1 - SKU-1', Decimal('20000.00'), 5, True),
        })
        # Chilexpress activo (sus llaves en la base) y su tarifa simulada, sin red
        from .test_chilexpress import guardar_credenciales
        guardar_credenciales(cotizador='llave-de-prueba')
        cotizacion = patch('ecommerce.infrastructure.ventas.serializers.precio_envio', return_value=3000)
        cotizacion.start()
        self.addCleanup(cotizacion.stop)

        self.promo_valida = Promocion.objects.create(
            codigo='REINTENTO',
            tipo_descuento='PORCENTAJE',
            valor_descuento=10.0,
            umbral_envio_gratis=15000.0,
            fecha_expiracion=self.ahora + timedelta(days=5),
            is_active=True,
            # Un solo uso, como funcionaban todos los códigos antes de poder elegirlo
            usos_maximos=1,
        )

        self.payload_base = {
            'items': [{'producto_mongo_id': 'prod1', 'variante_sku': 'SKU-1', 'cantidad': 1}],
            'email_invitado': 'comprador@example.com',
            'metodo_pago': 'TRANSFERENCIA',
            'direccion_envio_snapshot': {'calle': 'Calle 1', 'ciudad': 'Santiago', 'comuna': 'Santiago'},
            'subtotal': 20000,
            'proveedor_logistico': 'CHILEXPRESS',
            'acepta_terminos': True,
            **DESTINATARIO,
        }

    def test_cupon_invalido_o_expirado_rechaza_checkout(self):
        # E05: El checkout debe rechazar cupones no vigentes en vez de cobrar calladamente el total completo
        payload = {**self.payload_base, 'codigo_promocion': 'NO_EXISTE_123'}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('codigo_promocion', response.data)

    def test_cupon_no_se_desactiva_si_falla_pasarela(self):
        from unittest.mock import patch
        from .models import OrdenCompra
        # E04: Si falla el inicio de pasarela, el cupón no debe quedar consumido (is_active debe ser True)
        payload = {
            **self.payload_base,
            'metodo_pago': 'TRANSBANK',
            'codigo_promocion': 'REINTENTO'
        }
        with patch('ecommerce.infrastructure.ventas.adapters.transbank_adapter.TransbankWebpayAdapter.iniciar_transaccion',
                   return_value={'exito': False, 'error': 'Fallo simulado Transbank'}):
            response = self.client.post(self.url, payload, format='json')
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Confirmar que la orden se eliminó
        self.assertEqual(OrdenCompra.objects.count(), 0)
        # El uso se devuelve con el rollback: el cupón sigue disponible para reintentar
        self.promo_valida.refresh_from_db()
        self.assertEqual(self.promo_valida.usos, 0)
        self.assertTrue(self.promo_valida.esta_vigente)

    def test_cupon_con_envio_gratis_y_desactivacion_exitosa(self):
        from .models import OrdenCompra
        # E03 & E04 éxito: Envío gratis si supera el umbral y desactivación solo tras éxito
        payload = {
            **self.payload_base,
            'codigo_promocion': 'REINTENTO'
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        orden = OrdenCompra.objects.latest('pk')
        # Subtotal 20000 - 10% (2000) = 18000; umbral 15000 alcanzado => costo_envio 0, total_final 18000
        self.assertEqual(orden.costo_envio, 0.0)
        self.assertEqual(orden.total_final, 18000.0)

        # Su único uso queda contado: deja de valer, y el pedido guarda qué código se aplicó
        self.promo_valida.refresh_from_db()
        self.assertEqual(self.promo_valida.usos, 1)
        self.assertFalse(self.promo_valida.esta_vigente)
        self.assertEqual(orden.promocion, self.promo_valida)



class DescuentoAutomaticoTests(APITestCase):
    """RF-04.1: códigos con monto mínimo, automáticos y con límite de usos (domain/promociones.py)."""

    # La misma tienda y el mismo carrito de $20.000 que CheckoutPromocionTests, sin repetir sus tests
    setUp = CheckoutPromocionTests.setUp

    def checkout(self, subtotal=20000, **extra):
        return self.client.post(self.url, {**self.payload_base, 'subtotal': subtotal, **extra}, format='json')

    def test_el_automatico_se_aplica_solo_desde_su_minimo_y_no_se_gasta(self):
        Promocion.objects.create(codigo='AUTO15', tipo_descuento='PORCENTAJE', valor_descuento=15,
                                 monto_minimo=20000, automatica=True)
        for _ in range(2):
            self.assertEqual(self.checkout().status_code, status.HTTP_201_CREATED)
        orden = OrdenCompra.objects.latest('pk')
        # 20.000 - 15 % = 17.000, más el envío de 3.000 (el automático no lo deja gratis)
        self.assertEqual((orden.total_final, orden.costo_envio), (20000.0, 3000.0))
        self.assertEqual(orden.promocion.codigo, 'AUTO15')
        self.assertEqual(Promocion.objects.get(codigo='AUTO15').usos, 2)

    def test_bajo_el_minimo_no_se_aplica(self):
        Promocion.objects.create(codigo='AUTO15', tipo_descuento='PORCENTAJE', valor_descuento=15,
                                 monto_minimo=30000, automatica=True)
        self.assertEqual(self.checkout().status_code, status.HTTP_201_CREATED)
        orden = OrdenCompra.objects.get()
        self.assertIsNone(orden.promocion)
        self.assertEqual(orden.total_final, 23000.0)

    def test_con_un_codigo_escrito_gana_el_que_mas_ahorra(self):
        Promocion.objects.create(codigo='AUTO5', tipo_descuento='PORCENTAJE', valor_descuento=5,
                                 monto_minimo=10000, automatica=True)
        # REINTENTO: 10 % y envío gratis desde 15.000 -> ahorra 2.000 + 3.000; el automático, 1.000
        self.assertEqual(self.checkout(codigo_promocion='REINTENTO').status_code, status.HTTP_201_CREATED)
        self.assertEqual(OrdenCompra.objects.get().promocion.codigo, 'REINTENTO')

        Promocion.objects.create(codigo='AUTO50', tipo_descuento='MONTO_FIJO', valor_descuento=8000,
                                 monto_minimo=10000, automatica=True)
        self.promo_valida.usos = 0
        self.promo_valida.save()
        self.assertEqual(self.checkout(codigo_promocion='REINTENTO').status_code, status.HTTP_201_CREATED)
        orden = OrdenCompra.objects.latest('pk')
        self.assertEqual((orden.promocion.codigo, orden.total_final), ('AUTO50', 15000.0))
        # El código escrito no se aplicó: no gasta su uso
        self.promo_valida.refresh_from_db()
        self.assertEqual(self.promo_valida.usos, 0)

    def test_un_codigo_escrito_bajo_su_minimo_se_rechaza(self):
        Promocion.objects.create(codigo='GRANDE', tipo_descuento='PORCENTAJE', valor_descuento=20, monto_minimo=50000)
        respuesta = self.checkout(codigo_promocion='grande')
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('$50.000', str(respuesta.data['codigo_promocion']))
        self.assertFalse(OrdenCompra.objects.exists())

    def test_el_limite_de_usos_se_respeta(self):
        Promocion.objects.create(codigo='DOS', tipo_descuento='MONTO_FIJO', valor_descuento=1000, usos_maximos=2)
        for _ in range(2):
            self.assertEqual(self.checkout(codigo_promocion='DOS').status_code, status.HTTP_201_CREATED)
        respuesta = self.checkout(codigo_promocion='DOS')
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Promocion.objects.get(codigo='DOS').usos, 2)

    def test_reservar_un_uso_es_condicional(self):
        """Si otra compra se llevó el último uso entre la elección y el cobro, este no se suma."""
        from .serializers import reservar_uso_promocion
        promo = Promocion.objects.create(codigo='UNO', tipo_descuento='MONTO_FIJO', valor_descuento=1000,
                                         usos_maximos=1)
        self.assertTrue(reservar_uso_promocion(promo.pk))
        self.assertFalse(reservar_uso_promocion(promo.pk))
        promo.refresh_from_db()
        self.assertEqual(promo.usos, 1)

    def test_la_tienda_publica_los_automaticos_sin_sus_codigos(self):
        Promocion.objects.create(codigo='SECRETO-AUTO', tipo_descuento='PORCENTAJE', valor_descuento=10,
                                 monto_minimo=30000, automatica=True)
        Promocion.objects.create(codigo='AGOTADO', tipo_descuento='PORCENTAJE', valor_descuento=10,
                                 monto_minimo=30000, automatica=True, usos_maximos=1, usos=1)
        Promocion.objects.create(codigo='VENCIDO', tipo_descuento='PORCENTAJE', valor_descuento=10,
                                 monto_minimo=30000, automatica=True, fecha_expiracion=self.ahora - timedelta(days=1))
        respuesta = self.client.get(reverse('promociones-automaticas'))
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data, [{'tipo_descuento': 'PORCENTAJE', 'valor_descuento': 10.0,
                                           'monto_minimo': 30000, 'umbral_envio_gratis': None}])
        self.assertNotIn('SECRETO', str(respuesta.content))

    def test_validar_un_codigo_respeta_su_minimo(self):
        Promocion.objects.create(codigo='GRANDE', tipo_descuento='PORCENTAJE', valor_descuento=20, monto_minimo=50000)
        url = reverse('validar-promocion')
        respuesta = self.client.post(url, {'codigo': 'GRANDE', 'subtotal': 20000})
        self.assertEqual((respuesta.status_code, respuesta.data['monto_minimo']), (400, 50000))
        self.assertEqual(self.client.post(url, {'codigo': 'GRANDE', 'subtotal': 60000}).data['descuento'], 12000)


class GestionPromocionesPermisosTests(APITestCase):
    """Solo el admin crea, edita o borra cupones: un comprador podría crearse uno del 100 %."""

    def setUp(self):
        self.promo = Promocion.objects.create(codigo='BASE10', tipo_descuento='PORCENTAJE', valor_descuento=10.0)
        self.lista = reverse('promociones-list-create')
        self.detalle = reverse('promociones-detail', args=[self.promo.id])
        self.nueva = {'codigo': 'GRATIS100', 'tipo_descuento': 'PORCENTAJE', 'valor_descuento': 100.0}

    def test_comprador_o_visitante_no_pueden_gestionar_cupones(self):
        comprador = create_user('comprador-cupones@example.test')
        for usuario, codigo_esperado in ((None, status.HTTP_401_UNAUTHORIZED), (comprador, status.HTTP_403_FORBIDDEN)):
            self.client.force_authenticate(usuario)
            with self.subTest(usuario=usuario):
                self.assertEqual(self.client.get(self.lista).status_code, codigo_esperado)
                self.assertEqual(self.client.post(self.lista, self.nueva, format='json').status_code, codigo_esperado)
                self.assertEqual(self.client.patch(self.detalle, {'valor_descuento': 100.0}, format='json').status_code,
                                 codigo_esperado)
                self.assertEqual(self.client.delete(self.detalle).status_code, codigo_esperado)
        self.assertFalse(Promocion.objects.filter(codigo='GRATIS100').exists())
        self.promo.refresh_from_db()
        self.assertEqual(self.promo.valor_descuento, 10.0)

    def test_admin_gestiona_cupones(self):
        self.client.force_authenticate(create_user('admin-cupones@example.test', rol='ADMIN'))
        self.assertEqual(self.client.post(self.lista, self.nueva, format='json').status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.client.delete(self.detalle).status_code, status.HTTP_204_NO_CONTENT)

    def test_admin_fija_y_quita_la_fecha_de_expiracion_desde_el_panel(self):
        self.client.force_authenticate(create_user('admin-vence@example.test', rol='ADMIN'))
        # El panel envía la fecha sin zona horaria: vale la hora de la tienda (America/Santiago)
        response = self.client.patch(self.detalle, {'fecha_expiracion': '2020-01-31T23:59:59'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['fecha_expiracion'].startswith('2020-01-31T23:59:59'))
        self.promo.refresh_from_db()
        self.assertEqual(timezone.localtime(self.promo.fecha_expiracion).date().isoformat(), '2020-01-31')
        self.assertFalse(self.promo.esta_vigente)

        self.client.patch(self.detalle, {'fecha_expiracion': None}, format='json')
        self.promo.refresh_from_db()
        self.assertTrue(self.promo.esta_vigente)

    def test_rechaza_cupones_que_regalarian_la_compra_o_el_envio(self):
        """RF-04.1: un 250 % o un umbral negativo (envío gratis en toda compra) no se pueden guardar."""
        self.client.force_authenticate(create_user('admin-reglas@example.test', rol='ADMIN'))
        for cambios, campo in (
            ({'valor_descuento': 250}, 'valor_descuento'),
            ({'valor_descuento': -50}, 'valor_descuento'),
            ({'valor_descuento': 0}, 'valor_descuento'),
            ({'tipo_descuento': 'MONTO_FIJO', 'valor_descuento': 990.5}, 'valor_descuento'),
            ({'umbral_envio_gratis': -1}, 'umbral_envio_gratis'),
            ({'codigo': 'VERANO 20'}, 'codigo'),
            ({'codigo': 'base10'}, 'codigo'),
        ):
            with self.subTest(cambios=cambios):
                response = self.client.post(self.lista, {**self.nueva, **cambios}, format='json')
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(campo, response.data)
        self.assertEqual(Promocion.objects.count(), 1)

    def test_el_admin_crea_un_automatico_con_minimo_y_no_puede_tocar_los_usos(self):
        self.client.force_authenticate(create_user('admin-auto@example.test', rol='ADMIN'))
        sin_minimo = self.client.post(self.lista, {**self.nueva, 'codigo': 'AUTO', 'automatica': True}, format='json')
        self.assertEqual(sin_minimo.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('monto_minimo', sin_minimo.data)

        respuesta = self.client.post(self.lista, {**self.nueva, 'codigo': 'AUTO', 'automatica': True,
                                                  'monto_minimo': 30000, 'usos': 99}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED, respuesta.data)
        self.assertEqual((respuesta.data['usos'], respuesta.data['usos_maximos']), (0, None))


    def test_el_codigo_se_guarda_en_mayusculas_y_editar_otro_campo_no_lo_exige(self):
        self.client.force_authenticate(create_user('admin-mayus@example.test', rol='ADMIN'))
        response = self.client.post(self.lista, {**self.nueva, 'codigo': ' navidad-25 '}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['codigo'], 'NAVIDAD-25')

        respuesta = self.client.patch(self.detalle, {'valor_descuento': 15}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.data)
        respuesta = self.client.patch(self.detalle, {'valor_descuento': 150}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)


class ValidarPromocionEntradasRarasTests(APITestCase):
    def setUp(self):
        self.url = reverse('validar-promocion')

    def test_codigos_antiguos_que_solo_difieren_en_mayusculas_no_dan_error_500(self):
        Promocion.objects.create(codigo='verano20', tipo_descuento='PORCENTAJE', valor_descuento=10)
        Promocion.objects.create(codigo='VERANO20', tipo_descuento='PORCENTAJE', valor_descuento=20)
        response = self.client.post(self.url, {'codigo': 'Verano20', 'subtotal': 10000})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_subtotal_que_no_es_numero_responde_400(self):
        Promocion.objects.create(codigo='DIEZ', tipo_descuento='PORCENTAJE', valor_descuento=10)
        for subtotal in ('abc', 'nan', 'inf', -5):
            with self.subTest(subtotal=subtotal):
                response = self.client.post(self.url, {'codigo': 'DIEZ', 'subtotal': subtotal})
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
