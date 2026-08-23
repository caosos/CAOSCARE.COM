# Production deployment inspection + deployment mechanism design

**Status: design only. Nothing has been deployed. No deploy script exists
on disk yet - the two scripts below are proposed content, shown to Michael
for review, not yet written to the repo or run against production.**

## What this covers

Two things from the same working session: (1) a full read-only inspection
of the actual `caoscare.com` production server, and (2) the resulting
design for a real, repeatable `git commit -> push -> deploy` mechanism -
which did not exist before this.

## Part 1 — Production inspection findings

Server: `172.234.25.199` (Linode), reached via SSH as `michael-chambers`
with a dedicated key generated for this purpose. Read-only throughout.

- **Deployment directory**: `/opt/caoscare/app` - a real git checkout,
  `origin` = `github.com/caosos/CAOSCARE.COM`, branch `main`.
- **Deployed commit was `1528744d`, dated 2026-05-17 - 56 commits behind**
  the repo's current `main` at the time of inspection. Confirmed two ways:
  `git log` on the server, and externally (frontend `Last-Modified: May
  17`; live 404s on routes - `/api/transportation/...`,
  `/api/tasks/resident-request/...` - that don't exist in that old
  commit). None of Terminal 8/9, Resident Record, or the Realtime voice
  trust/provenance work from this session were live.
- **Process manager**: systemd, not Docker, not PM2 (PM2 isn't installed -
  a stray `.pm2` folder in the home directory is unrelated leftover).
  Three services confirmed `active`/`enabled`: `caoscare-backend.service`
  (`uvicorn server:app` on `127.0.0.1:8001`, `Restart=always`), `mongod`,
  `nginx`.
- **Reverse proxy**: nginx, Certbot-managed real TLS cert for
  `caoscare.com`. Serves `frontend/build/` directly (no copy step in
  practice, despite the runbook describing one); proxies `/api/` to
  `127.0.0.1:8001`; SPA fallback to `index.html`.
- **Environment**: `backend/app/.env` present, `600` permissions, not
  tracked by git - correct. Contents not read.
- **Database**: local MongoDB, single instance, bound to `127.0.0.1` only.
  Database name in actual use is `caoscare_server` (not `caoscare`, which
  is what `.env.example` implies - a real naming discrepancy worth
  knowing). **No backup automation existed at all** before this session's
  design work - no crontab, no dump script, nothing beyond standard Ubuntu
  system cron.
- **Important: this server is not dedicated to CAOSCare.** nginx also
  serves `caosai.net` (a separate project, its own git repo/branch, its
  own `caos-backend.service`) and `cutlerlawns.com` (unrelated). A
  home-directory `deploy.sh` initially looked like it might be CAOSCare's
  deploy process - it is not; it belongs to `caosai.net`. Any CAOSCare
  deployment mechanism must never touch either sibling.
- **Linode resize**: server was resized from 2GB to 4GB RAM mid-session.
  First check after the resize still showed 1.9GiB total and unchanged
  uptime - the resize hadn't taken effect yet (Linode plan resizes need a
  reboot). Michael rebooted; confirmed after: fresh boot, **3.8GiB total
  RAM**, all four services (`caoscare-backend`, `mongod`, `nginx`,
  `caos-backend`) came back `active` on their own, `caoscare.com`
  confirmed reachable end-to-end afterward.

## Part 2 — Deployment mechanism design (proposed, not yet built)

No CI/CD, no deploy script, and no repeatable path existed before this.
Designed two small scripts to close that gap, against Michael's explicit
requirements:

### `scripts/deploy_caoscare.sh`
- Takes a required, explicit full git SHA - never a branch, never a
  default. Deploying `main`'s current tip and rolling back to an older
  commit are the *same* operation with a different argument.
- Verifies the SHA is real and actually part of `origin/main`'s history
  (`git fetch` + `git cat-file -e` + `git merge-base --is-ancestor`)
  *before* touching anything else - no backup, no checkout, nothing.
- `mongodump`s `caoscare_server` (timestamped, tagged with the pre-deploy
  commit) before any code change lands.
- Checks out the exact commit; confirms `.env` survived the checkout;
  confirms the checkout landed exactly where expected.
- Installs backend/frontend dependencies **only if `requirements.txt` /
  `yarn.lock` / `package.json` actually changed** between the old and new
  commit (diffed, not assumed) - always rebuilds the frontend regardless,
  since source files change independently of dependencies.
- Restarts **only** `caoscare-backend.service`. nginx is never restarted
  (it just reads whatever's on disk); `caos-backend.service`,
  `caosai.net`, and `cutlerlawns.com` are never referenced anywhere in
  either script.
- Confirms the *new* process actually came up (compares systemd's
  `ActiveEnterTimestamp`, not just "service says active"), confirms the
  checked-out commit matches the target exactly, then verifies the real
  public site over HTTPS - both `/api/health` and the frontend.
- **Failure handling**: any failure after checkout but before a
  successful restart automatically reverts the working tree back to the
  previous commit - production's checked-out source can never end up
  mismatched with what's actually running. The live service is only ever
  touched after a build fully succeeds, so a bad build never reaches a
  restart attempt at all.
- Logs every run to `deploy_history.log` on the server; reports the
  deployed SHA and the exact rollback command on both success and
  failure.

### `scripts/rollback_caoscare_db.sh`
- Separate, deliberately not automatic. Restores a specific, named backup
  directory (from a completed `deploy_caoscare.sh` run) via `mongorestore
  --drop`.
- Requires typing the database name to confirm before doing anything
  destructive. Stops the backend before restoring (nothing writes mid-
  restore), restarts it after, verifies health.
- Never invoked automatically by the deploy script's own failure path -
  restoring a database backup is destructive to anything written since
  that backup, so it's always a separate, deliberate human decision.

### Rollback, concretely
- **Code only**: `deploy_caoscare.sh <previous-sha>` - same script, same
  guarantees.
- **Code + database**: the above, then `rollback_caoscare_db.sh
  <backup-dir>` naming the exact pre-deploy backup.

## Current status

Design reviewed with Michael, full script content shown inline for
review. **Neither file has been written to the repo yet, and nothing has
been run against production.** Next step is Michael's go-ahead to
actually create the files (a normal commit/push), and separately, his
go-ahead to run a first real deploy - those are two different approvals.
