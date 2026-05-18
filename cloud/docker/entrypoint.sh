#!/bin/sh
set -eu

: "${PORT:=8080}"
export PORT

cd /app/backend

python manage.py migrate --noinput
python manage.py collectstatic --noinput --verbosity 0 >/dev/null

exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:$PORT" \
    --workers 2 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
