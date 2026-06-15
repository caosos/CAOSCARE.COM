# CAOS Care Project State

This is the living project-state file for `caosos/CAOSCARE.COM`.

Do not replace or erase prior project history. Add dated entries as work progresses.

For full repository orientation, read:

1. `AGENTS.md`
2. `docs/PROJECT_STATE.md`
3. `docs/REPO_MAP.md`
4. `docs/BUILD_STATUS.md`
5. `docs/DEPLOYMENT_RUNBOOK.md`

---

## 2026-06-14 — Local Lenovo prototype restart

### Agent / tool
ChatGPT with Michael running local terminal commands on Lenovo Ubuntu laptop.

### Branch / ref
`main` at `b5f84f1` — `Add Google Sign-In to administrator login`

### Current confirmed local state
- Repository exists locally at `/home/michael-chambers/CAOSCARE.COM`.
- `AGENTS.md` exists.
- `docs/BUILD_STATUS.md` exists.
- `docs/REPO_MAP.md` exists.
- `docs/DEPLOYMENT_RUNBOOK.md` exists.
- `docs/PROJECT_STATE.md` did not exist before this entry.
- Laptop has `git`, `python3`, `node`, `npm`, `claude`, `rtl_433`, and `rtl_test`.
- Laptop does not currently have `docker`, `yarn`, or `codex`.
- SDR tooling is already installed, so Nooelec/pendant testing can be handled later without starting from zero.

### What changed
- Created `docs/PROJECT_STATE.md` as the living continuation/status file.
- Standardized the agent workflow: humans and agents only need to remember `AGENTS.md`; `AGENTS.md` points to the project-state and repo-map files.
- Updated `AGENTS.md` read order so future agents read `docs/PROJECT_STATE.md` before continuing work.

### What is verified
- Local repo is present.
- Documentation structure is present.
- Project state file is now established.

### Blocked / not yet done
- Local backend/frontend have not been started yet.
- MongoDB is not verified locally.
- Frontend package install is not verified locally.
- Wi-Fi A/C control is not connected yet.
- Claude-generated bridge/auth files are not currently located in the repo.
- No hardware test has been run in this session.

### Next safe step
Review and commit the documentation operating-procedure update, then continue with local Lenovo prototype setup.

---

## 2026-06-14 — Local MongoDB installed for Lenovo prototype

### Agent / tool
Claude Code with Michael running local sudo install commands on the Lenovo Ubuntu 24.04 (noble) laptop. CAOSCare is local-first; the room node should keep working without internet, so a local MongoDB was chosen over MongoDB Atlas for the first prototype path.

### Branch / ref
`main` at `022d90e` — `Add project state operating procedure`

### What changed
- Attempted to add the official MongoDB 7.0 apt repository for Ubuntu 24.04 (noble); this failed because the 7.0 `noble` Release file was unavailable from the repository.
- Added the official MongoDB 8.0 apt repository for `noble`, which succeeded.
- Installed `mongodb-org` from the 8.0 repository successfully.
- Enabled and started the `mongod` systemd service.

### What is verified
- MongoDB reports version `v8.0.26`.
- The `mongod` service is active.
- Port `27017` is listening on `127.0.0.1`.
- The backend connection target should be `mongodb://localhost:27017`.

### Blocked / not yet done
- `backend/.env` has not been created yet (still only `backend/.env.example`).
- Python virtual environment for the backend has not been created.
- Backend requirements (`backend/requirements.txt`) are not installed.
- FastAPI backend has not been started; `/api/health` has not been validated against the new local MongoDB.
- Frontend install/build and Wi-Fi A/C control remain unaddressed (carried over from prior entries).

### Next safe step
Create `backend/.env` locally (set `MONGO_URL=mongodb://localhost:27017`, `DB_NAME`, and a strong local `JWT_SECRET`), create the Python virtual environment, install backend requirements, then start the FastAPI backend and verify `/api/health`.

---

## 2026-06-14 — Local backend booted on Lenovo prototype

### Agent / tool
Claude Code with Michael on the Lenovo Ubuntu 24.04 laptop.

### Branch / ref
`main` at `4cb4a18` — `Record local MongoDB install in project state`

### What changed
- Verified `backend/.env` already exists (git-ignored) with all required keys present and non-empty: `MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `CAOSCARE_ENABLE_DEMO_SEED`, `CORS_ORIGINS`, `PUBLIC_API_URL`. No secrets printed; file not modified.
- Created the Python virtual environment at `backend/.venv` (Python 3.12.3) and upgraded pip.
- Installed `backend/requirements.txt` successfully (exit 0).
- Started the FastAPI backend via `uvicorn server:app --host 127.0.0.1 --port 8000`.

### What is verified
- `git check-ignore` confirms `backend/.env` is ignored by `.gitignore` (`*.env`).
- Backend startup completed cleanly; demo seed correctly skipped (`CAOSCARE_ENABLE_DEMO_SEED=false`).
- `curl -fsS http://127.0.0.1:8000/api/health` returns `{"ok":true,"db":"up"}` — backend reaches local MongoDB.
- `git status --short` is clean (`.env` and `.venv` are ignored).

### Blocked / not yet done
- Frontend dependencies not installed; frontend not started (intentionally deferred this session).
- Wi-Fi A/C control and SDR/pendant hardware tests not addressed this session.
- Backend is running as a foreground/`nohup` process, not yet a managed systemd service.

### Next safe step
Install frontend dependencies and start the frontend, pointing it at `PUBLIC_API_URL=http://localhost:8000`, then verify the admin login flow end-to-end against the running backend.

---

## 2026-06-14 — Frontend booted on Lenovo prototype

### Agent / tool
Claude #1 in main repo.

### Branch / ref
`main` at `704a832` (before this commit) — `Record local backend health check in project state`.

### What changed
- Created `frontend/yarn.lock` for a reproducible frontend dependency install (committed).
- Created `frontend/.env` locally (sets `REACT_APP_BACKEND_URL=http://localhost:8000`, the bare backend origin without `/api`); it is git-ignored and **not committed**.

### What is verified
- Node 20.20.2 installed via nvm (user-local) — required because `react-router-dom@7` needs Node ≥20 (Lenovo had only Node 18.19.1).
- `yarn install` (via `npx yarn@1.22.22`, matching the `packageManager` field) succeeded.
- Frontend compiled with warnings only (eslint react-hooks warnings; no errors).
- Frontend served at `http://localhost:3000` (HTTP 200).
- `frontend/src/lib/api.js` appends `/api` to the origin itself, so the env value is correctly the bare origin; effective API base is `http://localhost:8000/api`.
- Backend health remained `{"ok":true,"db":"up"}` throughout; backend untouched.

### Blocked / not yet done
- Admin login flow not yet verified end-to-end (browser → backend API).
- nvm appended source lines to `~/.bashrc`; Node 20 is active in nvm shells (default alias set). A fresh shell needs `nvm use 20` if not auto-loaded.
- Backend and frontend both run as `nohup`/dev processes, not managed services.

### Next safe step
Open the frontend in a browser and verify the admin login / API flow end-to-end against the running backend.

---

## 2026-06-14 — Local admin/auth end-to-end verified (automated, voice/AI testing posture)

### Agent / tool
Claude #1 in main repo.

### Branch / ref
`main` clean at `4ad0c72` — `Record frontend boot dependencies and project state` (no commit made this session).

### What changed
- Created a temporary local-only **owner** account via the sanctioned `backend/scripts/bootstrap_owner.py` (using temporary env vars only). Password was generated in-session, never printed, never stored outside the bcrypt hash in Mongo, and is intentionally unrecoverable.
- No application code edited. No commit, no push.

### Finding (logged for future agents)
- The login endpoints validate `email` as pydantic `EmailStr`, which **rejects reserved TLDs** (`.test`, `.localhost`, `.local`). The originally requested `owner@local.test` was accepted by the bootstrap (the `User` model stores `email` as a plain `str`) but could **never authenticate** — `/api/auth/admin-login` returned `422` before any password check.
- Resolution (Michael-approved): deleted the unusable `owner@local.test` record and re-bootstrapped with `owner@local.dev` (a non-reserved TLD). Valid local choices confirmed: `*.dev`, `*.app`, `example.com`.

### What is verified (automated, localhost only)
- Owner account exists after bootstrap: `total_users=1`, `owners=1`, `email=owner@local.dev`, `role=owner`, `auth_provider=jwt`.
- `POST /api/auth/admin-login` with correct credentials → **HTTP 200**, token captured in shell var (never printed).
- `GET /api/auth/me` with that token → `email=owner@local.dev role=owner provider=jwt`.
- `POST /api/auth/admin-login` with wrong password → **HTTP 401**.
- Frontend `/admin-login` route renders: headless `google-chrome --dump-dom` returned the form (`admin-login-email-input`, `admin-login-password-input`, `admin-login-submit-btn`, "Admin sign-in" all present). No browser driver (Playwright/Puppeteer/Selenium) installed; none installed per instruction.
- Backend healthy (`{"ok":true,"db":"up"}`); frontend HTTP 200 throughout.

### Blocked / not yet done
- The temporary owner's password is secret and unrecoverable; **Michael cannot manually log in** with it. If manual UI login is wanted, a new owner password must be set (stop-and-ask before exposing any password).
- Full browser click-through (form submit → token → /admin) not automated — would require installing Playwright (declined this round). Render + API-level proof used instead.
- nvm `~/.bashrc` change persists; Node 20 active in nvm shells only.
- Backend/frontend still run as dev processes, not managed services.

### Next safe step
Decide whether to keep the secret temporary owner (API-only proof) or provision an owner with a known password for manual UI login. If full UI automation is desired later, approve installing Playwright for a real click-through test.

---

## 2026-06-14 — Local Google OAuth configured + button render verified (sign-in NOT yet clicked through)

### Agent / tool
Claude #1 in main repo.

### Branch / ref
`main` clean at `5dad682` — `Record local admin auth verification in project state` (before this checkpoint).

### What changed
- Configured the local, git-ignored `backend/.env` and `frontend/.env` for Google OAuth.
- Extracted the **Web** OAuth `client_id` from `~/Downloads/GOOGLEOAUTHSECRET` without printing it.
- Ignored the installed/desktop OAuth JSON (`client_secret_*.apps.googleusercontent.com.json`, top-level `installed`) because it is the wrong client type for Google Identity Services browser sign-in.
- Set backend `GOOGLE_CLIENT_ID` and `GOOGLE_ADMIN_EMAILS` (= `mytaxicloud@gmail.com`) locally.
- Set frontend `REACT_APP_GOOGLE_CLIENT_ID` (same client_id) locally.
- Restarted backend and frontend with the fresh env (frontend relaunched on Node 20 so CRA bakes in the new client id; both relaunched detached via `setsid` for stability).

### What is verified
- Backend health: `{"ok":true,"db":"up"}`.
- Frontend: HTTP 200.
- `/admin-login` renders the Google sign-in button (headless render shows the `google-signin-admin` container, the loaded `accounts.google.com/gsi` script, and a "Sign in with" Google button) alongside the password form.
- `git status` was clean before this PROJECT_STATE edit.
- `backend/.env` and `frontend/.env` remain git-ignored (confirmed via `git check-ignore`).

### Blocked / not yet done
- **Real browser Google sign-in has NOT been clicked through** — this checkpoint covers configuration and button render only; end-to-end Google login is unproven.
- Google Cloud Console must list `http://localhost:3000` as an **Authorized JavaScript origin** for this client.
- OAuth consent screen must allow `mytaxicloud@gmail.com` if the app is in testing mode (publish or add as a test user).
- Local password fallback is still needed for offline / break-glass use (Google verify requires internet).

### Next safe step
- Michael opens `http://localhost:3000/admin-login` and signs in with Google using `mytaxicloud@gmail.com`.
- Then verify he lands on `/admin` as `owner`.

---

## 2026-06-14 — Google OAuth browser sign-in verified end-to-end

### Agent / tool
Claude #1 in main repo.

### Branch / ref
`main` at `047336d` — `Record local Google OAuth configuration in project state` (before this checkpoint).

### What changed
- Google OAuth originally failed in the browser with `Error 401: invalid_client` / "no registered origin" — a Google-Console-side client/origin issue, not a CAOSCare code issue (zero `/api/auth/google/verify` requests reached the backend during those attempts).
- A new **Web** OAuth client JSON was used from `~/Downloads/CAOScare.com/dev2googleauthjson` (actual file on disk: `dev2googleoauth.json`; verified top-level `web` block, not `installed`).
- `backend/.env` (`GOOGLE_CLIENT_ID`) and `frontend/.env` (`REACT_APP_GOOGLE_CLIENT_ID`) were updated locally to the new client_id and remain git-ignored; `GOOGLE_ADMIN_EMAILS=mytaxicloud@gmail.com` preserved. Backend and frontend were restarted so CRA re-baked the new client id.

### What is verified
- Michael signed in with Google using `mytaxicloud@gmail.com`.
- `/api/auth/google/verify` reached the backend and returned **200** (preceded by a CORS preflight `OPTIONS` 200).
- MongoDB shows `mytaxicloud@gmail.com` as `MICHAEL CHAMBERS`, `role: owner`, `auth_provider: google` (promoted via the `GOOGLE_ADMIN_EMAILS` allowlist).
- Browser landed on `/admin` and showed "Welcome, MICHAEL CHAMBERS" / Role: Owner.
- Backend health remained `{"ok":true,"db":"up"}`; frontend remained HTTP 200 throughout.
- No client IDs, secrets, tokens, cookies, password hashes, or `.env` contents were printed or committed at any point.

### Blocked / not yet done
- Google sign-in requires internet (server-side token verification), so it is the **online** admin path only.
- Local password fallback (`/api/auth/admin-login`, bcrypt) remains **recommended for offline / break-glass** mode; keep at least one known offline owner password before relying solely on Google.
- Backend/frontend still run as detached dev processes (`setsid`), not managed services.

### Next safe step
Decide whether to provision/record a known offline break-glass owner password, and plan the production OAuth client (Authorized JavaScript origins for the deployed domain) when moving beyond localhost.
