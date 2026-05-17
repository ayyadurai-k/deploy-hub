#!/bin/sh
# Diagnostic entrypoint. Never exits on failure — start nginx + gunicorn
# regardless so the container stays up and we can probe it via HTTP and
# (if the platform allows) shell into it. Failures are logged loudly.

set -u

step() {
    echo ""
    echo "▶ $*"
}

warn() {
    echo ""
    echo "════════════════════════════════════════════════════════════════"
    echo "  WARN: $*"
    echo "════════════════════════════════════════════════════════════════"
}

: "${PORT:=8080}"
export PORT

step "entrypoint start (PORT=$PORT, $(date -u +%FT%TZ))"

step "env presence (values redacted)"
for var in DJANGO_SECRET_KEY FERNET_KEY DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD DB_SSLMODE DJANGO_DEBUG DJANGO_ALLOWED_HOSTS; do
    eval "val=\${$var:-}"
    if [ -z "$val" ]; then
        echo "  ✗ $var = (unset)"
    elif [ "$var" = "DB_HOST" ] || [ "$var" = "DB_PORT" ] || [ "$var" = "DB_NAME" ] || [ "$var" = "DB_USER" ] || [ "$var" = "DB_SSLMODE" ] || [ "$var" = "DJANGO_DEBUG" ] || [ "$var" = "DJANGO_ALLOWED_HOSTS" ]; then
        echo "  ✓ $var = $val"
    else
        echo "  ✓ $var = (set, ${#val} chars, redacted)"
    fi
done

step "render nginx config"
envsubst '${PORT}' < /etc/nginx/templates/app.conf.template > /etc/nginx/conf.d/app.conf
nginx -t 2>&1 || warn "nginx config test failed"

cd /app/backend

step "quick DB reachability probe (5s timeout)"
python - <<'PY' || warn "DB unreachable — migrations will fail and DB-backed views will 500, but the container will keep serving"
import os, socket, sys
host = os.environ.get("DB_HOST", "")
port = int(os.environ.get("DB_PORT", "5432"))
if not host:
    print(f"  ✗ DB_HOST is empty")
    sys.exit(1)
print(f"  dialing {host}:{port} …")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
try:
    s.connect((host, port))
    print(f"  ✓ TCP connect ok")
except Exception as e:
    print(f"  ✗ TCP connect failed: {type(e).__name__}: {e}")
    sys.exit(1)
finally:
    s.close()
PY

step "import Django settings"
python -c "import config.settings as s; print(f'  DEBUG={s.DEBUG}  ALLOWED_HOSTS={s.ALLOWED_HOSTS}')" \
    || warn "settings import failed — see traceback above"

step "run migrations (best-effort, won't block startup)"
timeout 30 python manage.py migrate --noinput --verbosity 1 \
    || warn "migrate failed/timed out — likely DB_HOST wrong or unreachable from ACA"

step "collect static (best-effort)"
python manage.py collectstatic --noinput --clear --verbosity 0 >/dev/null \
    || warn "collectstatic failed"

step "starting supervisord (nginx :$PORT + gunicorn :8000) — exec"
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/app.conf
