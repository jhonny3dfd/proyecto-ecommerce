# Backend de la tienda: Django con gunicorn. Se construye desde la raíz del repositorio (ver deploy/docker-compose.yml).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# El proceso no corre como root
RUN useradd --system --uid 1000 --home-dir /app tienda

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY manage.py .
COPY backend_project backend_project
COPY ecommerce ecommerce
COPY deploy/entrypoint.sh deploy/salud.py deploy/

# Las fotos (volumen), los archivos privados (volumen; ej. las fotos de las cotizaciones, que solo ve el admin) y
# los estáticos del admin quedan a nombre del usuario de la tienda. El sed quita los CRLF si la imagen se construye
# desde una copia de Windows
RUN mkdir -p media privado staticfiles && chown tienda media privado staticfiles \
    && sed -i 's/\r$//' deploy/entrypoint.sh && chmod +x deploy/entrypoint.sh

ENV MEDIA_ROOT=/app/media \
    ARCHIVOS_PRIVADOS_ROOT=/app/privado \
    STATIC_ROOT=/app/staticfiles

USER tienda
EXPOSE 8000
CMD ["deploy/entrypoint.sh"]
