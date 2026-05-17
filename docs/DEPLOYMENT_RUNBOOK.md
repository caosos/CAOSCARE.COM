# CAOS Care Deployment Runbook

## Status

This runbook defines a first runnable Linode/server path for `caosos/CAOSCARE.COM`.

No production deployment was performed while creating this runbook. Do not treat this document as proof of a live deployed website.

CAOS Care must remain assistive, advisory, human-supervised, receipt-backed, privacy-aware, and operationally useful. Do not add clinical-authority, medical-device, autonomous emergency-dispatch, or compliance-guarantee claims without Michael's explicit approval and the required legal/regulatory basis.

## First server target

Recommended base directory:

```text
/opt/caoscare
```

Recommended layout:

```text
/opt/caoscare/
  app/                         # Git checkout of caosos/CAOSCARE.COM
    README.md
    AGENTS.md
    docs/
    backend/
    frontend/
    android-bridge/
    android-companion/
    android-vision/

  env/
    backend.env                 # Real backend secrets; never commit
    frontend-build.env          # Build-time frontend variables; never commit if secret-bearing

  venv/
    backend/                    # Python virtual environment for FastAPI

  logs/
    backend/
    proxy/

  runtime/
    pids/
    sockets/

  frontend-build/
    build/                      # Optional copied static frontend artifact

  scripts/                      # Optional future helper scripts
    healthcheck.sh
```

## First non-Docker deployment path

This is the current recommended first-run path because the repository does not yet include Dockerfile or compose definitions.

### 1. Prepare OS packages

Install these on the target server by Michael-approved server process:

```text
python3
python3-venv
python3-pip
nodejs
corepack or yarn
mongodb or network access to the selected MongoDB service
nginx or caddy
```

Do not store real secrets in the Git checkout.

### 2. Prepare backend environment

Use the template:

```text
backend/.env.example
```

Create the real file on the server only:

```text
/opt/caoscare/app/backend/.env
```

Minimum required values:

```text
MONGO_URL=mongodb://localhost:27017
DB_NAME=caoscare
JWT_SECRET=<server-generated-random-secret>
CAOSCARE_ENABLE_DEMO_SEED=false
```

First-server boot requirements:

- Set `MONGO_URL` to the selected MongoDB service and confirm MongoDB is reachable before backend health validation.
- Set `DB_NAME` to the intended CAOS Care database name.
- Set `JWT_SECRET` to a long server-generated random value; never commit or reuse a placeholder.
- Keep `CAOSCARE_ENABLE_DEMO_SEED=false` for production/server boot. Do not enable demo seed for production.
- Set `CAOSCARE_BOOTSTRAP_OWNER_EMAIL`, `CAOSCARE_BOOTSTRAP_OWNER_NAME`, and `CAOSCARE_BOOTSTRAP_OWNER_PASSWORD` only for the one-time owner bootstrap window.
- After owner creation, unset/remove the bootstrap password env and any temporary bootstrap values from the server environment.

Optional OpenAI/research values:

```text
OPENAI_API_KEY=<approved-openai-key-if-ai-routes-are-used>
OPENAI_TEXT_MODEL=gpt-4o-mini
OPENAI_REALTIME_MODEL=gpt-realtime
OPENAI_VOICE=sage
PERPLEXITY_API_KEY=<approved-perplexity-key-if-live-research-is-used>
```

Backend AI, realtime, and research routes no longer require an Emergent key for import/startup. Missing provider keys should make provider-specific endpoints return HTTP 503 instead of blocking app import.

`CAOSCARE_ENABLE_DEMO_SEED` must remain `false` for production/server boot. Setting it to `true` enables known local/demo seed users and passwords and is only acceptable for disposable local demos or preview environments. First real owner creation now uses the manual bootstrap script; public registration is staff-only.

Recommended public routing values for CAOSCARE.COM:

```text
CORS_ORIGINS=https://caoscare.com,https://www.caoscare.com
PUBLIC_API_URL=https://caoscare.com
```

### 3. Install backend dependencies

```bash
cd /opt/caoscare/app/backend
python3 -m venv /opt/caoscare/venv/backend
source /opt/caoscare/venv/backend/bin/activate
pip install -r requirements.txt
```

### 4. Run one-time owner bootstrap after backend env is configured

After backend env is configured and MongoDB is reachable, create the first owner manually from the backend directory:

```bash
cd /opt/caoscare/app/backend
source /opt/caoscare/venv/backend/bin/activate
export CAOSCARE_BOOTSTRAP_OWNER_EMAIL=owner@example.com
export CAOSCARE_BOOTSTRAP_OWNER_NAME="Facility Owner"
export CAOSCARE_BOOTSTRAP_OWNER_PASSWORD='<one-time-strong-password>'
python scripts/bootstrap_owner.py
unset CAOSCARE_BOOTSTRAP_OWNER_PASSWORD
unset CAOSCARE_BOOTSTRAP_OWNER_EMAIL
unset CAOSCARE_BOOTSTRAP_OWNER_NAME
```

The repo path for the script is `backend/scripts/bootstrap_owner.py`; the command above uses `scripts/bootstrap_owner.py` because it is run from `/opt/caoscare/app/backend`. The critical rule is that `backend/scripts/bootstrap_owner.py` must run only after the real backend env is loaded and MongoDB can be reached.

Do not leave `CAOSCARE_BOOTSTRAP_OWNER_PASSWORD` set after owner creation. Do not enable demo seed to create production users.

### 5. Start backend manually for first verification

```bash
cd /opt/caoscare/app/backend
source /opt/caoscare/venv/backend/bin/activate
uvicorn server:app --host 127.0.0.1 --port 8000
```

For a durable deployment, add a Michael-approved process manager later, such as systemd. Do not invent or install a service without explicit server approval.


### Realtime voice status

Backend import no longer depends on Emergent realtime helpers. The realtime route is OpenAI-only and should fail closed with HTTP 503 when `OPENAI_API_KEY` is missing. Full-duplex browser voice remains planned OpenAI Realtime / `gpt-realtime` work until a deployment-like WebRTC path is validated end-to-end.

### 6. Verify backend health and admin/JWT login

```bash
curl -fsS http://127.0.0.1:8000/api/health
```

Healthy target shape:

```json
{"ok": true, "db": "up"}
```

If MongoDB is unavailable, the endpoint may return an unhealthy database status and the deployment is not ready.

Use the bootstrapped owner account to validate admin/JWT login for first server validation. Google login remains legacy/Emergent-mediated until owned OAuth is implemented, so it must not be the first-server validation dependency.

### 7. Prepare frontend environment

Use the template:

```text
frontend/.env.example
```

For a CAOSCARE.COM build, set `REACT_APP_BACKEND_URL` to the backend origin without trailing `/api`:

```bash
cd /opt/caoscare/app/frontend
export REACT_APP_BACKEND_URL=https://caoscare.com
export ENABLE_HEALTH_CHECK=false
```

The frontend will fail loudly if `REACT_APP_BACKEND_URL` is missing, blank, or ends with `/api`. Do not set `REACT_APP_BACKEND_URL=https://caoscare.com/api`; the app adds `/api` at request time.

### 8. Install and build frontend

```bash
cd /opt/caoscare/app/frontend
corepack enable
yarn install
yarn build
```

Build artifact:

```text
/opt/caoscare/app/frontend/build/
```

Optional copy target:

```bash
mkdir -p /opt/caoscare/frontend-build
rsync -a --delete /opt/caoscare/app/frontend/build/ /opt/caoscare/frontend-build/build/
```

## Reverse proxy assumptions

The first server should use Nginx or Caddy to:

- terminate TLS for `caoscare.com` and optionally `www.caoscare.com`
- serve the React static build
- proxy `/api/` to `http://127.0.0.1:8000/api/`
- preserve `X-Forwarded-Host` and `X-Forwarded-Proto` headers for backend install-info links
- use a client-side routing fallback to `index.html` for non-API frontend routes

Example behavior, not a server-ready secret-bearing config:

```text
https://caoscare.com/        -> static frontend build
https://caoscare.com/staff   -> static frontend build fallback
https://caoscare.com/api/*   -> FastAPI on 127.0.0.1:8000
```

Do not commit server certificates, API keys, private keys, or real environment files.

## Docker / compose status

Docker and compose are not implemented in this repository yet.

Classification:

```text
Dockerfile: missing
compose: missing
```

A future Docker task may add:

- backend Dockerfile
- frontend build/static image or static artifact path
- compose file with backend, MongoDB, and reverse proxy
- healthchecks
- named volumes

Do not create Docker assets until Michael approves Docker as the target deployment model.

## Healthcheck commands

Backend local health:

```bash
curl -fsS http://127.0.0.1:8000/api/health
```

Public health after reverse proxy is configured:

```bash
curl -fsS https://caoscare.com/api/health
```

Frontend static smoke after reverse proxy is configured:

```bash
curl -fsS https://caoscare.com/ >/tmp/caoscare-home.html
```

## First-run acceptance criteria

A first server run is ready for Michael review only when:

1. backend starts without missing environment-variable errors
2. MongoDB health returns `ok: true`
3. owner bootstrap runs once with `CAOSCARE_BOOTSTRAP_OWNER_*` values and the bootstrap password env is removed afterward
4. admin/JWT login works with the bootstrapped owner account
5. frontend builds successfully with `REACT_APP_BACKEND_URL=https://caoscare.com` and no trailing `/api`
6. reverse proxy serves frontend routes and proxies `/api/*`
7. no real secrets are committed
8. live website state is verified directly after deployment
9. safety boundaries remain assistive, advisory, human-supervised, and receipt-backed

## Pending decisions before production deployment

Michael must decide:

- Docker/compose vs native systemd/venv/static proxy path
- MongoDB location and backup process
- secret ownership and rotation process
- validate OpenAI Realtime / `gpt-realtime` browser voice end-to-end before presenting full-duplex voice as production-ready
- whether first production login policy is JWT/admin-only until owned OAuth ships; Google login remains legacy/Emergent-mediated until owned OAuth is implemented
- owned OAuth / direct Google OAuth implementation timing
- notification provider timing: log-only, Twilio, Resend, or both
- Android/RF/vision timing relative to web/backend launch
