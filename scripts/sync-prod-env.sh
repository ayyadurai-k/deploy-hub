#!/usr/bin/env bash
# Pull the production secrets + service configs from the Lightsail host into
# the local cloud/ folder (which is gitignored). Run this after rotating any
# secret on the server, or any time you want to refresh the local recovery
# copy. Idempotent.
#
# Pulls three files:
#   backend/.env                      → cloud/prod.env             (mode 600)
#   /etc/systemd/system/deploy-hub.service → cloud/deploy-hub.service     (644)
#   /etc/nginx/conf.d/deploy-hub.conf      → cloud/nginx-deploy-hub.conf  (644)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

KEY="cloud/deploy-hub.pem"
HOST="ec2-user@3.7.143.78"

if [[ ! -f "$KEY" ]]; then
    echo "ERROR: SSH key not found at $KEY"
    echo "       Re-download from Lightsail console → Account → SSH keys"
    exit 1
fi

echo "→ pulling backend/.env"
scp -q -i "$KEY" "$HOST:/home/ec2-user/deploy-hub/backend/.env" cloud/prod.env
chmod 600 cloud/prod.env

echo "→ pulling systemd unit"
ssh -q -i "$KEY" "$HOST" 'sudo cat /etc/systemd/system/deploy-hub.service' \
    > cloud/deploy-hub.service
chmod 644 cloud/deploy-hub.service

echo "→ pulling nginx config"
ssh -q -i "$KEY" "$HOST" 'sudo cat /etc/nginx/conf.d/deploy-hub.conf' \
    > cloud/nginx-deploy-hub.conf
chmod 644 cloud/nginx-deploy-hub.conf

echo ""
echo "✓ synced — current local state:"
ls -la cloud/prod.env cloud/deploy-hub.service cloud/nginx-deploy-hub.conf
