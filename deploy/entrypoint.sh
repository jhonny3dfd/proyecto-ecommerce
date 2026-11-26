#!/bin/sh
# Arranque del backend: aplica las migraciones de la versión nueva, junta los estilos del admin de Django y levanta
# gunicorn. Los comandos de manage.py (createsuperuser, cancelar_pagos_vencidos) se corren con `docker compose exec`.
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

# El registro de accesos va sin la query (%(U)s): los enlaces de reseña y los retornos de pago llevan tokens ahí
exec gunicorn backend_project.wsgi \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --threads "${GUNICORN_THREADS:-4}" \
    --timeout 60 \
    --no-control-socket \
    --access-logfile - \
    --access-logformat '%(h)s %(t)s "%(m)s %(U)s" %(s)s %(b)s %(M)sms'
