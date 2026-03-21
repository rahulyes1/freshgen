#!/bin/bash
# ============================================================
# deploy.sh — Fresh Gen one-shot server setup on Oracle Cloud Ubuntu 22.04
# Run once as ubuntu user after SSH-ing into your instance:
#   bash deploy.sh
# ============================================================
set -e

PROJECT_DIR="/home/ubuntu/fresh-gen"
VENV="$PROJECT_DIR/venv"
SERVICE_API="fresh-gen-api"
SERVICE_DASH="fresh-gen-dashboard"

echo "=========================================="
echo "  Fresh Gen — Oracle Cloud Deployment"
echo "=========================================="

# ── 1. System packages ─────────────────────────────────────────
echo "[1/8] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3.11 python3.11-venv python3-pip \
    git curl unzip \
    # Playwright / Chromium system deps
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 libpangocairo-1.0-0 \
    libxshmfence1 libx11-xcb1 libxcb-dri3-0 fonts-liberation \
    xdg-utils wget ca-certificates

# ── 2. Node.js 20 ─────────────────────────────────────────────
echo "[2/8] Installing Node.js 20..."
if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi
echo "  Node $(node -v) | npm $(npm -v)"

# ── 3. Python virtualenv + dependencies ───────────────────────
echo "[3/8] Setting up Python venv..."
python3.11 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip -q
"$VENV/bin/pip" install -r "$PROJECT_DIR/api/requirements.txt" -q
echo "  Python deps installed."

# ── 4. Playwright Chromium ────────────────────────────────────
echo "[4/8] Installing Playwright Chromium..."
"$VENV/bin/playwright" install chromium
echo "  Chromium installed."

# ── 5. Next.js dashboard build ────────────────────────────────
echo "[5/8] Building Next.js dashboard..."
cd "$PROJECT_DIR/dashboard"
npm install --silent
# Set API URL to same server (loopback — both services on same box)
echo "NEXT_PUBLIC_API_URL=http://$(curl -s ifconfig.me):8000" > .env.local
npm run build
echo "  Dashboard built."
cd "$PROJECT_DIR"

# ── 6. Create data directory + log directory ──────────────────
echo "[6/8] Creating directories..."
mkdir -p "$PROJECT_DIR/data"
sudo mkdir -p /var/log/fresh-gen
sudo chown ubuntu:ubuntu /var/log/fresh-gen

# ── 7. Systemd services ────────────────────────────────────────
echo "[7/8] Installing systemd services..."

sudo tee /etc/systemd/system/$SERVICE_API.service > /dev/null <<EOF
[Unit]
Description=Fresh Gen — FastAPI Backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$VENV/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 1
Restart=always
RestartSec=10
StandardOutput=append:/var/log/fresh-gen/api.log
StandardError=append:/var/log/fresh-gen/api.log

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/$SERVICE_DASH.service > /dev/null <<EOF
[Unit]
Description=Fresh Gen — Next.js Dashboard
After=network.target $SERVICE_API.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$PROJECT_DIR/dashboard
Environment=PORT=3000
Environment=NODE_ENV=production
ExecStart=/usr/bin/npm start
Restart=always
RestartSec=10
StandardOutput=append:/var/log/fresh-gen/dashboard.log
StandardError=append:/var/log/fresh-gen/dashboard.log

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_API
sudo systemctl enable $SERVICE_DASH

# ── 8. Firewall — Oracle uses iptables (UFW is disabled by default) ──
echo "[8/8] Opening ports 8000 and 3000 in iptables..."
# Oracle Cloud blocks all ports at OS level even if you open them in Security List
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT
sudo iptables -I INPUT 7 -m state --state NEW -p tcp --dport 3000 -j ACCEPT
# Persist across reboots
sudo apt-get install -y -qq netfilter-persistent iptables-persistent
sudo netfilter-persistent save

# ── Start services ─────────────────────────────────────────────
echo ""
echo "Starting services..."
sudo systemctl start $SERVICE_API
sleep 3
sudo systemctl start $SERVICE_DASH

echo ""
echo "=========================================="
echo "  Deployment complete!"
SERVER_IP=$(curl -s ifconfig.me)
echo "  API:       http://$SERVER_IP:8000"
echo "  Docs:      http://$SERVER_IP:8000/docs"
echo "  Dashboard: http://$SERVER_IP:3000"
echo ""
echo "  Logs:"
echo "    sudo journalctl -u $SERVICE_API -f"
echo "    sudo journalctl -u $SERVICE_DASH -f"
echo "=========================================="
