#!/bin/sh
set -eu

: "${PORT:=8080}"
export PORT

echo "▶ entrypoint: PORT=$PORT"

# Fail fast with a readable message if required env vars are missing,
# instead of a deep Python KeyError traceback from settings.py.
missing=""
for var in DJANGO_SECRET_KEY FERNET_KEY DB_HOST DB_NAME DB_USER DB_PASSWORD; do
    eval "val=\${$var:-}"
    [ -z "$val" ] && missing="$missing $var"
done
if [ -n "$missing" ]; then
    echo "✗ Missing required environment variables:$missing" >&2
    echo "  Set them in the platform UI → Settings → Environment Variables." >&2
    exit 1
fi
echo "✓ required env vars present"

# Render nginx config with the runtime $PORT (Azure Container Apps may inject one).
envsubst '${PORT}' \
    < /etc/nginx/templates/app.conf.template \
    > /etc/nginx/conf.d/app.conf

cd /app/backend

echo "▶ running migrations…"
python manage.py migrate --noinput

echo "▶ collecting static…"
python manage.py collectstatic --noinput --clear >/dev/null

echo "▶ starting supervisord (nginx + gunicorn)…"
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/app.conf
