"""GET /api/salud/: si la tienda puede atender. Lo usan el healthcheck de Docker y el monitor externo.

Público y sin datos sensibles: solo dice si PostgreSQL y MongoDB responden.
"""

import logging

from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from mongoengine.connection import get_db
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)


def _postgres_responde() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        return True
    except DatabaseError:
        logger.exception('PostgreSQL no responde')
        return False


def _mongo_responde() -> bool:
    try:
        get_db().command('ping')
        return True
    except PyMongoError:
        logger.exception('MongoDB no responde')
        return False


@never_cache
@require_http_methods(['GET', 'HEAD'])
def salud(request):
    bases = {'postgres': _postgres_responde(), 'mongo': _mongo_responde()}
    sana = all(bases.values())
    return JsonResponse({
        'estado': 'ok' if sana else 'error',
        **{nombre: 'ok' if responde else 'error' for nombre, responde in bases.items()},
    }, status=200 if sana else 503)
