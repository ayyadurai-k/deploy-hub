# ─── Stage 1: build the Vite SPA ─────────────────────────────────────────
FROM node:20-alpine AS frontend

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./

# Same-origin API in prod: the SPA hits `/api/v1` on the same host nginx serves it from.
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build


# ─── Stage 2: Python runtime + nginx + supervisord ───────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings \
    PORT=8080

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        nginx \
        supervisor \
        gettext-base \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/nginx/sites-enabled/default

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install -r /app/backend/requirements.txt

COPY backend/ /app/backend/

COPY --from=frontend /frontend/dist /app/frontend/dist

COPY cloud/docker/nginx.conf.template /etc/nginx/templates/app.conf.template
COPY cloud/docker/supervisord.conf /etc/supervisor/conf.d/app.conf
COPY cloud/docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh \
    && mkdir -p /app/backend/staticfiles /var/log/supervisor /var/log/nginx

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
