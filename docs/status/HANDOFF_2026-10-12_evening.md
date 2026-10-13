# Handoff — 2026-10-12 21:05 CDT (session caoscare-1-64 closing at Michael's request)

HANDOFF CAPSULE
- Objective: platform-wide resident Aria (continuity, lifelong memory, room control) proven in Michael's home test room (Room 214 = test room; all code is platform-wide). Owner directive da-a3817b6b9c on issue #129.
- Branch: `integration/2026-09-27` @ `48bd54f` (pushed; local = remote). Production `06e7e2b` (only PR #132: public "In pilot" statuses + room-screen HC wrap).
- Read first: `docs/reports/2026-10-12-platform-build-log.md` (built / problems + fixes / what's left), then `docs/PROJECT_STATE.md` entries dated 2026-10-12, `docs/CURRENT_NODE_STATUS.md` (2026-10-12 snapshot).
- Last proven state (live Room 214 voice + receipts):
  - "Hey Aria" opener short and varied; re-wake within 15 min noticed ("Back again so soon, Michael?"); "when did I last talk to you" answered from clock-timed recap; "bye for now" → "Okay, bye for now." single voice, call closes.
  - Lifelong memory: per-conversation summaries + one life story per resident (Room 214 resident backfilled: 49 sessions → 34 summaries).
  - Real Sony TV via XIAO IR Mate (`ir_blaster` adapter, `sony_sirc12`): power on/off/on, volume steps; calls MUTE the TV at wake and unmute at end (6 calls 20:38–20:58, 12 mutes executed, receipted unverified).
  - Device record create/update/delete receipted + owner/admin only; backfilled receipt `rcpt_fe312748ba12` for the TV record switch.
  - Gates at last full runs: backend 662/0/13, frontend 98/667.
- Runtime: dev backend `:8092` @ `61506b1` (PID 2037126, log `/tmp/room214_backend_61506b1.log`); Room 214 page build `816f5f2`; services `aria-wake`, `aria-wake-page`, `aria-wake-kiosk`, `ha-lan-proxy` active; HA `http://192.168.1.151:8123`; IR Mate `192.168.1.160` (firmware `room-node/ir_mate/caoscare_ir_mate.yaml`).
- Unresolved / next (in order):
  1. Faster wake response (now 3–4 s: mint 1.7 s, WebRTC 0.9 s, model 1.5 s) — pre-mint/pre-connect; trim re-wake opener's trailing question.
  2. Wake recall: labelled "Hey Aria" tries (shadow 0.01/3.5 logging beside live 0.05/1.5); TV mute is Michael's visible "she heard me" signal.
  3. Bravia network control (HA `braviatv`, Michael sets PSK on the TV) → verified power/volume; IR stays fallback.
  4. IR Mate: disable touch-to-send (top touch sends slot 0); reserve 192.168.1.160 on the router.
  5. Voice PE (not yet in hand): stock bring-up, mic test, then PR #46 "Hey Aria" firmware.
  6. Release: integration is 300+ commits ahead of production — release candidate, full gates, merge to `main` (Michael merges; auto mode blocks the agent), deploy, LIVE_VERIFY.
  7. Start-of-call mis-transcriptions (foreign fragments) — check transcription language settings.
  8. Owner decisions pending: Alerts acknowledge/close roles; review-flag ownership; family re-notify on repeat presses; Front Desk message scope. Twilio credentials when available.
- Rules that bit today: restart :8092 by the PID on the port (never `pgrep -f` with the pattern in the command line), only when `aria-wake` last showed `mode_listening`; room page via `room-node/aria_wake/ctl.sh rebuild` then restart `aria-wake-kiosk`; no device/state change without a receipt; Michael merges to `main`.
- Do NOT change: production without a release candidate; live wake score without labelled tries; `docs/status/COORDINATOR_HANDOFF_2026-10-11.md` (untracked, another session's).
