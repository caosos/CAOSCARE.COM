# Terminal 9 — Laptop Relay, Transportation Acceptance, and Department Walkthrough

## Why this file exists

Michael's laptop is the terminal/window for the one Claude Code worker operating on the EliteDesk repository through SSH.

Michael's copy/paste is unreliable and he types slowly. This directive is stored in GitHub so Michael only needs to type:

> Fetch and execute Terminal 9.

Do not require Michael to retype long commands, prompts, paths, reports, secrets, or test data that can be discovered safely from the repository or host.

## Required remote-read procedure

The EliteDesk working tree contains valuable uncommitted work. Do not pull, merge, reset, switch branches, clean, discard, or overwrite anything merely to read this directive.

When Michael says **"Fetch and execute Terminal 9"**:

1. Confirm the current directory is the local `CAOSCARE.COM` repository.
2. Inspect `git status --short`, current branch, local HEAD, and configured remotes.
3. Run a fetch only:
   `git fetch origin main`
4. Read this directive directly from the remote ref without changing the working tree:
   `git show origin/main:commands/TERMINAL_9_LAPTOP_RELAY_ACCEPTANCE_ONBOARDING.md`
5. Follow it in inspect-first mode.
6. Stop whenever Michael must perform a browser, microphone, hardware, password, approval, staging, commit, push, merge, deletion, or destructive action.

If `git fetch` cannot authenticate or would require changing credentials, stop and give Michael one short exact instruction.

## Naming — use these exact meanings

- **EliteDesk** = HP EliteDesk development node, hostname `caoscare1-hp-elitedesk`. This is the local machine currently running CAOSCARE work.
- **CAOS** = the separate older platform. It is not this product.
- **CAOSCARE** = the product being built now.
- **caoscare** = the laptop SSH shortcut, deliberately not named `caos`.
- Laptop-to-EliteDesk command: `ssh caoscare`.
- EliteDesk SSH destination: `caoscare-1@192.168.1.151`.
- Ignore `192.168.122.1` for laptop SSH; it is a virtual bridge address.

## Authority and workflow

Three layers are used, and no one layer is the sole source of truth:

1. The classifier gates sensitive actions.
2. Claude Code reads the actual code and must challenge incorrect instructions with evidence.
3. Michael holds final authority and performs authoritative browser, voice, and hardware tests.

Use inspect-before-write discipline.

- Do not combine broad inspection and broad mutation into one opaque operation.
- Do not claim that compile success proves the user experience.
- Preserve receipts and observable verification for meaningful actions.
- Do not autonomously continue into a new phase after completing the requested phase.
- Do not stage, commit, push, merge, delete, reset, discard, or deploy without Michael's explicit approval for that action.

## Engineering size rule

Handwritten production-code files must not exceed **300 lines** unless Michael explicitly approves an exception.

Exempt:

- documentation
- informational files
- reports
- generated artifacts
- static data
- lockfiles
- necessary configuration files

For production code:

- Aim below 300 lines.
- Split by coherent domain or responsibility, never arbitrary line chopping.
- Do not create God files.
- Do not begin a broad refactor solely to shorten untouched legacy files.
- If modifying an existing code file already above 300 lines, do not make it larger; extract the responsibility being changed when practical.
- Before finishing a coding task, report the line count of every created or materially modified production-code file.
- Record this rule in `AGENTS.md` and the appropriate engineering/project-state documentation when it can be done without conflicting with current uncommitted edits. Preserve prior history.

## Verified session state — August 21, 2026

### Google owner login

Google owner login is browser-tested and working for `mytaxicloud@gmail.com`.

The implemented flow is Google Identity Services (GSI), not redirect OAuth:

1. `frontend/src/components/GoogleSignIn.jsx` renders the GSI button.
2. The browser receives a Google ID token.
3. The frontend posts it to `POST /api/auth/google/verify`.
4. The backend verifies the token and issues the same application session mechanism used by password login.

Do not add `/auth/google/callback` or another redirect flow.

Verified configuration names:

- Backend reads `GOOGLE_CLIENT_ID`.
- Backend owner allowlist is `GOOGLE_ADMIN_EMAILS=mytaxicloud@gmail.com`.
- Frontend reads `REACT_APP_GOOGLE_CLIENT_ID`.
- `OWNER_EMAILS` is not the correct variable.
- Do not hardcode the client ID into `GoogleSignIn.jsx`.
- Google Client Secret is backend-only and currently unused by the GSI ID-token verification path.
- Real `.env` files are git-ignored. Never print or commit their contents.

Verified backend behavior:

- Google ID-token audience is checked.
- Issuer is checked.
- `email_verified` must be true.
- Verification failure returns 401.
- A non-allowlisted email is rejected before it can create an owner.
- Existing owners are not silently demoted.
- Google login uses the existing JWT and cookie-session mechanism.

Potential dead code:

- `frontend/src/pages/AuthCallback.jsx` appears to be legacy Emergent OAuth code.
- Confirm all references before proposing removal or quarantine.
- Do not remove it merely because this directive labels it potentially dead.

### Runtime

Verified after restart:

- MongoDB is healthy.
- Backend is on port `8000`.
- `/api/health` returned `{"ok":true,"db":"up"}`.
- Frontend is CRA on port `3000`.
- Frontend compiled without new errors; pre-existing warnings may remain.
- There is no intended frontend port `3001` in this repository.
- A stale frontend process previously occupied port 3000 and retained old build-time environment values. This was identified by PID, stopped, and the correct frontend restarted.
- Home Assistant OS VM is running.
- Mosquitto inside the VM is running.
- Owner authentication is working.

This is local EliteDesk development state. Do not describe it as production deployment readiness.

### SSH

Verified:

- EliteDesk has `openssh-server`.
- `ssh.service` is active and listening on port 22.
- Laptop `~/.ssh/config` contains the `Host caoscare` shortcut.
- Laptop command `ssh caoscare` successfully lands at `caoscare-1@caoscare1-hp-elitedesk`.

Connection configuration belongs on the laptop. The EliteDesk only needs the SSH server side.

### Existing uncommitted product work

Claude previously reported the following current local state:

- `frontend/src/pages/DepartmentsTab.jsx` was created.
- It follows the existing `ScheduleTab.jsx` pattern.
- It provides list, active toggle, delete, and Add Department dialog behavior against the existing departments backend.
- Backend `routes/departments.py` was already wired with admin-only list/create/patch/delete.
- Frontend recompiled cleanly.
- MongoDB contained eight departments; six came from defaults and Therapy/Resident Programs appeared to have been added earlier.
- Prior transportation, menu, schedule, and other work remains uncommitted in the working tree.

Treat these as reported local state until re-inspected. Preserve all uncommitted work.

## Immediate mission

Do not redesign the application now.

First make the existing system work and prove the real resident-facing transportation path.

### Phase 1 — establish the exact local truth

Inspect and report:

- current branch and local HEAD
- `origin/main` HEAD
- working-tree changes
- staged changes
- untracked files
- local-only and remote-only commits
- exact files implementing Departments, Schedule, Menu, Transportation, Realtime voice, tools, tasks, and receipts
- created or materially modified production-code files over 300 lines
- current services and ports
- current database seed state without printing secrets or private resident data

Do not modify anything during this inspection phase.

### Phase 2 — record the August 21 checkpoint

Append a dated entry to `docs/PROJECT_STATE.md` and reconcile `docs/CURRENT_NODE_STATUS.md` with the verified August 21 state in this directive.

Also record the 300-line production-code rule in `AGENTS.md` and the appropriate engineering documentation.

Do not replace or erase prior project history.

If these files already have overlapping uncommitted edits, inspect carefully and append/merge only the intended material. Stop if authorship or intent is unclear.

Show Michael the exact documentation files changed. Do not stage or commit them yet.

### Phase 3 — prepare transportation acceptance

1. Confirm Admin → Transportation exists in the real frontend.
2. Determine whether the two-week transportation schedule is already seeded.
3. Do not create duplicate schedules.
4. If seeding is needed, identify the existing approved seed method and explain exactly what records it will create before executing it.
5. Stop for Michael's approval before creating seeded records.
6. Confirm the resident voice screen and exact test entry point.
7. Confirm logs/console/network/database observations are ready before the microphone test.

### Phase 4 — Michael's browser inspection

Guide Michael one action at a time. Keep each instruction short.

Michael signs in as owner with Google and inspects:

1. Admin → Departments
2. Admin → Schedule
3. Admin → Transportation
4. Admin → Menu, if implemented and reachable

For each verified page:

- capture a real screenshot
- record the visible controls
- record what the page actually does
- identify confusing or irrelevant controls
- do not redesign it during this phase

### Phase 5 — live resident voice acceptance

Michael performs the real microphone test:

> I need a ride to the pharmacy tomorrow.

Observe and verify separately:

- browser microphone/session connected
- speech transcript was correct
- Aria understood future time correctly
- correct tool was selected
- frontend dispatched the tool call
- backend received it
- database record was created or updated
- transportation slot was actually confirmed or remained only requested
- receipt was created when required
- status query returns the real state
- Aria's spoken language matches the actual state

Truth rule:

- available slot does not equal confirmed booking
- request created does not equal acknowledged
- acknowledged does not equal assigned
- assigned does not equal completed

Do not claim the voice lane works until Michael completes the microphone test and backend state confirms the result.

### Phase 6 — picture-by-picture departmental walkthrough

After a workflow is verified in the real browser, create a simple screenshot-based walkthrough using the actual interface.

Requirements:

- numbered screenshots in the correct order
- exact screen the user sees
- clear indication of what to click
- clear indication of what to enter
- short plain-language explanation of what happens next
- minimal words
- no technical jargon
- separate instructions by department and role
- show each department only its relevant actions
- owner/admin instructions remain separate
- do not use mock screenshots when a real screen can be captured
- do not document unverified behavior as working
- mark incomplete or unverified screens plainly

Initial role lanes:

- Maintenance: view requests, acknowledge, update status, complete, add result.
- Nursing: view authorized nursing requests, acknowledge, respond, resolve.
- Transportation: view schedule, request/accept a trip, change, cancel, complete.
- Kitchen: manage/approve menu information and respond to meal questions.
- Front desk: view callback/contact requests, acknowledge, respond, close.
- Owner/admin: manage departments, schedules, transportation, users, and system status.

Do not invent permissions, buttons, pages, APIs, or workflows that do not exist. Map actual implementation first.

For the initial transportation walkthrough, capture:

1. owner login
2. Admin navigation
3. Departments
4. Schedule
5. Transportation before seeding
6. approved seeding process, if performed
7. resulting schedule
8. resident voice screen before test
9. voice-test result
10. resulting transportation record
11. resulting status/assignment
12. resulting receipt

Store screenshots and walkthrough documentation under a clearly named documentation directory. They are exempt from the 300-line production-code limit.

Do not build a slideshow engine yet. The initial deliverable is a verified screenshot-based walkthrough of the existing system. After functional proof, report exactly where the interface should later be simplified.

## Stop conditions

Stop and ask Michael before:

- browser interaction
- microphone or hardware interaction
- entering a password or secret
- seeding or materially altering database records
- deleting or quarantining legacy code
- changing authentication configuration
- restarting services when a working session could be interrupted
- staging, committing, pushing, merging, rebasing, or pulling
- deploying
- destructive or difficult-to-recover actions
- a decision that materially changes architecture or user workflow

## Completion report

When stopping, give Michael:

1. the exact phase completed
2. what was observed
3. what changed
4. what remains unverified
5. the one short action Michael must perform next
6. the line counts of created/materially modified production-code files
7. the exact files still uncommitted
8. no claim beyond observable evidence
