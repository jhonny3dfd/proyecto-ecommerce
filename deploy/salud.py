"""Healthcheck del contenedor del backend: GET /api/salud/ (200 si PostgreSQL y MongoDB responden).

La petición lleva como Host el primer dominio de ALLOWED_HOSTS; con otro, Django responde 400.
"""
import os
import sys
import urllib.request

dominio = os.environ.get('ALLOWED_HOSTS', '').split(',')[0].strip().lstrip('.')
peticion = urllib.request.Request('http://127.0.0.1:8000/api/salud/',
                                  headers={'Host': dominio if dominio and dominio != '*' else 'localhost'})
try:
    with urllib.request.urlopen(peticion, timeout=5) as respuesta:
        sys.exit(0 if respuesta.status == 200 else 1)
except Exception:
    sys.exit(1)
