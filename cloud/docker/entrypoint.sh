#!/bin/sh
set -eu

: "${PORT:=8080}"
export PORT

# Render nginx config with the runtime $PORT (Azure Container Apps may inject one).
envsubst '${PORT}' \
    < /etc/nginx/templates/app.conf.template \
    > /etc/nginx/conf.d/app.conf

cd /app/backend

# Apply DB migrations on every cold start. Cheap and idempotent.
python manage.py migrate --noinput

# Collect Django static assets (admin + DRF). Vite assets are baked in already.
python manage.py collectstatic --noinput --clear >/dev/null

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/app.conf
