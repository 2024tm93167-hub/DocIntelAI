@echo off
REM ────────────────────────────────────────────────────────────────────────────
REM DocIntel AI - Backend launcher (Windows)
REM
REM Prerequisites:
REM   * Python 3.11+ installed and on PATH
REM   * Firebase service account key saved as backend\serviceAccountKey.json
REM   * backend\.env configured (copy .env.example -> .env and fill in values)
REM
REM Usage:
REM   run.bat          REM starts the FastAPI server on http://localhost:8000
REM ────────────────────────────────────────────────────────────────────────────
cd /d "%~dp0"

REM -- 1. Create virtual environment (first run only) -------------------------
if not exist "venv" (
    echo [1/5] Creating Python virtual environment...
    python -m venv venv
)

REM -- 2. Install / refresh dependencies ---------------------------------------
echo [2/5] Installing dependencies...
venv\Scripts\pip install --quiet --upgrade pip
venv\Scripts\pip install --quiet -r requirements.txt

REM -- 3. Sanity checks --------------------------------------------------------
if not exist ".env" (
    echo [3/5] WARNING: No .env file found. Copying from .env.example.
    echo       Edit it before using AI features.
    copy .env.example .env >nul
)

if not exist "serviceAccountKey.json" (
    echo [3/5] WARNING: serviceAccountKey.json not found!
    echo        Download it from Firebase Console -^> Project Settings -^>
    echo        Service Accounts -^> Generate new private key,
    echo        and save as backend\serviceAccountKey.json
)

REM -- 4. Run tests (optional, set SKIP_TESTS=1 to skip) ----------------------
if not "%SKIP_TESTS%"=="1" (
    echo [4/5] Running tests...
    venv\Scripts\python -m pytest -v
)

REM -- 5. Start the server -----------------------------------------------------
echo [5/5] Starting FastAPI server on http://localhost:8000
echo        Docs:  http://localhost:8000/docs
echo        Press Ctrl+C to stop.
venv\Scripts\uvicorn app.main:app --reload --port 8000
