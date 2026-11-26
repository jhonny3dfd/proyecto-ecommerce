"""Enlace para dejar la reseña de un pedido: /resena?t=<token>.

El token va firmado con la SECRET_KEY y una sal propia, así que no se puede alterar para reseñar otro pedido ni
reutilizar otro token del sistema. Vence a los DIAS_VIGENCIA_ENLACE días de generado; el plazo real (desde la
entrega) lo revisa el caso de uso.
"""

import os
from datetime import timedelta
from urllib.parse import quote

from django.core import signing

from ecommerce.domain.resenas import DIAS_VIGENCIA_ENLACE

SAL_RESENA = 'ventas.resena'


def token_resena(orden_id) -> str:
    return signing.dumps(int(orden_id), salt=SAL_RESENA)


def orden_del_token(token) -> int | None:
    """El número del pedido; None si el token fue alterado, es de otro uso o venció."""
    try:
        orden_id = signing.loads(str(token or ''), salt=SAL_RESENA, max_age=timedelta(days=DIAS_VIGENCIA_ENLACE))
    except signing.BadSignature:
        return None
    return orden_id if isinstance(orden_id, int) else None


def url_resena(orden_id) -> str:
    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173').rstrip('/')
    return f'{frontend_url}/resena?t={quote(token_resena(orden_id))}'
