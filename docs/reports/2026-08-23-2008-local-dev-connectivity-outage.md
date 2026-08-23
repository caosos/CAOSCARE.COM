# Local EliteDesk dev-stack outage: two distinct root causes

**Neither the database nor any application data was ever affected.** Both
failures were pure local-network connectivity issues on the EliteDesk dev
machine. Confirmed by direct query throughout: 6 residents, 7 kiosks, 19
staff_tasks, 26 receipts, 357 conversations, 1119 realtime_diagnostics
events in `caoscare` - unchanged the entire time.

## Failure A — backend (port 8000) unreachable from the browser

**Symptom:** Admin UI showed "Could not load requests", "Failed to load
pendants", kiosks/residents empty, Google sign-in failing - all at once.
Browser DevTools confirmed `net::ERR_CONNECTION_REFUSED` on every `/api/*`
call, not an auth rejection.

**Root cause:** this machine's system resolver returns `::1` (IPv6) for
the hostname `localhost` (confirmed via `getent hosts localhost`), but
uvicorn was bound only to the IPv4 loopback `127.0.0.1:8000` - nothing
was listening on `[::1]:8000` at all. `curl http://localhost:8000`
happened to keep working the whole time (curl's resolver fell back to
IPv4 cleanly); the browser's fetch to the same URL did not fall back the
same way and hit a hard connection refusal. The backend process itself
never crashed - same PID, continuously running - this was a pure
hostname-resolution mismatch, not a process or data problem.

**Fix:** `frontend/.env`'s `REACT_APP_BACKEND_URL` changed from
`http://localhost:8000` to `http://127.0.0.1:8000` - an explicit IP has
no resolution ambiguity at all. Backend itself was not modified.

## Failure B — frontend dev server (port 3000) unreachable from the browser

**Symptom:** immediately after Failure A was fixed and confirmed working,
`http://localhost:3000/admin` and `/login` both showed
`ERR_CONNECTION_REFUSED`.

**Root cause: the exact same class of bug as Failure A, on the other
port.** `craco start` / webpack-dev-server was bound to `0.0.0.0:3000`
(IPv4 only, no `HOST` env var set, matching CRA's default) - the browser
resolving `localhost` to `::1` hit a refusal there too. Proven directly:
`curl --resolve localhost:3000:::1 http://localhost:3000/` reproduced
`HTTP 000` (connection failure) before the fix, `HTTP 200` after. The
frontend process had **not** crashed or exited either - same PIDs,
continuously running since its last restart - this was never a process
death, despite looking exactly like one from the browser's side.

**Fix, two parts:**
1. Immediate: confirmed `127.0.0.1:3000` always worked as a bypass.
2. Proper fix: added `HOST=::` to the frontend's process environment,
   making webpack-dev-server bind dual-stack (`*:3000` - both IPv4 and
   IPv6 loopback) instead of IPv4-only. Verified all three of
   `localhost:3000`, forced-IPv6 `[::1]:3000`, and `127.0.0.1:3000` return
   200 after the change.

## Structural fix: real process supervision

Both the frontend and backend were previously raw `nohup`'d background
shell processes with no supervision, no restart-on-failure, and no
survival across a logout - not a real dependability story for "EliteDesk
is now the primary CAOSCARE development machine."

Added `~/.config/systemd/user/caoscare-frontend-dev.service` (local
machine config, not part of the git repo - absolute `nvm` node/yarn paths
are specific to this machine):

```ini
[Unit]
Description=CAOSCare frontend dev server (craco start, hot reload)
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/caoscare-1/CAOSCARE.COM/frontend
Environment=PATH=/home/caoscare-1/.nvm/versions/node/v24.18.0/bin:/usr/bin:/bin
Environment=HOST=::
ExecStart=/home/caoscare-1/.nvm/versions/node/v24.18.0/bin/yarn start
Restart=on-failure
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

Enabled (`systemctl --user enable --now`) and `loginctl enable-linger
caoscare-1` set so it survives even without an active login session.
Logs: `journalctl --user -u caoscare-frontend-dev.service -f`. Still a
dev server (`craco start`, hot reload intact) - not a production build,
not a deployment.

The backend was **not** touched or converted to a service this round -
Michael's explicit instruction was not to touch it again after Failure A
was already confirmed fixed. The same systemd-user pattern would apply
cleanly to it in a future round if wanted.

## Verified live, in order

1. `caoscare-frontend-dev.service` active, "Compiled successfully"
2. Port 3000 listening on `*:3000` (dual-stack)
3. `localhost:3000`, `[::1]:3000` (forced), `127.0.0.1:3000` all return 200
4. `127.0.0.1:8000/api/health` still `{"ok":true,"db":"up"}` - backend untouched
5. Frontend bundle confirmed to contain `127.0.0.1:8000`, not `localhost:8000`
6. `/login` and `/admin` both serve 200 (SPA routes)
7. `/api/kiosks` (public) returns real data; `/api/residents`, `/api/pendants`
   return 401 without a token - correct, expected behavior, not a bug
