# DocIntel AI

AI-assisted document editor with version control, built as a dissertation research
prototype. Users write in a rich-text editor, save meaningful versions, get
AI-powered rewriting/summarization assistance, and researchers can analyze
writing behavior and collect evaluation feedback.

## Tech Stack

- **Frontend**: Angular 22 (standalone components, signals), Angular Material,
  TipTap (rich text editor), Chart.js / ng2-charts, Firebase Auth (client SDK).
- **Backend**: FastAPI (Python 3.13), Firebase Admin SDK (Auth verification +
  Firestore), pluggable AI provider layer (OpenAI-compatible API or local Ollama).
- **Data**: Cloud Firestore (all access goes through the backend; see
  `firebase/firestore.rules` — direct client access is disabled).

## Project Structure

```
dissertation/
├── backend/                 FastAPI application
│   ├── app/
│   │   ├── api/              Routers + shared dependencies (auth, etc.)
│   │   ├── config/           Environment-driven settings
│   │   ├── firebase/         Firebase Admin SDK wiring (Auth + Firestore)
│   │   ├── models/           Internal domain models (Firestore documents)
│   │   ├── repositories/     Firestore data access
│   │   ├── schemas/          API request/response contracts
│   │   └── main.py           App entrypoint
│   ├── tests/                Pytest suite (mocks Firebase, no live services)
│   ├── requirements.txt
│   ├── run.sh                Launcher script (macOS/Linux)
│   ├── run.bat               Launcher script (Windows)
│   └── .env.example
├── frontend/                 Angular application
│   └── src/app/
│       ├── core/              Auth service, guards, HTTP interceptor, models
│       ├── auth/               Login / register pages
│       ├── dashboard/          Authenticated landing page
│       ├── documents/          Document editor + lazy-loaded routes
│       └── shared/             Shared components (confirm dialog, pipes)
├── firebase/                 Firestore security rules + indexes
├── docker-compose.yml         Optional local Ollama container
└── .env.example                Root environment reference
```

## Current Status — Phase 5 Complete

Project scaffolding, Firebase Authentication (email/password), Firestore
connectivity, protected routing, and a basic dashboard shell are implemented
(Phase 1). Phase 2 adds full document CRUD with a TipTap rich-text editor,
autosave, and a real document grid on the dashboard. Phase 3 adds explicit
version snapshots, version history in the editor, and a character-level diff
viewer. Phase 4 adds an AI assistant panel in the editor with rewrite,
summarize, improve, expand, and condense actions backed by a pluggable
OpenAI-compatible or Ollama provider. Phase 5 adds writing analytics on the
dashboard, per-document stats, readability evaluation, and Markdown/HTML/text
export from the editor. All backend endpoints and frontend routes are
implemented and the test suites are passing.

**Planned next phases**: further dissertation data collection workflows and
refinements based on user feedback.

## Prerequisites

- Node.js 20+ and npm
- Python 3.11+
- A Firebase project with **Authentication** (Email/Password provider) and
  **Firestore Database** (Native mode) enabled
- (Optional, for local AI) [Ollama](https://ollama.com) installed natively, or
  use the bundled `docker-compose.yml` service

## Quick Start (TL;DR)

**One-time Firebase setup** (see [Firebase Console One-Time Setup](#firebase-console-one-time-setup) below):
1. Create a Firebase project with Email/Password auth + Firestore (Native mode).
2. Download the service account key → save as `backend/serviceAccountKey.json`.
3. Copy the Web app config into `frontend/src/environments/environment.development.ts`.

**Backend** (macOS / Linux):
```bash
cd backend
cp .env.example .env          # edit values (FIREBASE_PROJECT_ID, AI settings)
./run.sh                      # creates venv, installs deps, runs tests, starts server
```

**Backend** (Windows):
```cmd
cd backend
copy .env.example .env        REM edit values
run.bat                       REM creates venv, installs deps, runs tests, starts server
```

**Frontend**:
```bash
cd frontend
npm install
npm start                     # opens http://localhost:4200
```

**(Optional) Local AI with Ollama**:
```bash
ollama pull llama3.1          # or any model you prefer
ollama serve                  # starts on http://localhost:11434
```

> Set `OLLAMA_MODEL` in `backend/.env` to match the model you pulled.

---

## Backend Setup (Detailed)

### 1. Create virtual environment & install dependencies

```bash
cd backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt      # macOS/Linux
# venv\Scripts\pip install -r requirements.txt  # Windows
```

### 2. Configure environment

```bash
cp .env.example .env   # then edit values as needed
```

Key settings in `.env`:

| Variable | Required | Description |
|---|---|---|
| `FIREBASE_PROJECT_ID` | Yes | Your Firebase project ID (e.g. `intellidoc-187c8`) |
| `FIREBASE_SERVICE_ACCOUNT_PATH` | Yes | Path to service account JSON (default: `serviceAccountKey.json`) |
| `AI_PROVIDER` | No | `ollama` (default) or `openai` |
| `OLLAMA_BASE_URL` | If using Ollama | Default: `http://localhost:11434` |
| `OLLAMA_MODEL` | If using Ollama | Model name (e.g. `llama3.1`, `gpt-oss:latest`) |
| `OPENAI_API_KEY` | If using OpenAI | API key for OpenAI-compatible endpoint |
| `OPENAI_BASE_URL` | If using OpenAI | Default: `https://api.openai.com/v1` |
| `OPENAI_MODEL` | If using OpenAI | Default: `gpt-4o-mini` |
| `CORS_ORIGINS` | No | Comma-separated allowed origins (default: `http://localhost:4200`) |

### 3. Add Firebase service account key

Download your Firebase project's **Admin SDK service account key** (Firebase
Console → Project Settings → Service Accounts → Generate new private key),
save it as `backend/serviceAccountKey.json` (gitignored — never commit it).

### 4. Run the API

**Option A — Using the launcher script** (recommended):

```bash
./run.sh                      # macOS/Linux
# run.bat                      # Windows
```

The script will:
1. Create a Python virtual environment (if not present)
2. Install all dependencies from `requirements.txt`
3. Run the test suite (skip with `SKIP_TESTS=1`)
4. Start the FastAPI server with hot-reload

**Option B — Manual commands**:

```bash
./venv/bin/uvicorn app.main:app --reload --port 8000      # macOS/Linux
# venv\Scripts\uvicorn app.main:app --reload --port 8000   # Windows
```

- Health check: `GET http://localhost:8000/health`
- Interactive API docs: `http://localhost:8000/docs`

### 5. Run tests

```bash
./venv/bin/python -m pytest -v      # macOS/Linux
# venv\Scripts\python -m pytest -v   # Windows
```

---

## Frontend Setup (Detailed)

```bash
cd frontend
npm install
```

Firebase **Web app** config lives in `src/environments/environment.ts` and
`environment.development.ts`. Get these values from Firebase Console →
Project Settings → General → Your apps → Web app → SDK setup and
configuration:

```ts
firebase: {
  apiKey: '...',
  authDomain: '...',
  projectId: '...',
  storageBucket: '...',
  messagingSenderId: '...',
  appId: '...',
}
```

These are safe to commit (they identify the project publicly; access is
governed by Firebase security rules and backend authorization, not secrecy).

Run the dev server:

```bash
npm start
```

Open `http://localhost:4200`.

Run unit tests:

```bash
npm test
```

## Firebase Console One-Time Setup

1. **Authentication** → Sign-in method → enable **Email/Password**.
2. **Firestore Database** → Create database → Native mode → pick a region.
3. **Project Settings** → General → Add a **Web app** if none exists, copy
   the `firebaseConfig` values into the frontend environment files above.
4. **Project Settings** → Service Accounts → Generate a new private key for
   the backend (`backend/serviceAccountKey.json`).

(Optional) Deploy the included Firestore rules (locks the database to
backend-only access) with the Firebase CLI:

```bash
firebase deploy --only firestore:rules,firestore:indexes
```

## AI Provider Configuration

Set in `backend/.env`:

- `AI_PROVIDER=ollama` (default) — uses `OLLAMA_BASE_URL` / `OLLAMA_MODEL`.
  Run Ollama natively or via `docker compose up -d`.
- `AI_PROVIDER=openai` — uses `OPENAI_API_KEY` / `OPENAI_BASE_URL` /
  `OPENAI_MODEL` (any OpenAI-compatible endpoint works).

## Security Notes

- `backend/serviceAccountKey.json` and `backend/.env` are gitignored — never commit them.
- The Angular app never talks to Firestore directly; it only uses Firebase
  for Authentication. All application data flows through the FastAPI
  backend, which verifies the Firebase ID token on every request.
