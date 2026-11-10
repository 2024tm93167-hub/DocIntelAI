#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# DocIntel AI – Backend launcher (macOS / Linux)
#
# Prerequisites:
#   • Python 3.11+ installed
#   • Firebase service account key saved as backend/serviceAccountKey.json
#   • backend/.env configured (copy .env.example → .env and fill in values)
#
# Usage:
#   chmod +x run.sh   # only needed once
#   ./run.sh          # starts the FastAPI server on http://localhost:8000
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")"

# ── 1. Create virtual environment (first run only) ───────────────────────────
if [ ! -d "venv" ]; then
  echo "▶ Creating Python virtual environment…"
  python3 -m venv venv
fi

# ── 2. Install / refresh dependencies ────────────────────────────────────────
echo "▶ Installing dependencies…"
./venv/bin/pip install --quiet --upgrade pip
./venv/bin/pip install --quiet -r requirements.txt

# ── 3. Sanity checks ─────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  echo "⚠  No .env file found. Copying from .env.example — edit it before using AI features."
  cp .env.example .env
fi

if [ ! -f "serviceAccountKey.json" ]; then
  echo "⚠  serviceAccountKey.json not found!"
  echo "   Download it from Firebase Console → Project Settings → Service Accounts →"
  echo "   Generate new private key, and save as backend/serviceAccountKey.json"
fi

# ── 4. Run tests (optional, set SKIP_TESTS=1 to skip) ────────────────────────
if [ "${SKIP_TESTS:-0}" != "1" ]; then
  echo "▶ Running tests…"
  ./venv/bin/python -m pytest -v
fi

# ── 5. Start the server ──────────────────────────────────────────────────────
echo "▶ Starting FastAPI server on http://localhost:8000"
echo "   Docs:  http://localhost:8000/docs"
echo "   Press Ctrl+C to stop."
exec ./venv/bin/uvicorn app.main:app --reload --port 8000
