# CAOS Care Build Status

## Status

This document records the first runnable/deployment-prep status for `caosos/CAOSCARE.COM`.

No production deployment was performed while creating this document. No server or Linode action was taken.

CAOS Care remains an assistive, advisory, human-supervised, receipt-backed care platform. This build status does not make medical-device, clinical-authority, autonomous emergency-dispatch, or compliance-guarantee claims.

## Repository role

This repository is a mixed CAOS Care product/build surface with:

- React/CRA/CRACO frontend surfaces
- FastAPI backend surfaces
- MongoDB-backed domain storage
- Android bridge, companion, and vision surfaces for later device work
- product, memory, and governance documentation

## Frontend

### Framework

- React
- Create React App
- CRACO
- Tailwind/shadcn-style component surface

### Package manager

Declared package manager:

```bash
yarn@1.22.22
```

Current blocker: no committed `yarn.lock`, `package-lock.json`, or `pnpm-lock.yaml` was present during audit. First-run installs are therefore not fully reproducible until Michael approves a package-manager lockfile write.

### Environment

Template:

```text
frontend/.env.example
```

Required:

```text
REACT_APP_BACKEND_URL=http://localhost:8000
```

Optional local-development setting:

```text
ENABLE_HEALTH_CHECK=false
```

### Install

```bash
cd frontend
corepack enable
yarn install
```

If Yarn is not available on the target host, use an explicitly approved npm fallback and commit the resulting lockfile in a separate task.

### Development

```bash
cd frontend
REACT_APP_BACKEND_URL=http://localhost:8000 yarn start
```

### Build

```bash
cd frontend
REACT_APP_BACKEND_URL=https://caoscare.com yarn build
```

Build output:

```text
frontend/build/
```

### Test

```bash
cd frontend
yarn test
```

### Frontend blockers / pending decisions

- Add or approve a package lockfile for reproducible deployment builds.
- Decide whether to keep or remove Emergent visual-edit development tooling in a separate task.
- Decide whether to replace Emergent-hosted Google auth before production use.
- Verify the public deployed frontend after a future deployment; do not infer live website state from repo files.

## Backend

### Framework

- FastAPI
- Uvicorn
- Motor/PyMongo
- Pydantic
- MongoDB

### Entrypoint

```text
backend/server.py
```

FastAPI app import target:

```text
server:app
```

### Environment

Template:

```text
backend/.env.example
```

Required for backend startup:

```text
MONGO_URL=mongodb://localhost:27017
DB_NAME=caoscare
JWT_SECRET=replace-with-long-random-secret
```

Optional values documented in `backend/.env.example` include CORS, public API URL, OpenAI models/voice, Perplexity, Twilio, Resend, facility defaults, device auth, receipt signing settings, and `CAOSCARE_ENABLE_DEMO_SEED=false`. Backend AI, realtime, and research routes no longer require an Emergent key for import/startup. If `OPENAI_API_KEY` or `PERPLEXITY_API_KEY` is absent for an endpoint that needs it, that endpoint should return HTTP 503 instead of crashing app import.

Demo seed is disabled by default. Known demo credentials must not be enabled in production. Local/demo environments may opt in with `CAOSCARE_ENABLE_DEMO_SEED=true`, but first real admin/user creation remains a pending decision until an owned bootstrap flow exists.

### Install

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Development / first local run

```bash
cd backend
source .venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

### First server run target

```bash
cd /opt/caoscare/app/backend
source /opt/caoscare/venv/backend/bin/activate
uvicorn server:app --host 127.0.0.1 --port 8000
```

### Health check

```bash
curl -fsS http://127.0.0.1:8000/api/health
```

Expected healthy shape:

```json
{"ok": true, "db": "up"}
```

### Backend blockers / pending decisions

- MongoDB must exist and be reachable before `/api/health` can pass.
- `MONGO_URL`, `DB_NAME`, and `JWT_SECRET` are still required for import/startup in the current code.
- Backend AI/realtime/research boot no longer depends on Emergent runtime imports or `EMERGENT_LLM_KEY`.
- Realtime full-duplex voice remains planned OpenAI Realtime / `gpt-realtime` work until the browser flow is validated end-to-end; missing OpenAI configuration returns HTTP 503.
- Emergent Google auth remains in place by design for this small backend-only task.
- Startup demo seed behavior is guarded by `CAOSCARE_ENABLE_DEMO_SEED=false` by default; production/server boot must not create known demo users/passwords unless explicitly and temporarily enabled outside production.
- First real admin/user creation remains a pending decision until an owned bootstrap flow exists.
- Twilio/Resend can remain unset for log-only notification behavior during first run.

## Android / device surfaces

Android/device work is not required for the first server-only deployment path.

### android-bridge

Status: later device work.

Purpose: Android RF bridge surface that posts pendant events to the backend.

Pending:

- Confirm Gradle wrapper strategy or Android Studio build path.
- Validate USB/RF receiver behavior with real hardware.
- Configure device token/HMAC policy before field use.

### android-companion

Status: later device work.

Purpose: native Android companion/kiosk hub surface.

Pending:

- Native `rtl_433` decode remains a stub until source is vendored and CMake is wired.
- Release signing and sideload/update channel decisions remain open.

### android-vision

Status: later device work.

Purpose: Android vision/voice assistance surface for smart glasses or Android camera devices.

Pending:

- Confirm build wrapper/Android Studio workflow.
- Confirm privacy and resident consent workflow before field camera use.
- Backend vision routes currently depend on the configured LLM path.

## Verification status

Verified in repository:

- Frontend package scripts exist.
- Backend entrypoint and health route exist.
- Required environment variables were identified from source references.
- Android docs and build files exist as repo-visible surfaces.
- Deployment/runbook docs now define a first non-Docker target path.

Pending runtime verification:

- Fresh frontend install/build/test on a deployment-like host.
- Backend import/start with real placeholder-replaced env values.
- MongoDB connection and `/api/health` success.
- Reverse proxy configuration and TLS.
- Live CAOSCARE.COM crawl after deployment.
- Android builds and physical-device validation.
