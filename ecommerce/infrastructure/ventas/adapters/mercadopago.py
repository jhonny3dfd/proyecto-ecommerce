"""Adaptador Checkout Pro de Mercado Pago (RF-02.2): preferencia de pago, firma del webhook y consulta de pagos."""

from decimal import Decimal
import hashlib
import hmac
import logging

import requests

from ecommerce.application.pagos import (
    ErrorPasarelaPago, PagoConsultado, PagoIniciado, PasarelaConAvisos, PasarelaConBusqueda,
)
from ecommerce.domain.medios_pago import CodigoMedioPago, EstadoPago

from ..repositorio_medios_pago import DjangoRepositorioMediosPago

logger = logging.getLogger(__name__)

# Los estados de un pago en Mercado Pago, traducidos a los de la tienda. Uno desconocido (ej. in_mediation) se
# trata como pendiente: no aprueba ni cancela la orden
ESTADOS_MERCADO_PAGO = {
    'approved': EstadoPago.APROBADO,
    'pending': EstadoPago.PENDIENTE,
    'in_process': EstadoPago.PENDIENTE,
    'authorized': EstadoPago.PENDIENTE,
    'rejected': EstadoPago.RECHAZADO,
    'failure': EstadoPago.RECHAZADO,
    'cancelled': EstadoPago.ANULADO,
    'refunded': EstadoPago.REEMBOLSADO,
    'charged_back': EstadoPago.REEMBOLSADO,
}


class MercadoPagoAdapter(PasarelaConAvisos, PasarelaConBusqueda):
    nombre = 'Mercado Pago'
    API_BASE_URL = "https://api.mercadopago.com"

    def __init__(
        self,
        *,
        access_token: str | None = None,
        webhook_secret: str | None = None,
    ):
        if access_token is not None and webhook_secret is not None:
            # Si ambos se pasan explícitamente (ej. en tests unitarios), no tocamos la base de datos
            self.access_token = access_token
            self.webhook_secret = webhook_secret
        else:
            datos = DjangoRepositorioMediosPago().obtener(CodigoMedioPago.MERCADO_PAGO).datos
            self.access_token = access_token if access_token is not None else datos.get('access_token', '')
            self.webhook_secret = webhook_secret if webhook_secret is not None else datos.get('webhook_secret', '')

    def _headers(self) -> dict[str, str]:
        if not self.access_token:
            raise ErrorPasarelaPago("Mercado Pago no tiene un access_token configurado.")
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def iniciar(self, orden_id, monto, url_retorno, url_aviso=''):
        monto_clp = int(round(float(monto)))
        payload = {
            "items": [
                {
                    "id": f"ORD-{orden_id}",
                    "title": f"Pedido #{orden_id}",
                    "quantity": 1,
                    "currency_id": "CLP",
                    "unit_price": monto_clp,
                }
            ],
            "external_reference": str(orden_id),
            "back_urls": {
                resultado: f"{url_retorno}?resultado={resultado}&orden={orden_id}"
                for resultado in ("success", "failure", "pending")
            },
        }
        if url_retorno.startswith("https://"):
            payload["auto_return"] = "approved"
        # Mercado Pago rechaza notification_url si es localhost; solo la enviamos si es una URL pública
        if url_aviso and "localhost" not in url_aviso and "127.0.0.1" not in url_aviso:
            payload["notification_url"] = url_aviso

        try:
            response = requests.post(
                f"{self.API_BASE_URL}/checkout/preferences",
                json=payload,
                headers=self._headers(),
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.error("Error creando preferencia en Mercado Pago: %s", exc)
            raise ErrorPasarelaPago(f"No se pudo crear la preferencia de Mercado Pago: {exc}") from exc

        pref_id = str(data.get("id") or "")
        # En el flujo vigente de Mercado Pago con cuentas TEST y producción, init_point
        # reconoce automáticamente las credenciales de prueba y procesa las tarjetas ficticias
        # oficiales sin redirigir al subdominio legacy sandbox que colapsa con error fatal.
        url_pago = data.get("init_point") or data.get("sandbox_init_point") or ""

        if not pref_id or not url_pago:
            raise ErrorPasarelaPago("Mercado Pago no devolvió una URL de pago válida.")

        return PagoIniciado(referencia=pref_id, url_pago=url_pago)

    def aviso_autentico(self, firma, id_peticion, referencia):
        """Verifica la firma HMAC-SHA256 enviada por Mercado Pago en el header x-signature."""
        if not self.webhook_secret or not firma or not referencia:
            return False

        partes = {}
        for item in firma.split(","):
            if "=" in item:
                k, v = item.strip().split("=", 1)
                partes[k.strip()] = v.strip()

        ts = partes.get("ts")
        v1 = partes.get("v1")
        if not ts or not v1:
            return False

        data_id_clean = str(referencia).lower()
        manifest = f"id:{data_id_clean};request-id:{id_peticion or ''};ts:{ts};"
        firma_calculada = hmac.new(
            self.webhook_secret.encode("utf-8"),
            manifest.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(firma_calculada, v1)

    @staticmethod
    def _pago(data: dict, referencia: str = '') -> PagoConsultado:
        """Un pago de la API de Mercado Pago, con su estado traducido."""
        return PagoConsultado(
            referencia=str(data.get("id") or referencia),
            orden_id=str(data.get("external_reference") or "").replace("ORD-", "").strip(),
            estado=ESTADOS_MERCADO_PAGO.get(str(data.get("status") or "").lower(), EstadoPago.PENDIENTE),
            monto=Decimal(str(data.get("transaction_amount") or 0)),
        )

    def resultado(self, referencia):
        """Consulta el estado real del pago directamente en la API de Mercado Pago."""
        try:
            response = requests.get(
                f"{self.API_BASE_URL}/v1/payments/{referencia}",
                headers=self._headers(),
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.error("Error consultando pago %s en Mercado Pago: %s", referencia, exc)
            raise ErrorPasarelaPago(f"No se pudo consultar el pago en Mercado Pago: {exc}") from exc

        return self._pago(data, referencia)

    def _buscar(self, filtros: str) -> list[PagoConsultado]:
        try:
            response = requests.get(
                f"{self.API_BASE_URL}/v1/payments/search?{filtros}&sort=date_created&criteria=desc",
                headers=self._headers(),
                timeout=10,
            )
            response.raise_for_status()
            resultados = response.json().get("results", [])
        except Exception as exc:
            logger.error("Error buscando pagos en Mercado Pago: %s", exc)
            raise ErrorPasarelaPago("Error al consultar la API de Mercado Pago.") from exc
        return [self._pago(data) for data in resultados]

    def pagos_de_orden(self, orden_id):
        return self._buscar(f"external_reference={orden_id}")

    def pagos_recientes(self, limite):
        return self._buscar(f"limit={int(limite)}")
