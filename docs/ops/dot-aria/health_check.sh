#!/usr/bin/env bash
set -euo pipefail
base_url="${CAOSCARE_DOT_ARIA_BASE_URL:-http://192.168.122.1:8092/api/dot-aria}"
if [[ -t 0 ]]; then
  read -r -s -p 'Dot Aria bearer token (not echoed): ' token
  echo >&2
else
  IFS= read -r token
fi
auth_file="$(mktemp)"
chmod 0600 "$auth_file"
trap 'unset token; rm -f "$auth_file"' EXIT
[[ -n "$token" ]] || { echo 'No token supplied' >&2; exit 2; }
printf 'header = "Authorization: Bearer %s"\n' "$token" >"$auth_file"
unset token
common=(--config "$auth_file" --silent --show-error --fail-with-body --max-time 10 --connect-timeout 3)
curl "${common[@]}" "$base_url/capabilities"
printf '\n'
curl "${common[@]}" "$base_url/profile"
printf '\n'
curl "${common[@]}" "$base_url/departments"
printf '\n'
curl "${common[@]}" -H 'Content-Type: application/json' -d '{}' "$base_url/menu"
printf '\n'
