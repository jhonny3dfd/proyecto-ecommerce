"""Registro de las pasarelas de pago en línea (RF-02.2). Para sumar una: crear su adaptador del puerto
`PasarelaPago` (ecommerce/application/pagos.py), registrarlo aquí con sus rutas y declarar el medio en
ecommerce/domain/medios_pago.py."""

from ecommerce.application.pagos import PasarelaPago
from ecommerce.domain.medios_pago import CodigoMedioPago

from .adapters.mercadopago import MercadoPagoAdapter
from .adapters.transbank_adapter import TransbankWebpayAdapter

PASARELAS = {
    CodigoMedioPago.TRANSBANK: TransbankWebpayAdapter,
    CodigoMedioPago.MERCADO_PAGO: MercadoPagoAdapter,
}

# Bajo /api/ventas/: adonde vuelve el comprador y adonde avisa la pasarela ('' si no avisa por webhook)
RUTAS = {
    CodigoMedioPago.TRANSBANK: ('transbank/retorno/', ''),
    CodigoMedioPago.MERCADO_PAGO: ('mercadopago/retorno/', 'mercadopago/webhook/'),
}


def pasarela(codigo) -> PasarelaPago:
    return PASARELAS[codigo]()


def urls_pasarela(codigo, request=None) -> tuple[str, str]:
    """(url de retorno, url de aviso) completas, con el dominio por el que llegó la compra."""
    base = f"{request.scheme}://{request.get_host()}" if request else "http://localhost:8000"
    retorno, aviso = RUTAS[codigo]
    return f"{base}/api/ventas/{retorno}", f"{base}/api/ventas/{aviso}" if aviso else ''
