# Release readiness — integration/2026-09-27 → production (RQ-026)

Read-only analysis, 2026-10-08. Written from the repository only; **nothing
was run on or read from production**. Anything that needs production access
is marked **UNVERIFIED**. This document does not approve or start a release;
that is Michael's decision.

Refs examined: integration tip `2a2d569`, `origin/main` `880d10f`, production
`d7ff96a` (as last recorded in `docs/MICHAEL_ACTION_RUNBOOK.md` — UNVERIFIED
today).

## 1. Merge-to-main mechanics

- `origin/main` (`880d10f`) is an **ancestor** of the integration tip
  (`rev-list integration..main` = 0; `main..integration` = 223 commits).
  Merging integration into main is a **fast-forward**; no conflict is possible.
- Confirmed in a scratch worktree (removed afterwards): `git merge
  --no-commit --no-ff integration` onto main → "Automatic merge went well",
  no conflicts, aborted.
- `d7ff96a` is an ancestor of both `main` and integration. Main has 24 commits
  beyond production (docs, Wake Phrase Lab, `/experience`, favicon); all are
  already inside integration, so deploying integration also ships those.
- `scripts/deploy_caoscare.sh` refuses any SHA not reachable from
  `origin/main` (step 1 of the script). So the integration tip must be pushed
  to `main` first. Changing `main` is a release decision for Michael
  (`docs/MICHAEL_ACTION_RUNBOOK.md`, release approval format). The deploy
  script itself is unchanged since `d7ff96a`.
- Size: `d7ff96a..tip` = 384 files, +31 045 / −2 085. Backend runtime code
  69 files (+4 992/−787), frontend `src` 118 files, 39 backend test files,
  plus docs, media, `telephony/`, `tools/wakelab`, `.github/workflows`.
- **Release-control requirement** (`docs/reports/2026-09-25-release-control-requirement.md`):
  the approval must show the exact commit range and its content, since the
  2026-09-25 deploy shipped unreviewed commits. This range is large; the
  approval request should list it by feature (this document's sections) and
  the gate results, not just a SHA.

## 2. Environment variables

Backend code reads these names that `d7ff96a` did not (diff of
`os.environ`/`getenv`/quoted env-name strings in backend code, excluding
tests). Production `backend/.env` contents are **UNVERIFIED**; none of these
are required for the existing resident/staff app to start.

| Variable | Default / behaviour when missing |
|---|---|
| `CAOSCARE_ESCALATION_AUTO` | default **on** (unset = enabled). `0/false/no/off` disables. See §4. |
| `CAOSCARE_ESCALATION_INTERVAL` | 30 s (minimum 5) |
| `CAOSCARE_DEMO_CONTINUITY_AUTO` | default **off**; startup/sign-in catch-up does nothing |
| `SIM_TICK_SECONDS` | simulator tick; simulator runs only when an admin starts one |
| `CAOSCARE_TEST_GATE_RUN_ID` | test gate only; also needs `CAOSCARE_TEST_HOOKS` |
| `ASTERISK_ARI_URL/USER/PASSWORD` | listener not started unless URL set |
| `OPENAI_WEBHOOK_SECRET` | OpenAI SIP webhook rejects (fail-closed) |
| `CAOS_TELEPHONY_TOKEN`, `CAOS_TELEPHONY_ALLOWED_HOSTS` | dial-target endpoint fail-closed; hosts default `127.0.0.1,::1` |
| `CAOS_PHONE_VOICE`, `CAOS_REFER_HOST`, `CAOS_SIP_TRUNK_ENDPOINT`, `OPENAI_REALTIME_WS` | telephony only |

Existing names that gain new behaviour: `RESEND_API_KEY`, `RESEND_FROM_EMAIL`,
`RESEND_WEBHOOK_SECRET` (delivery records / webhook; the inbound route was
already present), `TWILIO_*` (SMS fallback; note `TWILIO_FROM_PHONE` vs
`TWILIO_FROM_NUMBER` name drift is recorded in `docs/PILOT1_COMMUNICATIONS.md`).
No new **required** variable was found. Frontend: no change to
`package.json`/`yarn.lock`; the build still uses `REACT_APP_BACKEND_URL`.
Do **not** set `CAOSCARE_ENABLE_DEMO_SEED` or `CAOSCARE_DEMO_CONTINUITY_AUTO`
on production without a decision (continuity is the demo room's catch-up).

## 3. Dependencies

- Backend: one new line, `websockets>=14.0` (`backend/requirements.txt`). The
  deploy script will see the change and run `pip install -r`. UNVERIFIED that
  production's PyPI access/venv succeeds; the install runs *before* restart,
  and a failure aborts with the previous commit restored.
- Frontend: lockfile unchanged → `yarn install` skipped; `yarn build` runs.
  `.github/workflows/frontend-check.yml` is CI-only.

## 4. Startup side effects and data effects (server lifespan)

On every backend start the new code does:

1. `seed_default_departments()` — also inserts an `activities` department if
   missing (one row, idempotent). If the community deliberately deleted it, it
   comes back (deactivate instead).
2. `aria_continuity.ensure_indexes()` — creates a `db.conversations` index
   (`resident_id + created_at`). Safe, additive; build time grows with
   collection size (UNVERIFIED on production data).
3. Demo continuity catch-up — no-op unless `CAOSCARE_DEMO_CONTINUITY_AUTO`.
4. Asterisk ARI listener — only if `ASTERISK_ARI_URL` is set.
5. **Escalation background loop — on by default, every 30 s.**

New indexes created lazily at first use (not at startup):
- `db.alerts` **unique partial index** `one_open_resident_event` on
  `open_event_key` (only for documents where it is a string and status is
  active/acknowledged), created on the first resident activation. Legacy
  alerts have no `open_event_key`, so existing history cannot violate it
  (code comment: duplicate history is preserved). Index build on a large
  `alerts` collection: UNVERIFIED.
- `db.resident_aria_leases` unique index on `room`.
- New collections written on use: `sim_runs`, `demo_continuity`,
  `interpretation_patterns`, call-session collections (telephony), receipts
  with new provenance fields. No migration script exists or is needed;
  documents without the new fields read as legacy.

### Escalation vs. production's existing stale alerts (from code)

`routes/escalation_tick.py::run_tick`:
- considers alerts with status in `open/active/escalated`, no
  `acknowledged_at`, no `resolved_at` (first 1000);
- **skips** alerts older than `STALE_ALERT_HOURS` = 72 h
  (`alert_is_stale`, based on `created_at`; counted as `stale_skipped`);
- skips alerts whose `created_at` is unparseable;
- escalates alerts **younger than 72 h** that nobody has acknowledged:
  level 2 at the rule's `level_2_seconds` (default 90), level 3 at
  `level_3_seconds` (default 150), appending a new `alert_escalated` receipt
  each time; sends SMS only if the facility's `EscalationRule` has
  `notify_oncall_phone`/`notify_supervisor_phone` **and** Twilio env vars are
  set (otherwise it only logs).
- Consequences to check before release: (a) any real, unacknowledged alert
  created in the last 72 h at deploy time will be escalated to level 3 within
  minutes of the first tick — including leftover demo/test alerts on the
  production Room 401 demo kiosk (UNVERIFIED: query production for alerts
  with `status` active/open, no `acknowledged_at`, `created_at` within 72 h);
  (b) the 300+ old test alerts the 2026-09-20 audit found are > 72 h old and
  stay untouched (`status` unchanged; the audit's 319 active alerts were
  2026-08-29 → 09-06, i.e. stale) — still UNVERIFIED on today's production
  data; (c) the feed (`GET /alerts/feed`) no longer writes escalation, so the
  levels staff see now change only through this loop. If production should
  not escalate on day one, set `CAOSCARE_ESCALATION_AUTO=0` in
  `backend/.env` before the restart and enable it after review.

## 5. Routes needing auth review

New route modules at the tip and how each is guarded (from source; not
exercised against production):

| Module | Guard seen in source |
|---|---|
| `simulation.py` (10 routes) | all behind admin dependency |
| `demo_continuity.py` (2) | admin dependency |
| `call_lifecycle.py`, `telephony_endpoints.py` | auth dependencies on every route |
| `transportation_runs.py`, `transportation_staff.py` | auth dependencies |
| `front_desk.py` | auth dependency |
| `telephony_local.py` (1) | **no user auth**: fail-closed shared token (`CAOS_TELEPHONY_TOKEN`) **and** caller host allowlist (default loopback) |
| `phone_aria.py` (1) | **no user auth**: OpenAI webhook signature verified with `OPENAI_WEBHOOK_SECRET`; rejects when unset |
| `demo_kiosk.py` `POST /api/demo/reset` | **public, no auth**. Refuses (409) unless the `public_demo` kiosk is in room `DEMO`, and refuses a room with any non-mock device. Until `setup_demo_room.py` runs, production's public demo kiosk is Room 401, so a reset call returns 409 and changes nothing. After setup, anyone on the internet can reset the demo room (intended for the demo; it closes only simulated demo requests) |
| `/departments/labels` | any signed-in user, `{slug,label}` only |

Also relevant, already recorded as open decisions (not changed by this
release): public `GET /api/kiosks` enumerates kiosk ids; B1/B2/A in
`docs/reports/2026-10-06-security-followup-aria-public-routes.md`. The
B3 fix (`/residents/public/by-kiosk` allowlist) and the `/realtime/aria-session`
owner-only fix are in the tip, so the release **closes** those two exposures
on production (production `d7ff96a` has both).

Behaviour changes callers may notice: PATCH on tasks accepts only notes and
the visit window (status/assignee via action routes); closed requests are
refused (409); receipts append instead of rewriting; the escalation level no
longer moves on a feed poll.

## 6. `scripts/setup_demo_room.py` step

- `cd backend && .venv/bin/python scripts/setup_demo_room.py` — idempotent.
  Creates the synthetic resident "Demo - Sample Resident" (room `DEMO`) and its
  kiosk, makes that kiosk the only `public_demo` kiosk; every other kiosk
  loses the flag; real rooms otherwise untouched.
- Effect on production: `caoscare.com/kiosk/demo` stops being Room 401's
  resident and becomes the DEMO room. Then run DEMO RESET once to create the
  simulated devices. This is a **data change on production** → needs Michael's
  explicit yes and, per the script, it uses the backend's configured DB.
  Not required for the app to run; skip it if the public demo should stay as is.
- Do not run it before confirming which kiosk production currently flags as
  `public_demo` (UNVERIFIED).

## 7. Frontend build

`yarn build` with `REACT_APP_BACKEND_URL=https://caoscare.com` (deploy
script). No dependency change; 118 `src` files changed, plus media under
`frontend/public/media` (screenshots, marketing images, resident-experience
video assets) and 12 added lines in `sitemap.xml`. Build output size is
UNVERIFIED (latest recorded CI/local builds compiled clean; frontend tests
39 suites / 312 at the RQ-024 merge). The public media adds tens of MB to the
build directory; check disk (`df`) on the Linode before building (UNVERIFIED).
Landing copy changed (capability status registry; "In pilot"/"In development"
labels) — review as a content release too.

## 8. Recommended pre-deploy checklist

1. Michael approves the exact SHA and range in the release-approval format.
2. `main` fast-forwarded to that SHA (a push of the integration tip to
   `origin/main`), confirmed `git merge-base --is-ancestor <sha> origin/main`.
3. Last green gate on that SHA recorded (`backend/scripts/run_backend_tests.sh`
   with `OPENAI_API_KEY=` and HA blank; latest recorded: 314 passed /
   0 failed / 31 skipped at RQ-023/024; frontend 39 suites / 312).
4. Production read-only inspection (a person with access): `git rev-parse
   HEAD` = `d7ff96a`; tree clean; free disk; `backend/.env` has no
   `CAOSCARE_ENABLE_DEMO_SEED=true`, no local-owner bypass; note existing
   values of `RESEND_*`, `TWILIO_*`; count unacknowledged alerts < 72 h old
   (escalation effect, §4); which kiosk is `public_demo`.
5. Decide: `CAOSCARE_ESCALATION_AUTO` (on/off for day one), `activities`
   department OK, run `setup_demo_room.py` yes/no.
6. Fresh DB backup is taken by the deploy script (`mongodump` before any
   change); also note the rollback command it prints.
7. Pick a quiet time; confirm no resident session is live (no active
   `resident_aria_leases`) since the restart drops connections.
8. Sibling `caos-backend.service` and nginx are not touched by the script;
   confirm the same PIDs after.

## 9. Post-deploy smoke tests

1. `https://caoscare.com/api/health` → `{"ok":true,"db":"up"}`; deployed
   `git rev-parse HEAD` equals the approved SHA; served `main.<hash>.js`
   equals the freshly built file.
2. `/`, `/login`, `/admin`, `/staff`, `/front-desk`, `/for-residents`,
   `/for-communities`, `/experience`, `/robots.txt`, `/sitemap.xml` → 200;
   video/poster play on the landing page.
3. Anonymous: `GET /api/auth/me` → 401; `GET /api/residents/public/by-kiosk/<id>`
   returns only id/name/preferred name/room; `POST /api/realtime/aria-session`
   anonymous → 401; `POST /api/demo/reset` → 409 (or the DEMO reset if setup
   was run).
4. Owner sign-in (password or Google) → `/admin` Operations overview loads;
   Activities department exists; Live Operations tab loads (do not start a
   simulator run on production).
5. Create one test request through the UI for a clearly-marked test resident
   and walk it claim → start → note → complete; check the history timeline
   and that each step has its own receipt; then confirm Aria's status wording
   (Room 401 kiosk) — mark it as test data.
6. Escalation: `journalctl -u caoscare-backend` shows no loop errors; unacked
   alerts < 72 h behave as decided in §8.5; older alerts unchanged.
7. Email: Admin → Email & notifications shows provider status; send the test
   email only if `RESEND_API_KEY` is set (otherwise expect "Recorded only —
   not sent").
8. Journal clean after 10 minutes; `systemctl is-active caoscare-backend`,
   sibling service/nginx unchanged.
9. Rollback readiness: the printed `deploy_caoscare.sh <previous sha>` command
   and DB restore command are saved before declaring done.

## 10. Not covered / UNVERIFIED

Production env contents, data volumes, index build times, disk, current
`public_demo` kiosk, live alert ages, provider keys, whether telephony/
Resend/Twilio are configured, Linode firewall for the webhook. No test was
run for this document (documentation only).
