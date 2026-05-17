#!/bin/sh
# Diagnostic-heavy entrypoint. Every step is announced. On failure we
# sleep before exiting so the orchestrator definitely captures logs.

set -u

die() {
    echo ""
    echo "════════════════════════════════════════════════════════════════"
    echo "  STARTUP FAILED: $*"
    echo "════════════════════════════════════════════════════════════════"
    # Give the log shipper time to flush before the container is reaped.
    sleep 5
    exit 1
}

step() {
    echo ""
    echo "▶ $*"
}

: "${PORT:=8080}"
export PORT

step "entrypoint start (PORT=$PORT, PWD=$(pwd))"

step "env presence check"
missing=""
for var in DJANGO_SECRET_KEY FERNET_KEY DB_HOST DB_NAME DB_USER DB_PASSWORD; do
    eval "val=\${$var:-}"
    if [ -z "$val" ]; then
        missing="$missing $var"
        echo "  ✗ $var = (unset)"
    else
        echo "  ✓ $var = (set, ${#val} chars)"
    fi
done
echo "  · DJANGO_DEBUG = ${DJANGO_DEBUG:-(unset, defaults to False)}"
echo "  · DJANGO_ALLOWED_HOSTS = ${DJANGO_ALLOWED_HOSTS:-(unset)}"
echo "  · DB_HOST = ${DB_HOST:-(unset)} :${DB_PORT:-5432}"
echo "  · DB_SSLMODE = ${DB_SSLMODE:-(unset, defaults to prefer)}"
[ -n "$missing" ] && die "missing required env vars:$missing"

step "rendering nginx config"
envsubst '${PORT}' \
    < /etc/nginx/templates/app.conf.template \
    > /etc/nginx/conf.d/app.conf \
    || die "envsubst failed"
nginx -t 2>&1 || die "nginx config invalid"

cd /app/backend || die "cannot cd to /app/backend"

step "importing Django settings"
python -c "import config.settings as s; print(f'  settings imported. DEBUG={s.DEBUG}, ALLOWED_HOSTS={s.ALLOWED_HOSTS}')" \
    || die "settings import failed (see traceback above)"

step "running migrations"
python manage.py migrate --noinput --verbosity 2 \
    || die "migrations failed (DB unreachable, wrong creds, or schema mismatch — see traceback above)"

step "collecting static"
python manage.py collectstatic --noinput --clear --verbosity 1 \
    || die "collectstatic failed"

step "starting supervisord (nginx :$PORT + gunicorn :8000)"
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/app.conf
