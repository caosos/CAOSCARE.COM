# Terminal 6 — Session Handoff (read this to catch up)

## Purpose

This is not a new build directive. It's a briefing so a fresh Claude Code
session on `caoscare1-hp-elitedesk` (or anywhere else this repo is cloned)
can get current on the Aria voice-first work in progress without Michael
having to re-explain it. A different terminal/session cannot see another
session's live conversation — this file, plus the docs it points to, is how
state actually transfers between them.

## Do this first

1. `git pull origin main`
2. Read, in order:
   - `docs/PROJECT_STATE.md` — read from the bottom up; the most recent
     dated entries are what's current.
   - `docs/ARIA_VOICE_FIRST.md` — the Aria build log (Phases A/C so far).
   - `docs/ARIA_CAPABILITY_PORTFOLIO.md` — schema/API for the capability
     registry.
   - `docs/ELITEDESK_NODE_BUILD.md` — the underlying host/HA-VM build this
     all sits on top of.
3. Confirm current live state before assuming anything is still true:
   - `curl http://127.0.0.1:8000/api/health` (backend)
   - `curl -o /dev/null -w '%{http_code}\n' http://localhost:3000` (frontend)
   - `sudo virsh list --all` (Home Assistant VM)
   - These are dev processes started with `setsid`/`nohup`, not systemd —
     they do NOT survive a host reboot. If they're down, restart them the
     same way the docs above describe (same commands, same `.env` files,
     don't touch or regenerate the `.env` files).

## Exactly where things stand (as of the entries you just read)

- The OpenAI Realtime voice pipeline works: `OPENAI_API_KEY` is configured
  in `backend/.env`, `POST /api/realtime/aria-session` mints real ephemeral
  sessions with Aria's own persona (not the resident-facing CAOS companion).
- A real pre-existing bug was found and fixed in
  `frontend/src/lib/useRealtimeVoice.js` (wrong field for the ephemeral key)
  — already committed and pushed.
- A minimal `/aria` page exists (`frontend/src/pages/AriaVoice.jsx`,
  owner-only route) but **nobody has actually talked to Aria yet** — the
  live browser/microphone round-trip is unproven. That's the standing
  next step whenever Michael is at the EliteDesk with a browser open there.
- The capability portfolio (`db.aria_capabilities`, `/api/capabilities`)
  and Aria's separate operator-memory scope (`db.aria_memories`,
  `/api/aria/memory`) are both built and seeded.
- Login redirect-back-to-intended-page was just fixed (`Protected` in
  `App.js` now carries `state={{from: location}}`; `Login.jsx`,
  `AdminLogin.jsx`, `GoogleSignIn.jsx` all honor it) — owner/admin-only
  routes now send logged-out visitors to `/admin-login` instead of `/login`.
- **Google Sign-In is not yet configured on this host.** Michael has an
  existing Google OAuth Client ID from an earlier CAOSCare session and was
  about to paste it in chat (it's not a secret — it's meant to be public,
  ships in the frontend bundle). If he's given it to you:
  1. Set `GOOGLE_CLIENT_ID=<the id>` in `backend/.env`.
  2. Set `GOOGLE_ADMIN_EMAILS=mytaxicloud@gmail.com` in `backend/.env` (not
     strictly required for his own account, which already has `role=owner`
     in `db.users` — but required if he wants the admin-portal's Google
     button specifically, since that path hard-gates on this allowlist).
  3. Set `REACT_APP_GOOGLE_CLIENT_ID=<the id>` in `frontend/.env`.
  4. Remind him to confirm `http://localhost:3000` (and the LAN IP,
     `http://192.168.1.151:3000`, if he wants it) are in that Client ID's
     **Authorized JavaScript origins** in Google Cloud Console — that's a
     console action only he can do.
  5. Restart backend + frontend, verify `/login` or `/admin-login`'s
     Google button appears and signs him in.
  If he hasn't given you the Client ID yet, ask him for it plainly — don't
  invent one.
- Midea/Matter LAN work (Terminal 4) is deliberately paused, tracked as a
  `blocked` capability in the portfolio, not abandoned. Do not resume it
  unless Michael asks — voice-first has priority per Terminal 5A.

## What to actually do once you've read all this

Tell Michael, in your own words, a short confirmation of what you now
understand is current (so he can correct you if something changed), then
ask what he wants to work on next rather than assuming it's the same task
this file was written during.
