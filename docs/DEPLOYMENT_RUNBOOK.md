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
EMERGENT_LLM_KEY=<approved-runtime-llm-key>
```

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

### 4. Start backend manually for first verification

```bash
cd /opt/caoscare/app/backend
source /opt/caoscare/venv/backend/bin/activate
uvicorn server:app --host 127.0.0.1 --port 8000
```

For a durable deployment, add a Michael-approved process manager later, such as systemd. Do not invent or install a service without explicit server approval.

### 5. Verify backend health

```bash
curl -fsS http://127.0.0.1:8000/api/health
```

Healthy target shape:

```json
{"ok": true, "db": "up"}
```

If MongoDB is unavailable, the endpoint may return an unhealthy database status and the deployment is not ready.

### 6. Prepare frontend environment

Use the template:

```text
frontend/.env.example
```

For a CAOSCARE.COM build:

```bash
cd /opt/caoscare/app/frontend
export REACT_APP_BACKEND_URL=https://caoscare.com
export ENABLE_HEALTH_CHECK=false
```

### 7. Install and build frontend

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
3. frontend builds successfully with `REACT_APP_BACKEND_URL=https://caoscare.com`
4. reverse proxy serves frontend routes and proxies `/api/*`
5. no real secrets are committed
6. live website state is verified directly after deployment
7. safety boundaries remain assistive, advisory, human-supervised, and receipt-backed

## Pending decisions before production deployment

Michael must decide:

- Docker/compose vs native systemd/venv/static proxy path
- MongoDB location and backup process
- secret ownership and rotation process
- whether first run keeps Emergent LLM integrations or replaces them first
- whether first run keeps Emergent Google auth or uses JWT-only/owned OAuth first
- whether startup seed/demo users stay enabled, are guarded, or are disabled
- notification provider timing: log-only, Twilio, Resend, or both
- Android/RF/vision timing relative to web/backend launch
