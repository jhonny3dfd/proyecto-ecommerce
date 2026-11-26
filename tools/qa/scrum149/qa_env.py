"""Carga las credenciales privadas de QA sin sustituir variables de la sesión."""
import os
from pathlib import Path

from dotenv import load_dotenv

ENV_FILE = Path(__file__).with_name('.env.local')
BACKEND_VARIABLES = (
    'QA149_POSTGRES_PASSWORD', 'QA149_SECRET_KEY', 'QA149_CLAVE_CIFRADO_CREDENCIALES',
)
ADMIN_VARIABLES = ('QA149_ADMIN_EMAIL', 'QA149_ADMIN_PASSWORD')


def require_env(names):
    load_dotenv(ENV_FILE, override=False, interpolate=False)
    missing = [name for name in names if not os.environ.get(name, '').strip()]
    if missing:
        raise RuntimeError('Faltan variables de QA: ' + ', '.join(missing)
                           + '. Configure la sesión o tools/qa/scrum149/.env.local.')
    return {name: os.environ[name] for name in names}
