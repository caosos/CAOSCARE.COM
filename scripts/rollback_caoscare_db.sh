#!/usr/bin/env bash
# Restore caoscare_server from a specific backup taken by deploy_caoscare.sh.
# DESTRUCTIVE - overwrites current data. Never run automatically; always a
# deliberate, named, human-confirmed action.
#
# Usage:
#   ./scripts/rollback_caoscare_db.sh /opt/caoscare/backups/mongo/<timestamp>-pre-deploy-<sha>
set -euo pipefail

DB_NAME="caoscare_server"
SERVICE="caoscare-backend.service"
DUMP_PATH="${1:?Usage: $0 <path-to-backup-dir-from-deploy_history.log>}"

[ -d "$DUMP_PATH/$DB_NAME" ] || { echo "No $DB_NAME dump found under $DUMP_PATH"; exit 1; }

echo "About to REPLACE the live $DB_NAME database with the backup at:"
echo "  $DUMP_PATH"
echo "This is destructive to any data written since that backup."
read -r -p "Type the database name ($DB_NAME) to confirm: " confirm
[ "$confirm" = "$DB_NAME" ] || { echo "Confirmation did not match - aborting, nothing changed."; exit 1; }

echo "Stopping $SERVICE so nothing writes during restore..."
sudo systemctl stop "$SERVICE"

mongorestore --quiet --drop --db "$DB_NAME" "$DUMP_PATH/$DB_NAME"

echo "Starting $SERVICE..."
sudo systemctl start "$SERVICE"
sleep 3
curl -fsS --max-time 5 http://127.0.0.1:8001/api/health; echo
echo "Database restored from $DUMP_PATH and $SERVICE restarted."
