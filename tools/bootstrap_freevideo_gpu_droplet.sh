#!/usr/bin/env bash
set -euo pipefail

# Production bootstrap for an Ubuntu/NVIDIA GPU machine (DigitalOcean AI/ML-ready image recommended).
# This script intentionally refuses to accept the MiniMax/FreeVideo model license unless the
# operator explicitly sets FREEVIDEO_ACCEPT_MODEL_LICENSE=1.

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

if [[ "${FREEVIDEO_ACCEPT_MODEL_LICENSE:-0}" != "1" ]]; then
  cat >&2 <<'EOF'
FreeVideo model installation requires acceptance of the MiniMax H3 Community License.
Review the license linked from the FreeVideo project, then rerun with:
  FREEVIDEO_ACCEPT_MODEL_LICENSE=1 bash tools/bootstrap_freevideo_gpu_droplet.sh
EOF
  exit 2
fi

FREEVIDEO_DIR="${FREEVIDEO_DIR:-/opt/FreeVideo}"
MPT_DIR="${MPT_DIR:-/opt/MoneyPrinterTurbo}"
WORKER_VENV="${WORKER_VENV:-/opt/mpt-freevideo-worker-venv}"
WORKER_PORT="${FREEVIDEO_WORKER_PORT:-8765}"
ENV_FILE="/etc/mpt-freevideo-worker.env"
SERVICE_FILE="/etc/systemd/system/mpt-freevideo-worker.service"
CADDY_FILE="/etc/caddy/Caddyfile"

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  ca-certificates curl git gnupg debian-keyring debian-archive-keyring \
  apt-transport-https ffmpeg python3 python3-venv python3-pip build-essential

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "nvidia-smi is missing. Use an NVIDIA AI/ML-ready GPU image with driver 580+ installed." >&2
  exit 3
fi

nvidia-smi

clone_or_update() {
  local repo="$1" destination="$2"
  if [[ -d "$destination/.git" ]]; then
    git -C "$destination" fetch --depth 1 origin main
    git -C "$destination" reset --hard origin/main
  else
    rm -rf "$destination"
    git clone --depth 1 "$repo" "$destination"
  fi
}

clone_or_update "https://github.com/FlashML-org/FreeVideo.git" "$FREEVIDEO_DIR"
clone_or_update "https://github.com/ashokudu14-lang/MoneyPrinterTurbo.git" "$MPT_DIR"

chmod +x "$FREEVIDEO_DIR/setup.sh" "$FREEVIDEO_DIR/freevideo" || true
(
  cd "$FREEVIDEO_DIR"
  ./setup.sh --install-system-deps --yes --accept-model-license
)

python3 -m venv "$WORKER_VENV"
"$WORKER_VENV/bin/python" -m pip install --upgrade pip
"$WORKER_VENV/bin/pip" install \
  'fastapi==0.136.3' 'uvicorn==0.32.1' 'pydantic>=2,<3'

if [[ -z "${FREEVIDEO_API_TOKEN:-}" ]]; then
  FREEVIDEO_API_TOKEN="$($WORKER_VENV/bin/python - <<'PY'
import secrets
print(secrets.token_urlsafe(40))
PY
)"
fi

cat >"$ENV_FILE" <<EOF
FREEVIDEO_ROOT=$FREEVIDEO_DIR
FREEVIDEO_API_TOKEN=$FREEVIDEO_API_TOKEN
FREEVIDEO_TIMEOUT_SECONDS=${FREEVIDEO_TIMEOUT_SECONDS:-3600}
FREEVIDEO_WORKER_HOST=127.0.0.1
FREEVIDEO_WORKER_PORT=$WORKER_PORT
EOF
chmod 600 "$ENV_FILE"

cat >"$SERVICE_FILE" <<EOF
[Unit]
Description=MoneyPrinterTurbo FreeVideo GPU Worker
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$MPT_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$WORKER_VENV/bin/python tools/freevideo_worker.py
Restart=always
RestartSec=5
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now mpt-freevideo-worker.service

# Install Caddy from its official Debian repository so the worker is exposed through HTTPS.
if ! command -v caddy >/dev/null 2>&1; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    | tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  chmod o+r /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y
  apt-get install -y caddy
fi

PUBLIC_IP="$(curl -fsS http://169.254.169.254/metadata/v1/interfaces/public/0/ipv4/address || true)"
if [[ -z "$PUBLIC_IP" ]]; then
  PUBLIC_IP="$(curl -4fsS https://ifconfig.me || true)"
fi
if [[ -z "$PUBLIC_IP" ]]; then
  echo "Could not determine the machine's public IPv4 address." >&2
  exit 4
fi

DASHED_IP="${PUBLIC_IP//./-}"
PUBLIC_HOST="${FREEVIDEO_PUBLIC_HOST:-$DASHED_IP.sslip.io}"

cat >"$CADDY_FILE" <<EOF
$PUBLIC_HOST {
  encode zstd gzip
  reverse_proxy 127.0.0.1:$WORKER_PORT
}
EOF

caddy validate --config "$CADDY_FILE"
systemctl enable --now caddy
systemctl restart caddy

# Verify the private worker first. Public TLS issuance can take a few seconds.
curl -fsS \
  -H "Authorization: Bearer $FREEVIDEO_API_TOKEN" \
  "http://127.0.0.1:$WORKER_PORT/health" >/tmp/freevideo-health.json

cat >/root/freevideo-worker-connection.txt <<EOF
FREEVIDEO_MODE=remote
FREEVIDEO_BASE_URL=https://$PUBLIC_HOST
FREEVIDEO_API_TOKEN=$FREEVIDEO_API_TOKEN
FREEVIDEO_TIMEOUT_SECONDS=${FREEVIDEO_TIMEOUT_SECONDS:-3600}
EOF
chmod 600 /root/freevideo-worker-connection.txt

cat <<EOF

FreeVideo GPU worker bootstrap completed.
HTTPS endpoint: https://$PUBLIC_HOST
Health check (authenticated):
  curl -H 'Authorization: Bearer <token>' https://$PUBLIC_HOST/health

Render connection values are stored root-only at:
  /root/freevideo-worker-connection.txt

Service status:
  systemctl status mpt-freevideo-worker --no-pager
  systemctl status caddy --no-pager
EOF
