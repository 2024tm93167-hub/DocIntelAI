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
│   └── .env.example
├── frontend/                 Angular application
│   └── src/app/
│       ├── core/              Auth service, guards, HTTP interceptor, models
│       ├── auth/               Login / register pages
│       └── dashboard/          Authenticated landing page
├── firebase/                 Firestore security rules + indexes
├── docker-compose.yml         Optional local Ollama container
└── .env.example                Root environment reference
```

## Current Status — Phase 1 Complete

Project scaffolding, Firebase Authentication (email/password), Firestore
connectivity, protected routing, and a basic dashboard shell are implemented
and verified end-to-end.

**Planned next phases**: (2) document CRUD + TipTap editor, (3) version
history + diffing, (4) AI-assisted rewriting/summarization, (5) writing
analytics + evaluation/export tooling.

## Prerequisites

- Node.js 20+ and npm
- Python 3.11+
- A Firebase project with **Authentication** (Email/Password provider) and
  **Firestore Database** (Native mode) enabled
- (Optional, for local AI) [Ollama](https://ollama.com) installed natively, or
  use the bundled `docker-compose.yml` service

## Backend Setup

```bash
cd backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env   # then edit values as needed
```

Download your Firebase project's **Admin SDK service account key** (Firebase
Console → Project Settings → Service Accounts → Generate new private key),
save it as `backend/serviceAccountKey.json` (gitignored — never commit it).

Run the API:

```bash
./venv/bin/uvicorn app.main:app --reload --port 8000
```

- Health check: `GET http://localhost:8000/health`
- Interactive docs: `http://localhost:8000/docs`

Run tests:

```bash
./venv/bin/python -m pytest -v
```

## Frontend Setup

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
