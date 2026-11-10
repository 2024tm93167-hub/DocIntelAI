#!/usr/bin/env bash
# One-time EC2 setup for DocIntel AI. Run as the ubuntu user on a fresh
# Ubuntu 22.04/24.04 instance AFTER cloning the repo to /home/ubuntu/docintel.
#
#   git clone https://github.com/2024tm93167-hub/DocIntelAI.git /home/ubuntu/docintel
#   bash /home/ubuntu/docintel/deploy/setup-server.sh
#
# Afterwards, manually create backend/.env and upload serviceAccountKey.json
# (both gitignored — see backend/.env.example for required variables).
set -euo pipefail

cd /home/ubuntu/docintel

echo "==> Installing system packages"
sudo apt-get update
sudo apt-get install -y nginx python3 python3-venv python3-pip git curl

echo "==> Installing Node.js 22 (required by Angular 22)"
if ! command -v node >/dev/null || [[ "$(node -v | cut -d. -f1 | tr -d v)" -lt 20 ]]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi

echo "==> Python backend venv + dependencies"
cd /home/ubuntu/docintel/backend
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "==> Checking backend env files"
if [[ ! -f .env ]]; then
  echo "WARNING: backend/.env missing — copy backend/.env.example and fill in values"
fi
if [[ ! -f serviceAccountKey.json ]]; then
  echo "WARNING: serviceAccountKey.json missing — upload it to backend/ before the backend can start"
fi

echo "==> Installing systemd service"
sudo cp /home/ubuntu/docintel/deploy/docintel-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable docintel-backend

echo "==> Installing nginx site"
sudo cp /home/ubuntu/docintel/deploy/nginx-docintel.conf /etc/nginx/sites-available/docintel
sudo ln -sf /etc/nginx/sites-available/docintel /etc/nginx/sites-enabled/docintel
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

echo "==> Building frontend"
cd /home/ubuntu/docintel/frontend
npm ci
npm run build

echo "==> Starting backend"
sudo systemctl restart docintel-backend
sleep 3
systemctl is-active docintel-backend || true

echo ""
echo "Done. Verify with:"
echo "  curl http://127.0.0.1:8000/health"
echo "  curl http://127.0.0.1/api/health"
echo ""
echo "Remaining manual steps:"
echo "  1. Fill in backend/.env (see backend/.env.example) and place serviceAccountKey.json in backend/"
echo "  2. sudo systemctl restart docintel-backend"
echo "  3. Add GitHub secrets AWS_HOST, AWS_USER, AWS_SSH_KEY to the repo"
echo "  4. For HTTPS + Firebase Auth: point a domain at this IP, run 'sudo certbot --nginx',"
echo "     and add the domain to Firebase Console > Authentication > Settings > Authorized domains"
