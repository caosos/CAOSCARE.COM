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
