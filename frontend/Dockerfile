# Frontend de la tienda: compila React con Vite y lo entrega Caddy, junto con las fotos y el paso a la API.
# Se construye desde la raíz del repositorio (ver deploy/docker-compose.yml).
FROM node:22-slim AS compilacion

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
# La API va en el mismo origen que la tienda: el mismo build sirve para todas
ENV VITE_API_URL=/api/
RUN npm run build

FROM caddy:2-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=compilacion /frontend/dist /srv/tienda
