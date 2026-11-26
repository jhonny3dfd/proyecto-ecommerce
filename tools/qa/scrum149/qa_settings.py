"""Configuración local aislada de PostgreSQL y MongoDB para verificar el catálogo."""
import os
from pathlib import Path
from qa_env import BACKEND_VARIABLES, require_env

credentials = require_env(BACKEND_VARIABLES)

QA_ROOT = Path(__file__).resolve().parents[3] / '.tmp' / 'scrum149'
os.environ.update({
    'DEBUG': 'True',
    'SECRET_KEY': credentials['QA149_SECRET_KEY'],
    'CLAVE_CIFRADO_CREDENCIALES': credentials['QA149_CLAVE_CIFRADO_CREDENCIALES'],
    'POSTGRES_DB': 'ecode_qa_scrum149',
    'POSTGRES_USER': 'qa149',
    'POSTGRES_PASSWORD': credentials['QA149_POSTGRES_PASSWORD'],
    'POSTGRES_HOST': '127.0.0.1',
    'POSTGRES_PORT': '55439',
    'MONGO_URI': 'mongodb://127.0.0.1:27049/ecode_qa_scrum149',
    'MONGO_TEST_URI': 'mongodb://127.0.0.1:27049/',
    'RESEND_API_KEY': '', 'EMAIL_HOST': '', 'GOOGLE_CLIENT_ID': '',
    'DEFAULT_FROM_EMAIL': 'qa149@example.test',
    'SECURE_SSL_REDIRECT': 'False', 'SESSION_COOKIE_SECURE': 'False',
    'CSRF_COOKIE_SECURE': 'False',
    'ALLOWED_HOSTS': 'localhost,127.0.0.1,testserver',
    'CORS_ALLOWED_ORIGINS': 'http://localhost:5173,http://127.0.0.1:5173',
    'CSRF_TRUSTED_ORIGINS': 'http://localhost:5173,http://127.0.0.1:5173',
    'FRONTEND_URL': 'http://127.0.0.1:5173',
    'MEDIA_ROOT': str(QA_ROOT / 'media'),
})

from backend_project.settings import *  # noqa: F403,E402

MAILERS = {'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}}
DATABASES['default']['TEST'] = {'NAME': 'test_ecode_qa_scrum149'}
