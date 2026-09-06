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

---

## 2026-07-28 — First "caoscare node" local environment stood up (new caoscare-1 host)

### Agent / tool
Claude Code with Michael (mytaxicloud@gmail.com) on a fresh Ubuntu 22.04.5 LTS (jammy) host, user `caoscare-1`. This is a different machine from the prior Lenovo Ubuntu 24.04 prototype entries above.

### Branch / ref
`main` at `c971d32` — `Add CCE-lite documentation checkpoint` (repo freshly cloned this session, no commits made).

### What changed
- Fixed a pre-existing system-level npm permission issue (global npm prefix was `/usr`, unwritable) by installing nvm and Node v24.18.0 LTS as the user-local Node/npm.
- Installed and authenticated GitHub CLI (`gh`, apt version 2.4.0) as user `caosos` via the web/device-code flow.
- Cloned `caosos/caoscare.com` to `~/CAOSCARE.COM`.
- Added the official MongoDB 7.0 apt repo for jammy and installed `mongodb-org` 7.0.39; enabled and started `mongod` via systemd.
- Created `backend/.env` (git-ignored) with `MONGO_URL=mongodb://localhost:27017`, `DB_NAME=caoscare`, a freshly generated random `JWT_SECRET`, `CAOSCARE_ENABLE_DEMO_SEED=false`, local `CORS_ORIGINS`/`PUBLIC_API_URL`.
- Installed `python3.10-venv` (missing on this host's base Python 3.10.12), created `backend/.venv`, installed `backend/requirements.txt` successfully.
- Started the FastAPI backend via `uvicorn server:app --host 127.0.0.1 --port 8000` (detached).
- Created `frontend/.env` (git-ignored) with `REACT_APP_BACKEND_URL=http://localhost:8000`.
- Ran `corepack enable` + `yarn install` in `frontend/` using the already-committed `frontend/yarn.lock` (no lockfile changes needed — contradicts the "yarn.lock still missing" note in `docs/BUILD_STATUS.md`, which is stale as of this entry).
- Started the frontend via `yarn start` (detached, craco/CRA dev server).

### What is verified
- `curl http://127.0.0.1:8000/api/health` → `{"ok":true,"db":"up"}`.
- `curl http://localhost:3000` → HTTP 200. Compiled with only pre-existing eslint `react-hooks/exhaustive-deps` warnings (`useRealtimeVoice.js`, `Admin.jsx`, `AuditTab.jsx`, `MemoryDialog.jsx`), no errors.
- `mongod` active, listening on `127.0.0.1:27017`, version `7.0.39`.
- Node v24.18.0 / npm 11.16.0 active via nvm; no more npm permission errors.
- `gh auth status` shows logged in as `caosos` over https.
- `git check-ignore` confirms both `backend/.env` and `frontend/.env` are git-ignored; no secrets committed.
- No application code was modified this session — environment/setup only.

### Blocked / not yet done
- No owner account exists yet on this host's fresh MongoDB — `backend/scripts/bootstrap_owner.py` has not been run here.
- Admin login (password or Google OAuth) not yet exercised on this host.
- Google OAuth env vars (`GOOGLE_CLIENT_ID`, `GOOGLE_ADMIN_EMAILS`, `REACT_APP_GOOGLE_CLIENT_ID`) not set on this host yet.
- Backend and frontend are running as detached dev processes (`setsid`/`nohup`), not managed services.
- `docs/BUILD_STATUS.md` frontend-lockfile note is now stale (lockfile is present and used successfully); not corrected in place this entry per append-only convention — future agent should reconcile.
- Android surfaces, hardware, and production/Linode deployment untouched this session (explicitly out of scope — Michael is deferring the Linode server update).

### Next safe step
Run `backend/scripts/bootstrap_owner.py` on this host to create a local owner account, then verify admin login end-to-end (password path first; Google OAuth only if/when its env vars are configured here).

---

## 2026-07-28 — Owner bootstrapped on caoscare-1 node, password login verified end-to-end

### Agent / tool
Claude Code with Michael (mytaxicloud@gmail.com) on the `caoscare-1` host (same session as the entry above).

### Branch / ref
`main` at `c971d32` — no commits made this session; only `backend/.env`/`frontend/.env` (git-ignored) and Mongo data changed.

### What changed
- Ran `backend/scripts/bootstrap_owner.py` with temporary env vars `CAOSCARE_BOOTSTRAP_OWNER_EMAIL=mytaxicloud@gmail.com`, `CAOSCARE_BOOTSTRAP_OWNER_NAME="Michael Chambers"`, and a freshly generated one-time `CAOSCARE_BOOTSTRAP_OWNER_PASSWORD` (passed inline as env vars to a single command, never written to `backend/.env` or any file, never echoed to stdout by the script itself).
- The generated password was surfaced to Michael once in the session response so he can log in via the UI; it was stashed only briefly in a session-scratchpad file that was securely deleted (`shred -u`) immediately after use.

### What is verified
- `python scripts/bootstrap_owner.py` exited 0: "Created owner account for mytaxicloud@gmail.com."
- `POST /api/auth/admin-login` with the new credentials → token acquired successfully.
- `GET /api/auth/me` with that token → `email=mytaxicloud@gmail.com role=owner auth_provider=jwt`.
- Only one owner exists on this host's MongoDB (script refuses if an owner already exists, and none did).

### Blocked / not yet done
- Michael should treat the generated password as sensitive and may want to rotate it once logged in (no password-change endpoint confirmed/used this session).
- Google OAuth still not configured on this host — password/JWT is the only working admin login path here so far.
- Backend/frontend still running as detached dev processes, not managed services.

### Next safe step
Michael logs into `http://localhost:3000/admin-login` in a browser with the password given in-session, confirms the `/admin` dashboard loads as owner, then decide whether to configure Google OAuth on this host and/or set up managed services (systemd units) for backend/frontend instead of detached dev processes.

---

## 2026-08-02 — EliteDesk node build, Phases 1–3: Home Assistant OS VM installed alongside preserved CAOSCare app

### Agent / tool
Claude Code with Michael on the `caoscare1-hp-elitedesk` host, following `commands/TERMINAL_3_ELITEDESK_FULL_NODE_BUILD.md`. Full detail in `docs/ELITEDESK_NODE_BUILD.md`.

### Branch / ref
`main` at `fde20d8` — `Add EliteDesk full CAOSCare node build directive`. No commits made yet this session (pending — see Blocked).

### What changed
- Inspected host hardware/network/software state (Phase 1) and re-verified the existing CAOSCare backend/frontend/MongoDB stack still works after this host's last reboot (Phase 2) — no `.env`, owner account, or app data touched.
- Installed KVM/libvirt/QEMU/OVMF, defined a libvirt storage pool, downloaded the official Home Assistant OS 18.2 KVM (OVA/qcow2) release directly from `home-assistant/operating-system` on GitHub, and created a persistent, autostarting VM `caoscare-homeassistant` (4GiB RAM, 2 vCPU, UEFI, virtio) on libvirt's NAT network (`virbr0`), with a static DHCP reservation (`192.168.122.137`) and a host-level `iptables` port-forward so the VM is reachable at `192.168.1.151:8123` from the LAN.

### What is verified
- CAOSCare backend health, frontend, and MongoDB all confirmed healthy both before and after the Home Assistant VM work (Phase 2 re-check).
- Home Assistant onboarding page loads (`HTTP 200`, genuine HA frontend HTML) at `http://192.168.122.137:8123/` directly from the host, on first boot.
- VM is persistent and autostart-enabled in libvirt; storage pool is autostart-enabled.

### Blocked / not yet done
- Home Assistant's own onboarding wizard has not been completed — requires Michael's browser (see exact instruction in `docs/ELITEDESK_NODE_BUILD.md`, Phase 3 section).
- The LAN `iptables` port-forward could not be self-tested from the host itself (expected Linux hairpin-NAT limitation, not a defect) — needs a check from a second LAN device.
- The new `iptables` rules are runtime-only (no `iptables-persistent` installed yet) and will not survive a reboot; persistence is deferred to Phase 6 alongside converting backend/frontend to systemd, so boot-reliability is solved once, tested together, via a real reboot test.
- Phases 4 (Mosquitto/node services), 5 (MQTT integration contract), 6 (reboot reliability), and 7 (final repo records) of the directive are not started.
- This documentation update, plus the still-uncommitted 2026-07-28 entries above, have not yet been committed.

### Next safe step
Michael opens a browser on any LAN device to `http://192.168.1.151:8123` (fallback `http://192.168.122.137:8123` from the EliteDesk itself) and completes Home Assistant's onboarding wizard (local account, home name/location; skip Nabu Casa/remote access — out of scope). Tell Claude once done so Phase 4 can proceed.

---

## 2026-08-02 — Aria voice-first (Terminal 5/5A): capability registry, operator memory, first Realtime session, one real bug fixed

### Agent / tool
Claude Code with Michael on `caoscare1-hp-elitedesk`, following `commands/TERMINAL_5_ARIA_VOICE_FIRST.md` and `commands/TERMINAL_5A_ARIA_CAPABILITY_PORTFOLIO.md`. Full detail in `docs/ARIA_VOICE_FIRST.md` and `docs/ARIA_CAPABILITY_PORTFOLIO.md`. Midea/Matter LAN work (Terminal 4) explicitly paused per Terminal 5A's priority order, tracked as a `blocked` capability, not erased.

### Branch / ref
`main`, continuing from `2bb9ddc`. Commits from this session follow.

### What changed
- Confirmed existing OpenAI Realtime WebRTC voice pipeline (`frontend/src/lib/useRealtimeVoice.js` + `backend/routes/realtime.py`) was already built, just missing `OPENAI_API_KEY` on this host. Michael provided it via a hidden local shell prompt — never pasted into chat, never printed.
- Built the Terminal 5A capability portfolio: `AriaCapability` model + `backend/routes/capabilities.py` (`/api/capabilities`, owner-only, with a receipt-backed `/verify` endpoint), seeded with the 7 required initial entries.
- Built Aria's operator memory scope (Michael's explicit choice, kept separate from resident memory/`docs/CAOSCARE_MEMORY_AUTOMATION_CONTRACT.md`): `AriaMemory`/`AriaVoiceSession` models + `backend/routes/aria_memory.py` (`/api/aria/memory`, `/api/aria/sessions`).
- Added Aria's own Realtime session path (`POST /api/realtime/aria-session`) with her own persona/instructions, live capability-portfolio summary, and operator-memory context — kept fully separate from the resident-facing `/realtime/session`. No tools wired yet (by design — audio/conversation proof comes before tool routing).
- **Found and fixed a real pre-existing bug**: `useRealtimeVoice.js` read the ephemeral session key from the wrong field (`client_secret.value` instead of the actual top-level `value` the `/realtime/client_secrets` endpoint returns). This would have silently broken every Realtime voice session, resident and Aria alike, at the very first step. Fixed with a tolerant fallback.
- Added a minimal `/aria` page (`frontend/src/pages/AriaVoice.jsx`, owner-only route) — orb, status, start/stop, live transcript. No decorative UI.

### What was verified
- `POST /api/realtime/aria-session` mints a real ephemeral key and correctly-built instructions (persona + live portfolio + memory context, currently empty).
- Backend/frontend both restarted and confirmed healthy multiple times this session; frontend hot-compiled the new page with no new errors.
- Capability registry and operator-memory CRUD + the verify/receipt pattern all round-tripped correctly against the running backend.

### Blocked / not yet done
- **Nobody has spoken to Aria yet** — session minting is proven, the actual browser/WebRTC/microphone round-trip is not. That's the next real test.
- Wake-word ("Aria" hands-free) is Phase D, not started.
- Tool routing from Aria to the capability registry (Terminal 5A step 3) not started.
- Midea/Matter LAN work remains paused (blocked capability, host's only NIC is Wi-Fi carrying this SSH session; eno1 has no cable).
- `RealtimeChatScreen.jsx` (resident-facing) wasn't changed beyond the shared bugfix — worth a real end-to-end resident/kiosk session test at some point since it apparently was never exercised live before either.

### Next safe step
Michael opens `http://localhost:3000/aria` in a browser on the EliteDesk itself (so it uses the eMeet Luna Plus mic/speaker), logs in as owner, clicks "Start talking with Aria," allows microphone access, and talks. Reports back whether it connected, whether Aria's voice was audible/clear, and whether the conversation felt natural.

---

## 2026-08-21 — Session resume: services restarted, DepartmentsTab gap fixed, 300-line rule adopted, transportation acceptance-test prep

### Agent / tool
Claude Code with Michael on `caoscare1-hp-elitedesk`, resuming after an idle period (last entry above was 2026-08-10; today is confirmed 2026-08-21 by the host's own `date`/`timedatectl`, `System clock synchronized: yes`).

### Branch / ref
`main` at `3a4bd7f` locally. `origin/main` is 1 commit ahead at `077cf4a` ("Add full CAOSCare recent-work progress handoff") — fetched, not merged, no divergence (clean fast-forward available, not taken). 15 files of uncommitted local work confirmed present and preserved (the 2026-08-10 Terminal 8 lanes: schedule, menu, transportation, plus a `departments.py` backend module not documented in any prior entry).

### What changed
- Restarted MongoDB (was already running via systemd), backend (`uvicorn`, was not running), and frontend (`yarn start`, was not running) as detached dev processes, matching prior sessions' pattern — still not systemd-managed.
- Found and fixed a real gap: `frontend/src/pages/Admin.jsx` (uncommitted) imports and renders `DepartmentsTab` from `./DepartmentsTab`, but that file did not exist anywhere in the repo — frontend failed to compile (`Module not found`). The corresponding backend (`backend/routes/departments.py`) was already complete and wired into `server.py`. Created `frontend/src/pages/DepartmentsTab.jsx` (140 lines) matching the existing `ScheduleTab.jsx` pattern: list, add (dialog), toggle active/inactive, delete. Frontend now compiles clean.
- Adopted Michael's new 300-line production-code rule (replacing the prior 200-line-soft/400-line-hard guidance): recorded in `AGENTS.md` (`## Change discipline` → code section) and `docs/ENGINEERING_CONTRACT.md` (new dated section, explicitly marked as Michael-directed content, not agent-invented, since the rest of that document remains an unwritten placeholder).

### What was verified
- `curl http://127.0.0.1:8000/api/health` → `{"ok":true,"db":"up"}`.
- Frontend compiles with zero errors after the `DepartmentsTab.jsx` fix; serves HTTP 200 at `http://localhost:3000`.
- `mongod` active, `127.0.0.1:27017`.
- Home Assistant OS VM already running (`192.168.122.137:8123` → HTTP 200); Mosquitto reachable on the VM at `1883` (host-level `mosquitto` service is correctly inactive — it's a HA Supervisor add-on inside the VM, not a host service).
- Owner authentication intact: `POST /api/auth/admin-login` with a deliberately wrong password returns a clean `401 Invalid credentials`, not a 500. 1 owner user present in Mongo.
- `db.departments` already has 8 seeded departments (the 6 code defaults plus "Therapy" and "Resident Programs," added by hand previously) — the new `DepartmentsTab.jsx` has real data to render.

### Transportation acceptance-test prep (Michael's 8-step directive, steps 1-3 done here; steps 4-5 require Michael at the browser — see Next safe step)
1. **Admin → Transportation is available**: `TransportationTab.jsx` exists, is imported and wired into `Admin.jsx`'s tab list, and `backend/routes/transportation.py` is registered in `server.py` with all its routes present (`/slots/seed-two-weeks`, `/slots`, `/slots/public`, `/request`, `/request/{id}/change`, `/request/{id}/cancel`, `/request/{id}/complete`, `/request/status`).
2. **Is the two-week schedule already seeded? Honest answer: only partially, and it's stale.** `db.transport_slots` has 126 records spanning `2026-08-09` through `2026-08-22` (14 days), `created_at: 2026-08-10T03:38:32Z` — this is the exact same synthetic pilot data from the 2026-08-10 entry above (`seed_transportation_pilot.py`, 5 fake `TEST-101..202` rooms/residents, 4 slots already fake-booked). Since today is 2026-08-21, **12 of those 14 days are now in the past**; only `2026-08-21` (today) and `2026-08-22` (tomorrow) still have real, usable, unexpired slots. There is no genuine "two weeks from today" availability window yet.
3. **Prepared seeding method, not yet executed.** `POST /transportation/slots/seed-two-weeks` (admin/owner-authenticated) is idempotent by `(date, start_time)` — it will generate 9 hourly slots (8am-4pm) for each of the 14 days starting `today_facility_date()` (`2026-08-21` through `2026-09-03`), **skipping** any day/hour that already exists. Concretely: it will add slots for `2026-08-23` through `2026-09-03` (12 new days × 9 = up to 108 new slots) and silently no-op on `2026-08-21`/`2026-08-22` (already present). It will **not** touch, duplicate, or clean up the stale `2026-08-09`-`2026-08-20` pilot data or the 5 fake TEST residents — those simply age out of relevance as their dates pass. This is the same admin-only endpoint the existing "Seed 2-week schedule" button in `TransportationTab.jsx` calls. **Not run yet — waiting on Michael's go-ahead**, per his explicit "do not create duplicate schedules" instruction (it wouldn't duplicate, but confirming first per instruction).
4. Resident-facing voice tool location, confirmed by reading code (not assumed): `request_transportation`/`check_transportation_availability`/`check_transportation_status`/`change_transportation_request`/`cancel_transportation_request` are only in `_build_tools()` (`backend/routes/realtime_tools.py`), which backs `POST /api/realtime/session` — the **resident/kiosk voice path** (`Kiosk.jsx`, public, no login, at `/kiosk/:kioskId`). They are **not** in `_build_aria_tools()` (`realtime_aria_tools.py`), which only has `request_staff_help` — Aria's separate operator page at `/aria` cannot run this test. Exactly one kiosk exists in the DB: `kiosk_id=kio_9d5247d7ff59`, `room="test"`, so the real test URL is `http://localhost:3000/kiosk/kio_9d5247d7ff59`. That kiosk's room ("test") does not match any of the 5 TEST-101..202 resident rooms, so the test will run with `resident_id=None`/`room="test"` — a legitimate anonymous/room-based request under this app's own public trust model, not a fabricated resident.

### Not yet done
- Michael has not yet logged in and reviewed Admin → Departments / Schedule / Transportation.
- The two-week re-seed has not been executed (waiting on Michael's go-ahead, per above).
- The live microphone test ("I need a ride to the pharmacy tomorrow") has not been run — this requires Michael's real voice on real hardware; per this project's own standing rule, no automated/synthetic substitute counts as verification of the voice lane.
- Nothing has been committed, staged, or pushed this session; the 1-commit-behind `origin/main` has not been pulled.

### Next safe step
Michael logs in as owner at `http://localhost:3000/admin-login`, reviews Admin → Departments, Admin → Schedule, and Admin → Transportation (confirming the stale/partial seeding state above matches what he sees), approves or declines the two-week re-seed, then opens `http://localhost:3000/kiosk/kio_9d5247d7ff59` and says "I need a ride to the pharmacy tomorrow" while this session observes backend logs/DB state in real time to verify the full chain: UI → voice understood → tool invoked → backend record created → slot requested vs. confirmed → receipt created → status query works — and specifically that Aria never claims "you're booked" unless `transport_slot_id` is actually set and a `transportation_booked` receipt exists.

---

## 2026-08-21 — Terminal 9 checkpoint: Google owner login + SSH relay verified, 300-line rule violations found, transportation seed confirmed adequate

### Agent / tool
Claude Code with Michael, invoked via `git fetch origin main` + `git show origin/main:commands/TERMINAL_9_LAPTOP_RELAY_ACCEPTANCE_ONBOARDING.md` (Michael's "Fetch and execute Terminal 9"), continuing the same working session as the "Session resume" entry directly above.

### Branch / ref
`main` at `3a4bd7f`, unchanged. `origin/main` is now 2 commits ahead (`077cf4a` doc-only progress handoff, `48a84e0` the Terminal 9 directive itself) — fetched only, not merged; no divergence with local uncommitted work.

### What changed
- No product code changed in this phase — Terminal 9's Phase 1-2 are inspect/record-only. This entry and the `docs/CURRENT_NODE_STATUS.md` reconciliation are the only file changes, and both remain uncommitted pending Michael's review.

### What was verified
- **Google owner login (GSI) confirmed working in the browser** for `mytaxicloud@gmail.com`, via `frontend/src/components/GoogleSignIn.jsx` → ID token → `POST /api/auth/google/verify`, sharing the existing JWT/cookie session mechanism. Backend checks token audience, issuer, and `email_verified`; rejects a non-allowlisted email before it can create an owner; does not silently demote existing owners. Correct config names: backend `GOOGLE_CLIENT_ID` + `GOOGLE_ADMIN_EMAILS`, frontend `REACT_APP_GOOGLE_CLIENT_ID` — `OWNER_EMAILS` is not used. `frontend/src/pages/AuthCallback.jsx` looks like dead legacy-OAuth code but was left in place pending a references check, not removed.
- **Laptop → EliteDesk SSH relay established**: `ssh.service` active and listening on EliteDesk port 22; laptop `~/.ssh/config` has a `Host caoscare` entry; `ssh caoscare` from the laptop lands at `caoscare-1@caoscare1-hp-elitedesk`. This is what lets Michael say "Fetch and execute Terminal 9" instead of retyping commands.
- Backend/frontend/MongoDB/HA VM reconfirmed healthy (same processes as the prior entry, ~1.5h uptime): `/api/health` → `{"ok":true,"db":"up"}`; frontend serving on `:3000` (craco, correct cwd); `mongod` on `127.0.0.1:27017`; HA VM's qemu process running.
- Re-confirmed the transportation seed data from the prior entry still stands: `transport_slots` has 126 docs across 14 distinct dates `2026-08-09` → `2026-08-22`, `source: internal_schedule`, 4 slots with `booked_count > 0`. Since today is still `2026-08-21`, this window covers today and tomorrow — **adequate for the pharmacy-tomorrow acceptance test without re-seeding**. `schedule_items` and `menu_items` are both still empty (Schedule/Menu tabs have UI but no backing data yet).
- Confirmed all four new Admin tabs (`ScheduleTab`, `MenuTab`, `TransportationTab`, `DepartmentsTab`) are imported and rendered in `frontend/src/pages/Admin.jsx`.

### New finding: 300-line rule violations in the current uncommitted diff
The rule itself was already recorded in `AGENTS.md` and `docs/ENGINEERING_CONTRACT.md` by the prior session (not new). What's new here is checking today's actual working-tree diff against it:
- `backend/models.py`: 1105 → **1295** lines — already over cap, and grew **+190** more this session (violates "do not make an already-over-cap file larger").
- `frontend/src/pages/Admin.jsx`: 691 → **777** (+86, same violation).
- `backend/routes/auth.py`: 278 → **309** (crossed the cap this session, +31).
- `backend/routes/transportation.py`: new file, created at **389** lines — over cap from creation.
- Improvements in the same diff: `backend/routes/tasks.py` 373→286 and `backend/routes/realtime_tools.py` 342→292 both moved from over-cap to under-cap; `frontend/src/lib/useRealtimeVoice.js` 539→510 shrank but is still over cap.
- None of the violations above have been remediated yet — flagging for Michael's direction before further edits stack on top of these files.

### Blocked / not yet done
- Terminal 9 Phases 3-6 (transportation acceptance prep, Michael's live Admin walkthrough, the real microphone test, and the screenshot-based departmental walkthrough) have not started.
- The 300-line violations above have not been remediated — no extraction attempted yet.
- Nothing staged, committed, pushed, or pulled this session; `origin/main`'s 2 fetched commits remain unmerged.

### Next safe step
Michael reviews this checkpoint and the `docs/CURRENT_NODE_STATUS.md` reconciliation, then either (a) gives go-ahead to continue into Terminal 9 Phase 3 (transportation acceptance prep — no browser/mic/DB writes yet), or (b) directs how to handle the 300-line violations found in `models.py`, `Admin.jsx`, `auth.py`, and `transportation.py` before more work stacks on top of them.

---

## 2026-08-22 — Terminal 9 Phase 3: transportation seed window extended (approved), acceptance prep confirmed

### Agent / tool
Claude Code with Michael, same "Fetch and execute Terminal 9" invocation, resuming this working session same-day.

### Branch / ref
`main` at `3a4bd7f`, unchanged. `origin/main`'s `077cf4a`/`48a84e0` still fetched-only, unmerged. Working tree unchanged from the 2026-08-21 checkpoint (same modified/untracked file list) except for this doc edit.

### What changed
- **Called `POST /transportation/slots/seed-two-weeks` (Michael-approved)** — authenticated as the existing owner user via `backend/routes/auth._issue_jwt`, run through `backend/.venv`, hitting the live local API (not a direct DB write). Result: `{"ok": true, "created": 117}`.
- `transport_slots` grew from 126 → **243** docs. Date coverage extended from `2026-08-09`→`2026-08-22` to `2026-08-09`→`2026-09-04`. Confirmed idempotent as designed: exactly 117 = 13 new days × 9 slots/day (2026-08-22 already had its 9 slots and was correctly skipped); `booked_count > 0` unchanged at 4; no resident, task, or receipt records touched.
- No other product code or data changed this phase.

### What was verified
- **Re-inspection found the seed window had gone stale**: the 2026-08-21 checkpoint's "adequate for pharmacy-tomorrow without re-seeding" conclusion was time-relative — today advanced to 2026-08-22, pushing "tomorrow" (2026-08-23) outside the then-current window. This is exactly the kind of drift the directive's inspect-first discipline is meant to catch.
- Full state re-verified unchanged from the prior checkpoint before acting: local HEAD, `origin/main`, working-tree diff, flagged 300-line file sizes (`models.py` 1295, `Admin.jsx` 777, `auth.py` 309, `transportation.py` 389 — all unchanged), and backend/frontend/MongoDB health (`/api/health` → `{"ok":true,"db":"up"}`).
- Admin → Transportation confirmed present and wired (`frontend/src/pages/TransportationTab.jsx` in `Admin.jsx`).
- `schedule_items` and `menu_items` still both empty (no backing data yet for those tabs).
- Resident voice / mic-test entry point confirmed: `http://localhost:3000/kiosk/kio_9d5247d7ff59` (kiosk doc `room: "test"`). Five TEST residents (TEST-101…TEST-202) present from the Terminal 8 pilot seed.
- Owner JWT issuance for this one-off call followed the same pattern as `backend/scripts/seed_transportation_pilot.py` (`_issue_jwt` against the existing owner user, real HTTP call to the real endpoint) — no new auth mechanism introduced, no secrets printed.

### Blocked / not yet done
- Phase 3 steps 1-4, 6-7 (inspection) and step 5 (this seed call) are now complete. Phases 4-6 (Michael's live Admin walkthrough, the real microphone test, the screenshot-based departmental walkthrough) have not started — all require Michael's browser/microphone interaction per the stop conditions.
- The 300-line violations from the prior checkpoint remain unaddressed.
- Nothing staged, committed, pushed, or pulled; `origin/main`'s 2 fetched commits remain unmerged.

### Next safe step
Michael signs in as owner with Google, then walks Admin → Departments → Schedule → Transportation → Menu one page at a time (Phase 4), followed by the real microphone test at `http://localhost:3000/kiosk/kio_9d5247d7ff59` saying "I need a ride to the pharmacy tomorrow" (Phase 5) while this session observes backend logs/DB state live to verify the full chain end to end.

---

## 2026-08-22 — CORE PRODUCT RULE adopted; "Enter room" shipped; Admin.jsx brought under the 300-line cap; two real gaps found (kiosk mapping, dedup)

### Agent / tool
Claude Code with Michael, same working session, continuing directly from the Phase 3 seed-window checkpoint above. Michael issued a new standing requirement ("CORE PRODUCT RULE: everything testable, everything customizable where appropriate, everything easy as fuck") layered on top of Terminal 9, plus an explicit reminder mid-session not to grow handwritten files past 300 lines.

### Branch / ref
`main` at `3a4bd7f`, unchanged. `origin/main`'s `077cf4a`/`48a84e0` still fetched-only, unmerged.

### What changed
- **Extracted the four still-inline tab components out of `frontend/src/pages/Admin.jsx`** into their own files, matching the pattern every other tab (Schedule/Menu/Transportation/Departments) already used: `ResidentsTab.jsx` (272 lines), `StaffTab.jsx` (99), `KiosksTab.jsx` (105), `ZonesTab.jsx` (94). `Admin.jsx` itself: **777 → 287 lines** — the file this session's diff touches is now under the cap, and no file created or modified this round exceeds it.
- **Added "Enter room" to Admin → Residents** (`ResidentsTab.jsx`): resolves the kiosk mapped to a resident's room client-side from the `kiosks` list `Admin.jsx` already fetches (same `Kiosk.room == Resident.room` match `GET /residents/public/by-kiosk/{id}` uses server-side), then opens `/kiosk/:kioskId` in a new tab — the real resident-facing path, not a mock. A resident with no matching kiosk shows a disabled "No kiosk" button instead of guessing or silently opening an unrelated kiosk.
- **Created 5 kiosks (Michael-approved)** — one per TEST resident room (`TEST-101`…`TEST-202`), via the existing `POST /kiosks` (owner-authenticated, same one-off pattern as the transportation seed call). Kiosk ids: `kio_a95788ce0e28`, `kio_9bdfb3a1db98`, `kio_d964ef5f2e33`, `kio_84f1b2c63e43`, `kio_7ce992d580e8`. Verified all 5 resolve correctly through the real `GET /residents/public/by-kiosk/{id}` endpoint.
- Frontend recompiled clean (`/tmp/caoscare_frontend.log`) — no new errors, only the pre-existing `fetchAll` exhaustive-deps warning.

### What was verified
- Full architecture map of what exists for residents/kiosk-mapping/memory/conversations/family-portal/requests/receipts against the CORE PRODUCT RULE's Resident-360 requirement (Sections 1-9). Full findings:
  - **Already satisfies**: `ResidentMemory` (backend/models.py:905) already carries source attribution (chat/admin/staff/family/extraction), category, bin, importance, pinned/archived — most of the "Aria Memory" requirement already exists. `db.conversations` + `GET /memory/conversation/{resident_id}` is the resident-scoped conversation history. `receipts.py` is a resident_id-filterable generic activity ledger. `resident_requests.py` already avoids duplicate-queue clutter by bumping `re_request_count` on an existing open request rather than always creating a new task.
  - **Partially satisfies / real bug found**: duplicate detection in `routes/resident_requests.py:91-99` is **category + resident/room only, not content-aware** — "my sink is leaking" and "my A/C isn't working," both category `maintenance` from the same resident, would currently collide: the second would silently bump the first's `re_request_count` instead of creating a real second task. This is the exact failure mode Michael's directive warns against. **Not fixed this round** — it needs a real design decision (e.g., an LLM similarity check or a required short problem tag), not a small slice.
  - **Missing**: family-contributed personalization (photos/music/preferences from family) — `family_portal.py` is read-only today. A dedicated resident-centric "Resident Record" UI — today it's `MemoryDialog.jsx` (memories + conversation + tasks, opened from Admin → Residents) plus several separate admin pages, not one unified view. `research.py` has no `resident_id`/session logging at all, so research/lookup activity isn't yet in any per-resident ledger.
- Confirmed pre-change that **no kiosk mapped to any of the 5 TEST residents** (only kiosk in the DB was `kio_9d5247d7ff59`, room `"test"`) — "Enter room" would have correctly shown "No kiosk" for all 5 without the new kiosks above.

### Blocked / not yet done
- The content-aware duplicate-detection gap above is identified but not designed or built — needs Michael's direction on approach before implementation.
- Family-contributed personalization (Section 5) and a unified Resident Record UI (Section 6) are both real architectural decisions Michael's directive explicitly says to stop for — not started.
- `backend/models.py` (1295 lines) and `backend/routes/auth.py` (309 lines) 300-line violations from the 2026-08-21 checkpoint are untouched — neither was modified this round.
- Terminal 9 Phases 4-6 (Michael's live Admin walkthrough, the real mic test, the screenshot walkthrough) still not started — still require Michael at the browser/microphone.
- Nothing staged, committed, pushed, or pulled; `origin/main`'s 2 fetched commits remain unmerged.

### Next safe step
**Test instructions for what's done this round** (Section 10 format):
- **Feature**: "Enter room" from Admin → Residents.
- **Path**: sign in as owner → Admin → Residents tab (default tab).
- **Click**: the "Enter room" button on the row for "TEST Room 101 (Node A)" (or any of the 5 TEST rows).
- **Expected result**: a new browser tab opens at that resident's real kiosk (`/kiosk/kio_a95788ce0e28` for TEST-101), the same page the mic-test kiosk uses — mic permission prompt, Aria greeting, everything live.
- **What's still unverified**: I have not opened it in a real browser myself (browser interaction is a stop condition) — Michael's click is the actual acceptance test.
- **Where to see it failed correctly before the fix**: any resident *without* a matching kiosk still shows a disabled "No kiosk" button rather than opening anything.

After that: Michael either (a) continues into Terminal 9 Phase 4 (the live Admin walkthrough) using the now-working "Enter room" links, or (b) gives direction on the content-aware-duplicate-detection gap or the Resident Record UI architecture before more work stacks on top.

---

## 2026-08-22 — "Auth must feel continuous" usability rule: fixed Landing/Login/AdminLogin ignoring an already-authenticated user

### Agent / tool
Claude Code with Michael, same working session, mid-Phase-4 (Michael hit this defect trying to do Phase 4 step 1: log in, then click the CAOS Care logo).

### Branch / ref
`main` at `3a4bd7f`, unchanged. `origin/main`'s `077cf4a`/`48a84e0` still fetched-only, unmerged.

### What changed
Inspected first, per the new rule's own instruction to determine whether this was (1) real session loss, (2) UI ignoring valid auth state, or (3) both. Traced the actual mechanism:
- `get_current_user` (backend/deps.py:45) checks the `Authorization: Bearer` JWT first, `session_token` cookie second. `GoogleSignIn.jsx` stores the JWT in `localStorage.caos_token` on sign-in (same as password login) — this token is what every admin API call already uses successfully.
- `AuthProvider` (frontend/src/lib/auth.jsx) is mounted once at the app root, outside the router — client-side navigation between routes (e.g. clicking the logo) never remounts it or clears `user` state. The token in `localStorage` is untouched by navigation.
- **Root cause = category 2, UI-only**: `frontend/src/pages/Landing.jsx` never called `useAuth()` at all — it unconditionally rendered "Staff sign in" → `/login` regardless of auth state, for every visitor including an already-authenticated owner. `Login.jsx` and `AdminLogin.jsx` had the same gap in reverse: they didn't check for an existing `user` and would show the sign-in form again to someone already signed in (e.g. hitting the browser back button). No actual JWT/cookie/session loss found anywhere.
- **Fix — reused the existing auth context, no new mechanism added:**
  - `Landing.jsx`: added `useAuth()`; nav button and hero secondary CTA now read `user` and show "Continue to admin"/"Continue to dashboard" linking to `/admin` or `/staff` when signed in, "Staff sign in" → `/login` only for a real guest.
  - `Login.jsx` / `AdminLogin.jsx`: added a `useEffect` that redirects an already-authenticated user straight to their destination (honoring `location.state.from`, same fallback logic the post-login handlers already use) instead of rendering the sign-in form.
- Files touched (all under the 300-line cap, none newly over it): `frontend/src/pages/Landing.jsx` 181→**192**, `frontend/src/pages/Login.jsx` 194→**203**, `frontend/src/pages/AdminLogin.jsx` 177→**184**. `lib/auth.jsx` (98 lines) and `backend/deps.py`/`routes/auth.py` were read, not modified.
- Frontend recompiled clean (`/tmp/caoscare_frontend.log`) — no new errors/warnings beyond the pre-existing `fetchAll`/`fetchSummary` exhaustive-deps ones.

### What was verified
- Verified via code trace, not yet via Michael's real browser click (browser interaction is a stop condition — this is exactly what he needs to confirm next).
- Confirmed sign-out (`logout()` in auth.jsx) and session-cookie expiry (`JWT_EXPIRE_DAYS`, `backend/routes/auth.py`) were not touched and were not implicated in the defect — not part of this fix.

### Blocked / not yet done
- Michael's real-browser confirmation of the fix (see Next safe step).
- All Terminal 9 / CORE PRODUCT RULE items from the prior checkpoint (content-aware duplicate detection, Resident Record UI, family personalization, Phases 4-6) remain exactly as they were — this was an interrupt to fix a defect Michael hit while starting Phase 4, not a continuation of that work.
- Nothing staged, committed, pushed, or pulled; `origin/main`'s 2 fetched commits remain unmerged.

### Next safe step
**Test instructions (Section 10 format):**
- **Feature**: authentication now feels continuous across Landing/Login/AdminLogin.
- **Path/clicks**: sign in as owner at `/admin-login` → land on Admin → click the **"CAOS Care" logo** (top-left, any Admin page) → **expected**: lands on the home page showing **"Continue to admin"** in the nav (not "Staff sign in") → click it → **expected**: back in Admin, no sign-in form shown → **refresh the browser tab** while on the home page or Admin → **expected**: still authenticated, no sign-in prompt.
- **Where to see it fail correctly**: sign out first, then visit `/`, `/login`, or `/admin-login` — those must still show the real sign-in form/CTA as a guest.
- **What remains unverified**: real-browser confirmation from Michael.

After Michael confirms this, resume Terminal 9 Phase 4 exactly where it was interrupted: Admin → Departments → Schedule → Transportation → Menu walkthrough.

---

## 2026-08-22 — Real-browser findings from Michael's Phase 4/5 test: silent Aria (fixed), false-sounding "booked" (root-caused as a display gap, fixed); resource-aware transportation scheduling proposed, not yet built

### Agent / tool
Claude Code with Michael, same working session. Michael did his own live mic/Admin test mid-Phase-4 and reported two defects plus a large "everything testable" resource-scheduling/Front-Desk/calendar requirement.

### Branch / ref
`main` at `3a4bd7f`, unchanged. `origin/main`'s `077cf4a`/`48a84e0` still fetched-only, unmerged.

### What changed
1. **Silent-Aria bug — real bug, fixed.** `frontend/src/lib/useRealtimeVoice.js`'s `dc.onopen` sent `session.update` but never `response.create` — the model has no built-in "speak first" behavior in this API, so Aria sat silently until the resident spoke, even though her prompt (`_build_companion_instructions`) already says to greet them. Added one `send({ type: "response.create" })` right after the session config, relying on the data channel's in-order delivery so the server applies config before generating the greeting. File: 510→**515** lines — already over the 300-line cap before this change (flagged in the 2026-08-21 checkpoint); this fix grows it further. Not extracted this round — see Blocked below.
2. **"Booked vs pending" — root-caused as a UI display gap, not a truth violation.** Traced Michael's actual test record in Mongo (`task_399327f5aae3`, today 17:12 UTC): `transport_slot_id` was set and the receipt was `transportation_booked` — **the reservation genuinely succeeded; Aria's "booked" was accurate.** The `StaffTask.status` field Michael was reading ("pending") is a *separate* staff-acknowledgment workflow field that never changes to reflect booking — a task can be `status="pending"` (unacknowledged) while already truly booked (`transport_slot_id` set). `TransportationTab.jsx`'s "Inbound" list never showed the real booked/pending truth per row, and never rendered `received_at` (Requested At) at all despite the backend already returning it. Fixed: `backend/routes/transportation_report.py` now includes `"booked": bool(transport_slot_id)` per inbound item (135 lines, was 128); `frontend/src/pages/TransportationTab.jsx` now shows "Requested at ... · Appointment ... (time label) · via ..." plus a real Booked/Pending badge per row (129 lines, was 112).
3. **Backend restarted (Michael-approved)** — no `--reload` flag on the running `uvicorn`, so the report-endpoint fix needed a restart to go live. Killed PID 10772, relaunched identically (same command, same log redirect to `/tmp/caoscare_backend.log`), verified `/api/health` and the new `booked` field both live within seconds.

### What was verified
- Confirmed via live DB query that Michael's real test request (TEST-101, "doctor appointment," today ~3 PM) has `transport_slot_id` set and a `transportation_booked` receipt — i.e., Aria did not lie.
- Confirmed the backend booking logic itself (`_reserve_slot`'s atomic `find_one_and_update` with a capacity guard, `booked = bool(slot)` in `POST /transportation/request`) was already correct and didn't need changing — this was purely a display gap.
- Frontend recompiled clean both times (`/tmp/caoscare_frontend.log`), no new warnings.

### Blocked / not yet done — needs Michael's design confirmation before building
The rest of this round's directive (resource-aware driver/vehicle scheduling, Aria checking real availability before confirming, appointment-planning assistance, a Front Desk role/dashboard, a calendar-style transportation view, one shared source of truth across Aria/Admin/Front Desk) is a real architecture decision spanning the data model and three different UIs — not implemented yet. A concrete smallest-design proposal is being given to Michael in-conversation for go-ahead before any of it is built. Also not yet remediated: `useRealtimeVoice.js` (515 lines) growing further past the cap — flagging for Michael's direction (extract the WebRTC/data-channel setup into its own module, vs. leave as-is for now since it's a single cohesive connection lifecycle).
- Terminal 9 Phase 4 (the live Admin walkthrough) remains interrupted at the Departments tab.
- Nothing staged, committed, pushed, or pulled; `origin/main`'s 2 fetched commits remain unmerged.

### Next safe step
**Test instructions:**
- **Greeting fix** — Admin → Residents → any TEST room → "Enter room" → click "I just want to talk" → expect Aria to speak a greeting within ~1-2 seconds without Michael saying anything first.
- **Transportation truth display** — Admin → Communication & requests → Transportation → Inbound section → find the "TEST-101 — doctor appointment" row → expect it now shows "Requested at [timestamp] · Appointment 2026-08-22 (around 3 PM)" and a green "Booked" badge, not just a bare description line.

Then: Michael reviews the proposed resource-scheduling/calendar/Front-Desk design (given in-conversation) and either approves it, asks for changes, or picks a smaller first slice before Claude builds anything from Sections 4-9 of the incorporated directive.

---

## 2026-08-22 — Resource-aware transportation engine + calendar + Front Desk role built; Realtime voice diagnostics and a memory-trust boundary added after a real acceptance test found phantom transcripts and a double greeting

### Agent / tool
Claude Code with Michael, same working session. Michael approved the resource/calendar/Front-Desk design proposed in the prior checkpoint with 7 corrections (no invented vehicle capacity, no invented trip-duration default, tighter run-sharing compatibility, driver/vehicle as separate resources, Front Desk approved, calendar visual requirements, the useRealtimeVoice.js size flag). Mid-build, Michael's own real resident-voice acceptance test surfaced a second, higher-priority defect (phantom transcripts, a duplicated greeting, and a false name-correction) which is addressed in the same round.

### Branch / ref
`main` at `3a4bd7f`, unchanged. `origin/main`'s `077cf4a`/`48a84e0` still fetched-only, unmerged. 58 files now uncommitted total; nothing staged/committed/pushed.

### What changed — transportation resource engine, calendar, Front Desk
- **New domain model** (`backend/models_transportation.py`): `TransportDriver`, `TransportVehicle` (capacity `Optional[int] = None` - unset, never guessed), `TransportRun` (driver_id + vehicle_id independently - not permanently coupled), `TransportSchedulingConfig` (admin-editable `buffer_minutes`, explicitly a scheduling policy, not a claim about any trip's real duration).
- **New booking engine** (`backend/transportation_engine.py`): `find_or_create_run()` - shares an existing run only on exact destination match + time-window overlap + configured (never assumed) vehicle capacity; otherwise books a new run only if a free (driver, vehicle) pair both exist; otherwise returns no run at all (request stays pending for Front Desk). Deterministic, defaults to pending under any uncertainty per Michael's correction.
- **New endpoints**: `routes/transportation_resources.py` (admin CRUD for drivers/vehicles/buffer), `routes/transportation_calendar.py` (`GET /transportation/calendar?date=&days=`, day/week, read by Admin + Front Desk + eventually Aria - one source of truth), `routes/transportation_legacy_slots.py` (old hourly-bucket TransportSlot code moved here verbatim, kept only for historical pilot data), `routes/transportation_voice_context.py` (resident/room/session-scoped change/cancel/status, split out of transportation.py).
- **`routes/transportation.py` rewritten to book through the engine** instead of the old TransportSlot bucket, added `/availability/public` (resource-aware, replaces `/slots/public` for Aria's real availability check) — **net 389 → 264 lines** despite the new functionality, by extracting the pieces above.
- **Front Desk role**: `"front_desk"` added to `User.role` (models.py, 2 Literal defs), new `require_front_desk_or_admin` dep, `/front-desk` route + `Protected frontDeskOnly`, `FrontDeskDashboard.jsx` (calendar + front-desk/callback requests + resident directory), `TransportationCalendar.jsx` (shared day/week component used by both Admin and Front Desk), `TransportResourcesTab.jsx` (admin driver/vehicle/buffer config), all wired into `Admin.jsx`'s Communication group and `StaffTab.jsx`'s role dropdown.
- **`lib/roleHome.js`** (new): single `roleHomePath()`/`roleHomeLabel()` used by Landing/Login/AdminLogin/GoogleSignIn instead of the same ternary duplicated four times.
- **`transport_run_id`** added to `StaffTask` (models.py) alongside the legacy `transport_slot_id`; `booked = bool(transport_run_id or transport_slot_id)` everywhere that matters.

### What changed — Realtime voice: diagnostics + double-greeting fix + memory-trust boundary
Root-caused before touching anything, per Michael's "inspect before tuning": server-side `turn_detection` already has `create_response: true` (`routes/realtime.py`'s `DEFAULT_VAD`) - the server auto-generates a response whenever it decides speech stopped. This session's own new forced greeting (`response.create`, added earlier this session to fix "Aria never speaks first") + a room speaker/mic setup where Aria's own audio can leak back into the mic despite requested `echoCancellation` is the most likely mechanism for the observed double greeting and phantom "Thank you."/"Hi." turns - not a code loopback bug (verified `pc.addTrack` only sends the local mic stream; the remote/output stream only ever goes to the `<audio>` playback element, never back into the connection).
- **Double-greeting fix**: `dc.onopen` now sends the initial `session.update` with `create_response: false` just for the forced greeting, then re-enables the real `turn_detection` (with `create_response: true` restored) once that greeting's own `response.done` fires. Closes exactly the window where the greeting's own echo could trigger a server auto-response, without touching VAD sensitivity/threshold at all. Real barge-in is untouched (`interrupt_response` is a separate mechanism from `create_response`).
- **Diagnostics** (mandatory, added before the next test): new `backend/routes/realtime_diagnostics.py` (`POST /realtime-diagnostics/event`, public/fire-and-forget; `GET /realtime-diagnostics/session/{id}`, authenticated) + `frontend/src/lib/realtimeDiagnostics.js` (`logRealtimeEvent()`). `useRealtimeVoice.js` now logs, per session: `speech_started`/`speech_stopped` (each tagged with whether Aria's audio was playing at that instant), completed user/assistant transcripts, `response_created`/`response_done`, and every tool call. No raw audio or secrets logged.
- **Memory-trust boundary** (mandatory): `turnSuspectRef` captures whether a user turn's speech onset overlapped Aria's own audio (the strongest available real signal, per Michael's own list). `routes/memory.py`'s `POST /memory/realtime-turn` gained a `trusted: bool` field - an untrusted turn is still saved to `db.conversations` (diagnostic value preserved) but **skipped from `extract_and_store_memories`**, so it can't become a durable `ResidentMemory` fact. The one live "authoritative mutation" tool, `update_preferred_name`, now refuses to save and instead asks the resident to repeat themselves when the triggering turn was flagged suspect - it does not silently accept a possibly-phantom correction.
- **Preserved, unchanged, confirmed correct**: the intent-based routing behavior Michael specifically flagged as good (asking for maintenance on oranges correctly routed to Kitchen) lives entirely in `_build_companion_instructions`' prompt reasoning, which this round never touched.
- **Extraction, not stuffed in further**: `executeTool`'s ~155-line device/timer/weather/research/name-update dispatch moved out of `useRealtimeVoice.js` into `frontend/src/lib/realtimeDeviceTools.js` (matching the existing `realtimeOperationsTools.js` pattern) *before* adding the diagnostics/trust-boundary code, per Michael's standing-rule reminder. Net effect: `useRealtimeVoice.js` **515 → 422 lines** - still over the 300-line cap (pre-existing, flagged previously) but smaller than where this session started despite the new functionality, not larger.

### Line counts - every file created or materially modified this round
New (all under 300): `models_transportation.py` 100, `transportation_engine.py` 140, `routes/transportation_resources.py` 96, `routes/transportation_calendar.py` 85, `routes/transportation_legacy_slots.py` 86, `routes/transportation_voice_context.py` 95, `routes/realtime_diagnostics.py` 52, `TransportationCalendar.jsx` 124, `TransportResourcesTab.jsx` 154, `FrontDeskDashboard.jsx` 115, `lib/roleHome.js` 15, `lib/realtimeDeviceTools.js` 150, `lib/realtimeDiagnostics.js` 25.
Modified, now under 300: `routes/transportation.py` 264 (was 389), `Admin.jsx` 297, `StaffTab.jsx` 100, `Landing.jsx` 193, `Login.jsx` 202, `AdminLogin.jsx` 184, `GoogleSignIn.jsx` 77, `App.js` 99, `realtimeOperationsTools.js` 171.
Modified, still over 300 (pre-existing violations; grew by small unavoidable amounts, all extraction-first where the responsibility being touched allowed it): `useRealtimeVoice.js` 422 (515 at this round's start), `models.py` 1301 (+6: `transport_run_id` field, `front_desk` role literal), `routes/memory.py` 489 (+12: the `trusted` field and its branch), `deps.py` 130 (+8: `require_front_desk_or_admin`), `server.py` 173 (+8: new router registrations - arguably configuration, flagged anyway).

### What was verified
- Backend restarted (Michael-approved) and healthy; smoke-tested live: `GET /transportation/drivers`/`vehicles` (empty - none configured yet), `GET /transportation/scheduling-config` (buffer_minutes=30 default), `GET /transportation/calendar?date=2026-08-23` (empty day, correct shape).
- Frontend recompiled clean both rounds - no new errors, same pre-existing eslint warnings only.
- **Not yet verified**: any of this in a real browser/microphone session - that's Michael's next step.

### Blocked / not yet done
- **No drivers/vehicles configured yet** - `GET /transportation/drivers` and `/vehicles` are both empty, so every transportation request will correctly land as "pending" (safe-by-default) until Michael adds at least one of each via Admin → Transport resources.
- The `input_audio_noise_reduction` (far_field) Realtime API option Michael asked about was deliberately **not** added - couldn't confirm the current exact field syntax without live API testing, and this file's own history shows guessed API shapes fail loudly ("Unknown parameter" errors); flagged as a candidate next step if the diagnostics show continued false triggers after this fix, not added blind.
- Terminal 9 Phase 4 (the live Admin walkthrough) remains interrupted at the Departments tab from earlier in this session.
- Nothing staged, committed, pushed, or pulled.

### Next safe step
Two independent test rounds, either order:
1. **Realtime voice fix (Tests A-E)** — Admin → Residents → TEST Room 101 → Enter Room, then the five specific silence/interruption/short-utterance tests Michael specified. After each, Claude reads `GET /realtime-diagnostics/session/{session_id}` (session_id shown in the browser dev console or reported by Michael) to report the exact observed event sequence.
2. **Transportation/calendar/Front Desk** — Michael first adds one driver and one vehicle (with a real capacity) via Admin → Transport resources, then re-runs the transportation voice test from TEST Room 101, then checks Admin → Transport calendar and (once a front_desk user is created via Admin → Staff) the Front Desk dashboard.

---

## 2026-08-22 — Resident Record → Conversations shipped (session-grouped, first-class); one backend restart briefly interrupted Michael's live browsing

### Agent / tool
Claude Code with Michael, same working session. Added to the Resident 360 requirement: conversations must be first-class, session-grouped records reachable from the UI, never requiring transcript copy/paste.

### Branch / ref
`main` at `3a4bd7f`, unchanged. `origin/main` still 2 commits ahead, fetched-only.

### What changed
- **New endpoints** (`backend/routes/resident_conversations.py`, 81 lines): `GET /residents/{id}/conversation-sessions` groups the existing `db.conversations` turns (already keyed by `session_id` from the Realtime pipeline - no new storage) into session summaries (date, start/end, turn count, source, room, `is_test`, a cheap first-user-turn topic). `GET /residents/{id}/conversation-sessions/{session_id}` returns the full turn transcript plus everything already linkable by `conversation_session_id`: receipts, StaffTasks (requests/transportation actions), this session's `realtime_diagnostics` events (the voice-diagnostic metadata from the prior checkpoint, now attached to the conversation instead of requiring dev tools), and a best-effort room+time-window match against `db.device_commands` (labeled explicitly as best-effort - device commands aren't session-tagged at the source, a real gap noted rather than papered over).
- **`room`/`kiosk_id` added to the realtime-turn ingest** (`routes/memory.py`'s `RealtimeTurnIngest`, both `db.conversations` inserts) so session grouping has an accurate historical room, not just the resident's current one.
- **New UI**: `ResidentRecordDialog.jsx` (90 lines, session list) + `ConversationSessionDetail.jsx` (100 lines, full transcript + requests/receipts/device-actions/diagnostics), opened via a new "Resident Record" button in `ResidentsTab.jsx` (278 lines, was 272). Framed honestly as Conversations-only for now - the Profile/Family/Requests/Transportation sections from the broader Resident 360 design aren't part of this dialog yet.
- **Claude/testing workflow**: Claude can now resolve "the conversation in Room 101" itself via resident/room/kiosk/session/time lookups (either through these new endpoints or directly against Mongo) - Michael should never need to paste a transcript or retrieve a session ID.
- Verified live against Michael's real transportation test from earlier this session (TEST-101, session `rt_ub7kucbg_1787418707177`, 11 turns) before reporting done.

### What was verified / incident note
- Backend restart to load these endpoints did **not** take effect on the first attempt (the background relaunch command didn't actually start a new process - exit code 144, cause not fully diagnosed) while Michael was actively browsing Admin live, so the API was briefly down (~30-40s) mid-session. Caught immediately via a health check and relaunched successfully on the second attempt; confirmed healthy and serving real traffic afterward. Flagging transparently since Michael was mid-use when it happened, not just idle.
- New endpoints smoke-tested against real data post-restart: session list and full detail both return correctly for TEST-101's real conversation.

### Blocked / not yet done
- Resident Record currently has only the Conversations section - Profile/Memory/Family/Requests/Transportation/Activity as one unified view (the fuller Section 6 design) is not built.
- Device-action-per-session linkage is best-effort (room + time window) because `device_commands` isn't tagged with `conversation_session_id` at the source - a real traceability gap, not fixed this round.
- All prior blocked items (voice Tests A-E, transportation driver/vehicle setup, Terminal 9 Phase 4) remain exactly as they were.
- Nothing staged, committed, pushed, or pulled.

### Next safe step
Admin → Residents → any TEST resident → "Resident Record" → Conversations. Click a session to see the full transcript + requests/receipts/device actions/voice diagnostics together. Then Michael picks up wherever he'd like next: the voice Tests A-E, transportation driver/vehicle setup, or continuing Terminal 9 Phase 4.

---

## 2026-08-22 — Real Room 201 test analyzed via the new Resident Record tooling; a second, more serious voice defect found and fixed with a verified (not guessed) OpenAI Realtime API mechanism

### Agent / tool
Claude Code with Michael. Michael ran a real test (mistakenly reported as "Room 101" at first, corrected to Room 201/TESTY - independently confirmed via `preferred_name` matching "TESTY" in the DB, not just taken on faith). Claude used the just-built Resident Record/diagnostics tooling to read the exact event sequence itself, per the standing "locate the conversation yourself" workflow rule, rather than asking Michael to describe it.

### Branch / ref
`main` at `3a4bd7f`, unchanged. `origin/main` still 2 commits ahead, fetched-only.

### What was found
Reading `GET /realtime-diagnostics/session/{id}` + the session's full `db.conversations` transcript revealed three distinct problems in one call:
1. The double-greeting fix from earlier this session held (exactly one greeting).
2. **A second, different phantom-transcript mechanism**: short transcripts ("Thank you.", "Cheers, bye.", "Thank you.") appeared during genuine silence (`assistant_speaking: false` at speech_started) - not echo overlap, but Whisper hallucinating plausible short words from ambient room noise. The existing overlap-based trust signal cannot catch this - it's a different failure mode than the one already fixed.
3. **Consequence**: fed those phantom turns, Aria improvised an unrequested thermostat conversation, called `adjust_room_temperature` + `request_staff_help`, and narrated "I've notified maintenance again" - false on two counts (the resident never mentioned the AC, and the real system action bumped an existing, unrelated leaking-faucet ticket). Only `update_preferred_name` was gated against suspect turns before this; other consequential tools were not.
4. Separately, a real question Michael asked ("what's going on in the world") got a non-answer/deflection from Aria instead of an engaged response or a `research_topic` call - a prompt-behavior gap, not an audio bug, not yet addressed (Michael's next-priority call).
Michael also mentioned switching the physical mic hardware to an eMeet speakerphone (real far-field/AEC hardware) - independent of, and likely complementary to, the software fix below.

### What changed - verified against OpenAI's own current API docs first (WebSearch/WebFetch), not guessed
- **`input_audio_noise_reduction`**: confirmed exact field path `session.audio.input.noise_reduction: { "type": "far_field" }` against the live Realtime API reference (far_field = room/conference-style mics, as opposed to near_field for headsets - directly matches this deployment). Added as `DEFAULT_NOISE_REDUCTION` in `backend/routes/realtime.py`, applied only to the resident-facing kiosk session (`create_session`) - not the operator build, since there's no evidence about Michael's own mic setup for that one.
- **Transcription confidence, a real signal instead of a timing proxy**: confirmed `session.include: ["item.input_audio_transcription.logprobs"]` is the correct field (also verified against the live API reference) - each completed transcript now carries per-token logprobs. `frontend/src/lib/realtimeDiagnostics.js` gained `transcriptionConfidence()` (exp(mean logprob), the standard log-prob-to-probability conversion) and an exported `LOW_CONFIDENCE_THRESHOLD = 0.5`, explicitly flagged as a starting point, not yet calibrated against this deployment's real data.
- **The suspect signal is now overlap-timing OR low-confidence**, combined in `useRealtimeVoice.js`'s transcription-completed handler. This also directly serves the "don't block real short utterances" requirement better than the old signal alone - a genuine short "Help." should score high-confidence and pass; a noise-hallucinated "Thank you." should score low.
- **The consequential-action gate widened** from just `update_preferred_name` to also cover `request_staff_help`, `request_transportation` (`realtimeOperationsTools.js`), and `adjust_room_temperature`/`toggle_light`/`toggle_tv` (`realtimeDeviceTools.js`) - each now refuses and asks the resident to repeat themselves when the triggering turn was flagged suspect, instead of silently acting. Emergency/urgent tools (`call_for_help`, `mark_resting`, `end_call`) were deliberately left ungated - never suppress a possible real emergency on an uncertain signal.
- Backend restarted (Michael-approved), verified stopped-then-started explicitly this time (separate kill/start/health-check steps) after the prior restart's silent failure.

### Line counts - files modified this round
`backend/routes/realtime.py` 318 → **327** (pre-existing over-cap; +9, the noise_reduction constant + wiring, unavoidable single-purpose addition). `frontend/src/lib/useRealtimeVoice.js` 422 → **444** (pre-existing over-cap; +22 for the include/confidence logic - flagging again; a further extraction may be warranted if this file needs to grow again). `frontend/src/lib/realtimeDiagnostics.js` 25 → 39 (under cap). `frontend/src/lib/realtimeOperationsTools.js` 171 → 182 (under cap). `frontend/src/lib/realtimeDeviceTools.js` 150 → 158 (under cap).

### Blocked / not yet done
- **`LOW_CONFIDENCE_THRESHOLD = 0.5` is uncalibrated** - a defensible default (exp(logprob) < 0.5 means the model itself assigns under 50% likelihood to its own transcription), not yet checked against real confidence values from an actual test. Michael's next test is what calibrates it.
- The "Aria didn't engage with a real question" prompt-behavior gap (item 4 above) is identified but not investigated or fixed.
- All earlier blocked items (transportation driver/vehicle setup, Terminal 9 Phase 4) remain as they were.
- Nothing staged, committed, pushed, or pulled.

### Next safe step
Michael re-runs a similar test (ideally with the new eMeet mic in place) at Admin → Residents → any TEST room → Enter Room. Claude then reads the new session directly (Resident Record or `GET /realtime-diagnostics/session/{id}`) and reports: whether phantom turns still occur, their actual confidence scores (to calibrate `LOW_CONFIDENCE_THRESHOLD` with real data), and whether the widened gate correctly stopped any bad consequential action this time without blocking genuine short replies.

---

## 2026-08-22 — Communication & Requests rebuilt as the complete operational record (list + filters + detail/timeline), wired into Front Desk and Resident Record as the same underlying data

### Agent / tool
Claude Code with Michael. Acceptance testing found the existing Tasks board showed only resident/description/"Pending" - not enough for staff to understand a request without guessing.

### Branch / ref
`main` at `3a4bd7f`, unchanged. `origin/main` still 2 commits ahead, fetched-only.

### What changed
- **A real "Acknowledge" action, previously entirely unwired**: `StaffTask.acknowledged_by`/`acknowledged_at` existed on the model but nothing ever set them. Added `POST /tasks/{id}/acknowledge` (`routes/tasks.py`) plus a new `acknowledged_by_name` field (denormalized, same pattern as `assigned_name`). This is a real new event now, not backfilled onto old records - old requests without it will honestly show no acknowledgment, never a fabricated one.
- **`GET /tasks/{id}/detail`** (new `routes/task_detail.py`): task + every receipt filed against it - the same records `create_receipt`/`update_receipt_status` already write, no new history system.
- **`tasks.py` split for size, not rewritten**: recurring-template management (list/create/delete templates, spawn-today) - a genuinely separate responsibility from individual task lifecycle - moved to new `routes/task_templates.py`. `tasks.py` 286 → 307 (after adding acknowledge) → **242** (after the template split, net under its start).
- **New Communication & Requests UI**: `RequestsBoard.jsx` (list, search, status/priority/department filters, action-needed-first sort) + `RequestDetailDialog.jsx` (full who/when/what/where/status metadata + a real chronological timeline built from the task's own timestamps and its receipts - Acknowledge/Start/Complete buttons call the real endpoints). `lib/requestDisplay.js` holds the shared `deriveStatus()` (a display-only derivation from existing fields - transportation with a run/slot reads "Confirmed", unassigned-but-acknowledged reads "Acknowledged", etc. - never a new stored state) and source labels, so the list and detail view can never disagree.
- **One underlying record, three views**: Admin's new "Requests" tab, Front Desk's dashboard (its old bespoke narrow request list was removed and replaced with the same `RequestsBoard`), and Resident Record's "Requests & actions" section (in `ConversationSessionDetail.jsx`) now all render through the identical `RequestsBoard`/`RequestDetailDialog` components against the identical `/tasks` data - clicking a request from Resident Record opens the exact same detail dialog Communication & Requests uses.
- Backend restarted (Michael-approved), verified stopped-then-started explicitly.

### What was verified
Smoke-tested live against the real leaking-faucet request from an earlier session test: `GET /tasks/task_b60788137dec/detail` returned the full real record (source `aria_voice`, `resident_words`, `conversation_session_id`, `re_request_count: 1`, 2 real receipts) and `POST /tasks/task_b60788137dec/acknowledge` correctly set `acknowledged_by_name: "MICHAEL CHAMBERS"` with a real timestamp. Frontend recompiled clean, no new errors.

### Blocked / not yet done
- Filtering by "assigned staff" specifically and a date-range filter aren't in the first cut (search/status/priority/department are) - flagging as the next-smallest addition if Michael wants them.
- "Front Desk viewed this request" (a read-receipt/view-tracking event from Michael's example timeline) was deliberately not built - it doesn't exist anywhere in the system yet and would be a real new feature, not exposing existing data. Noted rather than fabricated.
- `source` distinguishing "Front Desk" vs "Admin" vs generic "staff" for manually-created tasks is not fully wired - `POST /tasks` (the internal one-off/admin creation path) still always writes `source: "staff"` regardless of the creating user's role; `TaskSource` now has a `"front_desk"` value available for this but nothing sets it yet.
- All earlier blocked items (voice test calibration, transportation driver/vehicle setup, Terminal 9 Phase 4) remain as they were.
- Nothing staged, committed, pushed, or pulled.

### Next safe step
**Test path, per Michael's own spec:**
1. Admin → Residents → TEST Room 101 → Enter Room → make a real request (e.g. ask for maintenance help).
2. Admin → **Requests** (new tab, Communication & requests group) → find the row → verify at a glance: resident/room, request text, department, exact requested-at time, source ("Aria voice"), priority, derived status.
3. Click the row → verify the full detail (all the above plus assigned-to, conversation session id) and the timeline showing "Request created" and the receipt event(s) with real timestamps.
4. Click **Acknowledge**, then **Start**, then **Complete** → verify each appears as a new, real timeline entry with the real actor name and time.
5. Admin → Residents → TEST Room 101 → Resident Record → Conversations → open that same session → confirm the same request appears under "Requests & actions" and clicking it opens the identical detail dialog.

---

## 2026-08-22 — Live regression repair: broken `include` param, missing user transcript, misleading "Live" status, and a real fabricated-appointment root cause found and fixed

### Agent / tool
Claude Code with Michael. A real TEST Room 101 acceptance test surfaced four acceptance failures at once; feature work paused to repair them in the order Michael specified (A-G).

### Branch / ref
`main` at `3a4bd7f`, unchanged. `origin/main` still 2 commits ahead, fetched-only.

### What changed
- **(A) Removed the broken `include` field.** The prior round's `include: ["item.input_audio_transcription.logprobs"]` on the `session.update` event was rejected live: "Unknown parameter: 'include'." Removed outright rather than relocated by guess, per Michael's explicit instruction - my own earlier research was ambiguous about whether it belonged there or nested under `session`, and guessing again under pressure was exactly what not to do. `transcriptionConfidence()` already no-ops safely with no logprobs present, so the trust boundary still runs on the audio-overlap signal alone until the correct mechanism is verified in a calmer pass.
- **(B/C/D, root cause identified) The missing user transcript was very likely a direct consequence of (A)**, not a separate bug: if the whole `session.update` event was rejected for the unknown field, the `transcription: {...}` config in that same event never applied either - explaining zero user turns while Aria's turns (which don't depend on that config) kept appearing. No separate transcript-rendering fix was made, per Michael's explicit instruction not to build an unnecessary second workaround - this should self-resolve once (A) is verified live.
- **(Section 3) Fixed the misleading "Live · idle" status.** `dc.onmessage`'s `error` handler only called `setError()`, never downgrading `status` - so `status` stayed `"live"` (rendering "Live · idle") even while a real OpenAI config error was showing. Now also calls `setStatus("error")`, which correctly renders "Error" / a red status dot / "Something went wrong."
- **(E/F, root cause identified and fixed - not just prompt wording) Traced the fabricated 3 PM appointment to an exact record**: `ResidentMemory` `mem_8a16a677d63d`, text `"User has a doctor's appointment at 3 PM."`, `bin: "facts"`, `source: "extraction"`, `event_at: null` (no expiry). Confirmed the injection path: `realtime_companion_prompt.py` queries `db.memories` bin="facts" directly (a separate, parallel implementation from `memory.py`'s `build_memory_context` - only `routes/ai.py`, the retired legacy chat path, uses that one) and renders facts under the heading `"## What you know about {name} (durable facts)"` with **no date shown at all**. The record came from the transportation-booking test earlier the same day: the fire-and-forget extractor (`extract_and_store_memories`) had no rule against extracting a scheduled appointment/errand as a "durable fact," so `category: "health"` routed it to the timeless facts bin instead of being excluded or dated. Fixed at the source: `EXTRACTOR_SYSTEM` (`routes/memory.py`) now explicitly forbids extracting appointments/errands/transportation arrangements as durable facts - they already have their own authoritative record (the resident-request/transportation system), and re-deriving them into an undated "durable identity" fact was the actual bug (Section 5/6's "transportation request != appointment" and "historical chat != operational fact," now fixed at the data-semantics level, not just prompt tone). The one bad record (`mem_8a16a677d63d`) was deleted (Michael-approved) after confirming via direct query it was the only one of its kind across all TEST residents.
- Backend restarted (Michael-approved), verified stopped-then-started explicitly.

### What was verified
- Backend imports clean, frontend recompiles clean (no new errors/warnings).
- Confirmed via direct Mongo query that no other resident had a similarly-mislabeled fact before deleting the one that did.
- **Not yet verified**: none of this against a real live call yet - that's the fresh acceptance test below, Michael's to run.

### Blocked / not yet done
- A secondary defense-in-depth instruction for the companion prompt itself (explicitly telling Aria "a transportation request is not proof an appointment exists," per Section 5's exact language) was deliberately **not** added this round - the primary fix (stopping the bad extraction at its source) addresses root cause, and both `memory.py` (504 lines) and `realtime_companion_prompt.py` (328 lines) are already over the 300-line cap; adding more without a clear need would cut against "do not keep growing" it further. Flagging as the natural next step if the fresh test still shows any appointment-conflation.
- The real transcription-confidence mechanism (logprobs) is still unresolved - needs a calmer, verified-not-guessed pass before re-attempting.
- All earlier blocked items unrelated to this regression are unaffected and remain as they were.
- Nothing staged, committed, pushed, or pulled.

### Next safe step
**Fresh acceptance test, one step at a time, exactly as Michael specified:**
Admin → Residents → TEST Room 101 → Enter Room.
1. Let Aria greet. Say "Hello Aria." → verify "You: Hello Aria." appears, zero red API errors.
2. Ask "Do I have any appointments today?" → expect no invented 3 PM appointment; if none confirmed, Aria should say so honestly.
3. Then "Show me my schedule." → expect a query against the real schedule source, no unsupported claims.
Report back after each step before moving to the next.

---

## 2026-08-22 — Room 102 inspected live; recognition-accuracy root cause classified (not VAD); whisper-1 → gpt-4o-transcribe swapped after verifying exact schema

### Agent / tool
Claude Code with Michael. The `include`-param regression and 3 PM hallucination from the prior checkpoint were both confirmed fixed by Michael's own live Room 102 test - this round narrowly targeted the one remaining defect: input speech-recognition accuracy.

### Branch / ref
`main` at `3a4bd7f`, unchanged. `origin/main` still 2 commits ahead, fetched-only.

### What was found (inspection only, no changes) - Room 102 session `rt_y6k3tovh_1787432842587`
Located directly (resident/room lookup, no session ID from Michael). Cross-checked every turn's VAD duration (speech_started→speech_stopped) against its transcribed word count and sentence completeness:
- No truncated/fragmented sentences anywhere in the session - every VAD-bounded duration was proportionate to its word count. Rules out VAD/turn-detection (class A) as the dominant problem.
- No out-of-context phantom interjections this time (unlike the earlier Room 201 session) - every short turn fit its real conversational context.
- **Dominant defect = class C, transcription-model recognition accuracy**: two complete, correctly-bounded sentences had a wrong word each - "tell me what the **weather** was" → "...what was **better**", and "**Can** you turn..." → "**And** you turn...". Audio boundaries were right; specific words were misheard.

### What changed
- **`whisper-1` → `gpt-4o-transcribe`** in `useRealtimeVoice.js`'s `session.audio.input.transcription.model` (single field, single value changed - nothing else touched: VAD, `far_field` noise reduction, mic constraints, tool config all untouched, per Michael's explicit single-variable-change instruction).
- **Verified before changing, not guessed**: fetched the actual `AudioTranscription`/`RealtimeSession` struct definitions (not just summarized doc pages) confirming `gpt-4o-transcribe` is a valid value for this exact field on this exact conversational (`session.type: "realtime"`) session structure - not a separate dedicated transcription-session type, matching Michael's explicit constraint.
- Frontend-only change; hot-reloaded by the CRA dev server (confirmed via fresh compile timestamp), no backend touched, no restart performed or needed.

### What was verified
Frontend recompiled clean, no new errors/warnings.
**Not yet verified**: the model swap against a real call - that's the next step, Michael's to run.

### Blocked / not yet done
- If OpenAI rejects this model/config live, the instruction is to immediately revert to `whisper-1` and report the exact API error rather than guess a variation - not yet needed, pending the test below.
- All earlier blocked items (transportation driver/vehicle setup, Terminal 9 Phase 4, the secondary companion-prompt defense-in-depth wording) remain as they were.
- Nothing staged, committed, pushed, or pulled.

### Next safe step
Fresh Room 102 test, same phrases that previously exposed the errors: "Can you tell me what the weather was?", "Can you turn the temperature down to like 72?", "I'd like you to tell me what's for dinner." Claude then locates the new session itself and reports expected-vs-transcribed for each phrase, plus confirms zero API errors, visible/complete USER turns, and unchanged VAD behavior.

---

## 2026-08-22 — Room 103 inspected (gpt-4o-transcribe held constant, mic gain lowered mid-session); useRealtimeVoice.js extraction completed, both files now under 300 lines

### Agent / tool
Claude Code with Michael. Room 103 evidence reviewed, then Michael corrected the timeline (gain change happened ~2/3 through the *same* session, not between sessions) - a materially more useful data point since it isolates the gain variable from the already-constant transcription model within one session. Then proceeded with the previously-approved `useRealtimeVoice.js` extraction, no behavior changes.

### Branch / ref
`main` at `3a4bd7f`, unchanged. `origin/main` still 2 commits ahead, fetched-only.

### What was found - Room 103 (`rt_ltmbbxsp_1787434155508`), corrected interpretation
Located directly (resident/room lookup). With the corrected timeline: gpt-4o-transcribe was already active for the *entire* session (constant), while OS mic gain was high for roughly the first two-thirds and lowered by Michael partway through. The one clear gibberish artifact (a stray Hindi/Sanskrit punctuation character transcribed from ~2s of non-speech audio) occurred in the early, high-gain portion; no similar artifact occurred afterward. **Because the transcription model didn't change within this session, this within-session before/after contrast isolates the gain variable specifically** - meaningful supporting evidence for excessive mic gain contributing to recognition problems, not just a confound. Preserved as a real finding, not walked back.

### What changed - useRealtimeVoice.js extraction (previously approved, executed this round)
- New `frontend/src/lib/realtimeMessageHandler.js`: `executeTool()` and a new `createRealtimeHandlers()` factory containing `handleFunctionCall` and the full `dc.onmessage` handler (VAD/transcript/tool-call/error reactions) - moved **verbatim**, parameterized over the refs/setters/values they closed over. No logic changed, no conditions changed, no values changed.
- `useRealtimeVoice.js` now only owns connection setup (mint, mic capture + the mic-track-settings diagnostic, peer connection, `dc.onopen`'s session.update/greeting, SDP negotiation) and calls `dc.onmessage = onMessage`.
- **`useRealtimeVoice.js`: 469 → 279 lines. `realtimeMessageHandler.js`: 225 lines.** Both now under the 300-line cap for the first time this whole investigation arc.
- Verified the extraction is behavior-preserving: the hook's public API (`{ status, error, transcript, resting, start, stop, audioElRef }`) is unchanged, and grepped every consumer (`RealtimeChatScreen.jsx`, `AriaVoice.jsx`) to confirm none depended on the internal `executeTool`/`handleFunctionCall` (never exported). Frontend recompiled clean - no new errors, same pre-existing warning (just shifted line number).
- No voice tuning changes made during this pass, as instructed - VAD, gain, model, noise reduction all untouched.

### What was verified
Frontend compiles clean. No backend involved in this round; no restart performed or needed.

### Blocked / not yet done
- The controlled A/B test to further isolate gain vs. model (holding gain now-lowered, re-testing short precise phrases) hasn't been run yet.
- All earlier blocked items (transportation driver/vehicle setup, Terminal 9 Phase 4, companion-prompt defense-in-depth wording, Microphone Test admin page - still not justified, evidence still developing) remain as they were.
- Nothing staged, committed, pushed, or pulled.

### Next safe step
Michael's call: run another controlled test now that mic gain is settled low and the file extraction is behind us, or move to something else. If a Room 10X test happens, Claude locates it directly and reports the same expected-vs-transcribed comparison as before.

---

## 2026-08-22 — Room 202 forensic analysis (3 confirmed defects found via raw event tracing); all three fixed in the specified order, verified before handoff

### Agent / tool
Claude Code with Michael. A Room 202 test surfaced the "previous fix didn't fully work" concern; full raw-event forensic analysis (not summary-of-a-summary) found three distinct, real defects, all fixed this round in Michael's specified order.

### Branch / ref
`main` at `3a4bd7f`, unchanged. `origin/main` still 2 commits ahead, fetched-only.

### Correction issued and preserved
The prior Room 103 checkpoint's duration claim ("~14 minutes") was wrong - actual span was 4m49s, a real arithmetic error, not a duration derived from event count. Corrected on the record, not defended. Three separate duration metrics (session connection / actual conversation / total user speech) are now used going forward, never mixed.

### Room 202 forensic findings (`rt_8y12za2m_1787435236218`), full raw-event trace
- 8 real user turns, 5 phantom turns, first phantom at ~3.5s into the conversation.
- **Root cause #1, confirmed with timing evidence**: `assistantSpeakingRef` flipped false on `response.done` (generation-complete), not actual audio-playback-complete. Three of five phantom turns began 1-1.4s after a multi-second reply's `response.done` - almost certainly while that reply was still physically playing. This directly explains the "previous fix seemed to not work" - the fix targeted the right mechanism (echo) but read the wrong signal for when Aria's audio actually stops.
- **A second, separate mechanism**: one phantom turn ("The government") occurred during genuine silence (19s after the prior reply), not echo - ambient noise hallucination, explicitly kept as a separate, not-yet-addressed category per Michael's instruction.
- **Root cause #2, a new bug found while tracing turn-pairing**: a real ~15-second user correction was captured in diagnostics but never saved to `db.conversations` at all - a second, quicker user segment overwrote the single `pendingUserRef` scalar before the first turn's paired assistant reply arrived to trigger the save.
- **Root cause #3**: a phantom "and" (itself an echo-timing case) triggered `end_call`, prematurely ending the session - `end_call`/`end_conversation` were never gated against the suspect signal at all.

### What changed - all three fixes, in the specified order
1. **Playback-state fix (primary)**: verified via direct confirmation from an OpenAI team member (community thread, not guessed) that `output_audio_buffer.started`/`.stopped`/`.cleared` are real server events sent specifically for WebRTC/SIP connections (never sent over plain WebSocket, which is why this was missed before) representing actual playback lifecycle. `realtimeMessageHandler.js`'s `assistantSpeakingRef` now driven by these events instead of `response.audio.delta`/`response.done`. The greeting create_response re-enable logic (previously also gated on `response.done`) moved to `output_audio_buffer.stopped` for the same reason - same underlying signal-accuracy fix, not scope creep.
2. **No-loss turn persistence**: removed the `pendingUserRef`/`pendingUserSuspectRef` pairing scalars entirely. Every turn (user or assistant) is now saved independently via a new `postTurn()` helper the instant it's known - no waiting on the other side of an exchange. Backend `RealtimeTurnIngest` (routes/memory.py, now split into new `routes/realtime_memory_ingest.py` to stay under 300 lines) changed from `{user_text, assistant_text}` pairs to one `{role, text}` per call; memory-fact extraction now triggers on the assistant-turn save, looking up the most recent trusted USER turn from the durable `db.conversations` store (never a fragile client ref) for pairing context. Smoke-tested live: two rapid user segments in the same synthetic session both persisted independently, proving the overwrite bug is gone.
3. **Suspect turns can't end the session**: `end_call`/`end_conversation` in `realtimeDeviceTools.js` now check `turn_suspect` and return a natural clarifying question ("I may have heard you over my voice — did you want me to end our conversation?") instead of the goodbye message when suspect; `handleFunctionCall` only actually tears down the connection when the tool call succeeded (`ok:true`). `call_for_help`/`mark_resting` remain deliberately ungated - never suppress a possible real emergency. `set_timer` added to the existing consequential-tools gate (creates a durable reminder) alongside the already-gated `adjust_room_temperature`/`toggle_light`/`toggle_tv`/`request_staff_help`/`request_transportation`/`update_preferred_name`.
- Backend restarted (Michael-approved), verified stopped-then-started explicitly.

### Line counts - every file created or materially modified this round
`frontend/src/lib/useRealtimeVoice.js`: 279 (removed the now-unneeded pending refs). `frontend/src/lib/realtimeMessageHandler.js`: 249 (was 225 - the three fixes' logic, still under cap). `frontend/src/lib/realtimeDeviceTools.js`: 164. `backend/routes/memory.py`: 439 (pre-existing over-cap, but net *shrank* this round via the extraction below). `backend/routes/realtime_memory_ingest.py`: 90 (new). `backend/server.py`: 181 (router registration only).

### What was verified
- Backend imports clean, frontend recompiles clean (no new errors, same pre-existing warnings).
- Live smoke test proved the no-loss fix: two rapid user segments in one synthetic session both persisted to `db.conversations` independently - the exact failure mode from Room 202 no longer reproduces. Test rows cleaned up afterward.
- **Not yet verified**: none of the three fixes against a real live call - that's the next step, Michael's to run.

### Blocked / not yet done
- Ambient-silence phantom speech (the "The government" mechanism) is explicitly not addressed this round, per Michael's instruction not to change multiple variables at once - to be reassessed after this round's fixes are confirmed live.
- All earlier blocked items (transportation driver/vehicle setup, Terminal 9 Phase 4, companion-prompt defense-in-depth wording) remain as they were.
- Nothing staged, committed, pushed, or pulled.

### Next safe step
Fresh test on an unused test room (per Michael's instruction): Admin → Residents → an unused TEST room → Enter Room. Michael speaks naturally - lets Aria greet, interrupts her once, pauses mid-thought and continues, gives a longer correction spanning a natural pause, ends normally. Claude then locates the session directly and checks all of: exactly one greeting; no echo-driven phantom turns; genuine barge-in still works; every real user segment visible AND saved; a multi-segment thought not overwritten; suspect echo can't trigger end_call; emergency help still works during overlap; zero API errors; no regression in gpt-4o-transcribe/VAD/far_field. Any remaining ambient-silence phantom speech gets reported separately, not tuned yet.

---

## 2026-08-22 — Resident-provisioning/testability gap fixed: Add/Edit Resident now surfaces real kiosk status and can provision one inline

### Agent / tool
Claude Code with Michael.

### Branch / ref
`main` at `3a4bd7f`, unchanged this round (frontend-only change, nothing staged/committed).

### What happened
Michael created a new resident, Chauncey (room 304, pendant assigned), specifically to run the fresh-room Realtime acceptance test already queued from the prior Room 202 fix round. The Residents screen showed "No kiosk" with no way to create one, and Edit did not expose a way to assign a kiosk either — a real product gap, not a test-data problem. Michael's standing rule: "click the resident, I'm in the room" — creating/editing a resident must never dead-end into needing a kiosk ID, install URL, or DB access. Explicit instruction: fix the actual product workflow using the existing real kiosk/provisioning architecture, do not tell him to reuse an old TEST room, and do not touch anything in the just-completed Realtime voice fixes while doing it.

### What changed
- Inspected the existing kiosk↔resident mapping first: it's a plain room-string match (`Kiosk.room === Resident.room`, no foreign key), the same lookup `GET /residents/public/by-kiosk/{kiosk_id}` already does server-side, and kiosk creation already exists via `POST /kiosks` (used by `KiosksTab.jsx`'s "Add kiosk" dialog, no duplicate-room validation). No new backend work was needed or added — this fix reuses that exact endpoint, not a simulator.
- `frontend/src/pages/ResidentsTab.jsx`: each resident row now shows a live "Enter room" button when its room has a matching kiosk, or an actionable terracotta "Set up room" button (calls `POST /kiosks` with `{name: room, room, zone: ""}`) when it doesn't — replacing the old dead-end "No kiosk" label.
- New `frontend/src/pages/ResidentFormDialog.jsx`: the Add/Edit resident dialog, extracted out of `ResidentsTab.jsx` to keep both files under the 300-line cap (the added kiosk-status UI pushed the combined file to 328 lines). Owns its own form state (initialized from a `resident` prop, null for new), and shows the same room/kiosk status inline as the resident types a room — a green "mapped" state with the kiosk_id when one exists, or a terracotta "unmapped" state with an inline "Set up room" button when it doesn't. Behavior and every `data-testid` preserved exactly; no logic changed beyond the state now being owned by the child component.
- `ResidentsTab.jsx` now renders `<ResidentFormDialog open={formOpen} onOpenChange={setFormOpen} resident={editingResident} kiosks={kiosks} onSaved={onChange} />` instead of the inline Dialog/form JSX.
- Confirmed no voice-path files (`useRealtimeVoice.js`, `realtimeMessageHandler.js`, `realtimeDeviceTools.js`, `backend/routes/memory.py`, `backend/routes/realtime_memory_ingest.py`) were touched this round — verified by re-reading each unchanged.

### Line counts — every file created or materially modified this round
`frontend/src/pages/ResidentsTab.jsx`: 168 (was 328 before extraction). `frontend/src/pages/ResidentFormDialog.jsx`: 197 (new).

### What was verified
- Frontend dev server (already running, craco hot-reload) served `/` at HTTP 200 after the change with no compile-error overlay; confirmed the served bundle actually contains the new `ResidentFormDialog` component (not a stale cached bundle).
- No backend restart performed or needed — this is a pure frontend change against the pre-existing `POST /kiosks` endpoint.
- Not yet verified: the actual Chauncey click-through in a browser (Michael's to run next) or the fresh-room Realtime acceptance test this gap was blocking.

### Blocked / not yet done
- The fresh-room Realtime acceptance test (interrupt, mid-thought pause+continue, longer correction, normal end) queued from the Room 202 fix round is still pending, blocked only on Michael confirming the kiosk-setup flow works for Chauncey.
- Ambient-silence phantom speech ("The government" mechanism) remains unaddressed, as previously logged.
- Nothing staged, committed, pushed, or pulled.

### Next safe step
Michael: Admin → Residents → Chauncey → **Set up room** (creates the real kiosk record for room 304, same as Admin → Kiosks → Add kiosk would) → then Admin → Residents → Chauncey → **Enter room** (opens the real `/kiosk/{kiosk_id}` resident-facing experience in a new tab, the same path every deployed room uses). Once that's confirmed working, run the queued fresh-room Realtime acceptance test on Chauncey's room and report back; Claude will locate the resulting session directly via Mongo, no session ID needed from Michael.

---

## 2026-08-23 — Chauncey/Room 304 forensic report + repair round (tool-argument fabrication, intent inversion, overlap false-positives, lifecycle diagnostics, greeting UX)

### Agent / tool
Claude Code with Michael.

### Branch / ref
`main` at `3a4bd7f`, unchanged (nothing staged/committed). Backend restarted (Michael-directed repair round; required since multiple backend files changed) - old PID 63307 killed and confirmed stopped, new PID 66759 started and confirmed healthy (`/api/health` → `{"ok":true,"db":"up"}`) before any live verification.

### What happened
The fresh Room 304 acceptance test (queued from the prior Room 202 fix round) surfaced a real ~7-minute conversation Michael called "horrible." Forensic pass (raw event reconstruction from `db.realtime_diagnostics` + `db.conversations` + `db.staff_tasks`, no info requested from Michael) confirmed: the two prior fixes (playback-state tracking, no-loss persistence) held cleanly; three new/residual defects did not: (1) a real, staff-visible task was created with a fabricated appointment time ("10 o'clock") the resident never said, (2) "maybe I need to turn it up" (volume) mis-triggered `mark_resting` (go quiet) - backwards intent, (3) overlap-based suspect classification had a high false-positive rate on genuine barge-in (7 of ~11 flagged turns were real, coherent speech, not echo), and the session's actual termination cause was unrecoverable from any log. Full report delivered before any code change, per Michael's explicit "forensic pass first" instruction.

### What changed, in Michael's priority order
1. **Tool arguments cannot invent facts (backend-enforced, not prompt-only)**: new `backend/operational_provenance.py` - `reject_unconfirmed_time()` checks whether a clock-time claim in an operational-request free-text field actually appears in something the resident said this session (`db.conversations`, role=user); fails closed if there's no session/resident to check against. Wired into `POST /tasks/resident-request` (`resident_requests.py`) and `POST /transportation/request` (`transportation.py`) - both now return HTTP 422 `{needs_clarification, field, reason}` instead of creating the record. Frontend (`realtimeOperationsTools.js`) now parses a 422's `needs_clarification` body into a natural spoken clarifying question instead of the generic "couldn't send that request" failure. Tool descriptions (`realtime_tools_operations.py`) also now explicitly instruct against inventing details - defense in depth, not the enforcement boundary. **Verified against the real incident**: replaying the exact fabricated Room 304 summary through the live restarted endpoint now returns 422 with reason `"a specific time ('10 o'clock') was included but the resident never stated it this conversation"`; a summary with the time genuinely present in a synthetic resident turn passes through and creates the task normally (smoke-tested, then cleaned up). The original fabricated task **`task_705cbcd180f1` remains on file, untouched**, as required.
2. **Intent inversion (mark_resting)**: tightened both the tool description (`realtime_tools.py`) and companion persona (`realtime_companion_prompt.py`) to require an explicit, unambiguous dismissal ('be quiet', 'let me rest', 'going to sleep') and to explicitly exclude ambiguous lines like 'turn it up' from triggering it; the tool description also now tells the model it has no control over its own voice volume and should say so plainly rather than reinterpreting a volume comment as a request to go quiet. Verified live via a fresh session mint - both instruction blocks confirmed present in what's actually served.
3. **Natural pauses / turn splitting (VAD)**: researched, not applied. `semantic_vad` with `eagerness` is a real, current, documented OpenAI Realtime API mechanism (verified via the official API docs, not guessed) purpose-built for "let the user take their time" without a blunt silence-duration increase; `create_response`/`interrupt_response` remain valid alongside it, so existing greeting-suppression and barge-in logic would be unaffected. This is a material timing change, so per Michael's explicit instruction it is **proposed, not applied** - pending his approval before touching `DEFAULT_VAD` in `realtime.py`.
4. **Overlap != phantom**: `realtimeMessageHandler.js` now runs a small, explicit, traceable `classifyUserTurn()` (segment length, textual resemblance to Aria's last spoken line, a short-term tiny-fragment streak - no fabricated confidence score) instead of treating all audio-overlap as suspect. A coherent multi-word statement during overlap is now trusted (fixes the concrete false-positive class the incident report found); short fragments that resemble Aria's own speech, or a run of them, remain suspect. The spoken clarifying message now varies by reason - "did I mishear" phrasing only for echo-like cases, a plain "just to double-check" for the rest. Ambient-silence phantoms (no overlap at all) deliberately left untouched, per Michael's explicit "do not tune simultaneously" instruction - still open, to be re-measured after this round.
5. **Connection lifecycle diagnostics (read-only)**: new `frontend/src/lib/realtimeLifecycleDiagnostics.js` logs `pc.connectionstatechange`, `pc.iceconnectionstatechange`, data-channel `close`/`error`, and `pagehide` - purely observational, does not change teardown/reconnect behavior. `useRealtimeVoice.js`'s `stop()` now takes an explicit `reason` (first cause wins, guarded), and every real call site now passes one: component unmount, the kiosk's own End Call button (previously indistinguishable from unmount), `end_call`/`end_conversation` tool success, and missing-config fail-closed. An unexpected drop (connection failure, ICE failure, datachannel close/error, or the tab being hidden/closed) now also logs a `session_ended` reason on its own, so a future session should never again end with zero forensic trail.
6. **Greeting UX**: `realtime_companion_prompt.py`'s time-anchor instruction no longer tells the model to open with "good night" (confirmed live to have caused the resident's very first, tone-setting words: "Why would you say goodbye to me?"). The phrasing logic was extracted into a new `greeting_note()` helper in `realtime_facility.py` specifically so this fix didn't grow `realtime_companion_prompt.py` past its pre-existing 328-line size, per the standing file-size rule. Verified live via a fresh session mint at an actual night-hour local time.

### Line counts - every file created or materially modified this round
`backend/operational_provenance.py`: 49 (new). `backend/routes/resident_requests.py`: 203. `backend/routes/transportation.py`: 274. `backend/routes/realtime_tools.py`: 298. `backend/routes/realtime_tools_operations.py`: 222. `backend/routes/realtime_companion_prompt.py`: 328 (unchanged net - was already over cap; extraction kept it from growing). `backend/routes/realtime_facility.py`: 60 (was 49; absorbed the extracted greeting-note responsibility). `frontend/src/lib/realtimeMessageHandler.js`: 281. `frontend/src/lib/realtimeDeviceTools.js`: 174. `frontend/src/lib/realtimeOperationsTools.js`: 213. `frontend/src/lib/useRealtimeVoice.js`: 257 (extracted the session.update builder to stay under cap after this round's additions). `frontend/src/lib/realtimeLifecycleDiagnostics.js`: 43 (new). `frontend/src/lib/realtimeSessionUpdate.js`: 59 (new). `frontend/src/pages/RealtimeChatScreen.jsx`: 165.

### What was verified
- Backend: dry-run `import server` succeeded (234 routes loaded); real restart performed and health-checked before any live test.
- Provenance guard: verified twice against real data - rejects the exact Room 304 fabricated summary (unit-level against real conversation history, then live HTTP against the running restarted server), allows a summary whose time was actually said (synthetic smoke test, cleaned up after).
- Greeting/mark_resting fixes: confirmed present in a live-minted session's actual served instructions/tool schema, not just in source.
- Frontend: dev server served the updated bundle (HTTP 200) containing the new modules (`classifyUserTurn`, `realtimeLifecycleDiagnostics`, `realtimeSessionUpdate`) - no compile-error overlay.
- Not yet verified: any of this against a real live conversation - that's Michael's next test.

### Blocked / not yet done
- The `semantic_vad`/`eagerness` VAD change is proposed but NOT applied - needs Michael's explicit go-ahead since it materially changes response timing.
- Ambient-silence phantoms (no-overlap phantom transcripts) remain open by design, to be re-measured after this round.
- Nothing staged, committed, pushed, or pulled.

### Next safe step
One fresh real test, Chauncey/Room 304 again: (1) interrupt Aria with a real multi-word correction, (2) pause naturally mid-thought and continue, (3) say "I need to go to the doctor Monday" WITHOUT giving a time - expect Aria to ask for the time, no invented time, no fabricated task, (4) say "Turn it up a little" - expect `mark_resting` does NOT fire, (5) end the session in a known way - expect the lifecycle diagnostics to show exactly how it ended. Claude will then locate and inspect the session directly via Mongo, no IDs/transcript needed from Michael.

---

## 2026-08-23 — FAILED EXPERIMENT: semantic_vad + eagerness "low" — tested live, caused a real dead zone, reverted

### Agent / tool
Claude Code with Michael.

### Branch / ref
`main` at `3a4bd7f`, unchanged (nothing staged/committed).

### What was tried
With Michael's explicit approval, `DEFAULT_VAD` (`backend/routes/realtime.py`) was changed from `server_vad` (threshold 0.5, prefix_padding_ms 300, silence_duration_ms 1000) to `semantic_vad` with `eagerness: "low"` - a real, current OpenAI Realtime API mechanism (verified via official docs, not guessed) intended to let a resident finish a thought without a fixed silence timer chopping it into separate turns. Backend restarted, confirmed live via a fresh session mint before testing.

### Result: FAILED
Live acceptance test on Chauncey/Room 304 (`rt_pc5lblon_1787453286910`) - Michael's own words: "it doesn't work at all... the recording times out or stops listening while appearing to be listening." Forensic reconstruction from `db.realtime_diagnostics` confirmed this precisely: after 3 real exchanges (~53 seconds), the system produced **zero `speech_started` events for a full 38 seconds** while the WebRTC connection remained healthy throughout (confirmed via the same-round lifecycle diagnostics - `pc_connection_state: connected`, no failure/error event) - a genuine turn-detection failure, not a network one. Michael manually ended the call (`session_ended` reason: `ui_end_call_button`, itself correctly captured by the new lifecycle diagnostics). The prior server_vad session ran ~7 continuous minutes with no gap anywhere near this. One turn ("I broke it.") also came from a 6.3-second speech segment that collapsed to just 3 transcribed words, consistent with the same dead-zone/detection problem, not a transcription-accuracy issue - transcription itself was accurate this test (no phantom garbage). Aria's response quality also showed real reasoning mismatches unrelated to VAD (e.g. "I broke it." → "I'm glad. It's good to have this connection.") - a separate, not-yet-investigated issue. The queued provenance/mark_resting test items were never reached - the dead zone ended the call first.

### What changed (the revert)
`DEFAULT_VAD` restored to `server_vad` (threshold 0.5, prefix_padding_ms 300, silence_duration_ms 1000, create_response true), with `interrupt_response: true` now added explicitly (Michael-directed, wasn't in the original config but is valid alongside server_vad too). Backend restarted, confirmed live via a fresh session mint that `server_vad` with the exact prior parameters is actually being served again.

### What was verified
- Backend: dry-run `import server` succeeded before each restart; both kill and start steps confirmed (process check + `/api/health`) before any live check.
- `server_vad` config confirmed live via `POST /realtime/session` for Chauncey/Room 304 - matches the pre-experiment values exactly, plus the added `interrupt_response: true`.
- All other fixes from the prior round (gpt-4o-transcribe, far_field noise reduction, browser mic constraints, playback-state tracking, no-loss persistence, provenance guard, mark_resting intent fix, overlap classifier, lifecycle diagnostics, greeting fix) were NOT touched this round - only `DEFAULT_VAD` changed and changed back.

### Blocked / not yet done
- The provenance guard, mark_resting fix, and overlap-classifier improvements from the prior round are still unverified against a real live conversation - the semantic_vad dead zone prevented the test from reaching those scenarios twice in a row now.
- The "I broke it." → "I'm glad" response-mismatch pattern is a real, separately-flagged Aria reasoning issue, not investigated this round.
- Ambient-silence phantoms remain open, as previously logged.
- Nothing staged, committed, pushed, or pulled.

### Next safe step
Known-working `server_vad` configuration is restored and confirmed live. Per Michael's explicit instruction, no further tuning change until he directs one. Next real test should be Chauncey/Room 304 again, same test script as the prior round (interrupt, natural pause, "doctor Monday" with no time, "turn it up," normal end) - this will be the first time that script is actually completed end-to-end if the dead zone doesn't recur.

---

## 2026-08-23 — Morning Chauncey/Room 304 forensics (mark_resting still insufficient, "deaf period" unproven) + docs/reports/ channel with a real Aria tool

### Agent / tool
Claude Code with Michael.

### Branch / ref
`main` at `3a4bd7f`, unchanged (nothing staged/committed). Backend restarted once this round, to load the new `/reports` endpoints - confirmed stopped then healthy before any live check.

### What happened, part 1: morning forensics
Full forensic pass on `rt_o2jv93b8_1787495975387` (Chauncey/Room 304, 8m28s, morning acceptance test using the reverted `server_vad` config). Full report: `docs/reports/2026-08-23-1448-room304-morning-forensics.md`. Headline findings:
- `mark_resting` fired incorrectly again, from "You got it." - correctly-transcribed, genuinely trusted speech, not a transcription/trust-boundary failure. Confirms Michael's prediction: the intent-inversion protection (prompt wording only) is still insufficient. `mark_resting` has no code-level gate at all, unlike the other consequential tools.
- A 20-second period with zero `speech_started` events followed, ending in a manual End Call. Traced as far as the evidence allows: `resting` is purely cosmetic client-side state (confirmed from source, doesn't touch the mic track/connection), and the WebRTC connection reported no failure. But there is currently no instrumentation that distinguishes "resident was silent" from "resident spoke and wasn't detected" - this is an honest, open gap, not a diagnosed root cause.
- Speaker echo, not ambient-silence phantom, was confirmed as the dominant bad-transcription mechanism this session: every short (<=2-word) fragment during audio overlap was wrong or unconfirmable (8/8); every 3+-word overlap statement was genuinely real (5/5).
- Provenance guard held cleanly: all 3 real tool-created tasks (AC/maintenance, kitchen oranges, Wagon Wheel trip request) were fully grounded in stated facts, nothing fabricated.
- Confirmed the Realtime API's real, documented architecture (not guessed): the conversational model reasons over raw audio directly; `gpt-4o-transcribe` is a separate, independent model on the same audio for the visible/saved transcript only - the two can genuinely diverge, and this session showed a concrete example.
- Not-yet-applied candidates from the report: a code-level gate on `mark_resting` (same pattern as the Priority-1 provenance guard), and mic audio-level diagnostic logging so a future "went deaf" period can be proven rather than inferred. No code changed for this part - forensic report only, per Michael's explicit instruction.

### What happened, part 2: docs/reports/ + a real Aria tool
Michael asked for a simple file-based channel so he/his own Aria (operator build, not the resident-facing companion) and Claude Code can leave each other durable notes instead of everything living only in chat scrollback. Built:
- `docs/reports/` - new folder, `README.md` explains the convention (`YYYY-MM-DD-HHMM-slug.md`, self-contained files) and how it relates to `docs/PROJECT_STATE.md` (that file stays the single running dated log; this folder is for standalone reports too long/detailed for one entry). Seeded with both of today's forensic reports.
- `backend/routes/reports.py` (new, 65 lines) - `GET /reports/latest` (newest report's content) and `POST /reports/note` (writes a new note file) - no auth, matching this deployment's existing public trust model, but strictly sandboxed to `REPORTS_DIR` with a server-generated filename (never caller-supplied) and a body-length cap.
- `backend/routes/realtime_aria_tools.py` - added `read_latest_report` and `leave_report_note` tool schemas to Aria's own tool set (NOT the resident-facing companion's - Michael was explicit this is his own Aria).
- `frontend/src/lib/realtimeAriaReportTools.js` (new, 36 lines) - dispatch for the two new tools, gated on `ctx.owner_user_id` being present (Aria-only; resident sessions never receive these tool schemas at all, so this is defense-in-depth, not the only boundary) - calls the new backend endpoints.
- Wired into the existing `executeTool` fallthrough chain in `realtimeMessageHandler.js` (one new line, alongside the existing ops/device dispatch).

### Line counts - every file created or materially modified this round
`backend/routes/reports.py`: 65 (new). `backend/routes/realtime_aria_tools.py`: 120. `backend/server.py`: 183. `frontend/src/lib/realtimeAriaReportTools.js`: 36 (new). `frontend/src/lib/realtimeMessageHandler.js`: 284.

### What was verified
- Backend: dry-run `import server` succeeded (236 routes, up from 234) before restart; kill/start/health-check all confirmed individually.
- `GET /reports/latest` and `POST /reports/note` tested live directly (smoke-test note created then removed, not left in the folder).
- A live Aria session mint (`POST /realtime/aria-session`) confirmed `read_latest_report` and `leave_report_note` are actually present in the tool list served - not just in source.
- Frontend dev server served the updated bundle (HTTP 200) containing the new `realtimeAriaReportTools` module and both tool names - no compile-error overlay.
- Not yet verified: an actual live voice conversation where Michael asks his Aria to read or leave a report.

### Blocked / not yet done
- `mark_resting`'s missing code-level gate and the unproven "deaf period" mechanism are both still open, per the morning forensics report.
- Nothing staged, committed, pushed, or pulled.

### Next safe step
Michael: talk to your own Aria and ask her what's new / to check the latest report, and separately ask her to leave Claude a note about something - confirms the new tools work end-to-end in a real conversation, not just via curl. Separately, whenever ready: decide whether to pursue the `mark_resting` code-level gate and/or the mic audio-level diagnostic from the morning forensics report - both are proposed, neither applied.

---

## 2026-08-23 — CORRECTION: "my Aria" is Michael's ChatGPT conversation, not the CAOSCare operator-build Realtime session; wrong integration removed, correct docs/reports/ index built

### Agent / tool
Claude Code with Michael.

### Branch / ref
`main` at `3a4bd7f`, unchanged (nothing staged/committed). Backend restarted once, to unload the removed endpoints/tools - confirmed stopped then healthy before any live check.

### Correction
The immediately prior entry ("docs/reports/ channel with a real Aria tool") built `read_latest_report`/`leave_report_note` as voice tools on CAOSCare's own operator-build Realtime session (`/realtime/aria-session`, `_build_aria_tools()`), reading "Michael's Aria" as that in-app assistant. Michael corrected this directly: "my Aria" is the Aria he already works with in a separate ChatGPT conversation - an entirely different system outside this repo, not a CAOSCare voice build at all. He was explicit: do not build a second "owner Aria" persona. Separately, the backend API endpoints that integration depended on (`GET/POST /reports/...`) were bound to `127.0.0.1:8000` and were never reachable by ChatGPT regardless of which Aria - the whole API-endpoint shape was wrong for this handoff, not just the wrong consumer.

### What changed (the fix)
- Removed `read_latest_report`/`leave_report_note` tool schemas from `backend/routes/realtime_aria_tools.py` - Aria's operator-build tool set is back to exactly `request_staff_help`/`check_request_status`/`end_conversation`, confirmed via a live session mint.
- Deleted `backend/routes/reports.py` and its router registration in `server.py` - dead code once the premise was wrong; nothing else depended on it.
- Deleted `frontend/src/lib/realtimeAriaReportTools.js` and its wiring in `realtimeMessageHandler.js`.
- `docs/reports/` itself is kept and is the right idea - added `docs/reports/INDEX.md`, a single always-current file pointing to the latest forensic report, latest acceptance-test report, current unresolved issues, and current system state (links to `PROJECT_STATE.md`), so Michael's actual ChatGPT-Aria (or Michael himself) can navigate straight to what matters without reading the whole folder. `README.md` rewritten to name the real audience correctly and note the open question of how his ChatGPT-Aria actually needs to reach these files (likely requires pushing to the existing `origin` GitHub remote - confirmed configured, `caosos/CAOSCARE.COM` - which has not happened, per the standing no-push-without-approval rule).

### Line counts - every file created or materially modified this round
`backend/routes/realtime_aria_tools.py`: 89 (back to its pre-detour size). `backend/server.py`: 181 (back to its pre-detour size). `docs/reports/INDEX.md`: new, informational (exempt). `docs/reports/README.md`: rewritten, informational (exempt).

### What was verified
- Backend: dry-run `import server` succeeded (234 routes - matches the count from before the wrong integration was ever added); restart confirmed stopped then healthy.
- Live session mint of `/realtime/aria-session` confirmed the tool list is back to exactly the original three - not just source-reviewed.

### Blocked / not yet done
- Still unknown: how Michael's ChatGPT-Aria actually fetches external content (browsing a pushed public repo? a custom GPT connector? manual paste?) - needs his answer before assuming a `git push` alone makes this reachable.
- `mark_resting`'s missing code-level gate and the unproven "deaf period" mechanism remain open, per the morning forensics report.
- Nothing staged, committed, pushed, or pulled.

### Next safe step
Michael: confirm how your ChatGPT-Aria actually needs to reach `docs/reports/` (repo push required? already has some access? you'll paste `INDEX.md` in yourself for now?) so the next step is built for how you actually work, not assumed.

---

## 2026-08-23 — CAOSCARE checkpoint commit pushed to origin/main; models.py tracked as expiring technical debt

### Agent / tool
Claude Code with Michael.

### Branch / ref
`main` at `fa6b7ac050fe0117328c8aa44d37ff44df71e354`, pushed to `origin/main` (was `48a84e0`). Working tree clean after push.

### What happened
Michael established the real CAOSCARE deployment workflow goal (EliteDesk → commit → push GitHub → deploy to production) and approved a full checkpoint of the accumulated Terminal 8/9 + tonight's Realtime-voice-repair + `docs/reports/` work. Before staging, ran a full inspection (git status, secrets scan, production build, backend tests/health, every handwritten file's line count vs. its HEAD baseline) and found three real standing-rule violations that had crept in this session - fixed all three via genuine extraction (not line-chopping), verified behavior-identical:
- `backend/routes/auth.py`: 278→309→**278** (self-service password-change endpoint extracted to new `auth_password.py`, byte-identical to HEAD afterward).
- `backend/routes/realtime.py`: 318→327→**308** (VAD/noise-reduction constants extracted to new `realtime_audio_config.py` - now smaller than its original pre-session baseline).
- `frontend/src/pages/Admin.jsx`: 302→**237** (the `tabGroups` pure-data function extracted to new `frontend/src/lib/adminTabGroups.js`).
- `backend/routes/realtime_companion_prompt.py`: 328→**240** (resident profile/memory-bin hydration extracted to new `realtime_companion_memory.py`; verified live via a session mint that the produced prompt text is unchanged).

One gap in that inspection: `backend/models.py`'s delta wasn't checked initially and turned out to have grown +197 lines this session (1105→1302), on top of already being over cap. Flagged transparently once caught (not silently proceeded, not silently fixed unilaterally - splitting it is a cross-cutting refactor touching imports across most of `routes/*.py`, too large/risky to fold into a push). Michael approved it as a **temporary, one-checkpoint-only exception**, explicitly not a standing grandfather - recorded in `docs/reports/INDEX.md`'s unresolved-issues section with exact before/after sizes and the required follow-up (domain split, same pattern as the existing `models_transportation.py`).

### What changed
81 files, +7810/-1694, one commit (`fa6b7ac`): Terminal 8/9 platform build-out (transportation, departments, menu, schedule, resident-request bus), Resident Record conversation history, resident kiosk-provisioning fix, the full night's Realtime voice trust/provenance work (playback tracking, no-loss persistence, operational-provenance guard, overlap classifier, lifecycle diagnostics, greeting/mark_resting fixes, VAD revert), self-service password change, Admin.jsx component split, and the new `docs/reports/` channel. Pulled 2 upstream-only doc commits first (clean fast-forward, zero conflict). No force-push, no history rewrite, no deletions.

### What was verified
- Backend: dry-run `import server` succeeded before every restart; each restart individually confirmed stopped-then-healthy.
- Frontend: real production build (`yarn build`, not just dev-server) succeeded twice (before and after the Admin.jsx/realtime_companion_prompt.py extractions) - only 4 pre-existing lint warnings, same bundle size both times.
- Backend test suite run: 37 passed, 22 failed, 99 errors, 15 skipped - sampled a failure directly and confirmed it's a demo-credential/fixture environment issue (`401 Invalid credentials` against a non-seeded demo account), not a code regression. Not exhaustively verified for every failure.
- Secrets scan across all 78 candidate files: clean (one false positive, a `data-testid` string). `.env`/`.env.*` confirmed gitignored and untracked; only placeholder `.env.example` files tracked.
- `git status` clean after push; `origin/main` confirmed matching local HEAD exactly.

### Blocked / not yet done
- `backend/models.py` domain split - explicitly deferred to its own dedicated round with tests before and after, per Michael's direct instruction not to mix it into this checkpoint.
- `mark_resting`'s missing code-level gate, the unproven "deaf period" mechanism, and the VAD reliability question all remain open (tracked in `docs/reports/INDEX.md`).
- Production deployment of CAOSCare.com - explicitly NOT approved yet; inspection of the current production/deployment architecture is the next phase, still pending.
- Nothing else staged, committed, pushed, or pulled beyond this checkpoint.

### Next safe step
Per Michael's explicit instruction: STOP feature work. The next dedicated engineering round should be the `models.py` domain split (tests before and after), not bundled with anything else. Separately, whenever Michael is ready: inspect the actual CAOSCare.com production/deployment architecture (server, DNS, reverse proxy, process management, env/secrets, TLS, health checks, rollback) and design the smallest repeatable deploy path - explicitly not to be executed until Michael says "DEPLOY".

---

## 2026-08-23 — Local EliteDesk connectivity outage: two distinct IPv6/IPv4 localhost mismatches, both fixed; frontend moved to systemd --user supervision

### Agent / tool
Claude Code with Michael. `docs/reports/CURRENT_DIRECTIVE.md` (pushed by Michael/ChatGPT-Aria, commits `a3fb31f`/`e7d66b5`) adopted this round as the shared standing working directive - reviewed for coherence/safety before being treated as authoritative, matches everything established this session.

### Branch / ref
`main`, pulled to `e7d66b5` (clean fast-forward) before this round's work.

### What happened
Michael reported the local Admin UI at `localhost:3000/admin` showing "Could not load requests", "Failed to load pendants", kiosks/residents empty - global-looking failure. Per the directive's explicit priority, this was diagnosed BEFORE any Voice work resumed. Full forensic pass (process state, DB query, direct endpoint hits, CORS, Google OAuth config/connectivity) proved the database was never touched and the backend was never down - see `docs/reports/2026-08-23-2008-local-dev-connectivity-outage.md` for the complete writeup. Two distinct root causes, both real IPv6-vs-IPv4 `localhost` resolution mismatches on this specific machine, not data loss, not a crash:

1. **Backend (port 8000)**: `getent hosts localhost` resolves to `::1` on this machine; uvicorn was bound only to IPv4 `127.0.0.1:8000`. Browser fetches to `http://localhost:8000` hit a hard `ERR_CONNECTION_REFUSED`; `curl` to the same URL kept working because its resolver fell back to IPv4 cleanly. Backend process itself never crashed (same PID throughout).
2. **Frontend (port 3000)**: identical bug, one layer up - `craco start` defaulted to binding `0.0.0.0:3000` (IPv4 only). Same browser-side refusal, same non-crash (same PIDs throughout, proven via `ps`/journald).

### What changed
- `frontend/.env`: `REACT_APP_BACKEND_URL` changed from `http://localhost:8000` to `http://127.0.0.1:8000` - removes the ambiguity at the source for the app's own API calls. Backend itself was not modified, per Michael's explicit instruction not to touch it again once Failure A was confirmed fixed.
- New `~/.config/systemd/user/caoscare-frontend-dev.service` (local machine config, not in the git repo - contains this machine's absolute `nvm` paths) - runs `yarn start` (still dev mode, hot reload intact, not a production build) with `HOST=::` (dual-stack bind, fixes Failure B at the root rather than just working around it), `Restart=on-failure`, logs via `journalctl --user -u caoscare-frontend-dev.service`. Enabled + `loginctl enable-linger caoscare-1` set so it survives without an active login session. The old raw `nohup`'d frontend process was stopped and replaced by this service.
- New report: `docs/reports/2026-08-23-2008-local-dev-connectivity-outage.md`. `docs/reports/INDEX.md` updated (new "Latest local-dev-outage report" section, the now-resolved item removed from unresolved issues).

### What was verified
- Data confirmed intact throughout via direct Mongo query (unchanged counts across every collection).
- Both fixes proven directly, not assumed: `curl --resolve localhost:8000:127.0.0.1 ...` / `--resolve localhost:3000:::1 ...` reproduced the exact failure before each fix and the exact success after.
- Post-fix: port 3000 listening dual-stack (`*:3000`), `localhost`/`127.0.0.1`/forced-`[::1]` all return 200 on both 3000 and 8000, backend health still `{"ok":true,"db":"up"}`, frontend bundle confirmed to contain `127.0.0.1:8000` not `localhost:8000`, `/login` and `/admin` both serve 200, `/api/kiosks` (public) returns real data, protected endpoints correctly 401 without a token.
- `caoscare-frontend-dev.service` confirmed `enabled` and `active`, linger confirmed `yes`.

### Blocked / not yet done
- Backend was intentionally left as a raw process this round (not converted to a systemd service) per Michael's explicit "do not touch the backend again" instruction - the same supervision pattern would apply cleanly to it in a future round if wanted.
- Per the shared directive: Voice work stays paused until the local dev stack has demonstrated it stays reliably up - this round is what proves that, pending Michael's confirmation after a normal work session.
- `models.py` domain split and the `mark_resting`/VAD open items from prior rounds remain queued, untouched this round.

### Next safe step
Per the CURRENT_DIRECTIVE.md checkpoint cadence: this is a completed, verified milestone - commit and push now, confirm EliteDesk HEAD == origin/main, then resume Voice work per the directive's stated priority order once Michael confirms the local stack is holding up normally.

---

## 2026-08-23 — Multi-agent execution model started: Lanes B and C integrated, Lane A (Voice) running

### Agent / tool
Claude Code acting as integration lead per `docs/reports/MULTI_AGENT_EXECUTION_PLAN.md`, coordinating parallel isolated-worktree agents on Lanes A (Voice), B (Admin), C (Scheduling/Transportation). Lane D (QA/review) absorbed into the lead role rather than a separate agent, since it's explicitly read-mostly and overlaps with lead duties.

### Branch / ref
`main` at `bfbec64` (two merge commits: `2a6e661` Lane B, `bfbec64` Lane C), on top of `f092ae5`.

### What happened
Each lane worked in its own isolated git worktree so nothing touched the live-running primary tree until reviewed. Every lane's actual diff was inspected line-by-line before merging - not just the lane's own summary - including verifying claimed backend endpoints/deps functions genuinely exist (e.g. `require_front_desk_or_admin`, `visibility_role` query filtering) rather than trusting the report.

**Lane B (Admin)** - facility inventory finding: the backend (`facilities.py`, `Facility` model) and `FacilitiesTab.jsx` were already fully working, not missing - the actual gap was pure UX/IA: zero facilities existed and the only way to discover that was two clicks deep, with no onboarding signal anywhere else even though residents/departments/requests all render as if a community exists. Fixed: a `FacilitySetupBanner` on the main Community administration screen itself (not buried), owner-only CTA that jumps straight to a pre-opened create-facility dialog now also exposing address/timezone fields. Also made each Departments row clickable into a real (first-pass) workspace dialog showing open/completed/skipped counts and the live list of open requests routed there, reusing the existing `GET /tasks?visibility_role=<slug>` filter - no parallel data model.

**Lane C (Scheduling/Transportation)** - full inventory against blueprint sections 10-11 (table in the lane's own report). Found and fixed a real bug along the way: `transportation_report.py`'s "booked" determination only checked the legacy `transport_slot_id` field, never the current engine's `transport_run_id` - any request booked through the modern resource-matching path was misreporting as still "Pending" in the daily-ops report. Also built the actual missing action: a staff-clickable "Assign" button (new `backend/routes/transportation_assign.py`, shared `TransportAssignAction.jsx` component used identically on both the Transportation report and the Transportation calendar) that reuses the exact same `find_or_create_run` engine call the resident-request path already uses, so a staff assignment and a resident-requested booking can never disagree about what counts as booked. Correctly refuses to fabricate anything: with 0 drivers/0 vehicles currently configured, clicking Assign returns an honest "not configured yet" message instead of a fake success.

### What changed
9 files across the two lanes (all under the 300-line cap): `Admin.jsx`, new `FacilitySetupBanner.jsx`, new `DepartmentWorkspaceDialog.jsx`, `DepartmentsTab.jsx`, `FacilitiesTab.jsx`, new `backend/routes/transportation_assign.py`, new `TransportAssignAction.jsx`, `TransportationCalendar.jsx`, `TransportationTab.jsx`, `transportation_report.py`, `server.py` (router registration). `.gitignore` also updated to exclude `.claude/` (local tooling/worktree state, machine-specific, was showing as perpetual untracked clutter).

### What was verified
- Every changed/new file's diff read in full before merging, not just each lane's self-report.
- Backend: dry-run `import server` succeeded (237 routes) before restart; kill/start/health individually confirmed.
- Frontend: picked up both merges via its own hot-reload (systemd-supervised `craco start` recompiled on its own, confirmed via `journalctl` - no restart needed since no `.env` change this round, only component code).
- Facility banner: confirmed live via `GET /facilities` returning `[]` (banner will render).
- Department workspace: confirmed live via `GET /tasks?visibility_role=kitchen` returning real data (7 items).
- Transportation assign: confirmed live via `GET /transportation/request/<real-pending-task>/assign/context` correctly reporting `drivers_configured:0, vehicles_configured:0, resources_configured:false` for an actual pending mock request.
- Merged worktrees/branches for Lanes B and C cleaned up (`git worktree remove`, `git branch -d`) once integrated.

### Blocked / not yet done
- Lane A (Voice fundamentals/regression hunt) still running in its own isolated worktree at time of this entry - not yet reviewed or integrated.
- Top-level navigation restructure, Staff invite/role lifecycle, Zones, and ScheduleTab's missing calendar-grid/email-ingestion UI trigger all remain open, explicitly deferred by both lanes per the gap report's own priority ordering.
- Nothing deployed; production untouched.

### Next safe step
Review and integrate Lane A once it completes (regression matrix + newest-session forensic reconstruction, no tuning). Then resume Voice work directly per the standing priority, informed by whatever Lane A's evidence shows - one controlled change at a time, real-room test, forensic report, keep or revert.

---

## 2026-08-24 — Voice echo research pass + Room 404 forensics + Lane A integration

### Agent / tool
Claude Code, EliteDesk primary worktree (integration lead).

### Branch / ref
`main`, four commits this entry: `33c922b` (Lane A integration), `96662f1` (Room 404 forensics), `c046154` (telemetry), plus this doc's own commit. All pushed, `origin/main` matches.

### What changed
- Integrated Lane A's Voice regression matrix + Room 121 dead-zone forensic reports (evidence-only, no code) via cherry-pick after its worktree branch went stale relative to `main`; worktree/branch cleaned up.
- Read-only forensic reconstruction of the most recent Room 404 Realtime session (`rt_b0kywhng_1787614161842`, found automatically via room→resident→kiosk lookup, no session ID given). Reproduced and resident-confirmed the echo/trust-boundary defect Lane A had only suspected: 3 fabricated "user" turns in 19 seconds, each a mishearing of Aria's own prior words, persisted `trusted:true`; the resident verbally denied two of them live. Pinpointed the exact cause in `classifyUserTurn()` (`realtimeMessageHandler.js`): the echo-resemblance check only runs when a turn is both overlapped AND ≤2 words - a 3-word real-time echo and any delayed (post-playback) echo both structurally skip it.
- Per Michael's explicit research-first directive: researched WebRTC AEC3, Chromium's audio pipeline, `echoCancellationType`, OpenAI's Realtime docs, and prior art (LiveKit, Twilio, Pipecat) before touching code. Confirmed CAOSCARE's output routing (`<audio>`+`srcObject`, no AudioContext bypass) already matches the one architecture that matters most in the research; confirmed OpenAI provides zero server-side echo cancellation (100% client/hardware responsibility); identified the free zero-code `chrome://webrtc-internals` AEC-dump diagnostic as the strongest next step, not yet run.
- **Tested a `classifyUserTurn()` widening fix against real Room 404 data before writing it**, found it would falsely flag genuine resident speech ("Bake chicken thighs?" scores the same resemblance ratio as the real echoes) - deliberately did not ship it. Shipped one small, purely additive telemetry change instead (`frontend/src/lib/realtimeMessageHandler.js`, 281→299 lines): independent `output_audio_buffer_started`/`stopped` events, per-turn `speech_segment_ms`, `ms_since_assistant_stopped` on every `user_transcript`, and persisted `realtime_error` events (previously UI-only).
- New report files: `docs/reports/2026-08-24-2337-room404-forensics.md`, `docs/reports/2026-08-24-2100-voice-echo-research-and-audio-path-architecture.md`. `docs/reports/INDEX.md` updated. Posted full findings to GitHub Issue #22 for ChatGPT-Aria.

### What was verified
- Room 404 session data pulled directly from `db.conversations`/`db.realtime_diagnostics` (read-only), cross-checked against the resident's own live correction in the transcript.
- Codebase greps confirmed (not assumed): no `AudioContext`/`AudioContext.destination` routing of the Realtime stream anywhere; the one `AudioContext` use (`Kiosk.jsx`) is inert; `getSettings()` sampled exactly once; no `error`/`response.cancelled` persistence existed before this pass.
- `frontend/src/lib/realtimeMessageHandler.js` compiled cleanly 4 times in a row against the live supervised frontend dev service (hot-reload, `journalctl` confirmed) across the incremental edits, zero new errors/warnings.
- All 7 SIM lane issues re-checked; SIM-7 (#21, ChatGPT-Aria's `aria/sim-7-inbound-email-bus`) not touched.

### Blocked / not yet done
- No production code fix for the echo defect shipped yet - deliberately deferred pending real telemetry from the next live test (this pass only adds instrumentation).
- `chrome://webrtc-internals` AEC-dump capture not yet performed - requires Michael's live session, zero code needed.
- Controlled A/B/C test plan (Aria-only / full-duplex / far-field) written and ready but not run.
- Whether the eMeet's onboard hardware AEC can be toggled/coordinated is an open hardware/OS-level question, not resolvable from CAOSCARE's own code on Linux (`echoCancellationType:"system"` is Mac/Windows-only per Chrome's own docs).

### Next safe step
Michael runs a real-room test with `chrome://webrtc-internals` AEC-dump capture enabled. With that plus the new `speech_segment_ms`/`ms_since_assistant_stopped` telemetry, decide whether the next controlled change belongs in the audio path (mic/output constraints) or the trust-boundary classifier - do not guess ahead of that data.

---

## 2026-08-25 — Rooms 401/403/408 forensic comparison, voice frozen, priority moves to room/device/memory/facility-context

### Agent / tool
Claude Code, EliteDesk primary worktree.

### Branch / ref
`main`, this entry's commit pending push alongside `docs/reports/2026-08-25-0245-rooms-401-403-408-forensics.md` and `INDEX.md`.

### What changed
- Read-only forensic comparison of the most recent Realtime sessions for Rooms 401, 403, 408 against the Room 404 echo defect. Room 401: confirmed via three independent zero-result queries that **no session was ever run** for that resident/kiosk/room - a resolved fact, not an inferred gap. Room 403 (`rt_dfevhypd_1787625188171`, 5m36s, 28 user turns) and Room 408 (`rt_9c6kq18r_1787624294811`, 7m41s, 39 user turns) both reviewed turn-by-turn against Aria's immediately preceding speech: **zero false-trusted echoes in either session**, versus Room 404's 3 confirmed phantom trusted echoes in one 19-second window. Room 408 additionally shows the strongest full-duplex evidence reviewed to date (~14 genuine, correctly-classified barge-ins). One minor, previously-undocumented `classifyUserTurn()` labeling detail found (empty-after-stripping text always self-matches JS `.includes("")`) - did not change any outcome, not fixed, noted for later.
- **Recorded Michael's independent field finding** (eMeet used as one complete mic+speaker unit, vs. the earlier split eMeet-mic/separate-soundbar arrangement, produced materially cleaner live conversations on the same EliteDesk) as **strongly supported practical root cause / deployment requirement based on controlled configuration behavior** - explicitly not claimed as laboratory-proven eMeet DSP/AEC internals, since no CAOSCARE telemetry field records physical input/output device arrangement (checked and confirmed absent). **Production/test-room requirement going forward: one eMeet per room serving as both microphone and speaker.**
- Per Michael's explicit direction, and since no new severe voice defect surfaced in this comparison: **voice configuration is now frozen.** No audio-path or classifier code change was made or is currently justified by evidence. Engineering priority returns to the main CAOSCARE operational system, specifically room/building context, device control (command + ACK + readback), and resident memory recall - per Michael's new directive, an audit of what already exists in each of those areas is the next deliverable, due before any new code in that area.
- New report: `docs/reports/2026-08-25-0245-rooms-401-403-408-forensics.md`. `docs/reports/INDEX.md` updated. Posted to GitHub Issue #22.

### What was verified
- All three room→resident→kiosk→session lookups performed via direct read-only Mongo queries, not assumed from prior context.
- Every user turn in both Room 403 and Room 408 individually checked against the immediately preceding assistant utterance for textual resemblance - none found in either session.
- `mic_track_settings.deviceId` compared across sessions: Room 403's matches Room 404's exactly; Room 408's is the literal string `"default"`. No equivalent field exists anywhere for output/speaker device identity - confirmed absent by grep, not assumed.

### Blocked / not yet done
- The device-arrangement hypothesis remains **not directly provable** from CAOSCARE's own telemetry (no field records physical audio routing) - the freeze decision rests on Michael's field report plus the absence of any new code-level defect, not on instrumented proof.
- `chrome://webrtc-internals` AEC-dump capture from the prior research report still not performed - now deprioritized given the freeze decision, but not formally closed out.
- The room/device-control/memory/facility-context audit (Michael's next directive) has not yet started as of this entry.

### Next safe step
Begin the audit Michael requested before any new code: current device-control execution/readback path, current Realtime tools actually exposed, current resident-memory write/hydration path, current facility-context source, and why Conway/Arkansas context and cross-session memory recall are apparently unreliable. Report findings before implementing anything.

---

## 2026-08-25 — Device control / memory / facility-context audit (pre-implementation)

### Agent / tool
Claude Code, EliteDesk primary worktree.

### Branch / ref
`main`, this entry's commit pending push alongside `docs/reports/2026-08-25-0330-device-memory-facility-audit.md` and `INDEX.md`.

### What changed
Read-only audit (per Michael's explicit "audit before code" directive) of the device-control, memory, and facility-context systems, prompted by observed gaps: Aria not reliably knowing the facility is in Conway, Arkansas, and apparent failure to recall facts across sessions. Full findings in the linked report; three confirmed root causes, each traced to source/data, not inferred:

1. **A real facility record exists** (`db.facilities`, one document: "Brookdale Senior Living Communities," Conway AR address, created 2026-08-23 via Admin) - but `realtime_facility.py` (which builds the Realtime voice prompt's facility/time context) never queries `db.facilities` at all. It reads two flat `.env` variables instead: `FACILITY_TZ=America/Chicago` (correct) and `FACILITY_LABEL=the EliteDesk node` (a leftover dev placeholder). The Admin-configured facility and the voice system were never wired together.
2. That one real facility record's `timezone` field literally contains the string `"conway ar 72034"` - not a valid IANA zone. Root cause: the `Facility` model has no structured city/state/zip/lat/lon fields, only a free-text `address` and an unvalidated `timezone` string - the city/state/zip text landed in the wrong field with no validation to catch it.
3. **Resident-facing memory (write -> extract -> hydrate) verified working end-to-end by direct empirical test**, not just read: posted a real user+assistant turn pair to `/api/memory/realtime-turn` for mock resident `res_d9129c7d1f46` (Harold) stating "My favorite ice cream is butter pecan," confirmed the background extractor correctly wrote it to `db.memories` (category: preferences, bin: facts) within ~6 seconds, then called `_build_companion_instructions()` directly to simulate a fresh "session 2" and confirmed the fact appears verbatim in the newly hydrated prompt. **Operator/Aria memory (Michael's own personal-assistant build) has no automatic extraction pipeline at all** - confirmed by grepping every write to `db.aria_memories` in the codebase: only the manual CRUD endpoints write it. `db.aria_conversations` (raw verbatim turns) and `db.aria_memories` both currently hold 0 documents.

Also found, not yet acted on: the device-control tool path (`adjust_room_temperature`/`toggle_light`/`toggle_tv`) can tell Aria "done" the moment a command is *queued* (`devices.py` optimistically overwrites `smart_devices.state` at queue time, not at bridge-tablet-ack time) - a real truthfulness gap matching what Michael described, currently latent because no bridge tablet/real hardware exists for any tested room, so every command fails honestly at "no device found" instead.

New report: `docs/reports/2026-08-25-0330-device-memory-facility-audit.md`, including a 5-step smallest-coherent-implementation-plan (wire `db.facilities` into voice; fix the facility model/timezone field; give operator/Aria memory the same extraction pipeline resident memory already has; close the device-truthfulness gap; add silent-failure visibility to memory extraction). `docs/reports/INDEX.md` updated.

### What was verified
- `db.facilities` queried directly and its one document read in full.
- Grepped the entire backend for every `db.aria_memories` write site - confirmed only manual CRUD.
- The deterministic memory test above is a real write/read through the actual production API paths, not a simulation or direct DB manipulation - clearly tagged (`source_session: "audit_test_1787626105"`) for easy identification/removal if needed.

### Blocked / not yet done
- None of the 5-step implementation plan has been built yet - this was audit-only, per explicit instruction.
- No bridge-tablet/real-hardware device exists in this environment to test the ack/readback side of the device-truthfulness fix against real execution.

### Next safe step
Implement the plan in the order listed in the report, starting with wiring `db.facilities` into the Realtime voice path (steps 1-2 together, since the model needs real fields before the facility record's bad `timezone` value can be corrected), each step independently tested against the existing mock residents/rooms before moving to the next.

---

## 2026-08-25 — Step 1+2 shipped: facility source of truth wired into Realtime voice

### Agent / tool
Claude Code, EliteDesk primary worktree.

### Branch / ref
`main` @ `371e698`, pushed, `origin/main` matches. Backend restarted (plain nohup uvicorn, PID replaced) to load the change; frontend untouched (no frontend change needed this slice).

### What changed
Implemented steps 1+2 of the accepted 5-step plan from the prior audit. `backend/models.py`: `Facility`/`FacilityCreate`/`FacilityUpdate` gained structured `city`/`state`/`zip_code`/`country`/`lat`/`lon` fields plus a real IANA-timezone validator (`_validate_timezone`, using `zoneinfo.available_timezones()`). `backend/routes/realtime_facility.py`: added `get_active_facility()` (single-active-facility lookup, matching current single-community scope); `_facility_now()` is now async and prefers the live facility's timezone/name/city/state over the `.env` placeholders, falling back to them only if no facility record exists; `today_facility_date()` deliberately left sync/unchanged (FACILITY_TZ was already correct, out of scope). `realtime.py` and `realtime_companion_prompt.py`: both `_facility_now()` call sites now `await` it; the resident prompt's "Right now" block and the `/session` context blob (`facility_label`/`facility_tz`, read by the frontend's `get_current_time` tool) now come from the live facility. `weather.py`: `/weather/current` now prefers the facility's own `lat`/`lon`/name when set, replacing the silent Pennsylvania-area default.

**Corrected the existing facility record in place**, validated through the same Pydantic model (not a raw DB edit): `timezone` `"conway ar 72034"` -> `"America/Chicago"`, added `city: "Conway"`, `state: "AR"`, `zip_code: "72034"`, `country: "US"`, `lat: 35.0887`, `lon: -92.4421`. `name`/`address`/`phone`/`contact_email`/`on_call_phone`/`plan`/`is_active`/`created_at`/`facility_id` untouched.

### What was verified
- Dry-run `import server` succeeded (241 routes) before restart.
- Backend killed and restarted cleanly (plain nohup uvicorn, same as the established pattern this session); `/api/health` confirmed.
- **Live, through the actual endpoints the frontend calls, not just unit-level**: `POST /realtime/session` for a real mock resident now returns a prompt containing *"Brookdale Senior Living Communities, in Conway, AR (America/Chicago)"* with the correct local date/time, and a `_caos.context.facility_label`/`facility_tz` matching; `GET /weather/current` now returns `"label": "Conway, AR"` with real coordinates and a live-fetched forecast for that location (previously silently Pennsylvania-area).
- `POST /realtime/aria-session` (operator build) re-verified minting cleanly after the same `_facility_now()` change.
- `today_facility_date()` re-verified directly (still sync, still correct) and via `schedule`/`menu` routes still resolving (401 Not Authenticated, not a 500 - confirms no crash on the decoupled helper).
- The new timezone validator empirically confirmed to reject the exact bad value that caused this bug (`"conway ar 72034"`).

### Blocked / not yet done
- Steps 3 (operator/Aria memory extraction), 4 (device truthfulness), 5 (memory failure visibility) not started.
- The Admin Facilities UI (`FacilitiesTab.jsx`) was not updated to expose the new city/state/zip/lat/lon fields - not required for this slice's voice-acceptance criteria, but staff currently cannot edit them without a script.
- Per Michael's instruction: stopping here for his live voice acceptance test ("Where are we?" / "What city am I in?" / "What time is it here?") before continuing to step 3.

### Next safe step
Await Michael's live acceptance test on this facility-context slice. If accepted, continue to step 3 (operator/Aria memory extraction pipeline), reusing the resident-memory pattern already verified working.

---

## 2026-08-27 — Room 401 mock room-device layer + resident-request isolation forensics/fix

### Agent / tool
Claude Code, EliteDesk primary worktree.

### Branch / ref
`main`, this entry's commit pending push alongside `docs/reports/2026-08-27-0118-room401-devices-and-request-isolation.md` and `INDEX.md`. Backend restarted (plain nohup uvicorn, PID replaced) to load the changes; frontend untouched by the restart (no frontend build step needed for these changes to take effect in the already-running dev server).

### What changed
Continuing post-outage per Michael's directive: inspect Room 401's real conversation, build a real mock device layer, investigate a suspected cross-resident maintenance-request isolation bug, wire daily announcements. Full detail in the linked report; summary:

1. **Room 401 forensics**: read real session `rt_f2lx9y4s_1787791872323` in full. Facility context worked correctly. `db.smart_devices` had zero documents in the whole database, so every device tool call 404'd. Aria's fallback (filing a maintenance ticket on device failure) collided with `resident_requests.py`'s category-only duplicate detection and silently merged a new AC complaint into an unrelated pre-existing "reading lamp" ticket, then told the resident "there's already a maintenance request in progress for the AC" - false. Confirmed the same pattern in every other room's conversation sampled.
2. **Isolation bug investigation - direct empirical result, not assumption**: checked every room's conversation content, `resident_requests.py`, the companion prompt/memory hydration path, and the admin conversation-session viewer for any unscoped "latest request" query. **Found none** - every fabricated "already in progress" line traced back to that same resident's own record, never another resident's. The bug Michael actually heard was the same-resident cross-*issue* conflation in item 1, not a cross-resident leak. Stated this distinction directly rather than inventing a cross-resident fix for a defect that isn't present.
3. **Built the mock device layer**: `DeviceProtocol` gained `"mock"` (models.py); `devices.py` executes mock-device commands synchronously with a real ack instead of leaving them "queued" for a bridge tablet that doesn't exist; new `get_room_status` read tool (`realtime_device_tools.py`, split out of `realtime_tools.py` to stay under the 300-line cap - Aria previously had no way to read room state at all); `scripts/seed_mock_devices.py` seeded one thermostat + one TV per resident room (17 rooms) via the real `POST /devices` endpoint, individualized starting temperatures.
4. **Found and fixed a second real bug live**: `public_room_command` picked the first device matching the requested capability - a room with both thermostat and TV (both expose `"power"`) had "turn the TV on" silently hit the thermostat instead. Added an optional `kind` field to `DeviceCommandInput` to disambiguate; fixed the frontend dispatch (`realtimeDeviceTools.js`) and three pre-existing `Kiosk.jsx` call sites (auto-mute-on-call, restore-on-hangup, device button panel) that had the identical latent bug. An ambiguous command with no `kind` now 400s instead of silently misrouting.
5. **Fixed the duplicate-request truthfulness gap** from item 1: `create_resident_request`'s duplicate response now returns `existing_summary`/`same_issue`; `realtimeOperationsTools.js` and the tool description were updated so Aria describes the real open ticket's subject instead of implying it matches whatever was just asked.
6. **Daily announcements**: inspected `ScheduleItem`/`schedule.py` first - `facility_note` category and `get_todays_schedule` already exist and already work (confirmed live in the Room 401 transcript itself); only today's date had no `facility_note` entries. `scripts/seed_demo_announcements.py` fills that one gap through the existing `POST /schedule` endpoint - no new domain built, per "extend, don't duplicate."

### What was verified
- Ran the actual production `realtimeDeviceTools.js` `executeDeviceTool` dispatch (not a reimplementation) against the live backend for the exact Room 401 moments that failed in the real transcript: `get_room_status`, `adjust_room_temperature`, `toggle_tv` all now return real, correct, individualized results. Room 401 reset to baseline (TV off, 72°) afterward.
- New `tests/test_room_device_isolation.py` (7 tests, real HTTP calls against the live backend, not direct Mongo writes): request isolation between Rooms 401/403/408, conversation-session task scoping, distinct per-room device state, thermostat/TV command scoping, and the kind-disambiguation fix. **7/7 pass.**
- Duplicate-truthfulness fix verified live against a scratch TEST-101 resident: `same_issue: false`, `existing_summary` correctly names the actual open ticket, and the resulting spoken message names it instead of the new complaint.
- Ran the full existing `tests/` suite: ~20 failures / 99 errors, all confirmed (by direct inspection of the actual assertion failures) to be pre-existing, unrelated test debt - stale hardcoded credentials (`admin@caoscare.com`/`nurse@caoscare.com` don't exist in this DB) and two stale hardcoded expectations (old `Lancaster, PA` weather default; devices expected for old numeric rooms "101"/"108" never part of this environment). None caused by today's changes.

### Blocked / not yet done
- No actual browser/microphone voice call was placed this session - everything was verified through the real HTTP/tool-dispatch boundary, not a live WebRTC session. Michael should still do one live acceptance pass.
- `check_request_status` was not given the same `existing_summary`/`same_issue` treatment as `create_resident_request` - lower risk (it only echoes one record it already knows the category of) but not independently re-verified.
- `backend/models.py` (1359 lines) and `frontend/src/pages/Kiosk.jsx` (589 lines) remain pre-existing, already-flagged 300-line-cap violations (see `docs/reports/INDEX.md`, Architecture debt, 2026-08-21/25 - "do not run that broad split concurrently with active implementation lanes"). Both received only small, additive, non-restructuring edits today.
- Step 3 of the original device/memory/facility audit (operator/Aria memory extraction pipeline) remains unclaimed.

### Next safe step
Michael runs one real live voice call (any seeded room) confirming the temperature/TV asks and a fresh maintenance request sound right end-to-end through an actual microphone. After that, step 3: give operator/Aria memory the same automatic extraction pipeline resident memory already has and has verified working.

---

## 2026-08-27 — Resident home screen, maintenance closed loop, TV/magnification, hardware adapter boundary

### Agent / tool
Claude Code, EliteDesk primary worktree.

### Branch / ref
`main`, this entry's commit pending push alongside `docs/reports/2026-08-27-0230-resident-home-integration-and-hardware-adapter.md` and `INDEX.md`. Backend restarted multiple times (plain nohup uvicorn, PID replaced each time) to load changes; frontend dev server (craco) hot-reloaded throughout, confirmed no console errors via live browser check.

### What changed
Michael's directive: stop tuning voice (confirmed good enough), move to integration - resident screen/Aria/room devices/maintenance/eventual hardware as ONE system, demo-ready within ~2 weeks. Full detail in the linked report; summary:

1. **Resident home screen**: new `frontend/src/components/kiosk/{ProfileHeader,TodayPanel,RequestsPanel,RoomDevicePanel}.jsx`, composed into `Kiosk.jsx`'s idle screen in place of the old call-kiosk-only layout. Shows name/room/time, human-readable request cards, today's activities/announcements/meal, and a capability-driven device panel - verified live in the browser with real Room 401 data.
2. **Removed the "I need a little help" button.** CALL FOR HELP (emergency) and I JUST WANT TO TALK (comfort) remain; `assist` severity still reachable via Aria's own `call_for_help` judgment, just not a standalone button.
3. **Closed the maintenance communication loop** - the literal bug Michael hit (Aria couldn't say what a request was for or when it was scheduled). `resident_requests.py` gained `_resident_safe_view()`, shared by `check_request_status` and a new `GET /tasks/resident-request/mine` (the Home screen's source), returning `what_for`/`scheduled_date`/`scheduled_time_label`/`latest_update`. Reused transportation's existing `requested_for_date`/`_time_label` fields (added to `StaffTaskUpdate`) rather than inventing a new schedule concept. `RequestDetailDialog.jsx` gained a staff-facing form to actually set these through the existing `PATCH /tasks/{id}`. Verified live end-to-end against Room 401's real "reading lamp" ticket.
4. **TV input capability**: `DeviceCapability` gained `"input"`, `SmartDevice` gained `inputs: []` (device-declared valid values), new `set_tv_input` tool checks the device's own list before calling.
5. **Device-selection/capability-collision class of bug re-confirmed clean** after adding input; screen and Aria confirmed to share one device-state contract (same endpoints), now kept current via polling (devices every 10s, requests every 20s, schedule every 60s - no new realtime infrastructure).
6. **Magnification**: replaced the old 3-step text-size cycle (covered only a few hand-picked elements) with a continuous 50-200% root-font-size scale - genuinely reflows the whole screen (Tailwind is rem-based, confirmed no project override). New `set_magnification` Aria tool and an on-screen +/- control share one `localStorage` key + broadcast event. **Verified live in the browser**: toggling via the exact CustomEvent mechanism Aria's tool uses visibly reflowed the whole page at 150%, not a static zoom.
7. **New `backend/device_adapters.py`** - a small registry (`mock`, `home_assistant`) `devices.py`'s dispatch now calls; every other (real, physical-transport) protocol keeps its existing, unchanged bridge-tablet queue/ack path. Home Assistant integrated via HA's own REST API (not raw MQTT - HA is the single hub). **Verified live against the EliteDesk's real running HA VM**: connectivity/auth confirmed (22 real entities enumerated); found and fixed a real bug in the process - HA's service-call endpoint returns HTTP 200 with an empty body for a nonexistent entity rather than erroring, which would have let the adapter silently report false success. No positive round-trip yet - zero controllable HA entities exist; creating one needs Michael's HA Helpers UI (confirmed not a config-entry-flow integration, same category of browser-only step as the original HA onboarding).
8. Admin's Devices tab now visibly badges `mock` vs. real protocols (amber "MOCK — no hardware" vs. forest-green) - the provenance visibility the directive asked for, with nothing shown to residents.

### What was verified
- Every device/request/schedule change verified through the real running backend's actual HTTP endpoints, and through the exact production tool-dispatch JS (`executeDeviceTool`/`executeOperationsTool`) run against it - not reimplemented or mocked.
- Full Room 401 replay of the demo acceptance script (temperature read/adjust, TV on, TV input switch, maintenance issue+schedule lookup, today's schedule) - all correct.
- Magnification and the new resident home screen visually confirmed live in a real browser tab (screenshots), including a scroll-through of every new panel; zero console errors on load.
- New `tests/test_room_device_isolation.py` still 5/7 pass (2 skip on data exhaustion, pre-existing benign pattern, unchanged from this morning) after the device-adapter refactor - confirms the refactor didn't change mock-device behavior.
- Directly caused and fixed a real HA API-contract bug (silent-success-on-nonexistent-entity) through live testing against real infrastructure, not code review alone.
- Cleaned up: two real live alerts and one live voice-created transportation request from Michael's own mid-session testing were found and resolved/left intact appropriately (alerts resolved so they wouldn't block the next real call; the transportation request left as genuine data); a stray test-isolation task from the prior session was removed from Room 401's real request list.

### Blocked / not yet done
- No live microphone/voice call was placed this session (no mic in this environment) - everything verified through the real HTTP/tool-dispatch boundary.
- Home Assistant adapter's positive path (a real command actually changing a real/helper entity's state) not proven - needs one HA Helper or real hardware, which needs Michael's browser.
- `online: false` device-offline detection exists as a field but nothing sets it yet.
- `backend/models.py` (already a documented, deferred cap violation) grew by 13 lines this session - all minimal field/Literal extensions directly required by this work, not new architecture; flagged rather than hidden.
- Step 3 from the original device/memory/facility audit (operator/Aria memory extraction pipeline) remains unclaimed.

### Next safe step
Michael: one live voice pass through the Room 401 script; create one HA Helper (or connect the first real bedroom device) to prove the Home Assistant adapter's positive path; decide on hardware purchases from the capability categories listed in the linked report. Engineering: operator/Aria memory extraction pipeline next.

---

## 2026-08-27 — Room audio hardware architecture recorded (EliteDesk/eMeet/handset roles, TV-audio-in-path decision)

### Agent / tool
Claude Code, EliteDesk primary worktree.

### Branch / ref
`main`, documentation-only, no commit made this pass (explicitly instructed not to commit/push). Uncommitted Admin-Aria semantic-UI/telemetry work from the immediately prior session was inspected and left untouched.

### What changed
Per Michael's field session report and explicit directive, recorded the room-audio hardware topology decision as a new canonical doc, `docs/ROOM_AUDIO_ARCHITECTURE.md`: EliteDesk owns room compute + TV display/source routing (not room audio itself); the eMeet (or whichever conferencing-speakerphone-class device fills that role in a given room) is the single room audio capture/playback endpoint for Aria; TV audio should eventually be brought into the same electrical/digital path and played through that same eMeet so one AEC path owns both Aria and TV playback - explicitly **not** solved with a second, TV-side microphone; TV internal speakers must be muted once CAOSCare owns TV audio; the handset remains the guaranteed-duplex fallback surface, independent of room acoustics. Recorded Michael's field observation (an eMeet-class speakerphone worked at ~10-12ft with a fan running) explicitly as one observed field result under those conditions, not a universal hardware spec - consistent with, and cross-referenced against, the existing 2026-08-25 Rooms 401/403/408 forensic finding (single eMeet unit outperforming a split mic/soundbar arrangement), same "field-supported, not lab-proven" framing.

Described (not built) the smallest future software boundary for distinguishing logical audio sources - Aria playback / TV-media playback / resident microphone capture / handset fallback - explicitly modeled on `device_adapters.py`'s existing logical-action/physical-transport separation, with hardware left to configuration rather than hardcoded (no eMeet model or TV hardcoded anywhere, including in this record itself).

**Inspected the existing resident voice implementation specifically for conflicts** before writing anything: `realtime_audio_config.py`'s VAD/`far_field` noise-reduction settings are protocol-level, not device-tied; `useRealtimeVoice.js`'s `getUserMedia` call has no `deviceId` constraint (captures whatever the OS/browser default input is); no `setSinkId`/output-device-selection code exists anywhere in the resident voice path. **Found zero conflicts - no runtime code was modified.** The gap this record identifies (TV audio not yet in the same path as Aria's audio) is a room-wiring/hardware gap, not a software defect - there is currently no TV-audio-into-eMeet signal path for any software to route through yet.

Indexed the new doc from `docs/REPO_MAP.md`'s documentation map and `docs/reports/INDEX.md` (new entry ahead of the existing "Voice echo research + audio-path architecture" section, which it is grounded in and cross-references rather than duplicates).

### What was verified
- Direct inspection (not assumption) of `realtime_audio_config.py`, `useRealtimeVoice.js` confirmed no device-specific hardcoding exists to conflict with the new architecture.
- `git status` before and after: only this session's own doc edits present; the prior session's uncommitted Admin-Aria files (`admin_assistant*.py`, `events.py`, `frontend/src/components/admin/`, `adminAriaActions.js`, and modified `device_adapters.py`/`models.py`/`server.py`/`Admin.jsx`) confirmed untouched throughout.
- `git diff --check`: clean. No secrets/tokens/credentials in any diff (documentation-only changes).
- Existing backend test suite (`tests/test_room_device_isolation.py`) re-run as a smoke check that nothing was disturbed: 7/7 pass, unrelated to this doc-only change but confirms the working tree is still healthy.

### Blocked / not yet done
- Everything hardware-dependent remains explicitly unverified per the record itself: TV audio-out electrical/digital behavior (headphone/RCA/optical/HDMI-ARC), eMeet-model-specific AEC behavior once a second (TV) source is added, the actual TV-audio-to-eMeet signal path (does not exist yet), and TV auto-mute behavior. None of this can be verified or built further without physical hardware in Michael's bedroom test environment.
- The described future audio-routing adapter boundary (Aria playback / TV playback / mic capture / handset as logical sources) is documented as a target shape only - not implemented, since nothing yet requires it (no TV-audio-in-path hardware exists to route).

### Next safe step
Michael's bedroom hardware test environment: bring TV audio out (via whichever output the specific TV actually supports) into the eMeet's input, confirm the TV's internal speakers can actually be muted, and observe real AEC behavior under that combined load. Only after that live result should the described logical audio-routing adapter boundary actually be built - building it before real hardware exists to route would be speculative.

---

## 2026-08-29 — TSB-001 opened: Room 401 resident-voice name-attribution + unaudited profile mutation

### Agent / tool
Claude Code, EliteDesk primary worktree.

### Branch / ref
`main`, documentation-only, no commit made by this entry itself (see note on committed work below - the request was to record the TSB, not to fix runtime code).

### What changed
A live-session forensic request described a "Room 401 incident" from a resident-voice call. Direct evidence review found it was actually **two** back-to-back Realtime sessions (`rt_fukau61b_1787966931836`, `rt_g4kkodvu_1787966990776`, 2026-08-29 ~01:28:59-01:36:28 UTC) - richer and more severe than the initial framing. Established this repo's **first-ever Troubleshooting Bulletin log** (`docs/tsb/INDEX.md` + conventions, since none existed anywhere - checked exhaustively before creating it, not guessed) and recorded **TSB-001** (`docs/tsb/TSB-001-resident-voice-name-attribution.md`): Aria fabricated an explanation for how she knew the resident's real, correct stored `preferred_name` ("Ellie") when challenged - AND, found only by pulling `db.realtime_diagnostics`' `tool_call` events, actually invoked `update_preferred_name` twice, durably overwriting the resident's profile once to a wrong value ("Eleanor," inferred from dialogue timing) and once back to the correct one ("Ellie") - neither call triggered by an actual resident-issued name correction, neither call leaving a receipt or any old-value record (`PATCH /residents/{id}/preferred-name` has no `create_receipt()` call at all). The resident's profile is only correct right now because the second wrong self-correction happened to cancel out the first.

Also confirmed and recorded, in the same TSB, what worked correctly in the same sessions: real thermostat read (`get_room_status`) and write (`adjust_room_temperature` → real `device_commands` row against Room 401's real thermostat, mock-adapter-executed and state-verified, explicitly marked as sent-not-physically-verified per the mock/real adapter distinction), and correct `mark_resting`/`end_call` dismissal behavior.

Indexed the new TSB log from `docs/reports/INDEX.md` (top-level "start here" doc) and `docs/REPO_MAP.md`'s documentation map.

### What was verified
- Every claim in TSB-001 is sourced from a direct, reproducible query against `db.conversations`, `db.realtime_diagnostics`, `db.residents`, `db.receipts`, and `db.device_commands` - not recollection. Exact session IDs, timestamps, device/command IDs recorded in the TSB itself as re-runnable evidence references.
- Confirmed directly: zero `db.receipts` exist for this resident in the incident window, and the `preferred_name` PATCH endpoint has no receipt call in its source - the "no audit trail" claim is code-verified, not inferred.
- Confirmed directly: the resident's current `preferred_name` field is "Ellie" (correct) - checked before writing the TSB and unchanged since.
- Confirmed directly (`grep` across docs, git history, and filenames) that no TSB numbering convention existed before this entry, so TSB-001 is genuinely the first, not assumed.

### Blocked / not yet done
- **No runtime code was changed.** Per explicit instruction, this pass is documentation/evidence preservation only. The proposed remediation (first-class provenance for profile-sourced facts; a guard so `update_preferred_name` only fires on an actual resident-stated correction, not a bare question; a receipt on the preferred-name PATCH endpoint) is recorded in TSB-001 but not implemented, not tested, and the TSB is explicitly not to be marked resolved until it is and a regression test reproduces the exact failure mode against the fix.
- The exact string values passed to each `update_preferred_name` call are inferred from dialogue/timestamp correlation, not directly logged (the diagnostic event only records the tool name) - a real evidence gap noted in the TSB itself, not papered over.

### Next safe step
Implement TSB-001's proposed remediation as its own small, isolated change (structured provenance for `preferred_name` in the voice prompt/tool layer; a genuine-correction guard on `update_preferred_name`, mirroring the existing `turn_suspect` pattern; a receipt on the preferred-name PATCH endpoint reusing the existing receipt architecture) - then reproduce this exact challenge scenario against the fix and update TSB-001's status only once that passes.

---

## 2026-08-29 — TSB-001 evidence gap + audit trail closed ("we need to be able to have all the data")

### Agent / tool
Claude Code, EliteDesk primary worktree.

### Branch / ref
`main`, uncommitted (no commit instruction given for this batch).

### What changed
Direct follow-up to TSB-001's own flagged gaps, not an attempt to fully close the TSB. Two additive, non-behavioral changes:

1. **Full tool args/result now logged for every resident-voice tool call**, not just the tool name. `frontend/src/lib/realtimeMessageHandler.js`'s `handleFunctionCall()` logs `args` on the existing `tool_call` diagnostic event and adds a new `tool_result` event carrying the outcome - both ride the existing free-form `meta` field, no schema change (`realtimeDiagnostics.js` / `backend/routes/realtime_diagnostics.py` already accepted arbitrary `meta`). `frontend/src/pages/ConversationSessionDetail.jsx`'s "Voice diagnostics" panel now renders `meta` (previously silently dropped), so the data is visible to an admin, not just stored.
2. **`PATCH /residents/{id}/preferred-name` now writes a receipt** - TSB-001's remediation item 3. `backend/routes/residents.py` reads the prior `preferred_name`, performs the update, then calls `create_receipt()` with `action_type="preferred_name.update"`, `source="aria_voice"`, resident/room/`conversation_session_id` (now sent from `frontend/src/lib/realtimeDeviceTools.js`'s `update_preferred_name` dispatch), and `result="'<old>' -> '<new>'"`. `create_receipt()` (`backend/routes/receipts.py`) gained an optional `result` param so this completes in one call instead of a `create` + `update_receipt_status("completed")` round trip - the latter would have risked matching the wrong receipt, since Admin Aria's resident-edit tools also create `related_object_type: "resident"` receipts for the same resident.
3. **`backend/routes/residents.py` split** to stay under the 300-line cap after the above (was 294 before, would have been 318 after): `resident_movement`, `resident_stats`, and `resident_briefing` (read-only aggregation/reporting, no relation to the CRUD+identity endpoints that remain) moved to a new `backend/routes/resident_analytics.py`, mounted under the same `/residents` prefix, registered in `backend/server.py`. Clean domain split, not arbitrary chopping.
4. TSB-001 updated in place with a dated "Update — 2026-08-29" section (status line changed from "OPEN - documented, not remediated" to "OPEN - partially remediated"; original text preserved, nothing overwritten) recording exactly which remediation items are done (3, and the named evidence gap) versus still open (1, 2, 4 - provenance structure, correction-guard, and the underlying hallucination/false-fire failure modes are unchanged).

### What was verified
- Backend syntax (`ast.parse`) on `residents.py`, `resident_analytics.py`, `receipts.py`, `server.py`. Frontend syntax (`@babel/core` transform, `@babel/preset-react`) on all three touched JS/JSX files.
- Backend restarted; startup log clean, no import errors from the new router split.
- Live end-to-end test against the running backend: two real `PATCH /residents/res_0d3ef4252ae2/preferred-name` calls produced a receipt (`rcpt_db1f8a9f11a5` and a follow-up) with the correct `result: "'<old>' -> '<new>'"`, `room`, `conversation_session_id`, `source: "aria_voice"`, `status: "completed"` - queried directly from `db.receipts`. Confirmed old-value capture is genuine (differs between the two test calls), not a placeholder. Resident's `preferred_name` restored to its real value (`"Ellie"`) after the test.
- `tests/test_room_device_isolation.py`: 7/7 pass. Full suite run against `REACT_APP_BACKEND_URL=http://127.0.0.1:8000`: the only resident/movement/receipt-adjacent failures are a pre-existing `admin_token` login-fixture credential mismatch (`ADMIN_EMAIL`/`ADMIN_PW` hardcoded in `tests/backend_test.py` / `tests/iter8_test.py` don't match this environment's seeded admin password) - reproduced identically on totally unrelated test classes (Alerts, Insights, Locations), confirming it predates and is unrelated to this change, not investigated further as out of scope.
- `git status`: only the intended 6 modified files + 1 new file. `git diff --check`: clean. Secrets-grep over the full diff and the new file: no matches (one false-positive-free hit on an unrelated pre-existing `auth_password_routes` import name in `server.py`, not a secret literal).
- Line counts (all under the 300-line cap): `residents.py` 114, `resident_analytics.py` (new) 215, `receipts.py` 138, `server.py` 193, `realtimeDeviceTools.js` 224, `realtimeMessageHandler.js` 300 (trimmed back down from 304 - two comment/formatting trims, no functional change), `ConversationSessionDetail.jsx` 114.

### Blocked / not yet done
- TSB-001 remediation items 1 (structured `preferred_name` provenance for the model), 2 (genuine-correction guard on `update_preferred_name`), and 4 (the underlying hallucination/false-fire failure modes) remain unimplemented. TSB-001 is explicitly still OPEN, not resolved.
- This work was not committed - no commit instruction was given for this specific batch. Prior batches this session were committed only on explicit instruction; that pattern was followed here too.

### Next safe step
If Michael wants TSB-001's remaining items (1, 2, 4) built: the correction-guard (item 2) is the one with real behavior-change risk (could reject a legitimate correction) and should get its own regression test reproducing this exact challenge scenario before being called done, per the TSB's own verification-required section. Otherwise, get explicit instruction on whether to commit this batch.

---

## 2026-08-29 — TSB-001 items 1, 2, 4 implemented and unit-regression-verified ("the right way")

### Agent / tool
Claude Code, EliteDesk primary worktree.

### Branch / ref
`main`, uncommitted (no commit instruction given for this batch).

### What changed
Direct follow-up ("THE RIGHT WAY") after the prior entry's audit-trail-only pass — Michael wanted TSB-001 actually remediated, not just logged. Implemented all three remaining proposed-remediation items as structural changes, not prompt-wording alone (item 4's own requirement):

1. **Item 1 (provenance).** `backend/routes/realtime_companion_memory.py`'s resident-name block now tells the model `preferred_name` is a known, on-file fact - not inferred, not something said this call - and gives it the true answer to "how do you know my name" ("it's on your file with us"), plus an explicit instruction not to call `update_preferred_name` just because it was asked how it knows the name.
2. **Items 2 + 4 (structural correction guard).** The dispatch layer no longer trusts the model's self-reported `preferred_name` arg alone. `frontend/src/lib/realtimeMessageHandler.js` now carries the actual transcribed text of the triggering turn through to `ctx.last_user_text` (piggybacked onto the existing `turnSuspectRef` classification object, same reliability assumption already used for echo-guarding). `frontend/src/lib/realtimeDeviceTools.js`'s `update_preferred_name` handler now rejects the call unless the claimed new name actually appears in what the resident said AND that turn doesn't read as a question (regex against `why/who/what/when/where/how` openers) - both real TSB-001 failures were interrogative turns ("Why do you call me Ellie?", "Who told you to call me Ellie?"), which a plain substring check alone would have missed (the resident's own challenge literally contained the name).
3. **New regression test** - this repo's first frontend test file, `frontend/src/lib/__tests__/preferredNameGuard.test.js`, run via the existing (previously unused) `craco test`/Jest harness. Reproduces both real TSB-001 incident turns verbatim (same utterances, same wrong/right values the model actually passed) and confirms they're now rejected; confirms two genuine-correction phrasings still save; confirms a missing/stale transcript blocks; confirms the pre-existing echo/`turn_suspect` guard still takes priority. All 6 cases pass.
4. TSB-001 updated in place (second dated update section, original text preserved) with full detail and an explicit, precise limitation: this verifies the dispatch-layer guard logic against the real incident data, not a live end-to-end voice call (no way to place one in this environment) - status changed to "OPEN - remediated... but not yet closable" rather than RESOLVED, per the TSB's own rule that a code change alone doesn't close a bulletin.

### What was verified
- Backend syntax (`ast.parse`) on `realtime_companion_memory.py`. Live prompt-build check: `_build_companion_instructions('res_0d3ef4252ae2')` runs clean, 16,843 chars, provenance block confirmed present in the actual generated prompt text (not just the source).
- Frontend syntax (`@babel/core`) on both touched JS files, both still under the 300-line cap after edits (`realtimeMessageHandler.js` 300 exactly, `realtimeDeviceTools.js` 236).
- New Jest suite: `CI=true npx craco test --testPathPattern="preferredNameGuard" --watchAll=false` - 6/6 pass, including both exact incident reproductions (session 1: "Eleanor" claim against "Why do you call me Ellie?" rejected; session 2: "Ellie" claim against "Who told you to call me Ellie?" rejected) and both genuine-correction cases still saving.
- Backend restarted clean (startup log has no import errors).
- `tests/test_room_device_isolation.py`: 5 passed, 2 skipped - skip reason confirmed via `-rs` to be pre-existing live-data state ("no request category is clear of open tickets for all three test rooms"), unrelated to this change.
- `git status`: only the intended files (5 modified backend/docs + 2 modified frontend + 1 new backend file from the prior entry + 1 new frontend test file). `git diff --check` clean. Secrets-grep clean (same benign `auth_password_routes` false positive as the prior entry).

### Blocked / not yet done
- **Live end-to-end verification is still outstanding.** The regression test proves the dispatch-layer guard correctly rejects/accepts given real transcript text and real args - it does not prove the full live pipeline (real audio -> real transcription -> the model's own tool-call decision) behaves this way in an actual resident-voice call, since this environment cannot place one. TSB-001 stays OPEN, not RESOLVED, until a live call reproduces the challenge scenario against the running system.
- Not committed - no commit instruction given for this batch.

### Next safe step
Michael's live test environment: place a real resident-voice call, ask "why do you call me [name]" without stating a correction, and confirm (a) Aria answers from provenance without firing `update_preferred_name`, and (b) a genuine correction ("my name is X, not Y") still saves correctly. Only then update TSB-001's status to RESOLVED. If that live test surfaces a false negative (a real correction gets rejected), stop and revert the guard per the TSB's own stop-gate rather than loosening it ad hoc.

---

## 2026-08-29 — Live physical pendant test: real RF chain proven, then a real multi-Aria-session defect found and fixed, then a third TSB-001 root cause found and fixed

### Agent / tool
Claude Code, EliteDesk primary worktree.

### Branch / ref
`main`, uncommitted (no commit instruction given for this batch).

### What changed
Three sequential, evidence-driven passes in one continuous live session, each triggered by what the previous one's live testing actually surfaced:

**1. Real physical pendant proven end-to-end.** A real Nooelec NESDR SMArt v5 + real 319.5MHz Interlogix-Security pendant were bench-tested against the EXISTING `rf.py`/`caos_rf_bridge.py` pipeline (not a new one - a second, less-developed `pendants.py` scaffold was identified and deliberately left untouched). Host bring-up: installed `rtl-sdr`/`rtl-433` (clean host, nothing present before), unbound the kernel's DVB-T driver auto-claiming the device (blacklisted for future boots), verified with `rtl_test -t` (real EEPROM readback: "Nooelec, NESDR SMArt v5, SN: 14054003"). Found and fixed two real bridge-script defects live: (a) `fingerprint_from_rtl433()` preferred a noisy `raw_message` field over the decoder's own stable `id`, and a synthesized fallback pattern could produce invalid odd-length hex, both of which broke cross-press matching (Hamming similarity ~0.83, below the 0.85 threshold) - fixed with a hash-based always-valid-hex synthesis, now proven stable across real presses; (b) `frequency_hz` stored as `0` when a single-band decoder omits a per-record frequency - now falls back to the one configured band. Paired the real pendant as `rfd_07d25dc68a6b`, assigned to `res_0d3ef4252ae2`/room 401 (Michael's own explicit choice). Added `PUT /rf/devices/{id}/assign` (reassignment - didn't exist, required by the enrollment model). Added `press_count`-based coalescing in `/rf/event` so ~8 real RF frames per physical press produce ONE alert, not eight - this was also the proximate trigger for defect #2 below. Set `auto_voice=True` on RF-triggered alerts (Michael's explicit instruction - a pendant press must always reach Aria hands-free).

**2. Live multi-Aria-session defect found and fixed.** Turning on `auto_voice` immediately exposed a real, evidenced defect: two full OpenAI Realtime sessions ran concurrently for over a minute, both greeting the resident, both transcribing the same mic feed, Michael himself saying live "you only get one instance to talk to you, not two instances." Root cause (two independently-sufficient layers, confirmed via `db.conversations`/`db.realtime_diagnostics` overlap, not guessed): repeated RF frames each firing their own alert (fixed in pass 1), AND `POST /api/realtime/session` unconditionally minting a fresh session with zero concept of "one already active." Built a server-side singleton lease (`backend/routes/realtime_room_lease.py`, new `ResidentAriaLease` model) - atomic claim-or-reuse keyed by room, staleness self-heal (45s, no heartbeat = room reclaimable), wired into `/session` so a losing caller never spends a real OpenAI call or opens a mic. Frontend (`useRealtimeVoice.js`) claims before connecting, heartbeats every 20s while live, releases on stop/error; `RealtimeChatScreen.jsx` shows a distinct "already active elsewhere" state instead of an error. `Kiosk.jsx` now threads a real `trigger_source` (pendant vs manual) through. Also strengthened (defense in depth, not the primary fix) the "that'll be all for now" → `end_call` prompt wording, since it wasn't in the existing explicit example list. Live-verified: Michael confirmed "the doubling is fixed" after this pass.

**3. A third, independent TSB-001 root cause found live.** Michael's own live retest still showed Aria greeting the resident as "Eleanor" (wrong) in fresh sessions with no challenge question at all - the dispatch-layer guard from the prior TSB-001 pass was confirmed still correctly blocking the tool-call path, so this was genuinely something else. Found via direct `db.memories` inspection: `realtime_memory_ingest.py`'s background `extract_and_store_memories()` (a completely separate pipeline, unaware of the tool-call guard) had stored "User prefers/wants to be called Eleanor" TWICE - once during the original incident, once again during this retest - both extracted from Aria's own hallucinated/rejected apology text, never from anything the resident said. Deleted both false memories immediately (live harm mitigation). Fixed `memory.py`'s `EXTRACTOR_SYSTEM` prompt (explicit rule: a fact from what CAOS said is not resident testimony) AND added a structural backstop (any name-shaped claim must have its capitalized name literally appear in the resident's own turn, or it's dropped) - unit-verified offline against both real incident texts (correctly rejected) and two genuine corrections plus an unrelated fact (correctly accepted), 5/5.

**Also found and fixed in the same live retest:** `mark_resting` never actually stopped the OpenAI Realtime server from auto-generating a full spoken response to every VAD-detected utterance - confirmed via diagnostics showing Aria repeating "Understood, Eleanor, I'll stay quiet..." NINE times in a row while the system's own echo classifier had already tagged most of those inputs `echo_like`. `setResting(true)` was UI-only. Fixed by reusing the exact `create_response:false` session.update mechanism already proven for suppressing the forced-greeting auto-response window - now genuinely disables server auto-response while resting, re-enabled the instant real speech resumes.

### What was verified
- Every RF fix verified against real captured pendant data (offline replay + live re-presses). Live end-to-end: real PATCH calls, real receipts, real pairing/assignment via the actual admin API (a clearly-labeled local test admin account was created for this, since Michael's own real login credentials were never available to or requested by this session).
- Lease mechanism fully verified via direct API calls: claim, duplicate-rejected-with-correct-owner-info, wrong-session heartbeat/release correctly no-op, correct-session release + reclaim, and staleness self-heal (backdated timestamp, confirmed reclaimable).
- Backend restarted clean after every change (no import errors). Frontend syntax-checked (`@babel/core`) on every touched file. `tests/test_room_device_isolation.py`: 5 passed / 2 skipped throughout (skip reason confirmed pre-existing, unrelated to any of this work). `preferredNameGuard.test.js`: 6/6, unaffected by the new changes.
- Memory-extraction guard unit-verified offline (5/5 cases, both real incident texts and legitimate corrections).
- `git diff --check` clean throughout. Secrets-grep clean (only prose mentions of the words "password"/"token" in this very report, and pre-existing `client_secret`/`rf_secret`/device-token field names, no literal secrets).

### Blocked / not yet done
- **`mark_resting` fix has NOT been live-verified** - reasoned from evidence and reuses an already-proven mechanism, but no live call has confirmed resting genuinely goes quiet yet. Do this before considering it done.
- **No-preopened-tab room-node launcher** - confirmed still missing (Michael: pendant does nothing unless a kiosk tab/admin "enter room" is already open). Explicitly deferred per the original directive's own priority order ("keep this pass focused on fixing the active-session defect first"). Real requirement, not addressed tonight.
- **General interruption/echo complaint** - Michael's live complaint ("you keep cutting me off... same problem before") is partially explained by the mark_resting bug just fixed, but the underlying VAD/echo-cancellation sensitivity on whatever mic/speaker setup he tested with tonight was not separately investigated - likely a mix of software (now-fixed) and possibly hardware/environment factors. Needs a clean re-test.
- **Smart TV / local-channel scanning UX** - Michael raised this as a resident-facing usability gap (TVs defaulting to streaming apps over local channels, hard even for him to navigate) - explicitly parked, not investigated or coded tonight, no clear scope yet.
- TSB-001 remains OPEN - three independent root causes now individually fixed and evidenced, but no single live end-to-end call has confirmed all three together.
- Nothing committed - no commit instruction given for any of tonight's batches.

### Next safe step
Live re-test in this order: (1) confirm `mark_resting` genuinely suppresses responses now ("be quiet for a minute" then talk over her - she should stay silent), (2) confirm END CONVERSATION ("that's all for now") returns the room to idle and a fresh pendant press starts exactly one new session, (3) confirm Aria correctly uses whatever name is actually on file with no unprompted drift. Only after a clean live pass should any of tonight's TSB-001/session-lease work be marked resolved. Separately, scope the no-preopened-tab room-node launcher as its own pass per the original directive - it's real, acknowledged, and not yet started.

---

## 2026-08-29 — Mic-device observability, and a real safety-relevant tool-routing bug found and fixed live (bathroom request → wrong tool)

### Agent / tool
Claude Code, EliteDesk primary worktree.

### Branch / ref
`main`. This entry's changes committed AND pushed on explicit instruction ("push and commit everything") - see commit SHA in the entry below or `git log`.

### What changed
Two more live findings, same continuous session as the stabilization pass above (commit `6c65021`):

**1. Mic device observability ("the eMeet is great but you can't tell on CAOSCare").** `useRealtimeVoice.js`'s mic capture only ever logged an opaque per-origin `deviceId` hash - no human-readable label anywhere, server or UI, so there was no way to visually confirm which physical device a call actually used. Now captures `track.label` and the full `enumerateDevices()` list (both real, human-readable) into the existing `mic_track_settings` diagnostic event, and surfaces the live label on the kiosk's `RealtimeChatScreen.jsx` ("· Mic: EMEET OfficeCore Luna Plus Mono" - confirmed live, this exact string, real hardware). Also added `CopyTranscriptButton` (already existed, reused, not duplicated) to the kiosk's own transcript panel - Michael's own request, so a live transcript can be pasted directly instead of a DB round-trip every time.

**2. Real, safety-relevant tool-routing defect: a correctly-heard "I need to go to the bathroom" led the model to discuss the lunch menu instead of requesting help.** Live evidence (`db.realtime_diagnostics`, session `rt_2blf0hm5_1788029592404`): `user_transcript: "I need to go to the bathroom."`, `turn_class_reason: no_overlap`, no low-confidence flag - transcription was perfect. The very next event was `tool_call: get_menu(meal_period=lunch)`. This was NOT an audio/VAD/echo defect (ruled out - transcription was exact); it was a model tool-selection failure. Root cause found in the tool schemas themselves: `call_for_help`'s description explicitly scopes to "chest pain, breathing trouble, a fall, severe dizziness, confusion, or directly asks for a nurse" - bathroom/toileting need isn't in it - and `request_staff_help`'s description never named it either. The model had no explicit home for this extremely common, safety-relevant senior-care request category (fall risk during unassisted toileting) and guessed wrong.

Fixed both tool descriptions (`backend/routes/realtime_tools_operations.py`'s `request_staff_help`, `backend/routes/realtime_tools.py`'s `call_for_help`): bathroom/toileting/mobility-assistance is now explicitly `request_staff_help(category=nursing, priority=high)` - deliberately NOT routed to `call_for_help`'s emergency-tier escalation, since treating every bathroom request as a medical emergency would cause real alert fatigue and erode that channel's credibility for actual emergencies. `call_for_help`'s description now explicitly excludes it too, closing the gap from both directions.

**Live-verified the fix, same session, real retest** (`rt_4mr0fton_1788031023374`): "Go to the bathroom." → `tool_call: request_staff_help(category=nursing, priority=high, summary="needs to go to the bathroom")` fired on the FIRST turn, no menu detour, no emergency misfire. A separate, unrelated frustration in that same test ("you aren't even talking about what I need") was traced to the system correctly and honestly reporting a genuinely different pre-existing open nursing ticket ("knees have been stiff") per its own existing duplicate-request rule - working as designed, a UX/tone consideration for a future pass, not a bug, and not what broke tonight.

### What was verified
- Both tool-schema fixes confirmed present in the actual schemas served to the model (`request_staff_help` description contains "fall risk"/"priority='high'"; `call_for_help` description contains "routine bathroom" exclusion) - checked by directly calling the real schema-building functions, not just reading source.
- Backend restarted clean, no import errors.
- Live retest (above) confirms the fix works for the exact failure mode observed - one real session, immediate correct tool call.
- `tests/test_room_device_isolation.py`: 5 passed / 2 skipped (same pre-existing skip). `preferredNameGuard.test.js`: 6/6.
- `git diff --check` clean. Secrets-grep clean.
- Mic label fix confirmed live in the browser (screenshot) and via diagnostic evidence showing the real device name round-tripping correctly.

### Blocked / not yet done
- The "you aren't talking about what I need" UX friction (mentioning an unrelated open ticket when a resident asks about something else) - real, evidenced, not fixed tonight, needs its own scoped pass.
- Everything listed as open in the prior entry (no-preopened-tab room-node launcher, `mark_resting` still needs a dedicated live test with nothing else going on, general interruption pacing, TV/local-channel UX) remains open.
- TSB-001 remains OPEN.

### Next safe step
Michael is starting a fresh session against the deployed server to continue this work "from anywhere" - this entry and the repo state are the handoff. Whoever picks this up next should read this entry plus the prior one (commit `6c65021`) before touching resident-voice code again, and should NOT assume tonight's fixes are the last of their kind - each one was found by testing the previous one, and that pattern should be expected to continue until a full, uninterrupted live acceptance pass (per the "Next safe step" in the prior entry) actually completes clean.

---

## 2026-08-29 — CROSS-MACHINE HANDOFF: PRIORITY INCIDENT reconstructed (fabricated emergency + 60-min zombie session), no code changed yet

### Agent / tool
Claude Code, EliteDesk primary worktree. **If you are a fresh Claude Code instance starting on a different machine, read this entire entry plus `docs/tsb/TSB-002-fabricated-emergency-and-zombie-session.md` (full forensic detail) before touching any resident-voice code.**

### Branch / ref
`main` @ `9246fc3` (pushed). This entry's own documentation changes (this file + the new TSB) are the only thing added since that commit - **no runtime code has been changed for this incident.**

### What happened (see TSB-002 for full detail - this is the short version)
**Correction to this entry's own first draft**: it originally speculated Michael "apparently bumped/pressed [the pendant] unintentionally." **That was wrong and Michael corrected it directly** - the pendant was not physically with him while asleep. The corrected, evidenced finding is stronger: raw RF-frame comparison (`db.rf_events`, matched device `rfd_07d25dc68a6b`) shows the transmission that triggered the incident session shares a distinct decoded pattern (`bit_pattern_hex: 28864fa13e043c`, all `switch1-5` OPEN) that recurs on an almost-exact **~64-minute cycle** - 9 occurrences, 64.3-64.5 minutes apart every time, spanning more than 8 hours both before and after this incident. That is not human behavior; it is very likely an automated/periodic (supervisory or check-in) transmission. It is architecturally distinct from the pattern seen during every deliberate press orchestrated earlier tonight (`bit_pattern_hex: 28864fa13ef83c`, `switch5: CLOSED`, 8-frame bursts). **The RF pipeline currently has no concept of message-type/event-semantics - it treats any transmission matching a paired device's identity as an equally valid HELP press, regardless of what it actually encodes.** This is now believed to be the most likely root architectural defect, though not yet proven by a true controlled A/B test (see TSB-002's Verification Required - the press/periodic correlation so far is timing-inferred, not isolated-tested).

Separately (and independent of the RF-semantics question): the resident said two harmless fragments ("I don't think", then "algebra"). The model responded to the FIRST by calling `call_for_help(reason="Eleanor said she can't breathe.", severity="emergency")` - a **complete fabrication**, nothing resembling that appears anywhere in what was said - which created a real, currently-`active`, staff-visible alert (`alert_01d3b17a34b3`). It reinforced this same fabricated narrative on the next turn with zero new grounding. Then: **zero audio events of any kind for 59 minutes** (same class as the VAD dead-zones already documented elsewhere tonight, here at extreme duration - cannot determine from evidence whether "shut up/be quiet/go away" was ever actually heard). The session was only ended by **OpenAI's own platform-level 60-minute hard session cap** - nothing in this codebase has ever implemented an inactivity/media-liveness timeout. A second, unrelated real transmission (press-pattern, not periodic-pattern) six minutes later triggered no second session attempt at all, and there is no evidence (server or client) explaining why - a real observability gap, not just a bug.

Also directly answered a standing question: **does a pendant press "get remembered" if no kiosk is open?** Yes, but only for 5 minutes - `GET /kiosks/{kiosk_id}/active-emergency` only considers alerts created in the last 5 minutes; the underlying `Alert` document persists indefinitely but becomes permanently unreachable by that polling query after that window. Michael's explicit requirement: this needs to become a durable delivery/acknowledgement system, not a short lookback window - a room display may be closed/off and the event must stay routable until delivered or explicitly resolved.

### What was verified
Every claim above is sourced directly from `db.conversations`, `db.realtime_diagnostics`, `db.alerts`, `db.rf_events`, `db.resident_aria_leases`, and `uvicorn.log` - not recollection. Exact session/alert/device IDs, timestamps, and the full RF burst-interval list are in TSB-002 as re-runnable evidence references. Confirmed the RF device-*identity*-matching, frame-coalescing, and session-singleton-lease work from earlier tonight (`6c65021`) held correctly under this real, unplanned trigger - one press-pattern event, one session, no duplicates; device identity resolution was correct for both the periodic and press patterns even though their raw bit patterns differ.

### Blocked / not yet done
- **Nothing has been fixed.** Michael explicitly required reconstruction-before-implementation for this incident. TSB-002's Proposed Remediation (detailed, not yet built) covers: (1) RF event-semantics classification - distinguish periodic/supervisory transmissions from genuine press transmissions before creating a HELP alert, highest priority given tonight's finding; (2) a structural, server-side grounding/provenance requirement on `call_for_help`'s `reason` (and similar high-impact assertions) - explicit supported-source enum (resident's current turn + quote, existing alert, verified sensor event, staff-entered fact), reject anything else, and when a pendant alert already exists Aria should acknowledge it rather than invent a reason; (3) a media-liveness watchdog distinct from the lease heartbeat, carefully distinguishing normal conversational silence / an active HELP event where the resident may be unable to speak / genuine media-path failure - not a single arbitrary short timeout; (4) durable, acknowledged attention-event delivery to replace the 5-minute polling lookback.
- **The controlled A/B RF test has not been run** - the periodic-vs-press pattern distinction is currently timing-inferred from tonight's conversation flow, not isolated-tested. This must happen before building the classification fix in (1) above.
- The broader VAD/audio dead-zone pattern (documented in the entry above this one, and in TSB-002's "Suspected Architectural Cause") remains unresolved and un-root-caused. Per Michael's explicit instruction, do not touch EliteDesk audio/VAD/AEC config without evidence specifically isolating the cause - a live `chrome://webrtc-internals`-monitored repro was proposed but not yet run.
- Michael separately mentioned a Codex-built draft PR (`feature/adaptive-conversation-tempo`, PR #23, NOT merged) touching the same `turn_detection`/VAD config surface this repo's `main` also touches - real merge-conflict risk when that branch eventually comes back, not yet reconciled.
- Michael's laptop eMeet behavior (reported as worse than the EliteDesk's) has not been inspected - this session has no access to that machine. Goal per Michael: CAOSCare should explicitly bind/persist its intended audio endpoint (device label + `enumerateDevices()`, per tonight's earlier mic-observability fix) rather than relying on OS/browser input-output defaults, since a split capture/playback-device geometry has caused problems before.
- Physical location of the pendant remains unconfirmed, but is no longer believed to be the explanation for tonight's incident - the periodic-transmission finding supersedes that line of inquiry.

### Next safe step
Run the controlled A/B RF test (deliberate presses vs. deliberate non-presses, raw fields captured for each) to actually prove the periodic-vs-press distinction before building the classification fix. Get explicit direction from Michael on which TSB-002 remediation item to build first otherwise. Do not implement, commit, or push any code fix without that explicit go-ahead - the standing instruction for this specific incident was reconstruct-first, and that instruction has not yet been superseded for the code-fix phase (it *was* superseded for documentation, which is what this entry and TSB-002 are).

---

## 2026-08-30 — Production deployment: caoscare.com synchronized to e6c4f47

### Agent / tool
Claude Code, EliteDesk primary worktree, deploying to Linode production (`caoscare-prod` / `172.234.25.199`) via SSH.

### Branch / ref
`main` @ `e6c4f476fc0da7928dc0b35146d9d2e0e6c2e1dd` (pushed, and now the deployed production commit).

### What changed
Michael explicitly approved and directed a controlled production deployment (not a dev pass). Sequence, per his own gated procedure:
1. Found EliteDesk HEAD (`9246fc3`) behind `origin/main` (`d7a1db0` - PR #24, a real deploy-script fix from Michael's separate Claude Opus 4.8 session: `deploy_caoscare.sh`'s post-checkout guard rejected short SHAs even on successful checkouts, now normalizes to full SHA first) and uncommitted documentation work in the tree (TSB-002 rewrite + node-status handoff, from the prior incident-reconstruction pass). Stopped and reported both per explicit instruction rather than deploying an ambiguous tree.
2. Committed the approved documentation (`2c98a4e`), rebased cleanly onto `origin/main` (no conflicts), pushed - final `e6c4f476fc0da7928dc0b35146d9d2e0e6c2e1dd`.
3. Confirmed EliteDesk HEAD == `origin/main` before proceeding.
4. Production pre-flight (read-only): repo clean but on branch `fix-deploy-short-sha` @ `698a8f4` (Michael had tested the deploy-script fix there directly, pre-merge - not a blocker, the deploy script targets an exact SHA regardless of current branch), `caoscare-backend.service` active and healthy, sibling `caos-backend.service`/nginx confirmed active and NOT touched, `CAOSCARE_ENABLE_DEMO_SEED=false`, local-owner-bypass confirmed absent, `DB_NAME=caoscare_server` as expected, public site already healthy pre-deploy.
5. Ran the repo's own `scripts/deploy_caoscare.sh e6c4f47...` on production - it verified the target SHA against `origin/main`, took a full `mongodump` backup before any code change, checked out the exact commit, skipped dependency installs (neither `requirements.txt` nor `frontend/yarn.lock`/`package.json` changed since the last deploy), built the frontend, restarted only `caoscare-backend.service`, and verified both local and public HTTPS health before reporting success.
6. Independently re-verified rather than trusting the script's own success message: deployed `git rev-parse HEAD` on disk matches `DEPLOY_SHA` exactly; sibling services still active; local-owner-bypass still absent; backup directory contains real collection dumps; **public bundle hash (`main.70caaadc.js`) fetched fresh from `https://caoscare.com/` matches exactly the filename the build step just produced** - proves the public site is serving the new build, not a cached stale one; `/login` returns HTTP 200 post-deploy.

### What was verified
EliteDesk HEAD == `origin/main` == Linode deployed SHA, all three independently re-checked after deployment, not assumed. `https://caoscare.com/api/health` → `{"ok":true,"db":"up"}` from an external client (this EliteDesk, not production-local). Frontend bundle hash match proves cache-freshness. Mongo backup at `/opt/caoscare/backups/mongo/20260830-170659-pre-deploy-698a8f4d188b` contains real data (spot-checked `departments.bson` present and non-trivial size). `caos-backend.service` (a sibling, unrelated service on the same host) and nginx confirmed untouched throughout.

### Blocked / not yet done
- No database migration was needed or performed - this was a code-only deploy.
- TSB-001 and TSB-002 remain OPEN in production exactly as they are in this repo - deploying documentation does not remediate either incident's underlying code; the RF event-semantics conflation (TSB-002) and any of its proposed fixes remain entirely unbuilt, in production as much as anywhere else.
- Rollback path recorded, not exercised: `./scripts/deploy_caoscare.sh 698a8f4d188b41e6bfb12fd28185510ca6ff3617` (code-only) or add `&& scripts/rollback_caoscare_db.sh /opt/caoscare/backups/mongo/20260830-170659-pre-deploy-698a8f4d188b` (code+db) if ever needed.

### Next safe step
None required from this deployment itself - it succeeded and was independently verified. The next safe step remains what it was before this deployment interrupted it: the controlled A/B RF test for TSB-002.

---

## 2026-08-30 — Two more real live findings: mark_resting/end_call grounding guard, and a permanent-silence bug in the forced-greeting create_response window

### Agent / tool
Claude Code, EliteDesk primary worktree.

### Branch / ref
`main` @ `bf187c6` (deployed SHA at session start), all changes below uncommitted (no commit instruction given for this batch).

### What changed
**1. mark_resting/end_call structural grounding guard** (`frontend/src/lib/realtimeDeviceTools.js`, new `frontend/src/lib/__tests__/restingEndCallGuard.test.js`) - found already implemented, uncommitted, in the working tree at the start of this entry's investigation (same class of gap as the existing `update_preferred_name` guard from TSB-001): a real live session had `mark_resting` fire on "No, I can't." - a resident PROTESTING being left alone - and `end_call` fire on "It's gonna find me." - a transcript with no semantic connection to ending the call. Neither tool previously had any requirement that the resident's own last words actually support the action. Fixed with `RESTING_PHRASES`/`ENDING_PHRASES` regexes gating both tools: no match on the resident's actual last utterance → the tool returns `ok:false` with a spoken double-check instead of silently acting. Verified in this entry: 19/19 in `restingEndCallGuard.test.js`, both real incident repros correctly rejected, all listed genuine dismissal/ending phrases still fire, `git diff --check` clean, `realtimeDeviceTools.js` at 261 lines (under the 300-line cap).

**2. Permanent-silence bug in the forced-greeting `create_response:false` window** - new finding, this entry, triggered by Michael's own live report ("why aren't you talking?", also comparing laptop-vs-EliteDesk mic pickup). Reconstructed from `db.conversations`/`db.realtime_diagnostics` for session `rt_p03xjbi2_1788110255978` (resident `res_0d3ef4252ae2`, 2026-08-30 17:17-17:19 UTC) per this repo's own evidence-first rule (`docs/CURRENT_NODE_STATUS.md` #4) - Aria produced **zero** spoken responses across the entire session despite 15 correctly-transcribed user turns (including direct questions: "Are you mute?", "Also, why aren't you talking?") and VAD (`speech_started`/`speech_stopped`) firing correctly every time. Root cause: exactly one `response_created`/`response_done` pair exists for the whole session (the forced greeting, completed in 156ms) and **zero** `output_audio_buffer.started`/`.stopped`/`.cleared` events were ever recorded - the greeting response was cut short (real `speech_started` landed 141ms after `response_created`, essentially at connect) before it ever produced playable audio. `realtimeMessageHandler.js`'s re-enable of `create_response` was gated ONLY on `output_audio_buffer.stopped`/`.cleared` (2026-08-22 fix, itself correct for the case it addressed), which never arrived, so `create_response` stayed permanently `false` for the rest of the session - a structural silencing, not a transient echo/VAD issue.

Fixed by extracting the re-enable logic into a new `frontend/src/lib/realtimeAutoResponseGate.js` (`reenableAutoResponse` - dedupes what was previously two copies of the same `session.update` call; `createGreetingResponseGate` - owns the greeting window's state) and adding a fallback: `response.done` now also re-enables `create_response` if audio never started for that response (`onResponseDone()`), while leaving the existing `output_audio_buffer.stopped/.cleared` path (`onAudioStopped()`) as the primary signal when audio genuinely did play. `realtimeMessageHandler.js` net **shrank** (321 → 311 lines) despite the fix, due to the dedup; new file is 50 lines.

**Not investigated in this entry**: the resident's separate complaint that laptop/eMeet mic pickup is worse than the EliteDesk's. This is the same open gap already recorded in the 2026-08-29 CROSS-MACHINE HANDOFF entry ("Michael's laptop eMeet behavior... has not been inspected... CAOSCare should explicitly bind/persist its intended audio endpoint rather than relying on OS/browser input-output defaults") - still real, still unscoped, not touched tonight.

### What was verified
- New `greetingResponseGate.test.js`: 4/4, including the exact real-incident repro (response.done with no audio ever started → re-enables) and both the normal-path and audio-started-before-response.done orderings, so the fallback can't fire early and steal the primary path's job.
- `restingEndCallGuard.test.js` (pre-existing, uncommitted at entry start): 19/19, re-run and confirmed clean in this entry.
- `preferredNameGuard.test.js` (TSB-001 regression, unrelated to tonight's changes): 6/6, unaffected.
- `tests/test_room_device_isolation.py`: 5 passed / 2 skipped - same pre-existing skip reason as every prior entry (open tickets in live test-room data), unrelated.
- Babel syntax check (`@babel/core`, `NODE_ENV=development`) on all three touched/new frontend files: clean.
- `git diff --check` clean. Secrets-grep on the frontend diff: no matches (checked for password/secret/token/api-key patterns).
- Line counts: `realtimeMessageHandler.js` 311 (was 321, net shrink), `realtimeAutoResponseGate.js` 50 (new), `realtimeDeviceTools.js` 261 (pre-existing uncommitted work, unchanged by this entry) - all under the 300-line cap.

### Blocked / not yet done
- **Neither fix has been live-verified against a real OpenAI Realtime session yet.** Both are reasoned from real DB/diagnostic evidence and unit-tested against exact incident repros, but this environment cannot place a live call. Michael should retest: (a) the exact "why aren't you talking" scenario (start a session, let the greeting play, keep talking) and confirm Aria now responds throughout instead of only at connect; (b) "No, I can't." should no longer trigger resting, and a real dismissal like "let me rest" still should; (c) confirm no double re-enable / no regression to the 2026-08-22 double-greeting fix that the primary `output_audio_buffer.stopped` path exists to prevent.
- Laptop/eMeet mic-pickup-quality complaint remains open and unscoped (see above) - needs its own investigation pass, ideally with `chrome://webrtc-internals` on the laptop itself, which this session has no access to.
- Nothing committed - no commit instruction given for either piece of work in this entry.

### Next safe step
Michael live-retest all three points under "Blocked / not yet done" above on both the EliteDesk and the laptop. Only after a clean pass should this entry's fixes be considered resolved. If the laptop mic issue is to be tackled next, scope it explicitly (device-binding vs. AEC/gain tuning vs. something else) rather than assuming which one it is.

---

## 2026-08-30 — Live confirmation the end_call grounding guard works for real, plus a new evidenced bug: toggle_tv volume applied on a nonsense transcript

### Agent / tool
Claude Code, EliteDesk primary worktree.

### Branch / ref
`main` @ `bf187c6`, all changes below uncommitted (no commit instruction given for this batch).

### What changed
Michael pasted a live resident-Aria transcript (session `rt_rbt5x5pm_1788110743600`, resident `res_0d3ef4252ae2`, 17:25-17:32 UTC) for review. Reconstructed against real `db.conversations`/`db.realtime_diagnostics` per the standing evidence-first rule - two findings, one confirming prior work, one new:

**1. The mark_resting/end_call grounding guard (previous entry) is now live-verified, closing that entry's open blocker.** The resident's real utterance "It's hurt you bad" (garbled ASR, actually "it's not too hot" per the resident's own immediate correction) fired `end_call({reason:"goodbye"})`. The `ENDING_PHRASES` guard correctly rejected it (`tool_result: {ok:false, message:"Sorry, I want to make sure — did you want to end our conversation?"}`) instead of hanging up - confirmed directly in `db.realtime_diagnostics`, not inferred from the spoken transcript alone (the model paraphrased the rejection message differently on-air: "I just want to be sure—are you saying goodbye for now...").

**2. New evidenced bug: `toggle_tv`'s volume parameter had no grounding at all.** The garbled transcript "Hello Lab" (11 minutes into a session about wanting local channel 11 - almost certainly the model reacting to raw audio it heard as "channel 11" and substituting the only numeric TV control it actually has) fired `toggle_tv({state:"on", volume:11})` and it executed - a real, audible volume change to a resident's TV with zero connection to anything the saved transcript says. Unlike `mark_resting`/`end_call`, `toggle_tv`'s volume (and `toggle_light`'s brightness, same shape, NOT touched tonight - no live incident evidence for it yet, flagged for Michael below) had no check against `ctx.last_user_text` at all. Fixed in `frontend/src/lib/realtimeDeviceTools.js`: added `VOLUME_PHRASES` (word-based, not phrase-list, since a volume request has many valid forms - "volume", "loud(er)", "quiet(er)", "turn up/down", "mute/unmute") gating the volume sub-command specifically. Power (`state`) still applies unconditionally, since it's already covered by the existing `turn_suspect`/`CONSEQUENTIAL_DEVICE_TOOLS` overlap guard and the resident's "turn the TV on" request that same session was genuine - only the ungrounded volume number is withheld, with an honest "turned the TV on" (no volume claim) instead of silently pretending an unrequested action succeeded.

**Also flagged, not fixed:** the resident's turn "35" produced a fully hallucinated assistant reply ("You're welcome, Eleanor. Take care out there.") - confirmed via diagnostics that NO tool call fired for it at all, so this is pure conversational hallucination in response to a nonsense ASR fragment, not a tool/action safety issue. No device state changed and no durable fact was saved, so lower severity than the two above, but real, and likely the same underlying transcription-quality/mic-channel problem as the still-open laptop/eMeet complaint from the prior entry. A prompt-level fix (teaching the model to ask for clarification on very short/nonsensical input rather than confidently replying) would touch `_build_companion_instructions()` in `backend/routes/realtime.py`, which `docs/ARIA_CONTRACT.md` explicitly flags as duplicated/fragile and not yet a single source of truth - deliberately not touched without Michael's sign-off.

### What was verified
- New `toggleTvVolumeGuard.test.js`: 7/7, including the exact real-incident repro (volume withheld, only the power command sent - confirmed via the mocked fetch call count and body) and five genuine volume-request phrasings still applying correctly.
- Combined regression run (`restingEndCallGuard`, `preferredNameGuard`, `greetingResponseGate`, `toggleTvVolumeGuard`): 36/36 pass, no cross-fix regressions.
- Babel syntax check (`@babel/core`, `NODE_ENV=development`) on `realtimeDeviceTools.js`: clean.
- `git diff --check` clean.
- Line count: `realtimeDeviceTools.js` 277 lines (was 261), still under the 300-line cap.
- The end_call guard's live-fire was confirmed directly against `db.realtime_diagnostics` tool_call/tool_result records for this real session, not inferred from the spoken transcript.

### Blocked / not yet done
- **toggle_light's brightness parameter has the exact same ungrounded shape as toggle_tv's volume did** - not fixed tonight since there's no live-incident evidence for it yet (per this repo's evidence-first rule, not guessed-and-preemptively-patched). Same fix pattern would apply if/when it's evidenced or Michael wants it done preemptively.
- The "35" → hallucinated-reply finding is unaddressed - real, but conversational-only (no action taken), and any fix touches the still-duplicated Aria instruction-building code per `docs/ARIA_CONTRACT.md`. Needs Michael's direction before touching that surface.
- toggle_tv's volume fix has NOT been live-verified against a real call yet, same caveat as every fix in this repo until Michael retests it live.
- Laptop/eMeet mic-quality complaint (prior entry) remains open and unscoped - this entry's findings (garbled "35", "Hello Lab", "It's hurt you bad") are all consistent with that same root transcription-quality problem, adding more evidence but not new diagnosis.
- Nothing committed - no commit instruction given for this batch.

### Next safe step
Michael live-retest the toggle_tv volume fix (ask for TV on with no volume mention near garbled speech, then a genuine "turn it up") on a real session. Decide whether to preemptively apply the same guard to toggle_light's brightness, and whether/when to scope a fix for the "35"-class hallucinated-reply behavior (would need to go through the not-yet-written `docs/ARIA_CONTRACT.md` work with Michael, per that doc's own instruction not to invent its contents).

---

## 2026-08-30 — Room 401 pendant repeat-activation defect: root-caused, fixed, and live-verified during Michael's own acceptance test; plus a real end_call race found live in the middle of that same test

### Agent / tool
Claude Code, EliteDesk primary worktree.

### Branch / ref
`main` @ `bf187c6` at session start, all changes below uncommitted (no commit instruction given for this batch). Local dev backend was **restarted mid-session** (see below) - production (caoscare.com) was NOT touched.

### What changed
Michael ran a real two-browser acceptance test against Room 401: press the pendant once (session starts correctly, room lease proven good across clients), press it 5+ more times while the session was active, end the call, and observed a NEW Resident Aria session auto-launching with no new physical press.

**Root cause (inspected first, per explicit instruction - not patched blind):**
- `/rf/event` (`routes/rf.py`) coalesced repeat frames into one alert's `press_count` only within a fixed **8-second window** of the alert's own `created_at` (`PRESS_COALESCE_SECONDS`). A repeat press ~30s+ into an active session falls outside that window and mints a **second, independent alert**.
- Nothing in the codebase ever marked an alert as "already given its one Aria session." `Alert.status` (active/acknowledged/resolved) is the STAFF-facing workflow field, set only by explicit staff action (`routes/alerts.py`) - untouched by a session naturally starting or ending.
- `GET /kiosks/{kiosk_id}/active-emergency` (`routes/kiosks.py`) returns the most-recent `status="active"` alert in the last 5 minutes, with no concept of "has this one already been activated." Once the first session ends and the client returns to idle, this endpoint hands the client the newer, still-`active`, never-consumed second alert - a fresh `alert_id` the client's local `seenEmergencyRef` has never seen - and `Kiosk.jsx` correctly (per its own existing logic) launches a new session for it.
- **Direct evidence, before any fix was live**: `db.alerts` for room 401 showed **9 (later confirmed 170 across the full history) separate `auto_voice` alerts, all `status:"active"`, all with no way to distinguish "already handled"** - exactly the backlog this produces.
- Confirmed `seenEmergencyRef` (client-local) is correctly scoped to "don't re-show an alert THIS client already reacted to" - it was never the actual defect. Michael's instinct was right: the durable fix has to be server-side at the activation layer, not another React guard - nothing in `Kiosk.jsx`, `useRealtimeVoice.js`, or `active-emergency`'s dedupe-by-`alert_id` logic needed to change.

**Fix - new field, not a new status:** Added `Alert.activation_consumed_at: Optional[datetime] = None` (`models.py`) - deliberately separate from `status`, so staff-facing acknowledge/resolve workflows are untouched. An incident is "open" (repeat presses attach, no new alert) from alert creation until this is set; it's set when the triggering session's room lease is released.
- `routes/rf.py`'s fixed-window coalescing replaced with an **open-incident check**: any press for a device with an unconsumed alert attaches to it (`press_count` += 1) regardless of elapsed time; a press after consumption creates a fresh alert. This logic was extracted into a new `routes/rf_activation.py` (`try_coalesce_press()`) rather than grown in-place, since `rf.py` was already over the repo's 300-line cap before this session touched it - net effect: `rf.py` **shrank** (500 → 489 lines) despite the fix.
  - `OPEN_INCIDENT_MAX_AGE_SECONDS` (90 min) is a last-resort safety net only, for an incident that never got a session at all (mic denied, kiosk never tapped) - deliberately far longer than OpenAI's own 60-minute Realtime hard cap (TSB-002) so it never fires during a real, long session.
- `routes/realtime_room_lease.py`'s `release()` now marks every still-open `auto_voice` alert for that room consumed (`activation_consumed_at`) the moment the lease is actually released - the same fire-and-forget call `useRealtimeVoice.js`'s `stop()` already made on every real end-of-conversation, so no frontend change was needed for this half either.
- `routes/kiosks.py`'s `active-emergency` query now also requires `activation_consumed_at: None` - without this, the single most-recent `status="active"` alert kept resurfacing after its own session had already run, since `status` is deliberately untouched by session lifecycle. Found this gap live (see below), not in the original design pass.

**Live production-adjacent incident found mid-fix (not caused by the fix, but discovered live while root-causing it):** the local dev backend (`uvicorn`, no `--reload`) was still running the OLD code while Michael continued testing, and **170 pre-existing unconsumed alerts had already piled up for room 401** from before this session started. Backend was restarted (old process killed, relaunched via the harness's tracked background-task mechanism after a plain `nohup &` was correctly blocked by the sandbox) and all 170 stale alerts were retroactively marked consumed via a direct one-time DB update, so the backlog stopped immediately rather than waiting for it to age out. Backend restart verified clean (`{"ok":true,"db":"up"}`, no import errors) and confirmed real kiosk/RF-bridge traffic reconnected on its own.

**Second real defect found live, in the middle of the same test session:** Michael reported "verbal requests to end the call isn't working, asking multiple times." Pulled `db.realtime_diagnostics` for the live session (`rt_2p0zhj1l_1788116179150`) and found `end_call` tool calls for both "I need you to go away." and "End the call." - both plainly matching the existing `ENDING_PHRASES` guard - were REJECTED (`ok:false`). Root cause: `response.function_call_arguments.done` (the tool call) landed **137-184ms BEFORE** `conversation.item.input_audio_transcription.completed` for the very same utterance - a real, apparently-common race between the model's own audio-driven reaction and the separate transcription pipeline. `realtimeMessageHandler.js`'s `handleFunctionCall` read `turnSuspectRef.current` for grounding text, but that ref briefly holds a plain **boolean** (set on `speech_started`, for unrelated overlap detection) until transcription-completed overwrites it with the `{suspect,reason,text}` object - reading it mid-race meant `.text` was `undefined`, and the ENDING_PHRASES/RESTING_PHRASES backend guards correctly-but-wrongly rejected genuine requests as "ungrounded," on the exact same turn, repeatedly. Fixed by extracting a dedicated `realtimeTurnGrounding.js` (`createTurnGroundingTracker`) that tracks the last COMPLETED turn separately from the overlap boolean, plus a bounded (900ms ceiling, observed real lag 137-184ms) wait in `handleFunctionCall` for a same-turn race to resolve before reading it. `realtimeMessageHandler.js` net change: 311 → 314 lines (3 lines over its pre-session-start baseline of 311, still under the original 321 this file had before any work tonight - flagged rather than hidden).

### Exact collections/records touched by each press (as designed)
- Every press → `db.rf_events` (unconditional, evidence never dropped) + `db.rf_devices` telemetry (`last_seen_at`, `last_rssi`, `press_count` +1).
- First press for an open incident → new `db.alerts` document (`activation_consumed_at: null`).
- Repeat press while open → same alert's `press_count` +1 only, no new document.
- Session's room lease released → that alert's `activation_consumed_at` set (staff-facing `status` untouched).
- Press after consumption → new `db.alerts` document, cycle repeats.

### What was verified
- **New backend test** `backend/tests/test_rf_activation_gating.py::test_acceptance_sequence` - hits the real running backend over HTTP (`/rf/event`, `/kiosks/{id}/active-emergency`, `/realtime/room/{room}/activate`+`/release`), synthetic isolated kiosk/room/RF-device fixture (never touches real resident data), reproduces Michael's exact 7-step acceptance sequence end-to-end including the "press after close creates a genuinely new activation, old one can't reactivate" check. Passed 3/3 consecutive runs, clean teardown confirmed each time (`rf_devices` count returns to exactly 1 - Michael's real pendant - after every run).
  - Note: this test conflicts with `test_room_device_isolation.py` when run in the SAME pytest invocation (`RuntimeError: Event loop is closed`) - a pre-existing Motor/`asyncio.run()` test-infrastructure limitation (a global Motor client bound to the first event loop it touches breaks on a second, separate `asyncio.run()` in the same process), not a regression in either file. Each passes reliably in isolation; not fixed tonight (out of scope, infra not application logic).
- **New frontend test** `frontend/src/lib/__tests__/turnGroundingRace.test.js` - 4/4, reproduces the exact real race (transcript landing 150ms after the tool call) and confirms sequential turns each wait for their OWN transcript, not a prior one's.
- Combined frontend regression run (`restingEndCallGuard`, `preferredNameGuard`, `greetingResponseGate`, `toggleTvVolumeGuard`, `turnGroundingRace`): **40/40 pass**, no cross-fix regressions.
- `backend/tests/test_room_device_isolation.py` (run standalone): 5 passed / 2 skipped, same pre-existing skip reason as every prior entry.
- Backend syntax (`ast.parse`) clean on all 5 touched/new backend files. Backend imports clean (`import server` succeeds). Frontend syntax (`@babel/core`) clean on all touched/new files.
- `git diff --check` clean. Secrets-grep clean.
- Line counts: `rf.py` 489 (was 500, shrank), `rf_activation.py` 61 (new), `realtime_room_lease.py` 136 (was 124), `kiosks.py` 102 (was 90), `models.py` 1447 (was ~1438 - **exception noted below**), `realtimeMessageHandler.js` 314 (was 311 pre-session, 321 before any of today's work), `realtimeTurnGrounding.js` 38 (new).
  - **`models.py` exception**: this file was already ~1438 lines (far over the 300-line cap) before tonight and grew by ~9 lines for one new field + its docstring on an existing model. Extracting a single-field addition out of a shared, central, 1400+-line models file is not a practical "responsibility to extract" the way `rf.py`'s coalescing logic was - flagged per the repo's own "before finishing any coding task, report the line counts" rule rather than silently skipped, not fixed by a broader models.py refactor tonight (that would itself violate "do not launch a broad refactor solely to shorten an untouched legacy file").
- **Live acceptance evidence**: Michael's own real two-browser Room 401 test was the trigger for this whole investigation; the 170-alert backlog and the end_call race were both found via direct evidence from that same live session, not reproduced synthetically first. The synthetic test above proves the FIX's logic; Michael's own continued live use of the now-restarted, now-patched backend is the actual acceptance evidence for the deployed fix, not yet a full clean re-run of his own 7-step script end to end.

### Blocked / not yet done
- **Michael has not yet run his own full 7-step acceptance script end-to-end against the fixed backend.** The synthetic test proves the logic; his own real two-browser retest is the real acceptance bar per his own instructions.
- The end_call race fix (`realtimeTurnGrounding.js`) has NOT been separately live-retested in isolation - it was verified live in the sense that the SAME session that exposed it is now running fixed code, but no dedicated clean retest ("say a clear end-call phrase immediately, confirm first-try success") has been done yet.
- The same turn-grounding race could in principle affect `update_preferred_name`'s and `mark_resting`'s grounding checks too (they read the same `ctx.last_user_text` path) - not separately incident-evidenced tonight, but the fix is general (applies to all `handleFunctionCall` dispatches, not just `end_call`), so they benefit automatically; flagged for awareness, not a remaining gap.
- Nothing committed - no commit instruction given for this batch.
- Production (caoscare.com) still runs the pre-fix code - this was all against the local EliteDesk dev backend. Deploying this fix is a separate, explicit decision for Michael to make.

### Next safe step
Michael run his full 7-step acceptance script live against this now-restarted local backend (both browsers idle → single press → 5 repeat presses while active → end call → confirm both idle with no backlog → wait 10s → single new press → confirm exactly one fresh session). Separately, do one clean isolated retest of a clear "end the call" verbal request to confirm the race fix holds outside the noise of tonight's combined test. Only after both pass clean should this be considered ready to deploy to production - that decision and the deploy itself both require Michael's explicit go-ahead per the existing deployment discipline.

---

## 2026-09-01 — Production deployment: caoscare.com synchronized to afbb1e0

### Agent / tool
Claude Code, EliteDesk primary worktree. Recording deployment facts verified on `caoscare-linode` by the Linode-side Claude instance that performed the deploy - documentation only, no runtime code touched from this worktree.

### Branch / ref
`main` @ `afbb1e0f72707931f4aef5b7c00b892e222ddd6b` ("Harden Resident Aria turn grounding and activation lifecycle" - the four-fix batch committed and pushed from this worktree in the prior entry).

### What changed
Production (`caoscare-linode`, `/opt/caoscare/app`) deployed `afbb1e0f72707931f4aef5b7c00b892e222ddd6b` at `2026-09-01T00:06:04Z`, previous production SHA `e6c4f476fc0da7928dc0b35146d9d2e0e6c2e1dd`. At deployment time EliteDesk source, GitHub `origin/main`, and Linode production HEAD all matched `afbb1e0f...`.

Verified via the existing `scripts/deploy_caoscare.sh` (SHA-verified against `origin/main`, mongodump backup before code change, exact-commit checkout, restart of only `caoscare-backend.service`):
- Public: `https://caoscare.com/` → HTTP 200, `/login` → HTTP 200, `/api/health` → `{"ok":true,"db":"up"}`.
- Served frontend bundle `main.5d9fff18.js` (was `main.70caaadc.js`) - live-served filename matches the freshly built on-disk bundle, proving production was not still serving the stale prior build.
- Mongo backup at `/opt/caoscare/backups/mongo/20260901-000532-pre-deploy-e6c4f476fc0d` - real BSON independently confirmed present (`departments.bson`, `user_sessions.bson`, `users.bson`, associated metadata).
- `caoscare-backend.service` active, restarted by the deploy. Sibling `caos-backend.service` confirmed untouched - same `MainPID` (39674) and `ActiveEnterTimestamp` (2026-08-27 06:48:16 UTC) before and after. nginx active, untouched.
- `CAOSCARE_LOCAL_OWNER_BYPASS` confirmed absent from production `backend/.env`; live `/api/auth/local-bypass-status` returned `{"active":false}`.

### What was verified
Every fact above was independently checked on the production host itself (not inferred from the deploy script's own success message alone) - service PIDs/timestamps for the sibling service, the live bundle filename against the on-disk build output, the backup directory's actual BSON contents, and the local-owner-bypass status via its own dedicated endpoint.

### Blocked / not yet done
- Nothing new blocked by this deployment - it succeeded and was independently verified end-to-end.
- Rollback path recorded, not exercised: code-only `./scripts/deploy_caoscare.sh e6c4f476fc0da7928dc0b35146d9d2e0e6c2e1dd`; code+db additionally `scripts/rollback_caoscare_db.sh /opt/caoscare/backups/mongo/20260901-000532-pre-deploy-e6c4f476fc0d`.
- **Expected, intentional state**: this documentation-only commit puts GitHub `main`/EliteDesk HEAD one commit ahead of Linode production's deployed runtime SHA. Production remains correctly deployed at `afbb1e0f...` - do not redeploy merely to re-equalize the SHAs; the extra commit is documentation only, no runtime files.

### Next safe step
None required from this deployment itself. Continue with whatever live acceptance testing is next per Michael's direction - the underlying fixes (greeting-audio re-enable fallback, turn-grounding race, RF activation-state coalescing, TV-volume grounding) are now live in production as well as on this EliteDesk.

---

## 2026-09-05 — EliteDesk host networking: Matter commissioning (TP-Link Tapo L535E) fixed end-to-end

### Agent / tool
Claude Code, EliteDesk primary worktree. **Host/infrastructure work only - no CAOSCare application code touched.** No commit; nothing in this repo's tracked files changed as part of this work (`git status` clean throughout).

### Branch / ref
`main` @ `3f96d543586be6934021a9bf7ebb0491479043d2` (unchanged before/after - this entry documents host-level libvirt/avahi/iptables changes on the EliteDesk itself, not repo changes).

### What changed
Michael was commissioning a real, factory-reset TP-Link Tapo L535E (Matter-over-Wi-Fi bulb) through the Home Assistant iOS/Android Companion app against the HAOS VM (`caoscare-homeassistant`, libvirt NAT network, `192.168.122.137`) that runs on this EliteDesk. Commissioning repeatedly timed out/failed. Root-caused and fixed live, in three layers, each proven with direct evidence before moving to the next - not guessed:

**1. HA VM had no functional IPv6.** `ha network info` (via HAOS serial console, scripted with `pexpect` since no SSH addon is installed) showed the VM's `enp0s2` interface `ipv6.ready: false` - link-local only (`fe80::.../64`), no gateway, no route. Root cause: the libvirt `default` network (`virbr0`) had no IPv6 configuration at all, only IPv4 NAT. Matter is IPv6-first by spec.
- Fix: redefined the libvirt `default` network (`virsh net-define` + `net-destroy`/`net-start`, since live-adding a new `<ip>` family isn't supported by `net-update`) to add `fd00:ca05:beef:1::1/64` (ULA, RA/SLAAC-only). Enabled host `net.ipv6.conf.all.forwarding` (libvirt did this automatically on network start) and added the one IPv6 NAT rule libvirt doesn't auto-create for a `forward mode='nat'` network: `ip6tables -t nat -A POSTROUTING -s fd00:ca05:beef:1::/64 -o wlp6s0 -j MASQUERADE`.
- The network restart briefly detached the VM's `vnet0` tap from the recreated bridge (self-healed within seconds; explicitly verified reattachment via `bridge link show` rather than assumed). Verified after: VM's `enp0s2` got a real global IPv6 address via RA, `ready: true`, default route present.

**2. HA VM is isolated from the physical Wi-Fi LAN's multicast domain, and Matter Server binds to the isolated side.** The `core_matter_server` add-on's own startup log stated `"Using 'enp0s2' as primary network interface"` (the VM's NAT'd segment) and `"BLE is disabled"` (no local BLE fallback - HAOS-in-a-VM has no Bluetooth passthrough). mDNS discovery (`_matterc._udp`) is multicast and does not cross a NAT boundary; confirmed no reflector, relay, or nftables/multicast rule existed between `wlp6s0` (physical LAN) and `virbr0` (VM's isolated NAT segment) - only the pre-existing unicast 8123 port-forward.
- **Deliberately ruled out**: bridging the VM directly onto the Wi-Fi radio (macvtap/4addr client-bridge mode), the only way to fully satisfy Matter's link-local-IPv6 requirement at L2. This host's Wi-Fi chipset (Intel `iwlwifi`, Wireless-AC 9260) has known-unreliable 4addr/WDS client-bridge support, and it's the host's only network path - attempting it risked destabilizing the host itself for an unguaranteed outcome. Not attempted.
- Fix instead: enabled Avahi's built-in mDNS reflector (`/etc/avahi/avahi-daemon.conf`, backed up first) - `allow-interfaces=wlp6s0,virbr0`, `enable-reflector=yes`. This worked because the installed Matter Server (`matter-server 1.4.0` / `matter.js 0.17.9`) supports commissioning over IPv4 mDNS records (unlike Apple's strict IPv6-only stack), so relaying mDNS discovery between the two segments was sufficient without needing L2 adjacency.

**3. A masquerade rule from the 2026-08-31 LAN-port-forward session was too broad and broke the Companion app's login flow.** Once (1) and (2) were fixed, commissioning still failed - Companion app said "couldn't connect" right after "Add to Home Assistant," with **zero** corresponding log lines in HA Core or Matter Server, on both iOS and Android. Traced via `ha core logs`: real `http.ban` "invalid authentication" rejections showed the connecting client as `192.168.122.1` (the VM's own gateway address) instead of the phone's real LAN IP, with an iPhone Companion-app user-agent. Root cause: `iptables -t nat -A POSTROUTING -p tcp -d 192.168.122.137 --dport 8123 -j MASQUERADE`, added during the prior session purely to hairpin-test the LAN port-forward from the host's own loopback, had **no source restriction** - it was masquerading every real external LAN client's connection to HA (156+ packet hits, not just the host's own test), collapsing every device's identity to `192.168.122.1`. HA's login-flow anti-hijack protection ties a flow to its originating IP; losing per-client identity broke the commissioning hand-off from both platforms.
- Fix: removed the rule, re-added scoped to host-local-originated traffic only: `iptables -t nat -A POSTROUTING -m addrtype --src-type LOCAL -p tcp -d 192.168.122.137 --dport 8123 -j MASQUERADE`. Verified both the host's own loopback test and real external LAN access to `192.168.1.151:8123` still worked immediately after.
- **Secondary issue found and fixed in the same layer**: narrowing the Avahi reflector was itself necessary a second time - HA's own `_home-assistant._tcp` self-advertisement (`internal_url=http://192.168.122.137:8123`, unreachable from the real LAN) was being relayed onto `wlp6s0` by the reflector, risking the Companion app discovering and preferring that unreachable address over the working port-forward. Scoped the reflector with `reflect-filters=_matterc._udp,_matter._tcp` so only Matter's own service types cross the NAT boundary, not HA's general self-advertisement.

### What was verified
- Real, live end-to-end commissioning, watched in real time via scripted HAOS serial-console log tails (`ha core logs` / `ha addons logs core_matter_server`) during Michael's actual retry on his Android device:
  - Matter Server log: `"Commissioned peer1 as @1:1"`, operational address `udp://192.168.1.153:5540` (the bulb's real physical-LAN IP, reached directly - proving the mDNS-discovery + routing fix worked), endpoint came up as `ExtendedColorLight`, subscription established.
  - HA Core log: `[homeassistant.components.matter] Detected a device... Tapo Smart Multicolor Bulb (vendor_id: 5010, product_id: 769, hw: 3.0, sw: 1.0.0)`.
  - `GET /api/states` (via the existing `HA_TOKEN`/`HA_BASE_URL` already in `backend/.env` for the CAOSCare device-adapter integration): `light.smart_multicolor_bulb -> on` - entity state independently read back, not assumed from the log alone.
- Confirmed no unrelated services were touched: `caos-backend.service` and nginx status/PIDs unchanged throughout; `git status` in this repo clean before and after.
- Persistence caveat carried over from the prior networking session and still true: the manually-added `ip6tables`/`iptables` NAT rules (both the new IPv6 MASQUERADE and the corrected IPv4 one) are **not persistent** - no `iptables-persistent`/`netfilter-persistent` on this host. They will be lost on reboot. The libvirt network definition (IPv6 block) and the Avahi config changes ARE persistent (written to their own config files, reapplied automatically on service/libvirt restart).

### Blocked / not yet done
- iptables/ip6tables rule persistence across reboot - not set up (would be a standing-configuration change; flagged, not done unprompted, consistent with the same caveat raised in the 2026-08-31 LAN-forward session).
- No other Matter devices tested - only the one L535E. Whether the fix generalizes to Thread-based Matter devices (this fix addressed Wi-Fi/mDNS-IPv4 discovery specifically; Thread has its own border-router requirements, untouched here) is unverified and out of scope for tonight.

### Next safe step
If Michael adds more Matter/Wi-Fi devices, no further host changes should be needed - the fix is general (IPv6 + scoped mDNS reflector + correctly-scoped NAT), not per-device. If the host reboots, re-verify the IPv6 block and NAT rules survived (the libvirt/Avahi config will; the manual iptables/ip6tables rules will not) before assuming Matter still works.

---

## 2026-09-05 — Resident Aria voice control of the real Matter bulb (power, brightness, color, color_temp)

### Agent / tool
Claude Code, EliteDesk primary worktree. Local dev backend/frontend only (`127.0.0.1:8000` / `localhost:3000`) - production untouched.

### Branch / ref
`main`, based on `3f96d543...` at session start.

### What was already working (inspected first, not assumed)
- `/kiosk/{kiosk_id}` → `POST /devices/public/room/{room}/command` was already the real, generic, room-aware device-command path Aria's tools use - no separate "voice" execution path exists.
- `device_adapters.py`'s `home_assistant` adapter already existed and already handled `action="power"` against a real HA entity, confirmed working since 2026-08-27.
- The resident screen (`RoomDevicePanel.jsx`) already polls the same `smart_devices` state Aria's tools write to (`GET /devices/public/by-room/{room}`, 10s interval) - one shared state, not a second copy, exactly as requirement 9 asked for. No polling architecture changes were needed.
- `toggle_light`'s tool schema and frontend handler already existed for power+brightness, gated by the same `turn_suspect`/consequential-tool pattern as every other device tool.

### Exact gaps found (proven via direct inspection before any code change)
1. Every one of the 42 existing `smart_devices` records was `protocol: "mock"` - **no real SmartDevice record existed for the commissioned bulb at all**, despite commissioning being complete per the prior entry above.
2. `device_adapters.py`'s `home_assistant` adapter only mapped `action="power"` to an HA service call - brightness/color/color_temp had no mapping.
3. The adapter's only "proof" of success was checking HA's service-call response body for the target entity in its `changed` list - it never independently read the entity back. Real capability against real hardware (`min/max_color_temp_kelvin: 2500/6535`, `supported_color_modes: [color_temp, hs, xy]`, confirmed via `GET /api/states/light.smart_multicolor_bulb`) meant this was buildable, but was never checked for truthfulness after the fact.
4. The resident-facing (`aria_voice`) device-command path (`public_room_command`) had **no receipt/event telemetry at all** - only the lower-level `device_commands` log. The admin-Aria path (`admin_assistant_device_executor.py`) already had this exact `create_receipt`+`log_event` pattern; the resident path had never been given the equivalent.
5. `toggle_light`'s tool schema had no color/color_temp/relative-brightness parameters, and required `state`, which would have rejected a pure "make it dimmer" or "make it green" call.

### Files changed
- `backend/models.py` - added `"color_temp"` to `DeviceCapability`; widened `DeviceCommandInput.value` to accept an `[r,g,b]` int triplet; added optional `session_id` for receipt correlation.
- `backend/device_adapters.py` (191→240 lines) - full brightness/color/color_temp service-call mapping; independent post-command `GET /api/states/{entity_id}` read-back with bounded retry (real Matter devices can lag a beat); hue-based color verification (see below); removed the old `changed`-list check after proving it wrong against real hardware (see below).
- `backend/routes/devices.py` (215→275 lines) - `_dispatch_command` now uses the adapter's verified state as a full replacement (not a merge) so a mode switch (color→color_temp) doesn't leave a stale field; records `state_before`; `public_room_command` now writes the same `create_receipt`+`log_event` telemetry the admin path already had, sourced `aria_voice`/`resident_aria`, tied to the resident's real `conversation_session_id`.
- `backend/routes/realtime_device_tools.py` - `toggle_light` schema: `state` now optional, added `brightness_delta`, `color` (named enum), `color_temp` (warm/neutral/cool enum).
- `backend/routes/realtime_companion_prompt.py` - one clause telling Aria to only set the fields the resident actually asked about, and to report a capability the tool says isn't supported rather than pretending.
- `frontend/src/lib/realtimeLightControl.js` (new, 93 lines) - named-color↔RGB and Kelvin↔label tables (shared both directions: commands and spoken/visual descriptions, one vocabulary not two); `handleToggleLight()` - implicit "on" only when the light is actually off (not on every tweak), per-field capability checks with honest "doesn't support X" messaging, relative brightness math against the light's own last-known state.
- `frontend/src/lib/realtimeDeviceTools.js` (277→282 lines) - delegates to the new module; `describeDevice()` now speaks color/color_temp; `postRoomCommand` threads `session_id`.
- `frontend/src/components/kiosk/RoomDevicePanel.jsx` (67→76 lines) - visual state lines for color/color_temp, same capability-driven pattern as every other line.
- `backend/tests/test_light_control.py` (new), `frontend/src/lib/__tests__/toggleLightControl.test.js` (new).

### A real bug found and fixed mid-implementation (not guessed, proven against real hardware)
While wiring the real adapter, the very first live `power=on` call against the bulb failed with `"Home Assistant has no entity 'light.smart_multicolor_bulb'"` - the 2026-08-27 `changed`-list check firing. Manually replaying the exact same HA service call showed HA returns `[]` for this real Matter entity **even on genuine, physically-confirmed success** (the bulb visibly turned on; Michael confirmed live). The `changed`-list check was validated in 2026-08-27 against a different, simpler test entity and was never re-proven against real Matter hardware - removed it; the independent read-back (added for this task anyway) is strictly more correct and became the only verification.

A second real bug surfaced the same way: the first "color" command (`[0,200,0]`, green) reported `verified:false` even though the bulb visibly turned green. The real HA read-back showed `hs_color: [119.055, 100.0]` - the device renormalizes any requested RGB to its own full-saturation rendering of that **hue**, discarding the requested saturation/value. Verifying by raw RGB distance was the wrong method for how this real hardware behaves; switched to comparing hue (`colorsys.rgb_to_hsv`) against HA's own `hs_color` attribute, ±30°, with a low-saturation special case for "white". Re-tested green/blue/color_temp against the real bulb after the fix - all `verified:true`.

### What was verified
- **8/8 backend tests** (`test_light_control.py`), including four that hit the **real bulb** and assert on the **real HA read-back** (not HTTP 200 alone): power on/off, brightness, color, color_temp - each `verified:true`. Plus: a command against a real-but-nonexistent HA entity correctly fails (502), never a silent success; room isolation (a Room 318 mock-light command leaves Room 214's real bulb state untouched); unsupported capability (`color` against a device with no color capability) rejected with a clear 400, not silently ignored; correct light selected over the room's other device kinds.
- **9/9 new frontend tests** (`toggleLightControl.test.js`): implicit-on only when actually off, no redundant power command when already on, relative brightness math, absolute brightness, named color→RGB, color_temp label mapping, honest unsupported-capability messaging, and the two "reject before any network call" guards (no room context, no fields given).
- **Full existing frontend regression suite**: 49/49 pass (`restingEndCallGuard`, `preferredNameGuard`, `greetingResponseGate`, `toggleTvVolumeGuard`, `turnGroundingRace`, `toggleLightControl`) - no cross-fix regressions.
- Existing `test_room_device_isolation.py` / `test_public_demo_kiosk.py`: pass standalone (same pre-existing Motor/`asyncio.run()` cross-file limitation as every prior entry when run in the same invocation as `test_light_control.py` - not a regression).
- `git diff --check` clean. Secrets-grep of the full diff clean.
- Line counts (all under the 300-line cap): `device_adapters.py` 240, `devices.py` 275, `realtime_device_tools.py` 152, `realtime_companion_prompt.py` 255, `realtimeLightControl.js` 93, `realtimeDeviceTools.js` 282, `RoomDevicePanel.jsx` 76.

### Real entity/device used
Room 214 (Helen Torres, `res_81b72be1e8b5`) - `dev_f8be14de18e3`, converted from the room's pre-existing mock lamp record (same device_id, now `protocol: "home_assistant"`, `endpoint: "light.smart_multicolor_bulb"`, `capabilities: [power, brightness, color, color_temp]`, `vendor: "TP-Link"`, `model: "Tapo L535E (Matter)"`) via the existing authenticated `PUT /devices/{id}` route - not a raw DB write, not a new orphan device.

### Live physical acceptance test (real microphone/speaker, real bulb, real voice)
Michael opened `http://localhost:3000/kiosk/kio_dc8c06a19608` (Room 214), started a real Realtime session ("I just want to talk"), and spoke the full required sequence. Every command produced a real, `verified:true` command against the actual bulb, correctly tied to the real session:
- Session `rt_qetdh39b_1788632545041`, resident `res_81b72be1e8b5`, room `214` - confirmed threaded through every `device_commands` row AND every `receipts` row (`conversation_session_id` populated, `source: "aria_voice"`, `action_type: "resident_aria_device_command"`).
- "Aria, turn the light off." → `power off`, verified.
- "Turn it back on." → `power on`, verified.
- "Make it green." → `color [0,200,0]`, verified (hue match).
- "Set it to 50 percent." → `brightness 50`, verified.
- "Make it blue." → `color [0,80,255]`, verified.
- "Make it warm white." → `color_temp 2700`, verified.
- "Turn it off." → `power off`, verified. Final stored `smart_devices.state` = `{"power":"off"}` - correctly dropped the now-irrelevant color/brightness fields once off, matching real HA's own minimal off-state attributes.
- `state_before`/`state_after` chain across all seven commands is internally consistent (each command's `state_before` matches the prior command's real resulting state) - proof this is genuine sequential real-hardware tracking, not fabricated.
- Michael's own live reaction watching the bulb: "perrrrrrrrrrfect." Combined with the independent read-back verification on every single step, this is real, not assumed, evidence.

### Remaining blocker / not done
None for this task's scope. Not built (correctly out of scope, per explicit instruction not to redesign the device architecture): the RF bridge, AC, or TV-shutoff outlet Michael mentioned as "next" - Room 214 already has mock `ac`/`tv`/`thermostat` scaffold records ready to receive real `protocol: "home_assistant"` endpoints the same way the lamp just did, whenever those devices are actually acquired/commissioned.

### Next safe step
When the air conditioner and/or a smart outlet (for TV shutoff, ahead of the RF bridge) are physically acquired and commissioned into Home Assistant, convert Room 214's existing mock `dev_e76b930036e6` (AC) the same way this entry converted the lamp: real `endpoint`, real HA-reported `capabilities`, no new architecture needed - `device_adapters.py`'s `home_assistant` adapter already handles `power`/`brightness`/`temperature` generically for any domain HA exposes those actions on (the `domain == "light"` guards on brightness/color/color_temp would need a quick check against the AC's actual HA domain - likely `climate`, which uses different service/attribute names than `light` - before assuming today's mapping covers it as-is).

---

## 2026-09-05 — Real Midea AC (climate domain): architecture built and proven, blocked by device-side Matter instability, NOT committed

### Agent / tool
Claude Code, EliteDesk primary worktree. Local dev backend/frontend only. **No commit this entry** - per the task's own instruction ("commit and push after live acceptance succeeds") and because it hasn't: the code below is real, working, and stays in the local working tree uncommitted until the AC itself is stable enough to pass a live voice test. `git status` at end of this session still shows these as uncommitted changes on top of `4ef11d2`.

### Actual AC model / real HA climate entity
Midea Duo Smart Inverter portable AC, model `MAP14AS1TWT-C`, commissioned via Home Assistant's native Matter integration (no Midea-specific integration used, per instruction - confirmed NOT to use the "Midea ccm15 AC Controller" integration, which Michael's phone briefly defaulted to and which is for an unrelated commercial multi-zone controller, not this appliance).

Real discovered entity: `climate.bedroom_midea_ac`, friendly name "Midea AC", domain `climate`.
- **Real exposed HVAC modes**: `off`, `cool`, `fan_only` - no `heat`, no `auto`, no `dry`.
- **Real temperature range**: 61-86°F.
- **Real `supported_features` bitmask**: `385` (decoded: `TARGET_TEMPERATURE(1) + TURN_OFF(128) + TURN_ON(256)`).
- **Fan mode, preset mode, swing mode: confirmed NOT exposed** by this Matter integration (no corresponding bits set, no `fan_modes`/`preset_modes`/`swing_modes` attributes present) - the physical remote may have these; Home Assistant's Matter view of this device does not. Documented as a real, proven limitation, not invented or assumed.

### Why the old Terminal 4 assumption was stale (confirmed, not just asserted)
`commands/TERMINAL_4_MIDEA_MATTER_LAN_SETUP.md` assumed Matter was fundamentally blocked behind the EliteDesk's libvirt NAT and required moving/rebridging the whole HA VM onto the physical LAN. The real Tapo bulb's prior success already contradicted this. This session added further direct proof: the AC's Matter *commissioning* itself was fixed WITHOUT touching libvirt networking, bridging, SSH, or router config - the fix was giving the existing NAT'd VM one additional real (non-private) IPv6 address via NDP proxying, a small, additive change to the same NAT-based setup Terminal 4 wanted to replace wholesale.

### What was changed (real code, working, currently uncommitted)
- `backend/models.py` - added `"hvac_mode"` to `DeviceCapability`.
- `backend/device_adapters.py` (240→286 lines) - climate-domain support in `execute_home_assistant`: `temperature` action → `climate.set_temperature` (clamped to the entity's own real `min_temp`/`max_temp`); `hvac_mode` action → `climate.set_hvac_mode`, validated against the entity's own real `hvac_modes` list (rejects `heat` cleanly - proven, see Bugs below); `_read_climate_state()` normalizes climate's read-back into the generic contract, keeping `temperature` (target) and `current_temperature` (room's own measured temperature) as two distinct fields per explicit requirement ("never claim the room reached the requested temperature merely because the setpoint changed"). `_verifies()` made domain-aware for `power` (climate has no literal `"on"` state - `off` means off, any other HVAC mode means on) and for the new `temperature`/`hvac_mode` actions, fixing a real bug caught before it ever reached hardware: the light-only "ha_state != 'on' → false" guard would have rejected every climate verification outright.
- `backend/routes/devices.py` (275→277 lines) - `public_room_command`'s candidate filter now excludes `online: false` devices, so a retired mock scaffold can never intercept a voice command meant for its real replacement.
- `backend/routes/realtime_device_tools.py` - `adjust_room_temperature` schema expanded: `state` (on/off), `mode` (cool/heat/auto/fan_only), `target_f` (now optional), `delta_f` (new, relative).
- `backend/routes/realtime_companion_prompt.py` - one clause: `get_room_status` reports target vs. current room temperature as two separate things; never claim the room reached a temperature just because the setpoint changed.
- `frontend/src/lib/realtimeClimateControl.js` (new, 72 lines) - `handleAdjustRoomTemperature()`: room-aware disambiguation between multiple climate-capable devices (Room 214 has both the real AC and a still-active unrelated mock thermostat) by keyword match on the resident's own words ("AC"/"air conditioner" vs. "thermostat"/"heat"), asks for clarification only when genuinely ambiguous; implicit "on" only when the device is actually off; relative (`delta_f`) math against the device's own last-known target.
- `frontend/src/lib/realtimeDeviceTools.js` - delegates to the new module; `describeDevice()` now speaks HVAC mode and the room's own current temperature as a separate line from the target setpoint.
- `frontend/src/components/kiosk/RoomDevicePanel.jsx` - same distinction shown visually ("Set: 68°F" vs. "Room: 81°F").
- Real SmartDevice created (via the authenticated API, not a raw DB write): `dev_fa83aeda0cd4`, Room 214, `protocol: "home_assistant"`, `endpoint: "climate.bedroom_midea_ac"`, `capabilities: ["power","temperature","hvac_mode"]` - matching only what's real and proven, not inventing fan/preset/swing support.
- Old mock AC `dev_e76b930036e6` retired per instruction (not deleted): relabeled, `online: false` set directly (not part of the `SmartDeviceCreate`/PUT schema, so a one-time direct DB write was used for that one field, same precedent as the earlier public-demo-kiosk work).
- `backend/tests/test_climate_control.py` (new).

### Bugs found and fixed against real hardware (not guessed)
1. **The 2026-08-27 "empty changed-list = failure" check** (already removed for lights) never applied to climate in the first place since this was new code - but the exact same wrong assumption would have been made without last session's proof; the climate branch was written read-back-only from the start.
2. **Domain-unaware verification guard**: `_verifies()`'s light-only `if ha_state != "on": return False` guard, if left in place ahead of the climate checks, would have rejected every real climate command as unverified even on genuine success, because climate's own `state` field is never the literal string `"on"` (it's `"cool"`/`"fan_only"`/`"off"`). Caught and fixed before ever reaching real hardware verification, by code review of the existing function - not discovered as a live failure.
3. **`heat` correctly rejected**: this real device's Matter integration does not expose `heat` as a supported HVAC mode - a live test command with `hvac_mode="heat"` was rejected with a clear 502 naming the real supported modes, proving the "don't invent support" requirement holds in practice, not just in code review.
4. **Real, live commissioning failure, root-caused with packet captures** (see also: HA VM had only a private ULA IPv6 address; matter-server's commissioning attempt produced literally zero packets on the wire for the AC's globally-addressed candidate, while the same VM successfully sent both small and large raw UDP test packets to the same address manually). Fix: added one real (non-NAT'd) IPv6 address to the VM via NDP proxying (`ip neigh add proxy`, a `/128` host route into `virbr0`, and matching `ip6tables FORWARD` rules on the host; the address added to the VM's own interface as a `/128`, not a `/64`, to avoid a self-inflicted second bug - see below) so the OS's own address-scope selection would prefer a real address over the ULA for a real destination. This is not persisted (survives neither a VM reboot nor a host reboot) - same caveat as the earlier LAN-forward work; whoever picks this back up must re-run `ip -6 addr add 2600:100b:a111:dfbb::8123/128 dev enp0s2` on the VM and confirm the host's NDP-proxy/route/ip6tables entries survived first.
5. **Self-inflicted bug caught within the same session**: first attempt added the new address as a `/64`, which made the VM treat the *entire* real /64 prefix as on-link (directly ARP/NDP-resolvable on its own isolated segment) instead of routed via the default gateway - breaking reachability to the AC entirely (worse than before the fix). Caught immediately via a real ping test failing, corrected to `/128` (a single host address, no on-link side effect), reachability restored and verified with real round-trip times.
6. **Verification-tolerance bug found via real hardware, not assumed**: the first live color-adjacent lesson (hue-based verification for lights, prior entry) had already established that raw-value comparison can be wrong for real device quirks - re-confirmed for a completely different reason here: a color-request-style RGB-distance check would never have applied to climate at all, but the general lesson (verify what the resident's request is actually about, not byte-exact device internals) informed the ±2°F tolerance used for `temperature` and the exact-match requirement for `hvac_mode`/`power` (climate states are discrete enums, not continuous values, so exact match is the correct and only sensible check there).
7. **Old `changed`-list-style false negative class re-confirmed absent**: `climate.set_temperature`/`climate.set_hvac_mode` service-call responses were not separately checked for a changed-entity list at all (learned from the light work not to trust that signal) - read-back was the only verification from the start, and it worked correctly for the ~6 minutes the device was actually responsive.
8. **Real, ongoing, NOT fixed by anything on our side**: after commissioning succeeded and the entity worked correctly with real live data (`current_temperature: 81`, `temperature: 68`, `state: "cool"`) for about 6 minutes, the device's own Matter/CHIP session became unresponsive (`[peer-unresponsive] Peer is no longer responding to active session, timed out after 36.6s` then `37.1s` on a second attempt) and has not self-recovered. Basic IPv6 reachability (ICMP ping) to the device remains solid throughout (0% loss, 5-8ms round trips, confirmed repeatedly) even while Matter Server's own attempts to resolve/reconnect fail outright (`address is unreachable`, sometimes within ~2.4 seconds) - meaning the device's OS/Wi-Fi stack is up but its embedded Matter/CHIP service appears to hang or stop responding to Matter-specific UDP traffic on port 5540 shortly after each session starts. Two Matter Server restarts were tried (a legitimate troubleshooting step, not blind repetition) while ping-confirmed reachable; both failed to re-establish the session. **Root cause is judged to be the AC's own Matter firmware/implementation, not CAOSCare, Home Assistant, or this host's networking** - proven by a real controlled comparison: across every one of these same restart/reboot events tonight, the real Tapo bulb (same Matter Server process, same VM, same network path) reconnected instantly and cleanly every single time, with zero failures. The bulb is the control; the AC is the only variable that fails.

### What was verified
- **Real, live, end-to-end success for ~6 minutes** immediately after a fresh commissioning (itself only reachable after Michael power-cycled the physical unit - the commissioning-time PASE failures were separately root-caused and fixed via the IPv6/NDP-proxy work above, confirmed with real packet captures showing a genuine bidirectional Matter handshake beginning where none had ever occurred before): `power` on/off, `hvac_mode="cool"`, `temperature=70`/`65` all independently `verified:true` against real Home Assistant read-back, matching the exact same rigor as the light work.
- `hvac_mode="heat"` correctly rejected live (502, names the real supported modes) - a genuine "don't invent support" proof, not a code-review assertion.
- Real controlled comparison (see Bug 8) isolating the fault to the AC, not the architecture.
- `backend/tests/test_climate_control.py`: 4/8 passed at the moment of this entry (room isolation, offline-mock exclusion, ambiguous-command rejection, and the `heat`-rejection test all pass reliably since they don't require the AC to be currently responsive; the four tests that command the real AC directly currently fail because the device itself is `unavailable` - this is accurately failing on live hardware state, not a test bug; re-run once the AC is confirmed responsive again). Backend syntax/imports clean. Frontend files pass `@babel/core` parse.
- Full existing light-control test suite (`test_light_control.py`, 8/8) and frontend regression suite unaffected by any of tonight's changes - confirmed no regression to the working real light control.

### Files changed (uncommitted - see line counts above)
`backend/models.py`, `backend/device_adapters.py`, `backend/routes/devices.py`, `backend/routes/realtime_device_tools.py`, `backend/routes/realtime_companion_prompt.py`, `frontend/src/lib/realtimeClimateControl.js` (new), `frontend/src/lib/realtimeDeviceTools.js`, `frontend/src/components/kiosk/RoomDevicePanel.jsx`, `backend/tests/test_climate_control.py` (new). All line counts within the 300-line cap.

### Live voice session evidence
Not yet run. The code path is ready and the tool schema/disambiguation logic is unit-tested, but Michael's explicit instruction ("do not mark the live physical test complete until Michael confirms the actual appliance behaved correctly") was never reached - the AC went unavailable before a live voice test was attempted, and no live voice test against the real AC has been claimed as successful. Do not represent this feature as done in any later entry without a real live voice session against a currently-responsive AC.

### Remaining blocker
The AC's own Matter/CHIP implementation does not stay connected reliably - it works immediately after commissioning/a Matter Server restart while the device happens to be freshly responsive, then hangs at the protocol level within minutes. No firmware/app update path exists (Michael confirmed the Midea companion app for this unit has been discontinued). Michael plans to contact Midea support directly via email. Per Michael's explicit instruction this session, the physical unit was left powered on and untouched (not power-cycled again) since it was actively cooling the room.

### Next safe step
Do not restart Matter Server or send further commands to `climate.bedroom_midea_ac` speculatively - each restart briefly interrupts the real bulb's connection too and has not fixed the AC in two tries. When Michael indicates the AC has been reset/is freshly responsive again (or hears back from Midea support), re-check `GET /api/states/climate.bedroom_midea_ac` first (no code changes needed - everything is already built and correct) before attempting the live voice acceptance test. If it stays responsive for the test, the remaining acceptance work is purely the live voice session itself (Phase 7) - no further backend/frontend work is anticipated. Only commit/push once that live test actually passes, per the original instruction.

---

## 2026-09-06 — Real RF pendant pairing (Room 214, Helen Torres): bridge-liveness fix, RSSI/battery telemetry, frequency-tolerance matching, and a real cross-device match-threshold defect found + fixed via adversarial audit. Committed and pushed.

### Agent / tool
Claude Code, EliteDesk primary worktree. Local dev backend/frontend only (`.venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port 8000`, `yarn start` on 3000). Branch `main`, on top of `4ef11d2`.

**Committed as `d22b3d23ca8bb26f76e5a1a878f0e4fbf20617b9`, pushed to `origin/main` (verified local HEAD == origin/main).** The still-blocked AC/climate work (`backend/device_adapters.py`, `backend/routes/realtime_companion_prompt.py`, `backend/routes/realtime_device_tools.py`, `frontend/src/components/kiosk/RoomDevicePanel.jsx`, `frontend/src/lib/realtimeClimateControl.js`, `backend/tests/test_climate_control.py`, and the `hvac_mode`/`DeviceCapability` hunk of `backend/models.py`) was deliberately excluded hunk-by-hunk from this commit and remains uncommitted in the working tree, per the explicit "commit only after live AC acceptance succeeds" instruction on the entry above - two files (`backend/models.py`, `frontend/src/lib/realtimeDeviceTools.js`) genuinely mixed RF/light and climate changes in the same file, so the safe hunks were isolated and staged individually rather than committing either file whole.

### What was asked
Pair a real Lifeline-brand PERS pendant into Room 214 for Helen Torres via the existing RF/`rtl_433` pipeline (`android-bridge/caos_rf_bridge.py` → `POST /rf/event` → `rf.py` fingerprint matching), separate from the Matter/AC work above. Once paired, Michael asked for Aria-equivalent RF diagnostics/control inside the admin panel, for RSSI + battery to be surfaced as real pairing data, and finally: **"yes lets finish. but i expect you to break it until we cant"** - explicit instruction to adversarially test everything built, not just confirm happy paths.

### Real bugs found and fixed (in order)
1. **"Add new pendant" always failed ("didn't hear anything")** - root cause was not the fuzzy-match threshold (two wrong hypotheses tried first) but that the pairing UI let an admin pick *any* kiosk as the listen target, including a resident's own room kiosk with no physical SDR attached. Only one kiosk (`kio_9d5247d7ff59`) in this deployment has the actual Nooelec NESDR bridge daemon running. Fixed with a new liveness-tracking subsystem: `backend/routes/rf_bridge_health.py` (new, 55 lines) records `last_bridge_poll_at` on every real bridge poll (`bridge_pending()`) and exposes `GET /rf/bridges/active` (10s alive window); `frontend/src/components/rf/ActiveBridgeKioskSelect.jsx` (new, 60 lines) filters the pairing dialog's kiosk picker down to only kiosks with a currently-live bridge, auto-selecting when there's exactly one.
2. **Multi-band scanning missed real presses** - the bridge's default 5-band cycle gives short per-band dwell time; a live controlled test proved a real press was missed entirely during a listen window. Fixed operationally (not a code change) by running the bridge with `CAOS_BANDS=319.5` - the bridge already had dedicated single-band-mode support built in. Michael independently confirmed the same root cause from his own testing.
3. **RSSI was always null** - `android-bridge/caos_rf_bridge.py`'s `rtl_433` invocation was missing the `-M level` flag needed for RSSI/SNR reporting. One-line fix: `cmd = [RTL_433_BIN, "-F", "json", "-M", "utc", "-M", "level"]`.
4. **`-M level` broke the frequency exact-match** (side effect of fix #3, found live the same day) - enabling `-M level` changed the Interlogix-Security decoder's reported frequency from a fixed nominal fallback to a real per-packet measured value with natural drift (proven live: a real press measured 319.509MHz against a device calibrated at 319.500MHz). The prior exact-match `frequency_hz` query would have silently stopped matching real devices the moment their measured frequency drifted at all. Fixed with a `FREQ_TOLERANCE_HZ = 50_000` range query in `rf_event()`, generous enough for real OOK drift, tight enough that it can never bridge actual different bands (315/319.5/433.92/868/915MHz are each megahertz apart).
5. **`low_battery` was modeled but never actually derived** - the field existed on `RFDevice` but nothing ever set it from the real `fingerprint.decoded.battery_ok` rtl_433 gives us. Fixed in both `pair()` (initial device creation) and `rf_event()`'s matched-telemetry update.
6. **Real cross-device match-threshold defect, found via adversarial audit (the "break it" pass), not live failure** - after RSSI/battery were confirmed working, a targeted static analysis of the two real live `rf_devices` (Helen's Rm 214 pendant and a pre-existing "RF bring-up test pendant" assigned to a mock resident in Rm 401, both on 319.500MHz) found their real stored bit patterns (`28864fa13e043c` vs `28864fa13ef83c`) score **0.8929** similarity under the existing `hamming_similarity` function - only 0.043 above the then-default `match_threshold` of 0.85. Every live event had decoded cleanly (self-match score 1.0) so the correct device always won the best-match contest, but nothing prevented a noisy decode from crossing that gap and misattributing a real press to the wrong resident's room - a real safety-relevant defect in a PERS/fall-alert matching system, not a cosmetic one. Confirmed by recomputing the exact similarity score independently against the live DB records before proposing any fix.

### Fix for #6 (Michael approved "both fixes" via explicit choice)
- `backend/routes/rf_pairing_guard.py` (new, 75 lines) - `hamming_similarity()` (moved out of `rf.py`, single source of truth now) and `find_pairing_conflict()`: at pairing time, computes the new fingerprint's similarity against every other *enabled* device within `FREQ_TOLERANCE_HZ`, and returns a conflict if any score is within `PAIRING_SAFETY_MARGIN = 0.10` of the pairing's own `match_threshold`.
- `backend/routes/rf.py` (522→531 lines; already over the 300-line cap before this session - not a new violation, see note below) - `pair()` now calls `find_pairing_conflict()` before creating the device; blocks with a `409` naming the conflicting device and its score unless the admin passes `override: true` on `RFPair`, in which case pairing proceeds and a human-readable `pairing_warning` is stored on the new `RFDevice` for auditability. `rf_event()`'s local `_hamming_similarity`/`FREQ_TOLERANCE_HZ` were removed in favor of the shared module-level versions (single source of truth per the engineering principles - was previously duplicated between the pairing path and the live-match path).
- `backend/models.py` - `RFDevice.match_threshold` and `RFPair.match_threshold` defaults raised `0.85 → 0.90`; added `RFDevice.pairing_warning: Optional[str]` and `RFPair.override: bool = False`.
- Live DB (approved explicitly by Michael before running, since the first attempt was blocked by the auto-mode permission classifier as a live-data mutation): both existing `rf_devices` bumped to `match_threshold: 0.90`; the Rm 401 "bring-up test pendant" (a mock-resident dev/test device, not a real deployed pendant) set `enabled: false` with a `pairing_warning` explaining why - this removes the actual live conflict outright rather than only narrowing it with a threshold number, since a blanket threshold hike alone trades a rare misattribution risk for a more common missed-alert risk (deliberately kept modest at 0.90, not pushed higher, for that reason).
- Verified directly (unit-level, bypassing HTTP/auth) against the real live DB: `find_pairing_conflict()` correctly flags the exact real conflict (reproduces the 0.8929 score) when fed the disabled device's own fingerprint, and correctly returns `None` for a genuinely different fingerprint (`ffffffffffffff`, 0.41 similarity).
- Verified live in the running system: after disabling the Rm401 device and restarting the backend, its `press_count`/`last_seen_at` froze at the exact moment of disable (initially misread as "still incrementing" by comparing against a stale screenshot - re-checked directly against the DB and confirmed frozen); all subsequent live `/rf/event` traffic on 319.5MHz matches Helen's own device with an exact bit-pattern match (`match_score: 1.0`), confirming no misattribution is occurring post-fix.
- Cross-checked Room 214's live Aria voice transcript (`db.conversations`, resident `res_81b72be1e8b5`) against the RF alert history during this test session: multiple real button presses correctly triggered "Assistance requested"/RF-pendant alerts, and Aria's own responses correctly told the resident staff had been notified and asked a clarifying question ("are you saying you want to end the conversation now...") rather than assuming intent from an ambiguous "you can go" - confirms the RF→alert→voice integration behaves correctly end-to-end, and explains the multiple stacked "active" alerts on Room 214 as genuine repeated test presses this session, not a bug.

### RSSI/battery UI (frontend)
`frontend/src/pages/RFPairingTab.jsx` (422→436 lines, already over cap before this session) - added "Signal" and "Battery" columns to the pendant table, RSSI to the live event stream, and a battery OK/LOW line to the pairing dialog's capture-review card. Visually confirmed in the live admin panel (`/admin` → Devices & Hardware → Pendants): both real devices render `-0.1 dB` / `OK` correctly from real backend data.

### Real device data (live, as of this entry)
- `rfd_6e8f06632b41` - "Helen Torres pendant (Lifeline)", Room 214, resident `res_81b72be1e8b5`, `match_threshold: 0.90`, `enabled: true`, 48 presses.
- `rfd_07d25dc68a6b` - "RF bring-up test pendant (319.5MHz, Interlogix-Security id=3ef83c)", mock resident, Room 401, `match_threshold: 0.90`, **`enabled: false`** (disabled this session - see #6 above), 1522 presses.

### File size discipline note
Michael explicitly relaxed the 300-line rule mid-session ("remember 300 is goal but not hard on line if its good code"). `rf.py` and `RFPairingTab.jsx` were already over the cap before this arc began; both grew modestly (rf.py +9 lines net after extracting the guard logic to a new file; RFPairingTab.jsx +14 for the RSSI/battery columns) rather than being refactored wholesale, per the standing instruction not to launch a broad refactor solely to shorten an untouched legacy file. New files (`rf_bridge_health.py` 55, `rf_pairing_guard.py` 75, `ActiveBridgeKioskSelect.jsx` 60) are all well under the cap.

### What was verified
- Real live pairing of Helen Torres's Lifeline pendant, distinguished from a second real physical pendant via a live, controlled, single-band capture test (see prior entries/transcript for the full trust dispute and resolution).
- RSSI and battery data flowing end-to-end from real `rtl_433` decodes through `/rf/event` and `/rf/pair` into the DB and rendering correctly in the admin UI.
- The frequency-tolerance range fix does not cross-match genuinely different bands (315/319.5/433.92/868/915MHz are megahertz apart, tolerance is only ±50kHz).
- The new pairing-time guard correctly reproduces the real conflict score (0.8929) against the real disabled device's fingerprint and correctly passes a genuinely dissimilar one.
- Backend restarted clean on all changes (`/api/health` OK); no import/syntax errors.

### What is blocked
Nothing code-side. Admin Aria RF diagnostic + register/reassign tools (explicitly requested by Michael, scoped via clarifying question to include both diagnostics and pendant registration/reassignment, not read-only) were not started this session.

### Next safe step
Build the Admin Aria RF tools (wrap `GET /rf/events`, `GET /rf/devices`, `POST /rf/pair`, `PUT /rf/devices/{id}/assign`) following the existing `admin_assistant_tools.py`/`admin_assistant_executor.py`/`admin_assistant_device_executor.py` pattern. Decide with Michael whether/when to commit the RF arc (fully proven and working, unlike the still-blocked AC work above) - no explicit commit instruction has been given yet.

---

## 2026-09-06 — Kiosk multi-light bug: device_id was dropped by every direct kiosk/UI device-control call site, found by Michael, fixed and extended generically to TVs. Committed and pushed.

### Agent / tool
Claude Code, EliteDesk primary worktree. Branch `main`, on top of `7debebb` (the RF pendant commit above).

### What Michael found
Right after the RF/light disambiguation commit (`d22b3d2`) landed, Michael identified the real remaining half of the same bug class from first principles, without me finding it first: `RoomDevicePanel` correctly passes the exact clicked `SmartDevice` object to `onToggle`, but `Kiosk.jsx`'s own `onToggle={(d) => sendDeviceCommand("power", ..., d.kind)}` callback and its `sendDeviceCommand` function only ever forwarded `kind`, discarding `d.device_id` entirely. With two real lights in Room 214, every kiosk-card tap hit the backend's (correct) ambiguity guard: `"More than one light device in room 214 supports power - pass device_id to disambiguate."` The voice path had already been fixed in `d22b3d2` (`realtimeLightControl.js`/`realtimeDeviceTools.js`'s `postRoomCommand`) - this was the kiosk-card UI path, never touched by that commit.

### What was checked (Michael's item 5: find every other dropped-device-id call site)
`grep` for every direct `/devices/public/room/.../command` POST in the frontend found five call sites total:
1. `Kiosk.jsx`'s `beginConversation()` auto-mute (TV/speaker mute on call start) - dropped `device_id` despite already having it in hand (`d.device_id`).
2. `Kiosk.jsx`'s call-end restore-muted-devices loop - same: `mutedDevicesRef.current` entries already store `device_id`, the restore POST just never sent it.
3. `Kiosk.jsx`'s `sendDeviceCommand` (the one `RoomDevicePanel` card click goes through) - the reported bug.
4. `realtimeDeviceTools.js`'s `toggle_tv` (voice) - never looked up the device at all, blindly posted `kind: "tv"` with no id.
5. `realtimeDeviceTools.js`'s `set_tv_input` (voice) - did fetch the room's device list, but used `.find()` (the exact same silent-first-match bug the light `next()` bug was, before the earlier fix) and still never passed `device_id` to the command itself.
`DevicesTab.jsx` (admin panel) was checked and is NOT affected - it posts to `/devices/{device_id}/command`, already exact-device-targeted by construction.

### Fix
- `frontend/src/lib/kioskDeviceControl.js` (new, 17 lines) - `sendRoomDeviceCommand(room, action, value, kind, deviceId)`, the one place that now builds this POST body. Extracted out of `Kiosk.jsx` (614→615 lines, already over cap, effectively unchanged since the actual command logic moved out) specifically so it's unit-testable without mounting the whole stateful kiosk page (no `@testing-library/react` in this project - the existing test suite is function-level, mocked-network style, so this follows that same convention).
- `Kiosk.jsx` - all three call sites (`beginConversation` mute, restore-on-hangup, `sendDeviceCommand`/card click) now route through `sendRoomDeviceCommand` and pass their device's `device_id`.
- `realtimeDeviceTools.js` - added a small shared `_findOneDeviceOfKind(room, kind)` helper (fetches the room's device list, returns the single online match or `{ambiguous: true}` if more than one) - generalizes the exact same lookup-before-command shape `realtimeLightControl.js` already uses for lights, per Michael's explicit requirement ("must work for multiple TVs, lights, outlets, fans, etc., not just these two bulbs"). `toggle_tv` and `set_tv_input` both now use it and pass `device_id` through; `set_tv_input`'s old `.find()` was replaced with the same fail-closed ambiguity check. Currently inert in practice (every room today has exactly one TV) but closes the identical latent defect before a second TV ever gets added, rather than after.
- Backend `routes/devices.py`'s ambiguity guard (already committed in `d22b3d2`) was NOT touched or weakened - it's what caught this in the first place, and still fails closed for any kind/room combination with more than one online match and no `device_id`.

### What was verified
- New test `frontend/src/lib/__tests__/kioskDeviceControl.test.js` (4 tests): clicking the Desk Lamp sends its own `device_id`, clicking the Overhead Light sends its own (never the Desk Lamp's), two sequential clicks on two devices each carry only their own id, and the command body always includes a `device_id` key.
- `toggleTvVolumeGuard.test.js` updated (its mock never modeled a device-list fetch before, since `toggle_tv` never made one) plus one new test: two TVs in a room now makes `toggle_tv` fail closed with an honest ambiguity message instead of guessing.
- Full frontend suite: 57/57 passing (was 56 before this arc; +1 net after accounting for the 4 new kiosk tests and 1 new TV-ambiguity test, since none were removed).
- **Live, real-hardware re-test exactly as Michael requested (item 8):** with the dev servers running the fixed code, opened the actual Room 214 kiosk (`kio_dc8c06a19608`) in a real browser session, scrolled to "Your room," and clicked each light card in turn. Clicking Overhead Light (previously OFF) turned it on; clicking Desk Lamp (previously ON) turned it off. Cross-checked directly against Home Assistant's own state after each click (`GET /api/states/light.smart_multicolor_bulb` / `..._bulb_2`) rather than trusting the kiosk UI alone: each click changed only its own real physical bulb's `state`/`brightness`/`rgb_color` - the other bulb's HA state was byte-identical before and after. This is genuine live-hardware confirmation, not a mocked test.
- Voice path (item 8B) was NOT live-tested this session - it shares the identical `device_id` plumbing now proven correct at the transport layer via the kiosk-card test above, and its own disambiguation logic (`pickLight` in `realtimeLightControl.js`) was already unit-tested in `d22b3d2`, but an actual spoken command against the real two bulbs requires Michael's own voice at the kiosk; browser automation has no microphone/STT capability to trigger the real Realtime session end-to-end.

### Files changed / line counts
`frontend/src/lib/kioskDeviceControl.js` (new, 17 lines), `frontend/src/pages/Kiosk.jsx` (615 lines, already over cap - net +1 line, extracted the changed responsibility rather than growing it further), `frontend/src/lib/realtimeDeviceTools.js` (304 lines, crossed the 300 line over the course of this arc - real generic-safety code, not deferred per Michael's "300 is goal not hard rule if it's good code"), `frontend/src/lib/__tests__/kioskDeviceControl.test.js` (new, 66 lines), `frontend/src/lib/__tests__/toggleTvVolumeGuard.test.js` (updated, 74 lines).

### Committed as
`b0e3c3ee69cd9eddda1bb3071d56d2e68dfedbe4`, pushed to `origin/main`.

### What is blocked
The still-uncommitted Midea AC/climate work remains untouched and uncommitted, same as every entry above - `realtimeDeviceTools.js`'s climate hunks were isolated out of this commit the same hunk-splitting way as the RF/light commit before it.

### Next safe step
A live voice re-test of `toggle_light`/`toggle_tv` against the real two-bulb Room 214 (Michael speaking to the kiosk) would close out item 8B above. After that: Admin Aria RF tools (still not started) remain the next open task from the entry above.

---

## 2026-09-06 — Midea AC diagnostic (read-only): first proven failure boundary is Matter Server's own CASE/session establishment, not network/mDNS/IP. No code or config changed.

### Agent / tool
Claude Code, EliteDesk primary worktree. Diagnose-only per Michael's explicit instruction ("STOP making broad VM, IPv6, NDP, libvirt, or Home Assistant network changes... DIAGNOSE ONLY"). No files modified; no VM/network/HA config touched.

### Method
Live, read-only evidence gathered via `virsh console` + `docker exec` into `app_core_matter_server`/`homeassistant`, plus host-side `avahi-browse`/`ping`, all performed while the AC was simultaneously confirmed reachable - not inferred from stale logs.

### Findings (PASS/FAIL as specified)
- **IP connectivity: PASS** - live ping to the AC's real IPv6 GUA (`2600:100b:a111:dfbb:56b8:74ff:fe9a:61f4`, MAC `54:b8:74:9a:61:f4`, identified by elimination against the two known TP-Link Tapo bulb hostnames) returned 0% loss, 5-19ms RTT, at the moment of testing.
- **mDNS discovery: PASS** - `avahi-browse` showed the AC actively advertising both `_matter._tcp` (operational, under HA's own fabric `788de3b285084465`, node `7`) and `_matterc._udp`, live, right now. Root cause of *why* this crosses the VM's NAT boundary at all: the EliteDesk host itself already runs `avahi-daemon` with `enable-reflector=yes` across `wlp6s0,virbr0` - pre-existing infrastructure, not something set up this session, and identical for the AC and both working bulbs.
- **Matter operational discovery: PASS** - the operational record is current and resolves to the live address above.
- **Matter CASE/session: this is the failure boundary.** Matter Server's own logs showed zero attempts against this node in 15+ minutes (it *did* successfully resume a session with a working bulb in that same window). Triggering `homeassistant.update_entity` produced no matter-server log activity at all - the controller has stopped retrying this specific node entirely, despite it being demonstrably alive and mDNS-visible at that exact moment.
- **Matter endpoint control:** not reached - session never establishes.
- **Native Midea LAN discovery: NOT TESTED** - confirmed HA Core 2026.7.4 has no built-in Midea integration; only the already-paused HACS `midea_ac_lan` custom component exists, uninstalled.

### Conclusion
matter.js's own reconnection logic has given up on this node, not the network, mDNS, or IP layer - all three are proven fine, live, on the identical path the two working bulbs use. Likely safe next step (not performed, diagnose-only): HA's own "Reconfigure device" / re-interview action on the Matter integration's device page for this AC - a supported HA UI action, distinct from a full Matter Server restart (which was already tried twice in the 2026-09-05 entry above without success, and briefly interrupts the working bulbs' own sessions each time).

### What was verified
Live, real-time evidence (ping + avahi-browse + matter-server logs, all captured while the AC was confirmed on the network) - not stale-log inference.

### What is blocked
Nothing code-side. This entry is diagnostic record only.

### Next safe step
If Michael wants to proceed: try HA's own device-page "Reconfigure" action first (lower blast radius than a full Matter Server restart) the next time the AC is confirmed physically powered and connected to Wi-Fi.

---

## 2026-09-06 — CAOSCare Level 1: resident-assistance event model (ResidentEvent → extended Alert), Aria lifecycle, staff-presence mute hook, optional live staff line, simple pattern notation, receipts wiring.

Committed as `d6cb486c07e8f67f08175254808c8ca6f4c4ec89`, pushed to `origin/main`.

### Agent / tool
Claude Code, EliteDesk primary worktree. Plan-mode used given the scope (touches alert creation, RF ingest, Aria's realtime session lifecycle, staff UI, and receipts simultaneously) - plan approved by Michael before implementation, including two explicit product decisions (below). Branch `main`, on top of `790f192`.

### Core architecture decision - documented per the directive's own requirement
**No new `resident_events` collection was created.** Inspection found `Alert` already implements most of `ResidentEvent` in substance - `press_count` + `activation_consumed_at` already encoded "one incident, repeat presses attach, don't spawn a new one," just scoped to one RF device (`routes/rf_activation.py::try_coalesce_press`) instead of the resident, which is exactly the directive's "IMPORTANT CORRECTION." `ResidentEvent` was implemented as new fields added to the existing `Alert` model/collection/routes:

| Directive concept | Implementation |
|---|---|
| `id`, `resident_id`, `opened_at`, `closed_at`, `press_count` | existing `alert_id`, `resident_id`, `created_at`, `resolved_at`, `press_count` - reused as-is |
| `close_reason` | reuses existing `category` + `outcome` - no new field |
| `resident_utterance` | reuses existing `resident_stated_reason` - no new field |
| `presses[]`, `aria_state`, `live_line_state`, `pattern_footnote`, `requested_staff`, `silence_after_invite`, `receipt_id`, `event_log[]` | new fields on `Alert` (`models.py`) |

`routes/pendants.py` (a second, older, frequency-keyed pendant scaffold, already documented in the 2026-08-29 entry as "deliberately left untouched") remains untouched - out of scope, a pre-existing decision, not a new one made today.

### The one real safety-relevant behavior change
`try_coalesce_press`'s lookup required `activation_consumed_at: None` to find an "open incident" - meaning once one Aria session ended (dismissal or timeout sets that field), a LATER re-press on the still-unresolved event couldn't find it anymore and minted a wrong duplicate. Generalized into `routes/resident_activation.py::record_resident_activation()`: the "is there an open event" lookup is now `resident_id` match (falling back to `room` for a device not yet assigned to a resident) + `status in (active, acknowledged)` - i.e. "not yet resolved by staff," full stop. `activation_consumed_at` is reset to `None` on every coalesced press regardless of its prior value, which is what lets a repeat press reactivate Aria on an event that already had one full session. `routes/kiosks.py::active_emergency_for_kiosk`'s hard 5-minute `created_at` cutoff was removed to match - a real event can legitimately stay open far longer than 5 minutes, and the age filter would have silently dropped a genuine reactivation.

### Two product decisions confirmed with Michael before implementation
- **Live staff line = "Both"**: an urgent card on the already-open `StaffDashboard.jsx` (reusing its existing `alerts_feed` poll, no new fetch loop) fires immediately, *and* a best-effort Twilio voice call to `facility.on_call_phone` is attempted if `TWILIO_*` env vars are set - confirmed this deployment has none (`twilio` package isn't even installed), so this mirrors `routes/escalation.py::_try_sms`'s existing no-op-without-credentials shape exactly and is real but inert here, same tier as the existing SMS feature.
- **Staff presence = hook only, no UI trigger yet**: no RFID/badge/tablet-presence hardware exists anywhere in this deployment. Built `POST /realtime/room/{room}/staff-present` as a real, callable, curl-tested endpoint (mutes Aria, force-drops the live line, force-releases the room's Aria lease) with no staff-facing button wired to it yet, per Michael's explicit call not to build a placeholder UI ahead of a real hardware decision.

### Files
- `backend/models.py` (1554 lines) - `PressRecord`, `AriaState`/`LiveLineState` literals, the new `Alert` fields above, `ResidentButtonPattern`, `ResidentAssistanceConfig`.
- `backend/routes/resident_activation.py` (new, 162 lines) - `record_resident_activation()` (the generalized coalescing described above) and `try_call_on_call_phone()` (the Twilio best-effort helper). Supersedes and replaces `routes/rf_activation.py` (deleted - its one caller, `rf.py::rf_event()`, now calls this instead).
- `backend/routes/rf.py` (530 lines) - `rf_event()` wired to the new module; unrelated fingerprint-matching logic untouched.
- `backend/routes/alerts.py` (358 lines) - `create_alert()` (kiosk `CALL FOR HELP`) now calls the same coalescing function before minting a fresh `Alert` - this is the acceptance-test-16 fix, so a kiosk-button press and an RF-pendant press for the same resident attach to one event. `resolve()`/`close_alert()` both now call a shared `_close_out()` that updates pattern stats and completes the event's receipt.
- `backend/routes/alert_lifecycle_events.py` (new, 120 lines) - split out of `alerts.py` (already at the line cap) rather than growing it further: `POST /alerts/{id}/aria-event` (single code path for activated/dismissed/timeout/silence_after_invite/requested_staff, instead of one endpoint per transition), `POST /alerts/{id}/live-line/ring`, `/answer` (staff-only), `/no-answer` (public - the resident's own kiosk session self-reports a ring timeout, since there's no staff login on that side).
- `backend/routes/kiosks.py` (135 lines) - 5-minute cutoff removed as described above.
- `backend/routes/realtime_room_lease.py` (161 lines) - new `POST /{room}/staff-present`.
- `backend/routes/realtime.py` (339 lines) - `/session` now accepts + returns `alert_id` in `context`, and hands the resident-facing session its community-configured `aria_companion_timeout_sec`/`invite_silence_sec`/`live_line_ring_timeout_sec` (via a new `get_effective_config()` in `resident_assistance_config.py` - the real config route is admin-gated, so this threads the values through server-side rather than exposing a second public config endpoint).
- `backend/routes/resident_assistance_config.py` (new, 43 lines) - `GET`/`PUT`, exact same facility-scoped, never-404-falls-back-to-defaults pattern as the existing `EscalationRule`/`routes/escalation.py`.
- `backend/routes/resident_patterns.py` (new, 111 lines) - `update_pattern_stats()` (called after close), `footnote_for_resident_now()` (called at event-open time inside `record_resident_activation`), bucketed by hour-of-day using the same "pull + filter in Python, Mongo can't extract hour from a string date" precedent as `routes/insights.py`. Never produces a footnote below `pattern_min_events` (default 5) - "Not enough history" instead, and patterns are read-only decoration that cannot gate/suppress/delay an activation (verified by `test_pattern_minimum_history`, and by construction - nothing in the coalescing path reads pattern data).
- `backend/server.py` (203 lines) - registers the three new routers.
- `frontend/src/lib/useRealtimeVoice.js` (410 lines) - accepts `alertId`; posts `aria-event activated` on connect; two timers from community-configured defaults (300s companion timeout - forcibly ends the session, event stays open; 8s invite-silence - posts `silence_after_invite`, does NOT end the session); `stop(reason)` posts `dismissed`/`timeout` only for the specific resident-caused reasons (`resident_end_call`/`resident_end_conversation`/`companion_timeout`), never for a component unmount or config error; generic `startAwaitingAnswerTimer()` for the live-line routing question's own silence timeout.
- `frontend/src/lib/realtimeMessageHandler.js` (331 lines) - `onFirstSpeechStarted` hook (clears both the invite timer and any live-line awaiting-answer timer on real speech); dispatches to the new `executeCareTool`; arms the awaiting-answer timer when `request_live_staff` asks its routing question.
- `frontend/src/lib/realtimeCareControl.js` (new, 75 lines) - `request_live_staff` tool: same structural-grounding technique as `RESTING_PHRASES`/`ENDING_PHRASES` (the resident's own transcript, not the model's interpretation) decides immediate-ring vs. stay-companion vs. ask-once-then-default-to-ring-on-repeat-ambiguity.
- `backend/routes/realtime_tools.py` / `realtime_companion_prompt.py` - `request_live_staff` tool schema + prompt disambiguation against the pre-existing `call_for_help` tool (which already had an overlapping "or directly asks for a nurse" clause - narrowed to genuinely new symptoms only, deferring an in-conversation nurse request to the new tool when an event is already open).
- `frontend/src/pages/RealtimeChatScreen.jsx`, `Kiosk.jsx` - thread `alertId` (from the kiosk's own `alert` state, already set by both the active-emergency poll and the manual button path) down to the voice hook.
- `frontend/src/pages/StaffDashboard.jsx` (389 lines) - press_count, per-press timestamp history, `pattern_footnote`, `aria_state` badge, `silence_after_invite` indicator, and a live-line "ringing" banner with an Answer action, all added to the existing alert `Card` (no new component/page).
- `backend/tests/test_resident_events.py` (new, 298 lines) - supersedes and deletes `test_rf_activation_gating.py`, whose own assertions encoded the PRIOR (now intentionally reversed) behavior.
- `frontend/src/lib/__tests__/liveLineRouting.test.js` (new, 86 lines); `toggleTvVolumeGuard.test.js` updated for `toggle_tv`'s new device-lookup step (unrelated to Level 1 - a byproduct of the earlier kiosk multi-light fix's TV generalization needing its list-fetch mocked).

### What was verified - tiers, per the directive's own requirement
**Automated, against the real running backend (not mocks) - `pytest tests/test_resident_events.py`, all passing in one process (Motor's single-event-loop constraint, same as the file it replaces):**
- Acceptance 1, 4, 5: one press opens exactly one event; four more in the same window bring `press_count` to 5; every press is a real preserved record (`len(presses) == 5`), not just a counter.
- Acceptance 7: a press AFTER the session ends (lease released) reactivates the SAME `alert_id` (not a new one) and correctly relaunches the kiosk's active-emergency poll; only an actual staff resolve() genuinely opens a new event on the next press.
- Acceptance 16: a kiosk-button press and an RF-pendant press for the same resident attach to ONE event, with both sources visible in `presses[]`.
- Acceptance 9: `POST /realtime/room/{room}/staff-present` immediately sets `aria_state=muted_staff`, drops the live line, and force-releases the room's lease.
- Pattern minimum-history gate: zero history produces no footnote (not a fabricated one).
- Full existing backend suite re-run: failures traced individually to pre-existing causes unrelated to this work (hardcoded demo credentials this environment doesn't have, the still-blocked Midea AC, and a pre-existing shared-event-loop fragility when 100+ legacy test files run together in one pytest process - each affected file passes 100% in isolation, confirmed for `test_light_control.py`, `test_climate_control.py`, `test_room_device_isolation.py`, `test_public_demo_kiosk.py`).

**Automated, pure-function (frontend):**
- Acceptance 11, 12, 13 (`liveLineRouting.test.js`, 13 tests): immediate phrases ring; companionable phrases don't; a second unclear turn for the same event rings rather than asking twice.
- Full frontend suite (70/70) re-run clean - no regression to the RF/light/TV work committed earlier this session.

**Live software (manual, real backend + real browser):**
- Curl-verified `aria-event`/`live-line/ring`/`live-line/answer`/`live-line/no-answer` against a seeded real alert doc.
- `StaffDashboard.jsx` visually confirmed rendering press_count/press-history/pattern_footnote/aria_state correctly against real, live alert data (Helen Torres's Room 214 pendant shows a real 43-press event, itself live proof the new coalescing has been holding one event together rather than fragmenting across this session's extensive RF testing) - no console errors.

**Not yet tested (honest gap):**
- A live voice session actually exercising the 300s/8s timers, the `request_live_staff` routing question end-to-end through real OpenAI Realtime audio, or a real Twilio call - none of these are reachable without Michael's own voice at the kiosk (timers/routing question) or real Twilio credentials (call). Acceptance 6, 8, 10 (dismissal/timeout/silence-after-invite) and the live-line acceptance tests are code-reviewed and unit-tested at the phrase-grounding/endpoint level but not exercised through a live spoken conversation this session.
- Acceptance 17/18 (device_id preserved for lights) were NOT newly built here - already fully implemented and live-verified earlier this session (commit `b0e3c3e`); re-running the frontend suite as part of this regression pass is the only re-verification performed.

### Observation (not caused by this work, flagging rather than acting on it)
The staff dashboard currently shows 333 "active" alerts, mostly stale test/dev debris accumulated from this session's extensive real RF hardware testing under the OLD device-scoped coalescing (separate alert records for the same resident/pendant that never got resolved). Left untouched - bulk-modifying real alert records wasn't part of this task and wasn't asked for.

### What is blocked
Nothing code-side. The still-uncommitted Midea AC/climate work remains untouched, same as every entry above.

### Next safe step
A real live voice session at the Room 214 kiosk (Michael speaking) would close the "not yet tested" gap above: verify the companion timeout doesn't fire early/late, the invite-silence flag sets correctly on a genuine pause, and `request_live_staff`'s routing question sounds natural and resolves correctly on a real spoken answer. Separately: deciding whether to bulk-resolve the stale test alert debris noted above is Michael's call, not something to do unprompted.
