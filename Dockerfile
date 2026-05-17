# ─── Stage 1: build the Vite SPA ─────────────────────────────────────────
FROM node:20-alpine AS frontend

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./

ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build


# ─── Stage 2: Python runtime — gunicorn serves API + static + SPA via WhiteNoise
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings \
    PORT=8080

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY --from=frontend /frontend/dist /app/frontend/dist
COPY cloud/docker/entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chmod +x /usr/local/bin/entrypoint.sh \
    && mkdir -p /app/backend/staticfiles \
    && useradd --uid 1000 --no-create-home --shell /sbin/nologin app \
    && chown -R app:app /app

USER app

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
