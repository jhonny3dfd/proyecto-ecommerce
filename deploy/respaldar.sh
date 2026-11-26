#!/bin/sh
# Respaldo de una tienda publicada con deploy/docker-compose.yml: PostgreSQL, MongoDB, las fotos y los archivos
# privados, en <carpeta>/<AAAA-MM-DD>/<tienda>/. Borra los respaldos de más de 7 días.
#
#   sh deploy/respaldar.sh <tienda> <archivo de la tienda> <carpeta de respaldos>
#   sh deploy/respaldar.sh alan /opt/tiendas/alan.env /opt/tiendas/respaldos
set -eu

if [ "$#" -ne 3 ]; then
    echo "Uso: $0 <tienda> <archivo de la tienda> <carpeta de respaldos>" >&2
    exit 2
fi
tienda=$1
archivo=$2
carpeta=$3
case "$carpeta" in
    /|"") echo "La carpeta de respaldos no puede ser $carpeta" >&2; exit 2 ;;
esac

compose="docker compose -p $tienda -f $(dirname "$0")/docker-compose.yml --env-file $archivo"
destino="$carpeta/$(date +%F)/$tienda"
mkdir -p "$destino"

# Las variables de usuario y clave existen dentro de cada contenedor: las comillas simples evitan que las
# reemplace este script
$compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$destino/postgres.dump"
$compose exec -T mongo sh -c 'mongodump --quiet --archive --gzip -u "$MONGO_INITDB_ROOT_USERNAME" \
    -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin' > "$destino/mongo.archive.gz"
$compose exec -T backend tar czf - -C /app/media . > "$destino/media.tar.gz"
# Los archivos que solo ve el admin (las fotos de las cotizaciones)
$compose exec -T backend tar czf - -C /app/privado . > "$destino/privado.tar.gz"

# Solo las carpetas por fecha dentro de la carpeta de respaldos
find "$carpeta" -mindepth 1 -maxdepth 1 -type d -name '????-??-??' -mtime +7 -exec rm -rf {} +
echo "Respaldo de $tienda en $destino"
