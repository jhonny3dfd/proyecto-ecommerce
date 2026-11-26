from decimal import Decimal
import hashlib
import hmac
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from ecommerce.application.ventas import (
    ConfirmarPago,
    InventarioVariantes,
    NotificadorPedidos,
    RepositorioOrdenes,
    ResultadoPago,
)
from ecommerce.domain.logistica import EnvioSolicitado
from ecommerce.domain.ventas import EstadoPedido, EventoPedido, ItemSolicitado, OrdenRegistrada
from ecommerce.application.pagos import (
    AplicarResultadoPago,
    ErrorPasarelaPago,
    FirmaAvisoInvalida,
    PagoConsultado,
    PagoIniciado,
    PasarelaConAvisos,
    ProcesarAvisoPago,
)
from ecommerce.domain.medios_pago import EstadoPago
from ecommerce.infrastructure.ventas.adapters.mercadopago import MercadoPagoAdapter
from ecommerce.infrastructure.ventas.views import token_verificacion_pago


def url_verificar_pago(orden_id) -> str:
    """Como la consulta el checkout: con el token que recibió al crear la orden."""
    return f"/api/ventas/checkout/verificar-pago/?orden_id={orden_id}&token={token_verificacion_pago(orden_id)}"


def generar_firma_hmac(secret: str, data_id: str, request_id: str, ts: str = "1700000000") -> str:
    manifest = f"id:{str(data_id).lower()};request-id:{request_id};ts:{ts};"
    v1 = hmac.new(secret.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={v1}"


class FakePaymentGateway(PasarelaConAvisos):
    def __init__(self, secret: str = "mi_secreto_webhook", pago: PagoConsultado | None = None):
        self.secret = secret
        self.pago = pago
        self.adapter_validador = MercadoPagoAdapter(access_token="TEST-TOKEN", webhook_secret=secret)

    def iniciar(self, orden_id, monto, url_retorno, url_aviso=''):
        return PagoIniciado(
            referencia=f"PREF-{orden_id}",
            url_pago=f"https://www.mercadopago.cl/checkout/v1/redirect?pref_id=PREF-{orden_id}",
        )

    def aviso_autentico(self, firma: str, id_peticion: str, referencia: str) -> bool:
        return self.adapter_validador.aviso_autentico(firma, id_peticion, referencia)

    def resultado(self, referencia: str) -> PagoConsultado:
        return self.pago


class FakeRepositorioOrdenes(RepositorioOrdenes):
    def __init__(self, orden: OrdenRegistrada):
        self.orden = orden
        self.motivo_cancelacion = ""
        self.motivo_revision = ""

    def obtener(self, orden_id) -> OrdenRegistrada | None:
        if str(self.orden.id) != str(orden_id):
            return None
        return self.orden

    def cambiar_estado(self, orden_id, desde: EstadoPedido, hacia: EstadoPedido,
                       motivo_cancelacion: str = '', motivo_revision: str = '') -> bool:
        if str(self.orden.id) != str(orden_id) or self.orden.estado != desde:
            return False
        self.motivo_cancelacion = motivo_cancelacion
        self.motivo_revision = motivo_revision
        self.orden = OrdenRegistrada(
            id=self.orden.id,
            estado=hacia,
            items=self.orden.items,
            stock_descontado=self.orden.stock_descontado,
            requiere_revision=bool(motivo_revision),
            total_final=self.orden.total_final,
        )
        return True

    def registrar_stock_descontado(self, orden_id, descontado: bool = True) -> None:
        self.orden = OrdenRegistrada(
            id=self.orden.id,
            estado=self.orden.estado,
            items=self.orden.items,
            stock_descontado=descontado,
            requiere_revision=self.orden.requiere_revision,
            total_final=self.orden.total_final,
        )

    def completar_pago(self, orden_id) -> None:
        self.motivo_revision = ""
        self.orden = OrdenRegistrada(
            id=self.orden.id,
            estado=self.orden.estado,
            items=self.orden.items,
            stock_descontado=True,
            requiere_revision=False,
            total_final=self.orden.total_final,
        )

    def marcar_revision(self, orden_id, motivo: str) -> None:
        self.motivo_revision = motivo
        self.orden = OrdenRegistrada(
            id=self.orden.id,
            estado=self.orden.estado,
            items=self.orden.items,
            stock_descontado=self.orden.stock_descontado,
            requiere_revision=True,
            total_final=self.orden.total_final,
        )

    def resolver_revision(self, orden_id) -> bool:
        return True

    def obtener_envio(self, orden_id) -> EnvioSolicitado | None:
        return None

    def registrar_orden_transporte(self, orden_id, numero_ot: str = '', error: str = '') -> None:
        pass

    def pagos_vencidos(self, metodo_pago: str, ahora) -> list:
        return []

    def pagos_por_recordar(self, metodo_pago: str, ahora) -> list:
        return []

    def marcar_recordatorio_pago(self, orden_id) -> bool:
        return False


class FakeInventario(InventarioVariantes):
    def __init__(self, stock_inicial: int = 10):
        self.stock = stock_inicial
        self.descuentos = 0

    def descontar(self, producto_id: str, sku: str, cantidad: int) -> bool:
        if self.stock < cantidad:
            return False
        self.stock -= cantidad
        self.descuentos += 1
        return True

    def reponer(self, producto_id: str, sku: str, cantidad: int) -> None:
        self.stock += cantidad


class FakeNotificador(NotificadorPedidos):
    def __init__(self):
        self.eventos: list[tuple[int, EventoPedido]] = []

    def notificar(self, orden_id, evento: EventoPedido) -> None:
        self.eventos.append((int(orden_id), evento))


class MercadoPagoWebhookTests(SimpleTestCase):
    def setUp(self):
        self.secret = "clave_secreta_test_123"
        self.request_id = "req-abc-123"
        self.payment_id = "99887766"
        self.firma_valida = generar_firma_hmac(self.secret, self.payment_id, self.request_id)

        self.orden_inicial = OrdenRegistrada(
            id=42,
            estado=EstadoPedido.PENDIENTE,
            items=(ItemSolicitado("prod_1", "SKU-1", 2),),
            total_final=Decimal("400000"),
        )
        self.repo_ordenes = FakeRepositorioOrdenes(self.orden_inicial)
        self.inventario = FakeInventario(stock_inicial=5)
        self.notificador = FakeNotificador()
        self.confirmar_pago = ConfirmarPago(
            self.repo_ordenes, self.inventario, orden_transporte=None, notificador=self.notificador
        )

    def test_pago_aprobado_pasa_a_pagado_descuenta_stock_y_envia_correo(self):
        pago = PagoConsultado(referencia=self.payment_id, orden_id="42", estado=EstadoPago.APROBADO, monto=Decimal("400000"))
        pasarela = FakePaymentGateway(self.secret, pago)
        caso = ProcesarAvisoPago(pasarela, AplicarResultadoPago(self.confirmar_pago))

        resultado = caso.ejecutar(
            firma=self.firma_valida, id_peticion=self.request_id, referencia=self.payment_id
        )

        self.assertEqual(resultado, ResultadoPago.PAGADO)
        self.assertEqual(self.repo_ordenes.orden.estado, EstadoPedido.PAGADO)
        self.assertTrue(self.repo_ordenes.orden.stock_descontado)
        self.assertFalse(self.repo_ordenes.orden.requiere_revision)
        self.assertEqual(self.inventario.stock, 3)
        self.assertEqual(self.notificador.eventos, [(42, EventoPedido.PAGO_APROBADO)])

    def test_pago_rechazado_cancela_orden_y_envia_correo(self):
        pago = PagoConsultado(referencia=self.payment_id, orden_id="42", estado=EstadoPago.RECHAZADO, monto=Decimal("400000"))
        pasarela = FakePaymentGateway(self.secret, pago)
        caso = ProcesarAvisoPago(pasarela, AplicarResultadoPago(self.confirmar_pago))

        resultado = caso.ejecutar(
            firma=self.firma_valida, id_peticion=self.request_id, referencia=self.payment_id
        )

        self.assertEqual(resultado, "RECHAZADO")
        self.assertEqual(self.repo_ordenes.orden.estado, EstadoPedido.CANCELADO)
        self.assertEqual(self.repo_ordenes.motivo_cancelacion, "Pago rechazado")
        self.assertEqual(self.inventario.stock, 5)
        self.assertEqual(self.notificador.eventos, [(42, EventoPedido.PAGO_RECHAZADO)])

    def test_pago_pendiente_deja_orden_en_pendiente_sin_descontar_stock(self):
        pago = PagoConsultado(referencia=self.payment_id, orden_id="42", estado=EstadoPago.PENDIENTE, monto=Decimal("400000"))
        pasarela = FakePaymentGateway(self.secret, pago)
        caso = ProcesarAvisoPago(pasarela, AplicarResultadoPago(self.confirmar_pago))

        resultado = caso.ejecutar(
            firma=self.firma_valida, id_peticion=self.request_id, referencia=self.payment_id
        )

        self.assertEqual(resultado, "PENDIENTE")
        self.assertEqual(self.repo_ordenes.orden.estado, EstadoPedido.PENDIENTE)
        self.assertEqual(self.inventario.stock, 5)
        self.assertEqual(self.notificador.eventos, [])

    def test_aviso_repetido_es_idempotente_no_descuenta_dos_veces_ni_reenvia_correo(self):
        pago = PagoConsultado(referencia=self.payment_id, orden_id="42", estado=EstadoPago.APROBADO, monto=Decimal("400000"))
        pasarela = FakePaymentGateway(self.secret, pago)
        caso = ProcesarAvisoPago(pasarela, AplicarResultadoPago(self.confirmar_pago))

        primero = caso.ejecutar(
            firma=self.firma_valida, id_peticion=self.request_id, referencia=self.payment_id
        )
        segundo = caso.ejecutar(
            firma=self.firma_valida, id_peticion=self.request_id, referencia=self.payment_id
        )

        self.assertEqual(primero, ResultadoPago.PAGADO)
        self.assertEqual(segundo, ResultadoPago.REPETIDO)
        self.assertEqual(self.inventario.descuentos, 1)
        self.assertEqual(self.inventario.stock, 3)
        self.assertEqual(len(self.notificador.eventos), 1)

    def test_firma_invalida_lanza_error_y_no_cambia_la_orden(self):
        pago = PagoConsultado(referencia=self.payment_id, orden_id="42", estado=EstadoPago.APROBADO, monto=Decimal("400000"))
        pasarela = FakePaymentGateway(self.secret, pago)
        caso = ProcesarAvisoPago(pasarela, AplicarResultadoPago(self.confirmar_pago))

        with self.assertRaises(FirmaAvisoInvalida):
            caso.ejecutar(
                firma="ts=1700000000,v1=firma_falsa_123",
                id_peticion=self.request_id,
                referencia=self.payment_id,
            )

        self.assertEqual(self.repo_ordenes.orden.estado, EstadoPedido.PENDIENTE)
        self.assertEqual(self.inventario.stock, 5)
        self.assertEqual(self.notificador.eventos, [])

    def test_monto_distinto_marca_orden_para_revision_del_admin(self):
        pago = PagoConsultado(referencia=self.payment_id, orden_id="42", estado=EstadoPago.APROBADO, monto=Decimal("350000"))
        pasarela = FakePaymentGateway(self.secret, pago)
        caso = ProcesarAvisoPago(pasarela, AplicarResultadoPago(self.confirmar_pago))

        resultado = caso.ejecutar(
            firma=self.firma_valida, id_peticion=self.request_id, referencia=self.payment_id
        )

        self.assertEqual(resultado, ResultadoPago.EN_REVISION)
        self.assertTrue(self.repo_ordenes.orden.requiere_revision)
        self.assertIn("no coincide", self.repo_ordenes.motivo_revision)
        self.assertEqual(self.notificador.eventos, [(42, EventoPedido.PAGO_EN_REVISION)])

    def test_vista_webhook_responde_401_con_firma_invalida(self):
        pago = PagoConsultado(referencia=self.payment_id, orden_id="42", estado=EstadoPago.APROBADO, monto=Decimal("400000"))
        pasarela = FakePaymentGateway(self.secret, pago)

        with patch("ecommerce.infrastructure.ventas.views.pasarela_mercado_pago", return_value=pasarela), \
             patch("ecommerce.infrastructure.ventas.views.confirmar_pago", return_value=self.confirmar_pago):
            respuesta = self.client.post(
                f"/api/ventas/mercadopago/webhook/?data.id={self.payment_id}&type=payment",
                data={"data": {"id": self.payment_id}, "type": "payment"},
                content_type="application/json",
                HTTP_X_SIGNATURE="ts=1700000000,v1=firma_invalida",
                HTTP_X_REQUEST_ID=self.request_id,
            )

        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(self.repo_ordenes.orden.estado, EstadoPedido.PENDIENTE)

    def test_webhook_refunded_marca_orden_para_revision_si_estaba_pagada(self):
        self.repo_ordenes.orden = OrdenRegistrada(
            id=42,
            estado=EstadoPedido.PAGADO,
            items=(ItemSolicitado("prod_1", "SKU-1", 2),),
            total_final=Decimal("400000"),
            stock_descontado=True,
        )
        pago = PagoConsultado(referencia=self.payment_id, orden_id="42", estado=EstadoPago.REEMBOLSADO, monto=Decimal("400000"))
        pasarela = FakePaymentGateway(self.secret, pago)
        caso = ProcesarAvisoPago(pasarela, AplicarResultadoPago(self.confirmar_pago))

        resultado = caso.ejecutar(
            firma=self.firma_valida, id_peticion=self.request_id, referencia=self.payment_id
        )

        self.assertEqual(resultado, ResultadoPago.EN_REVISION)
        self.assertTrue(self.repo_ordenes.orden.requiere_revision)
        self.assertIn(self.payment_id, self.repo_ordenes.motivo_revision)
        self.assertEqual(self.notificador.eventos, [(42, EventoPedido.PAGO_EN_REVISION)])

    def test_webhook_topic_no_relevante_es_ignorado(self):
        pago = PagoConsultado(referencia=self.payment_id, orden_id="42", estado=EstadoPago.APROBADO, monto=Decimal("400000"))
        pasarela = FakePaymentGateway(self.secret, pago)
        caso = ProcesarAvisoPago(pasarela, AplicarResultadoPago(self.confirmar_pago))

        resultado = caso.ejecutar(
            firma=self.firma_valida, id_peticion=self.request_id, referencia=self.payment_id,
            es_pago=False
        )

        self.assertEqual(resultado, "IGNORADO")
        self.assertEqual(self.repo_ordenes.orden.estado, EstadoPedido.PENDIENTE)
        self.assertEqual(self.notificador.eventos, [])

    def test_vista_retorno_si_orden_ya_estaba_pagada_redirige_a_exitoso(self):
        mock_instancia = MagicMock()
        mock_instancia.id = 42
        mock_instancia.estado = EstadoPedido.PAGADO
        mock_instancia.requiere_revision = False

        with patch("ecommerce.infrastructure.ventas.views.OrdenCompra.objects.filter") as mock_filter:
            mock_filter.return_value.first.return_value = mock_instancia

            respuesta = self.client.get("/api/ventas/mercadopago/retorno/?orden=42&status=null")
            self.assertEqual(respuesta.status_code, 302)
            self.assertIn("/pago-exitoso?orden=42", respuesta.headers["Location"])

    def test_vista_retorno_seguridad_no_aprueba_si_consulta_falla(self):
        pasarela = MagicMock()
        pasarela.resultado.side_effect = ErrorPasarelaPago("API timeout")

        mock_instancia = MagicMock()
        mock_instancia.id = 42
        mock_instancia.estado = EstadoPedido.PENDIENTE

        with patch("ecommerce.infrastructure.ventas.views.pasarela_mercado_pago", return_value=pasarela), \
             patch("ecommerce.infrastructure.ventas.views.confirmar_pago", return_value=self.confirmar_pago), \
             patch("ecommerce.infrastructure.ventas.views.OrdenCompra.objects.filter") as mock_filter:
            mock_filter.return_value.first.return_value = mock_instancia

            respuesta = self.client.get(
                "/api/ventas/mercadopago/retorno/?orden=42&payment_id=FALSO&status=approved"
            )
            self.assertEqual(respuesta.status_code, 302)
            self.assertIn("/pago-cancelado?orden=42", respuesta.headers["Location"])
            self.assertEqual(self.repo_ordenes.orden.estado, EstadoPedido.PENDIENTE)

    def test_vista_retorno_discrepancia_orden_id_redirige_a_cancelado(self):
        pago = PagoConsultado(referencia=self.payment_id, orden_id="99", estado=EstadoPago.APROBADO, monto=Decimal("400000"))
        pasarela = FakePaymentGateway(self.secret, pago)

        mock_instancia = MagicMock()
        mock_instancia.id = 42
        mock_instancia.estado = EstadoPedido.PENDIENTE

        with patch("ecommerce.infrastructure.ventas.views.pasarela_mercado_pago", return_value=pasarela), \
             patch("ecommerce.infrastructure.ventas.views.confirmar_pago", return_value=self.confirmar_pago), \
             patch("ecommerce.infrastructure.ventas.views.OrdenCompra.objects.filter") as mock_filter:
            mock_filter.return_value.first.return_value = mock_instancia

            respuesta = self.client.get(
                f"/api/ventas/mercadopago/retorno/?orden=42&payment_id={self.payment_id}&status=approved"
            )
            self.assertEqual(respuesta.status_code, 302)
            self.assertIn("/pago-cancelado", respuesta.headers["Location"])
            self.assertEqual(self.repo_ordenes.orden.estado, EstadoPedido.PENDIENTE)

    def test_vista_retorno_aprueba_orden_con_pago_valido(self):
        pago = PagoConsultado(referencia=self.payment_id, orden_id="42", estado=EstadoPago.APROBADO, monto=Decimal("400000"))
        pasarela = FakePaymentGateway(self.secret, pago)

        mock_instancia = MagicMock()
        mock_instancia.id = 42
        mock_instancia.estado = EstadoPedido.PENDIENTE
        mock_instancia.requiere_revision = False

        with patch("ecommerce.infrastructure.ventas.views.pasarela_mercado_pago", return_value=pasarela), \
             patch("ecommerce.infrastructure.ventas.views.confirmar_pago", return_value=self.confirmar_pago), \
             patch("ecommerce.infrastructure.ventas.views.OrdenCompra.objects.filter") as mock_filter:
            mock_filter.return_value.first.return_value = mock_instancia

            respuesta = self.client.get(
                f"/api/ventas/mercadopago/retorno/?orden=42&payment_id={self.payment_id}&status=approved"
            )
            self.assertEqual(respuesta.status_code, 302)
            self.assertIn("/pago-exitoso?orden=42", respuesta.headers["Location"])
            self.assertEqual(self.repo_ordenes.orden.estado, EstadoPedido.PAGADO)
            self.assertEqual(self.inventario.stock, 3)

    def test_vista_retorno_pago_pendiente_redirige_a_pedido_recibido(self):
        pago = PagoConsultado(referencia=self.payment_id, orden_id="42", estado=EstadoPago.PENDIENTE, monto=Decimal("400000"))
        pasarela = FakePaymentGateway(self.secret, pago)

        mock_instancia = MagicMock()
        mock_instancia.id = 42
        mock_instancia.estado = EstadoPedido.PENDIENTE

        with patch("ecommerce.infrastructure.ventas.views.pasarela_mercado_pago", return_value=pasarela), \
             patch("ecommerce.infrastructure.ventas.views.confirmar_pago", return_value=self.confirmar_pago), \
             patch("ecommerce.infrastructure.ventas.views.OrdenCompra.objects.filter") as mock_filter:
            mock_filter.return_value.first.return_value = mock_instancia

            respuesta = self.client.get(
                f"/api/ventas/mercadopago/retorno/?orden=42&payment_id={self.payment_id}&status=in_process"
            )
            self.assertEqual(respuesta.status_code, 302)
            self.assertIn("/pedido-recibido?orden=42", respuesta.headers["Location"])
            self.assertEqual(self.repo_ordenes.orden.estado, EstadoPedido.PENDIENTE)
            self.assertEqual(self.inventario.stock, 5)

    def test_verificar_pago_parametro_invalido_retorna_400(self):
        respuesta = self.client.get("/api/ventas/checkout/verificar-pago/?orden_id=abc")
        self.assertEqual(respuesta.status_code, 400)

    def test_verificar_pago_orden_no_existente_retorna_404(self):
        with patch("ecommerce.infrastructure.ventas.views.OrdenCompra.objects.filter") as mock_filter:
            mock_filter.return_value.first.return_value = None
            respuesta = self.client.get(url_verificar_pago(99999))
            self.assertEqual(respuesta.status_code, 404)

    def test_verificar_pago_sin_el_token_de_la_orden_responde_404_sin_consultar(self):
        """Los IDs son correlativos: sin el token que recibió quien creó la orden no se revela su estado."""
        with patch("ecommerce.infrastructure.ventas.views.OrdenCompra.objects.filter") as mock_filter, \
                patch("ecommerce.infrastructure.ventas.views.sincronizar_orden_con_mercadopago") as sincronizar:
            for token in ("", "token-inventado", token_verificacion_pago(43)):
                with self.subTest(token=token):
                    respuesta = self.client.get("/api/ventas/checkout/verificar-pago/",
                                                {"orden_id": "42", "token": token})
                    self.assertEqual(respuesta.status_code, 404)
            mock_filter.assert_not_called()
            sincronizar.assert_not_called()

    def test_verificar_pago_sincroniza_y_detecta_aprobado(self):
        mock_orden = MagicMock()
        mock_orden.id = 42
        mock_orden.estado = EstadoPedido.PAGADO
        mock_orden.metodo_pago = 'MERCADO_PAGO'
        mock_orden.requiere_revision = False

        with patch("ecommerce.infrastructure.ventas.views.OrdenCompra.objects.filter") as mock_filter:
            mock_filter.return_value.first.return_value = mock_orden
            respuesta = self.client.get(url_verificar_pago(42))
            self.assertEqual(respuesta.status_code, 200)
            self.assertTrue(respuesta.json()["pagado"])
            self.assertEqual(respuesta.json()["orden_id"], 42)

    def test_admin_sincronizar_pagos_requiere_autenticacion(self):
        respuesta = self.client.post("/api/ventas/mercadopago/sincronizar/")
        self.assertIn(respuesta.status_code, (401, 403))

    def test_e01_retorno_status_cancelled_con_pago_aprobado_en_mp_consulta_y_aprueba(self):
        """E01: Si la URL trae status=cancelled pero payment_id=801 aprobado en MP, se consulta MP y se aprueba."""
        pago_aprobado = PagoConsultado(referencia="801", orden_id="42", estado=EstadoPago.APROBADO, monto=Decimal("400000"))
        pasarela = FakePaymentGateway(self.secret, pago_aprobado)

        mock_instancia = MagicMock()
        mock_instancia.id = 42
        mock_instancia.estado = EstadoPedido.PENDIENTE
        mock_instancia.requiere_revision = False

        with patch("ecommerce.infrastructure.ventas.views.pasarela_mercado_pago", return_value=pasarela), \
             patch("ecommerce.infrastructure.ventas.views.confirmar_pago", return_value=self.confirmar_pago), \
             patch("ecommerce.infrastructure.ventas.views.OrdenCompra.objects.filter") as mock_filter:
            mock_filter.return_value.first.return_value = mock_instancia

            respuesta = self.client.get(
                "/api/ventas/mercadopago/retorno/?orden=42&payment_id=801&status=cancelled"
            )
            self.assertEqual(respuesta.status_code, 302)
            self.assertIn("/pago-exitoso?orden=42", respuesta.headers["Location"])
            self.assertEqual(self.repo_ordenes.orden.estado, EstadoPedido.PAGADO)
            self.assertEqual(self.inventario.stock, 3)

    def test_e01_retorno_anonimo_sin_payment_id_no_cancela_orden_en_bd(self):
        """E01: Parámetros de retorno sin payment_id no deben cancelar la orden pendiente en la BD."""
        mock_instancia = MagicMock()
        mock_instancia.id = 42
        mock_instancia.estado = EstadoPedido.PENDIENTE
        mock_instancia.requiere_revision = False

        with patch("ecommerce.infrastructure.ventas.views.OrdenCompra.objects.filter") as mock_filter:
            mock_filter.return_value.first.return_value = mock_instancia

            respuesta = self.client.get(
                "/api/ventas/mercadopago/retorno/?orden=42&status=cancelled"
            )
            self.assertEqual(respuesta.status_code, 302)
            self.assertIn("/pago-cancelado?orden=42", respuesta.headers["Location"])
            # La orden en la base de datos NO debe haber sido cancelada
            self.assertEqual(self.repo_ordenes.orden.estado, EstadoPedido.PENDIENTE)

    def test_e02_sincronizar_varios_intentos_prioriza_aprobado_sobre_rechazado(self):
        """E02: Si la búsqueda devuelve [802 aprobado, 801 rechazado], se concilia 802 y se descuenta stock."""
        pago_802 = PagoConsultado(referencia="802", orden_id="42", estado=EstadoPago.APROBADO, monto=Decimal("400000"))
        pasarela = MagicMock()
        pasarela.access_token = "TEST-123"
        pasarela.resultado.return_value = pago_802
        # Lo que devuelve la búsqueda de Mercado Pago, ya traducido por el adaptador
        pasarela.pagos_de_orden.return_value = [
            PagoConsultado(referencia="802", orden_id="42", estado=EstadoPago.APROBADO, monto=Decimal("400000")),
            PagoConsultado(referencia="801", orden_id="42", estado=EstadoPago.RECHAZADO, monto=Decimal("400000")),
        ]

        mock_instancia = MagicMock()
        mock_instancia.id = 42
        mock_instancia.estado = EstadoPedido.PENDIENTE
        mock_instancia.metodo_pago = "MERCADO_PAGO"

        from ecommerce.infrastructure.ventas.views import sincronizar_orden_con_mercadopago
        with patch("ecommerce.infrastructure.ventas.views.pasarela_mercado_pago", return_value=pasarela), \
             patch("ecommerce.infrastructure.ventas.views.confirmar_pago", return_value=self.confirmar_pago):
            sincronizar_orden_con_mercadopago(mock_instancia)

        self.assertEqual(self.repo_ordenes.orden.estado, EstadoPedido.PAGADO)
        self.assertEqual(self.inventario.stock, 3)
        pasarela.pagos_de_orden.assert_called_with("42")
        pasarela.resultado.assert_called_with("802")

    def test_e02_sincronizar_intento_pendiente_mantiene_orden_pendiente(self):
        """E02: Si hay un intento pendiente y otro rechazado, la orden no se cancela y se mantiene pendiente."""
        pasarela = MagicMock()
        pasarela.access_token = "TEST-123"
        pasarela.pagos_de_orden.return_value = [
            PagoConsultado(referencia="803", orden_id="42", estado=EstadoPago.PENDIENTE, monto=Decimal("400000")),
            PagoConsultado(referencia="801", orden_id="42", estado=EstadoPago.RECHAZADO, monto=Decimal("400000")),
        ]

        mock_instancia = MagicMock()
        mock_instancia.id = 42
        mock_instancia.estado = EstadoPedido.PENDIENTE
        mock_instancia.metodo_pago = "MERCADO_PAGO"

        from ecommerce.infrastructure.ventas.views import sincronizar_orden_con_mercadopago
        with patch("ecommerce.infrastructure.ventas.views.pasarela_mercado_pago", return_value=pasarela), \
             patch("ecommerce.infrastructure.ventas.views.confirmar_pago", return_value=self.confirmar_pago):
            sincronizar_orden_con_mercadopago(mock_instancia)

        self.assertEqual(self.repo_ordenes.orden.estado, EstadoPedido.PENDIENTE)
        self.assertEqual(self.inventario.stock, 5)
        pasarela.resultado.assert_not_called()

    def test_e03_verificar_pago_incluye_requiere_revision(self):
        """E03: verificar-pago devuelve la bandera requiere_revision adecuadamente."""
        mock_orden = MagicMock()
        mock_orden.id = 42
        mock_orden.estado = EstadoPedido.PAGADO
        mock_orden.metodo_pago = 'MERCADO_PAGO'
        mock_orden.requiere_revision = True

        with patch("ecommerce.infrastructure.ventas.views.OrdenCompra.objects.filter") as mock_filter:
            mock_filter.return_value.first.return_value = mock_orden
            respuesta = self.client.get(url_verificar_pago(42))
            self.assertEqual(respuesta.status_code, 200)
            self.assertTrue(respuesta.json()["pagado"])
            self.assertTrue(respuesta.json()["requiere_revision"])

    def test_retorno_pago_con_referencia_vacia_no_aprueba_ni_altera_orden(self):
        """Un pago aprobado con external_reference vacía NO debe aprobar, rechazar ni alterar la orden 42."""
        pago_sin_ref = PagoConsultado(referencia="801", orden_id="", estado=EstadoPago.APROBADO, monto=Decimal("10000"))
        pasarela = FakePaymentGateway(self.secret, pago_sin_ref)

        mock_orden = MagicMock()
        mock_orden.id = 42
        mock_orden.estado = EstadoPedido.PENDIENTE
        mock_orden.requiere_revision = False

        with patch("ecommerce.infrastructure.ventas.views.pasarela_mercado_pago", return_value=pasarela), \
             patch("ecommerce.infrastructure.ventas.views.confirmar_pago", return_value=self.confirmar_pago), \
             patch("ecommerce.infrastructure.ventas.views.OrdenCompra.objects.filter") as mock_filter:
            mock_filter.return_value.first.return_value = mock_orden

            respuesta = self.client.get("/api/ventas/mercadopago/retorno/?orden=42&payment_id=801")
            self.assertEqual(respuesta.status_code, 302)
            self.assertIn("/pago-cancelado", respuesta.headers["Location"])
            # La orden debe seguir en estado PENDIENTE y el stock intacto (5)
            self.assertEqual(self.repo_ordenes.orden.estado, EstadoPedido.PENDIENTE)
            self.assertEqual(self.inventario.stock, 5)

    def test_retorno_pago_con_referencia_nula_no_aprueba_ni_altera_orden(self):
        """Un pago con external_reference None NO debe aprobar ni alterar la orden 42."""
        pago_ref_nula = PagoConsultado(referencia="801", orden_id=None, estado=EstadoPago.APROBADO, monto=Decimal("10000"))
        pasarela = FakePaymentGateway(self.secret, pago_ref_nula)

        mock_orden = MagicMock()
        mock_orden.id = 42
        mock_orden.estado = EstadoPedido.PENDIENTE
        mock_orden.requiere_revision = False

        with patch("ecommerce.infrastructure.ventas.views.pasarela_mercado_pago", return_value=pasarela), \
             patch("ecommerce.infrastructure.ventas.views.confirmar_pago", return_value=self.confirmar_pago), \
             patch("ecommerce.infrastructure.ventas.views.OrdenCompra.objects.filter") as mock_filter:
            mock_filter.return_value.first.return_value = mock_orden

            respuesta = self.client.get("/api/ventas/mercadopago/retorno/?orden=42&payment_id=801")
            self.assertEqual(respuesta.status_code, 302)
            self.assertIn("/pago-cancelado", respuesta.headers["Location"])
            self.assertEqual(self.repo_ordenes.orden.estado, EstadoPedido.PENDIENTE)
            self.assertEqual(self.inventario.stock, 5)

    def test_retorno_pago_con_referencia_diferente_no_aprueba_ni_altera_orden(self):
        """Un pago con external_reference='99' NO debe asociarse a la orden 42."""
        pago_otra_orden = PagoConsultado(referencia="801", orden_id="99", estado=EstadoPago.APROBADO, monto=Decimal("10000"))
        pasarela = FakePaymentGateway(self.secret, pago_otra_orden)

        mock_orden = MagicMock()
        mock_orden.id = 42
        mock_orden.estado = EstadoPedido.PENDIENTE
        mock_orden.requiere_revision = False

        with patch("ecommerce.infrastructure.ventas.views.pasarela_mercado_pago", return_value=pasarela), \
             patch("ecommerce.infrastructure.ventas.views.confirmar_pago", return_value=self.confirmar_pago), \
             patch("ecommerce.infrastructure.ventas.views.OrdenCompra.objects.filter") as mock_filter:
            mock_filter.return_value.first.return_value = mock_orden

            respuesta = self.client.get("/api/ventas/mercadopago/retorno/?orden=42&payment_id=801")
            self.assertEqual(respuesta.status_code, 302)
            self.assertIn("/pago-cancelado", respuesta.headers["Location"])
            self.assertEqual(self.repo_ordenes.orden.estado, EstadoPedido.PENDIENTE)
            self.assertEqual(self.inventario.stock, 5)

    def test_retorno_pago_con_referencia_coincidente_aprueba_orden(self):
        """Un pago con external_reference='42' coincidente aprueba la orden y descuenta stock."""
        pago_correcto = PagoConsultado(referencia="801", orden_id="42", estado=EstadoPago.APROBADO, monto=Decimal("400000"))
        pasarela = FakePaymentGateway(self.secret, pago_correcto)

        mock_orden = MagicMock()
        mock_orden.id = 42
        mock_orden.estado = EstadoPedido.PENDIENTE
        mock_orden.requiere_revision = False

        with patch("ecommerce.infrastructure.ventas.views.pasarela_mercado_pago", return_value=pasarela), \
             patch("ecommerce.infrastructure.ventas.views.confirmar_pago", return_value=self.confirmar_pago), \
             patch("ecommerce.infrastructure.ventas.views.OrdenCompra.objects.filter") as mock_filter:
            mock_filter.return_value.first.return_value = mock_orden

            respuesta = self.client.get("/api/ventas/mercadopago/retorno/?orden=42&payment_id=801")
            self.assertEqual(respuesta.status_code, 302)
            self.assertIn("/pago-exitoso?orden=42", respuesta.headers["Location"])
            self.assertEqual(self.repo_ordenes.orden.estado, EstadoPedido.PAGADO)
            self.assertEqual(self.inventario.stock, 3)

    def test_retorno_referencia_coincidente_para_invitado_y_registrado(self):
        """Verifica que el retorno seguro funciona tanto para invitado como para usuario registrado."""
        pago_correcto = PagoConsultado(referencia="801", orden_id="42", estado=EstadoPago.APROBADO, monto=Decimal("400000"))
        pasarela = FakePaymentGateway(self.secret, pago_correcto)

        # 1. Comprador Invitado
        mock_orden_invitado = MagicMock()
        mock_orden_invitado.id = 42
        mock_orden_invitado.estado = EstadoPedido.PENDIENTE
        mock_orden_invitado.email_invitado = "invitado@correo.com"
        mock_orden_invitado.usuario = None
        mock_orden_invitado.requiere_revision = False

        with patch("ecommerce.infrastructure.ventas.views.pasarela_mercado_pago", return_value=pasarela), \
             patch("ecommerce.infrastructure.ventas.views.confirmar_pago", return_value=self.confirmar_pago), \
             patch("ecommerce.infrastructure.ventas.views.OrdenCompra.objects.filter") as mock_filter:
            mock_filter.return_value.first.return_value = mock_orden_invitado

            res_invitado = self.client.get("/api/ventas/mercadopago/retorno/?orden=42&payment_id=801")
            self.assertEqual(res_invitado.status_code, 302)
            self.assertIn("/pago-exitoso?orden=42", res_invitado.headers["Location"])
            self.assertEqual(self.repo_ordenes.orden.estado, EstadoPedido.PAGADO)

        # 2. Comprador Registrado
        self.repo_ordenes.orden = self.orden_inicial
        self.inventario.stock = 5
        mock_orden_registrado = MagicMock()
        mock_orden_registrado.id = 42
        mock_orden_registrado.estado = EstadoPedido.PENDIENTE
        mock_orden_registrado.email_invitado = ""
        mock_orden_registrado.usuario = MagicMock(id=10, email="registrado@correo.com")
        mock_orden_registrado.requiere_revision = False

        with patch("ecommerce.infrastructure.ventas.views.pasarela_mercado_pago", return_value=pasarela), \
             patch("ecommerce.infrastructure.ventas.views.confirmar_pago", return_value=self.confirmar_pago), \
             patch("ecommerce.infrastructure.ventas.views.OrdenCompra.objects.filter") as mock_filter:
            mock_filter.return_value.first.return_value = mock_orden_registrado

            res_registrado = self.client.get("/api/ventas/mercadopago/retorno/?orden=42&payment_id=801")
            self.assertEqual(res_registrado.status_code, 302)
            self.assertIn("/pago-exitoso?orden=42", res_registrado.headers["Location"])
            self.assertEqual(self.repo_ordenes.orden.estado, EstadoPedido.PAGADO)
            self.assertEqual(self.inventario.stock, 3)

    def test_crear_preferencia_prioriza_init_point_sobre_sandbox_init_point(self):
        """Verifica que la preferencia entrega init_point para evitar el error /fatal/ de sandbox_init_point."""
        adapter = MercadoPagoAdapter(access_token="TEST-12345678-abcd", webhook_secret="test_secret")

        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "id": "pref-123",
            "init_point": "https://www.mercadopago.cl/checkout/v1/redirect?pref_id=pref-123",
            "sandbox_init_point": "https://sandbox.mercadopago.cl/checkout/v1/redirect?pref_id=pref-123",
        }

        with patch("requests.post", return_value=mock_resp):
            pref = adapter.iniciar(
                orden_id="42",
                monto=10000,
                url_retorno="http://localhost:8000/api/ventas/mercadopago/retorno/",
            )
            # Debe entregar la URL unificada de init_point (no la de sandbox que falla en /fatal/)
            self.assertEqual(pref.url_pago, "https://www.mercadopago.cl/checkout/v1/redirect?pref_id=pref-123")
            self.assertEqual(pref.referencia, "pref-123")

    def test_preferencia_lleva_las_urls_de_retorno_y_el_aviso_solo_si_es_publico(self):
        adapter = MercadoPagoAdapter(access_token="TEST-12345678-abcd", webhook_secret="test_secret")
        respuesta = MagicMock()
        respuesta.json.return_value = {"id": "pref-1", "init_point": "https://mp.test/pagar"}
        retorno = "https://tienda.test/api/ventas/mercadopago/retorno/"

        for aviso, enviado in (("https://tienda.test/api/ventas/mercadopago/webhook/", True),
                               ("http://localhost:8000/api/ventas/mercadopago/webhook/", False)):
            with self.subTest(aviso=aviso), patch("requests.post", return_value=respuesta) as post:
                adapter.iniciar(orden_id="42", monto=Decimal("10000"), url_retorno=retorno, url_aviso=aviso)
                payload = post.call_args.kwargs["json"]
                self.assertEqual(payload["back_urls"]["success"], f"{retorno}?resultado=success&orden=42")
                self.assertEqual(payload["back_urls"]["failure"], f"{retorno}?resultado=failure&orden=42")
                self.assertEqual(payload["auto_return"], "approved")
                self.assertEqual(payload.get("notification_url"), aviso if enviado else None)

    def test_resultado_traduce_los_estados_de_mercado_pago(self):
        adapter = MercadoPagoAdapter(access_token="TEST-12345678-abcd", webhook_secret="test_secret")
        casos = {
            "approved": EstadoPago.APROBADO, "in_process": EstadoPago.PENDIENTE, "rejected": EstadoPago.RECHAZADO,
            "cancelled": EstadoPago.ANULADO, "refunded": EstadoPago.REEMBOLSADO,
            "charged_back": EstadoPago.REEMBOLSADO, "in_mediation": EstadoPago.PENDIENTE,
        }
        for estado_mp, esperado in casos.items():
            respuesta = MagicMock()
            respuesta.json.return_value = {"id": 801, "status": estado_mp, "external_reference": "ORD-42",
                                           "transaction_amount": 10000}
            with self.subTest(estado=estado_mp), patch("requests.get", return_value=respuesta):
                pago = adapter.resultado("801")
                self.assertEqual(pago, PagoConsultado(referencia="801", orden_id="42", estado=esperado,
                                                      monto=Decimal("10000")))

    def test_busqueda_fallida_lanza_error_de_pasarela(self):
        adapter = MercadoPagoAdapter(access_token="TEST-12345678-abcd", webhook_secret="test_secret")
        respuesta = MagicMock()
        respuesta.raise_for_status.side_effect = Exception("500")
        with patch("requests.get", return_value=respuesta), self.assertRaises(ErrorPasarelaPago):
            adapter.pagos_recientes(30)

