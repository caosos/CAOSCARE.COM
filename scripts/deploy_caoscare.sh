#!/usr/bin/env bash
# Deploy an EXACT commit to CAOSCare production (caoscare.com).
# Run ON the production server from /opt/caoscare/app.
#
# Usage:
#   ./scripts/deploy_caoscare.sh <full-git-sha>
#
# No default/branch mode - the exact commit must always be named. The same
# command is how you roll back code: pass the previous known-good SHA.
#
# Verified against the live production filesystem (2026-08-23): the real
# env path is backend/.env (/opt/caoscare/app/backend/.env), confirmed
# against caoscare-backend.service's own EnvironmentFile= line.
set -euo pipefail

APP_DIR="/opt/caoscare/app"
VENV_DIR="/opt/caoscare/venv/backend"
BACKUP_DIR="/opt/caoscare/backups/mongo"
LOG_FILE="/opt/caoscare/deploy_history.log"
SERVICE="caoscare-backend.service"
DB_NAME="caoscare_server"

TARGET_SHA="${1:?Usage: $0 <full-git-sha> - no default, the exact commit must always be named}"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOG_FILE"; }
fail() {
  log "DEPLOY FAILED: $*"
  if [ "${CHECKED_OUT:-0}" = "1" ] && [ "$(git -C "$APP_DIR" rev-parse HEAD)" != "$PREV_SHA" ]; then
    log "Reverting working tree to previous commit $PREV_SHA (service was never restarted, so production never served the new code)"
    git -C "$APP_DIR" checkout --quiet "$PREV_SHA"
  fi
  log "Previous known-good commit: $PREV_SHA"
  log "If a database restore is also needed: scripts/rollback_caoscare_db.sh ${DUMP_DIR:-<no backup was taken before this failure>}"
  exit 1
}

cd "$APP_DIR"
PREV_SHA="$(git rev-parse HEAD)"
log "Deploy requested. Current: $PREV_SHA  Target: $TARGET_SHA"

[ -f backend/.env ] || fail "backend/.env is missing - refusing to deploy"

# 1. Verify the target SHA is real and reachable from origin/main - BEFORE
#    touching anything else (no backup, no checkout, nothing).
git fetch origin --quiet
git cat-file -e "${TARGET_SHA}^{commit}" 2>/dev/null || fail "$TARGET_SHA is not a known commit"
git merge-base --is-ancestor "$TARGET_SHA" origin/main || fail "$TARGET_SHA is not part of origin/main's history - refusing to deploy an unmerged/unknown commit"
log "Verified $TARGET_SHA exists on origin/main"

# 2. Back up the database before any code change lands
mkdir -p "$BACKUP_DIR"
DUMP_DIR="$BACKUP_DIR/$(date -u +%Y%m%d-%H%M%S)-pre-deploy-${PREV_SHA:0:12}"
log "Backing up $DB_NAME to $DUMP_DIR"
mongodump --quiet --db "$DB_NAME" --out "$DUMP_DIR" || fail "database backup failed - refusing to proceed without one"

# 3. Check out the exact commit
git checkout --quiet "$TARGET_SHA"
CHECKED_OUT=1
[ -f backend/.env ] || fail "backend/.env vanished after checkout - aborting"
[ "$(git rev-parse HEAD)" = "$TARGET_SHA" ] || fail "checkout did not land on the requested commit"

# 4. Install dependencies ONLY if they actually changed
if ! git diff --quiet "$PREV_SHA" "$TARGET_SHA" -- backend/requirements.txt; then
  log "backend/requirements.txt changed - installing"
  "$VENV_DIR/bin/pip" install -q -r backend/requirements.txt || fail "backend dependency install failed"
else
  log "backend/requirements.txt unchanged - skipping pip install"
fi

if ! git diff --quiet "$PREV_SHA" "$TARGET_SHA" -- frontend/yarn.lock frontend/package.json; then
  log "frontend dependencies changed - installing"
  (cd frontend && yarn install --frozen-lockfile --silent) || fail "frontend dependency install failed"
else
  log "frontend dependencies unchanged - skipping yarn install"
fi

# 5. Build frontend (always - source files change even when deps don't).
#    nginx serves frontend/build/ directly - no copy step, and nginx is
#    never restarted here since only static files change. If a CAOSCare
#    nginx config ever gets added to this repo, its conditional
#    `nginx -t && systemctl reload nginx` belongs right here, gated on
#    that specific file having changed - not before, not unconditionally.
log "Building frontend"
(cd frontend && REACT_APP_BACKEND_URL=https://caoscare.com yarn build --silent) || fail "frontend build failed"
[ -f frontend/build/index.html ] || fail "frontend build produced no index.html"

# 6. Only after a fully successful build does anything live get touched.
#    Only caoscare-backend.service - never caos-backend.service (caosai.net),
#    never cutlerlawns.com.
RESTART_TIME_BEFORE="$(systemctl show -p ActiveEnterTimestamp --value "$SERVICE")"
log "Restarting $SERVICE"
sudo systemctl restart "$SERVICE" || fail "service restart failed"

# 7. Confirm the NEW process actually came up healthy (not just "still running")
ok=""
for _ in $(seq 1 10); do
  RESTART_TIME_AFTER="$(systemctl show -p ActiveEnterTimestamp --value "$SERVICE")"
  if [ "$RESTART_TIME_AFTER" != "$RESTART_TIME_BEFORE" ] && curl -fsS --max-time 3 http://127.0.0.1:8001/api/health 2>/dev/null | grep -q '"ok":true'; then
    ok=1; break
  fi
  sleep 2
done
[ -n "$ok" ] || fail "backend did not come up healthy after restart"

# 8. Verify the exact commit actually deployed
DEPLOYED_SHA="$(git rev-parse HEAD)"
[ "$DEPLOYED_SHA" = "$TARGET_SHA" ] || fail "post-restart commit ($DEPLOYED_SHA) does not match target ($TARGET_SHA)"

# 9. Verify the public site end-to-end, over HTTPS
log "Verifying https://caoscare.com"
curl -fsS --max-time 8 https://caoscare.com/api/health | grep -q '"ok":true' || fail "public HTTPS health check failed"
curl -fsS -o /dev/null --max-time 8 https://caoscare.com/ || fail "public HTTPS frontend check failed"

# 10. Report
log "DEPLOY SUCCEEDED - $DEPLOYED_SHA is live (was $PREV_SHA)"
log "Database backup for this deploy: $DUMP_DIR"
log "Rollback code only:       $0 $PREV_SHA"
log "Rollback code + database: $0 $PREV_SHA && scripts/rollback_caoscare_db.sh $DUMP_DIR"
echo "Deployed $DEPLOYED_SHA (was $PREV_SHA). caoscare.com verified healthy. Backup: $DUMP_DIR"
