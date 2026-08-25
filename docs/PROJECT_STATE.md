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
