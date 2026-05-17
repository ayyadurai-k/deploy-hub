#!/bin/sh
# Diagnostic entrypoint — never exits on a recoverable failure so the
# container stays up and the orchestrator can probe it. Logs each step.

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

step "entrypoint start (PORT=$PORT, $(date -u +%FT%TZ), user=$(id -un):$(id -u))"

step "env presence"
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

cd /app/backend

step "TCP probe $DB_HOST:$DB_PORT (5s)"
python - <<'PY' || warn "DB unreachable — migrations will fail; DB-backed views will 500. App still starts so /api/v1/healthz works."
import os, socket, sys
host = os.environ.get("DB_HOST", "")
port = int(os.environ.get("DB_PORT", "5432"))
if not host:
    print("  ✗ DB_HOST empty"); sys.exit(1)
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(5)
try:
    s.connect((host, port)); print(f"  ✓ {host}:{port} reachable")
except Exception as e:
    print(f"  ✗ {host}:{port}  →  {type(e).__name__}: {e}"); sys.exit(1)
finally:
    s.close()
PY

step "import Django settings"
python -c "import config.settings as s; print(f'  DEBUG={s.DEBUG}  ALLOWED_HOSTS={s.ALLOWED_HOSTS}')" \
    || warn "settings import failed"

step "collectstatic (best-effort)"
python manage.py collectstatic --noinput --verbosity 0 >/dev/null \
    || warn "collectstatic failed"

step "migrate (30s timeout, best-effort)"
timeout 30 python manage.py migrate --noinput --verbosity 1 \
    || warn "migrate failed/timed out"

step "exec gunicorn on 0.0.0.0:$PORT"
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:$PORT" \
    --workers 2 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
