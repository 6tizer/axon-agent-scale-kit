#!/usr/bin/env bash
# deploy.sh — build the frontend and (re)start the backend on the server.
#
# Run this script on the SERVER after pulling the latest code:
#   cd /home/ubuntu/axon-agent-scale
#   bash web/deploy.sh
#
# Prerequisites on the server:
#   - Node.js >= 18 (for Next.js build)
#   - Python >= 3.10 (for FastAPI backend)
#   - nginx installed and configured (see web/nginx/axon-dashboard.conf)
#   - axon-dashboard.service installed (see web/systemd/axon-dashboard.service)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="$REPO_ROOT/web"
FRONTEND_DIR="$WEB_DIR/frontend"
BACKEND_DIR="$WEB_DIR/backend"
# Keep the venv at a path reachable via `current` so the systemd unit finds it
# after each release deploy.
VENV_DIR="$WEB_DIR/.venv"

echo "=== Axon Dashboard Deploy ==="
echo "Repo root: $REPO_ROOT"
echo ""

# ── 1. Python venv + backend deps ──────────────────────────────────────────────
echo "[1/4] Setting up Python venv and installing backend dependencies..."
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$BACKEND_DIR/requirements.txt"
echo "      Backend dependencies installed."

# ── 2. Node.js deps + Next.js build ────────────────────────────────────────────
echo "[2/4] Installing frontend npm dependencies..."
cd "$FRONTEND_DIR"
npm install --silent

echo "[3/4] Building Next.js static export..."
npm run build
echo "      Build complete. Static files at: $FRONTEND_DIR/out"

# ── 3. (Re)start the backend service ───────────────────────────────────────────
echo "[4/4] Restarting axon-dashboard.service..."
if systemctl is-enabled axon-dashboard.service &>/dev/null; then
  sudo systemctl restart axon-dashboard.service
  sleep 1
  STATUS=$(systemctl is-active axon-dashboard.service || true)
  echo "      Service status: $STATUS"
else
  echo ""
  echo "  NOTE: axon-dashboard.service is not enabled yet."
  echo "  To install it:"
  echo "    sudo cp $WEB_DIR/systemd/axon-dashboard.service /etc/systemd/system/"
  echo "    # Edit /etc/systemd/system/axon-dashboard.service and set AXON_API_TOKEN"
  echo "    sudo systemctl daemon-reload"
  echo "    sudo systemctl enable axon-dashboard.service"
  echo "    sudo systemctl start axon-dashboard.service"
fi

# ── 4. Reload nginx ─────────────────────────────────────────────────────────────
if systemctl is-active nginx &>/dev/null; then
  echo ""
  echo "Reloading nginx..."
  sudo nginx -t && sudo systemctl reload nginx
  echo "nginx reloaded."
else
  echo ""
  echo "  NOTE: nginx is not running."
  echo "  To configure nginx:"
  echo "    sudo cp $WEB_DIR/nginx/axon-dashboard.conf /etc/nginx/sites-available/"
  echo "    sudo ln -s /etc/nginx/sites-available/axon-dashboard.conf /etc/nginx/sites-enabled/"
  echo "    sudo nginx -t && sudo systemctl enable --now nginx"
fi

echo ""
echo "=== Deploy complete ==="
echo ""
echo "Dashboard should be accessible at: http://$(hostname -I | awk '{print $1}')"
echo "Or via your Cloudflare Tunnel URL."
echo ""
echo "Sudoers note: to allow daemon restarts from the UI without a password, add:"
echo "  ubuntu ALL=(ALL) NOPASSWD: /bin/systemctl restart axon-heartbeat-daemon.service"
echo "  ubuntu ALL=(ALL) NOPASSWD: /bin/systemctl restart axon-challenge-daemon.service"
echo "  ubuntu ALL=(ALL) NOPASSWD: /bin/systemctl restart axon-dashboard.service"
echo "  ubuntu ALL=(ALL) NOPASSWD: /usr/sbin/nginx"
echo "to /etc/sudoers.d/axon-dashboard"
