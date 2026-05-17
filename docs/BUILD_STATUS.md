# CAOS Care Build Status

## Status

This document records the first runnable/deployment-prep status for `caosos/CAOSCARE.COM`.

No production deployment was performed while creating this document. No server or Linode action was taken.

CAOS Care remains an assistive, advisory, human-supervised, receipt-backed care platform. This build status does not make medical-device, clinical-authority, autonomous emergency-dispatch, or compliance-guarantee claims.

## Current verified status after PR #7 through PR #11

- PR #7 removed public Emergent branding from `frontend/public/index.html`; live website content still requires direct deployment verification.
- PR #8 added a frontend API URL guard: `REACT_APP_BACKEND_URL` must be present, non-blank, and set to the backend origin without a trailing `/api`; invalid values now fail loudly instead of silently constructing a bad API client.
- PR #9 removed Emergent visual-edit tooling from the frontend package/config surface.
- PR #10 added `backend/scripts/bootstrap_owner.py` for one-time owner creation and locked public `/auth/register` to create staff users only.
- PR #11 cleaned public UI copy so it no longer hardcodes Claude, Sonnet, or Haiku provider claims in public care-domain messaging.
- The frontend lockfile is still missing; no committed `yarn.lock`, `package-lock.json`, or `pnpm-lock.yaml` is present.
- Emergent Google auth still remains as legacy/pending replacement behavior; owned OAuth / direct Google OAuth is not implemented yet.
- Server deployment is not done; this repo state is deployment-prep only and still needs first-server validation.

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

Current guard behavior: the frontend now fails loudly when `REACT_APP_BACKEND_URL` is missing, blank, or ends with `/api`. Set it to the backend origin only, such as `http://localhost:8000` for local development or `https://caoscare.com` for a same-origin first server path.

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

- Add or approve a package lockfile for reproducible deployment builds; `yarn.lock` is still missing.
- Emergent visual-edit tooling has been removed from the frontend package/config surface; confirm deployment builds on the target host because no lockfile is committed.
- Decide whether to replace Emergent Google auth with owned/direct Google OAuth before production use.
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

Demo seed is disabled by default. Known demo credentials must not be enabled in production. Local/demo environments may opt in with `CAOSCARE_ENABLE_DEMO_SEED=true`. First real owner creation now has a manual one-time bootstrap path through `backend/scripts/bootstrap_owner.py` using `CAOSCARE_BOOTSTRAP_OWNER_EMAIL`, `CAOSCARE_BOOTSTRAP_OWNER_NAME`, and `CAOSCARE_BOOTSTRAP_OWNER_PASSWORD` after backend env is configured and MongoDB is reachable.

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
- Emergent Google auth remains in place as legacy/pending replacement behavior until owned OAuth / direct Google OAuth is implemented.
- Startup demo seed behavior is guarded by `CAOSCARE_ENABLE_DEMO_SEED=false` by default; production/server boot must not create known demo users/passwords unless explicitly and temporarily enabled outside production.
- Public `/auth/register` is staff-only; owner/admin creation must use the owner bootstrap path or an owner/admin-managed staff workflow.
- Owner bootstrap is one-time/manual: set `CAOSCARE_BOOTSTRAP_OWNER_EMAIL`, `CAOSCARE_BOOTSTRAP_OWNER_NAME`, and `CAOSCARE_BOOTSTRAP_OWNER_PASSWORD` only while running `backend/scripts/bootstrap_owner.py`, then unset/remove the bootstrap password env after owner creation.
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
- Frontend API URL fail-loud guard exists for `REACT_APP_BACKEND_URL`.
- Public Emergent branding and Emergent visual-edit tooling have been removed from the verified repo surface.
- Backend entrypoint, health route, staff-only public registration, and `backend/scripts/bootstrap_owner.py` exist.
- Required environment variables were identified from source references, including `MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `CAOSCARE_ENABLE_DEMO_SEED`, and one-time `CAOSCARE_BOOTSTRAP_OWNER_*` values.
- Android docs and build files exist as repo-visible surfaces.
- Deployment/runbook docs now define a first non-Docker target path.

Pending runtime verification:

- Fresh frontend install/build/test on a deployment-like host; frontend lockfile / `yarn.lock` is still missing.
- Backend import/start with real placeholder-replaced env values.
- MongoDB connection and `/api/health` success.
- One-time owner bootstrap, bootstrap password removal, and admin/JWT login validation.
- Reverse proxy configuration and TLS.
- Live CAOSCARE.COM crawl after deployment.
- Emergent Google auth replacement with owned OAuth / direct Google OAuth.
- Android builds and physical-device validation.

Remaining blockers before/after first server deployment:

- Emergent Google auth remains legacy/pending owned OAuth replacement.
- Owned/direct Google OAuth is not implemented.
- Frontend lockfile is missing, so frontend installs are not reproducible yet.
- Server deployment is not done and must still validate MongoDB connectivity, backend health, owner bootstrap, JWT/admin login, frontend build, reverse proxy, and live website behavior.
