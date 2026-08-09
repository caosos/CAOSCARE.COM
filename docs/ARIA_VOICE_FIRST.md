# Aria Voice-First CAOSCare Node

Living build record for `commands/TERMINAL_5_ARIA_VOICE_FIRST.md` and
`commands/TERMINAL_5A_ARIA_CAPABILITY_PORTFOLIO.md` on the
`caoscare1-hp-elitedesk` node. Do not replace or erase prior entries —
append dated sections as the build progresses.

Wake word: **Aria**, three syllables (Ar-i-a). Not yet implemented — see
Phase A findings below.

---

## 2026-08-02 — Phase A: establish the truth

### Agent / tool
Claude Code with Michael on `caoscare1-hp-elitedesk`, continuing directly from
the Terminal 3/4 EliteDesk node-build session (`docs/ELITEDESK_NODE_BUILD.md`).

### Branch / ref
`main` at `2bb9ddc` (`Add Terminal 5/5A Aria directives`) at start of this
phase. Commits from this phase follow below.

### What was found

**Existing voice infrastructure (bigger head start than assumed):**
- `frontend/src/lib/useRealtimeVoice.js` — a working OpenAI Realtime API
  voice hook over WebRTC. Mints an ephemeral session (`POST /api/realtime/session`),
  negotiates SDP (`POST /api/realtime/negotiate`), opens a `RTCPeerConnection`
  + `oai-events` data channel, streams mic audio in/out full-duplex, uses
  OpenAI server-side VAD for turn detection, supports tool/function calling
  routed to CAOS REST endpoints, and posts closed turns to
  `POST /api/memory/realtime-turn` for extraction.
- `backend/routes/realtime.py` (826 lines) — builds the realtime session,
  tool list, VAD config; consumed by the frontend hook above.
- Consumer UI: `frontend/src/pages/RealtimeChatScreen.jsx`, invoked from
  `frontend/src/pages/Kiosk.jsx`.
- No Wyoming/openWakeWord/Piper/Whisper-local stack present anywhere in the
  repo or installed on the host — wake-word and local-fallback are net-new.

**Audio hardware — works, mechanically verified:**
- eMeet Luna Plus (USB) is present (`lsusb`: `328f:0079`) and is already the
  OS default PulseAudio sink **and** source.
- `arecord -D default -f S16_LE -r 16000 -d 2` produced a valid 64044-byte
  16kHz mono WAV — capture path works end to end.
- `speaker-test -D default -c 2 -t sine -f 440 -l 1` ran without error; the
  Luna Plus sink showed active/IDLE state immediately after — playback path
  runs end to end. **Not yet confirmed audible/clear from normal room
  distance** — that requires Michael in the room, tracked as a capability
  next_step (see portfolio).
- PipeWire is active; PulseAudio-compat socket (`pactl`) also active and used
  for the tests above.

**Provider configuration — blocked:**
- `backend/.env.example` already declares `OPENAI_API_KEY`, `OPENAI_TEXT_MODEL`,
  `OPENAI_REALTIME_MODEL`, `OPENAI_VOICE`, consumed in `backend/routes/realtime.py`,
  `backend/routes/memory.py`, `backend/routes/ai.py`.
- **This host's actual `backend/.env` has no `OPENAI_API_KEY` set.**
  `curl -X POST /api/realtime/session` correctly returns `503`:
  `"OPENAI_API_KEY is not configured; OpenAI Realtime is unavailable."`
  The app already fails gracefully — nothing is broken, the key is simply
  absent. Per the directive, this is a stop-and-ask point, not something to
  invent a workaround for.

**Memory model — architecture decision needed and made:**
- Existing `db.memories`/`ResidentMemory` (`backend/routes/memory.py`,
  `backend/models.py`) is `resident_id`-scoped and governed by
  `docs/CAOSCARE_MEMORY_AUTOMATION_CONTRACT.md`, an elder-care-specific
  contract (no cross-session leakage, medical-adjacent field handling, etc.).
  It does not fit "Michael's own identity/projects/preferences."
- Presented Michael the choice; **he chose (a): a dedicated non-resident
  "operator/Aria" memory scope**, kept structurally and physically separate
  from resident data and outside that contract's governance. Implemented
  this phase — see below.

### What changed

- Added `AriaCapability` + `AriaCapabilityCreate/Update/Verify` models
  (`backend/models.py`) and `backend/routes/capabilities.py` — the Terminal 5A
  capability registry. Full schema/API documented in
  `docs/ARIA_CAPABILITY_PORTFOLIO.md`. Registered at `/api/capabilities` in
  `backend/server.py`.
- Added `AriaMemory`/`AriaVoiceSession` models and `backend/routes/aria_memory.py`
  — the approved separate operator-memory scope, keyed by `owner_user_id`,
  storing standing facts (identity/preference/project) and episodic notes
  (session summaries/decisions), plus voice-session receipts
  (`db.aria_voice_sessions`, no raw audio). Registered at `/api/aria` in
  `backend/server.py`.
- Restarted the backend (`uvicorn`, same manual `setsid`/`nohup` method as
  Terminal 3) to load the new routes. No `.env` file touched, no resident/owner
  data touched.
- Seeded the 7 initial capability portfolio entries required by Terminal 5A
  (voice/memory, HA API, Midea/Matter, eMeet hardware, MQTT, EliteDesk service
  health, future resident/family/staff capabilities) via the new API, using a
  short-lived JWT minted locally from the existing `JWT_SECRET` for testing
  (never printed, never persisted — the test-token scratch file was `shred -u`'d
  immediately after use).
- Exercised the receipt pattern for real: `POST /api/capabilities/{id}/verify`
  on the eMeet capability recorded a `verified_read` receipt referencing the
  arecord/speaker-test results above.

### What was verified

- `curl /api/health` → `{"ok":true,"db":"up"}`; frontend → HTTP 200 — both
  confirmed healthy before and after the backend restart.
- `GET/POST /api/capabilities`, `POST /api/capabilities/{id}/verify`,
  `GET /api/capabilities/{id}/receipts`, `GET/POST /api/aria/memory` all
  round-tripped correctly against the running backend with a real owner-role
  JWT (role check via `require_owner` confirmed working, not bypassed).
- 7/7 required initial capability entries present in `db.aria_capabilities`.
- HA VM onboarding already complete (`user`, `core_config`, `analytics`,
  `integration` all `done: true` per `GET /api/onboarding` on the HA VM) —
  carried over from the Terminal 3/4 session, unaffected by this work.

### Blocked / not yet done

- **`OPENAI_API_KEY`** — needed to unblock Phase C (first conversational loop)
  via the preferred OpenAI Realtime path. Michael has not yet provided one.
- Wake-word engine (Aria) — nothing installed yet; Phase D.
- Local-fallback voice path (Wyoming/Whisper/Piper) — not started; would let
  Phase C proceed without the OpenAI key, per the directive's own guidance
  not to let a missing key block proving the room can hear/speak.
- `get_capability_summary()` exists in `routes/capabilities.py` but is **not
  wired into `routes/realtime.py` yet** — that's ordered step 3 (connect tool
  routing to the registry), which comes after the voice foundation itself.
- Midea/Matter LAN work (Terminal 4) remains paused, tracked as `blocked` in
  the capability portfolio per Terminal 5A's explicit instruction not to erase
  or deprioritize it silently.
- No systemd conversion of backend/frontend yet (still Terminal 3 Phase 6,
  untouched).

### Next safe step
Michael provides `OPENAI_API_KEY` (and confirms `OPENAI_REALTIME_MODEL`/
`OPENAI_VOICE` if he wants non-defaults) so Phase C can use the real OpenAI
Realtime path; alternatively, tell Claude to proceed with the local-fallback
path first (Wyoming/Whisper/Piper) to prove Phase B/C without the key, and
swap in Realtime once the key is available.

---

## 2026-08-02 — Phase C: Aria's own Realtime session, and a real pre-existing bug fixed

### Agent / tool
Claude Code with Michael, same session continuing directly from Phase A.

### What changed
- Michael provided `OPENAI_API_KEY` via a hidden local shell prompt (never
  pasted into chat, never printed by Claude — only its presence/length/prefix
  format were checked, e.g. `sk-proj...`). Saved to `backend/.env`.
- Backend restarted; confirmed `POST /api/realtime/session` now mints a real
  ephemeral OpenAI session (previously 503'd in Phase A).
- **Found and fixed a real pre-existing bug** while wiring Aria's own session:
  `frontend/src/lib/useRealtimeVoice.js` read the ephemeral key from
  `session?.client_secret?.value`, but the backend calls
  `POST {OPENAI_API_BASE}/realtime/client_secrets`, whose actual response
  shape is `{value, expires_at, session}` — the key is a **top-level**
  `value`, not nested under a `client_secret` object. That nested shape
  belongs to the older `/realtime/sessions` endpoint. This bug would have
  silently broken **every** Realtime voice session (resident kiosk AND Aria)
  at the very first step — mic would connect, then `if (!ephemeral) throw
  new Error("no ephemeral key")` would fire immediately. Matches
  `docs/BUILD_STATUS.md`'s own note that full-duplex voice was never
  validated end-to-end. Fixed with a fallback (`session?.value ||
  session?.client_secret?.value`) so it tolerates either shape.
- Added Aria's own Realtime session path, kept fully separate from the
  resident-facing one:
  - `backend/routes/realtime.py`: `_build_aria_instructions(owner_user_id)` —
    Aria's persona (direct/accurate/practical, explicitly NO resident
    truth-discipline/attribution rules, those exist to protect a senior in
    care and don't apply here) + live capability-portfolio summary (via
    `get_capability_summary()`) + operator-memory context (via
    `build_aria_context_block()`) injected at session start — this is the
    Terminal 5A "load a concise summary of the capability portfolio" rule,
    now actually wired in for Aria's own sessions.
  - `POST /api/realtime/aria-session` — mints Aria's ephemeral session.
    Reuses the existing `/realtime/negotiate` endpoint unchanged (it's
    persona-agnostic, just relays SDP).
  - **No tools wired yet, by design** — Terminal 5A's stated order is prove
    audio/conversation first, connect tool routing to the capability
    registry second. Aria's system prompt says so explicitly rather than
    letting the model pretend to control anything.
  - `frontend/src/lib/useRealtimeVoice.js`: added optional
    `sessionEndpoint`/`sessionPayload` params (default unchanged, so the
    existing resident/Kiosk flow is untouched) so the same hook can point at
    either session-minting endpoint.
  - `frontend/src/pages/AriaVoice.jsx` (new) + a `/aria` route in `App.js`
    (owner-only) — deliberately minimal: an orb, a status line, a
    start/stop button, a live transcript. No decorative UI, per the
    directive.
- Restarted the backend again to load the new route; confirmed the frontend
  dev server hot-compiled with no new errors (only the pre-existing
  `react-hooks/exhaustive-deps` warning already documented in Terminal 3).

### What was verified
- `POST /api/realtime/aria-session` returns a real ephemeral key
  (`ek_...`) and a `session` object whose `instructions` field contains
  Aria's persona, the current date/time, the live capability portfolio
  summary (pulled from `db.aria_capabilities`), and the operator-memory
  context block (currently empty — no memories recorded yet).
- `_caos.tools` is `[]` as intended — confirmed no accidental tool leakage
  from the resident-facing builder.
- Backend and frontend both healthy after every restart this phase.

### Blocked / not yet done
- **Nobody has actually spoken to Aria yet.** Everything above proves the
  session mints correctly and carries the right instructions — it does NOT
  prove the WebRTC audio round-trip actually works in a real browser with a
  real microphone. That requires Michael, a browser, and the room's mic —
  see Next safe step.
- Wake-word ("Aria" by voice, hands-free) is still Phase D — right now
  starting a session means opening `/aria` and clicking a button.
- Tool routing to the capability registry (Terminal 5A step 3) intentionally
  not started yet.
- `frontend/src/pages/RealtimeChatScreen.jsx` (resident-facing) was NOT
  changed beyond the shared `useRealtimeVoice.js` bugfix — its own behavior
  should be re-verified with a real resident/kiosk session at some point
  since it was apparently never exercised end-to-end before either.

### Next safe step
Michael opens a browser on the EliteDesk itself (so it uses the eMeet Luna
Plus mic/speaker already confirmed as the OS default), logs in as owner, and
navigates to `http://localhost:3000/aria`. Click "Start talking with Aria,"
allow microphone access, and just talk. Report back: did it connect, did you
hear Aria's voice, was it clear, and did the conversation feel natural —
that's the actual Phase C proof this whole phase has been building toward.

---

## 2026-08-09 — Phase C proof landed; personality tuning pass

### Agent / tool
Claude Code with Michael, same EliteDesk node.

### What was found (Phase C finally proven)
Michael had a real spoken conversation with Aria for the first time — the
mic/WebRTC/speaker round trip works. Feedback: the conversational core is
solid ("we proved the conversational core works"), but the default
personality came across too enthusiastic/"AI-assistant"-sounding — stacked
exclamation points, praise, repeating things back, unsolicited explanations.

### Current Realtime config, inspected and reported (not changed, none of it
### was misconfigured)
```text
Model:            gpt-realtime            (OPENAI_REALTIME_MODEL unset -> default)
Voice:             shimmer                 (OPENAI_VOICE unset -> default)
Temperature:       0.6                     (floor - most factual, least improvisational)
Turn detection:    server_vad, threshold 0.5, prefix_padding_ms 300,
                   silence_duration_ms 1000, create_response true
                   (sent via a session.update over the data channel after
                   connect, not in the initial ephemeral-mint call - this is
                   existing, working, intentional architecture, not a bug)
Tools:             [] (still none wired - unchanged, by design)
```

### What changed
Rewrote `_build_aria_instructions()` in `backend/routes/realtime.py` (Aria's
own operator-facing persona only — did **not** touch
`_build_companion_instructions()`, the separate resident-facing "CAOS"
persona, which already has its own hard-won pacing/warmth rules from the
pilot and wasn't part of this request):

- **Identity**: now framed as "the conversational intelligence for CAOSCare"
  generally, explicitly not hard-coded to senior-care, with an explicit note
  that she's a distinct persona from resident-facing CAOS. This is the
  concrete instruction while environment/purpose injection (listed as
  future work below) doesn't exist yet.
- **Personality dialed back ~25-30%**: added a "How you sound" section —
  calm, grounded, understated; no stacked exclamation points, no praising
  the question, no repeating back what was just said, no unsolicited
  explanations. Still explicitly permitted to be warm, witty, direct,
  curious, personable — instructed not to go flat/robotic either.
  Michael/operator conversations stay at normal conversational pace (the
  senior-facing slow/clear-articulation pacing Michael also asked about
  applies to resident-facing conversations, which Aria doesn't have yet —
  see Next safe step).
- Truth-discipline and "no tools wired yet" sections kept unchanged — those
  are functionally load-bearing, not stylistic.
- Backend restarted; minted a real `/api/realtime/aria-session` afterward
  and confirmed the new instructions text is actually what's sent to
  OpenAI (`_caos.instructions` in the response), not just written to a file.

### What was verified
- Backend healthy after restart (`{"ok":true,"db":"up"}`).
- Live-minted Aria session's `_caos.instructions` contains the new "Who you
  are"/"How you sound" text verbatim.
- Model/voice/temperature/turn_detection all confirmed as listed above —
  none altered, per Michael's explicit instruction not to touch them absent
  a real misconfiguration (there wasn't one).

### Not done yet (explicitly out of scope for this pass, tracked as real
### future work per Michael's own priority list)
- **Environment/deployment-context injection** — one Aria core with a
  swappable context block (senior-living room / Michael's house / office /
  etc.) instead of a single fixed operator persona. This is the actual
  mechanism that would let the senior-pacing instructions apply
  automatically only when Aria is resident-facing; doesn't exist yet.
- Senior-facing pacing (slower, short sentences, natural pauses) was
  **not** added to Aria's current (operator-only) instructions, since Aria
  doesn't talk to residents today — it belongs on the future
  resident-context injection, not hard-coded into the general core.
- Home Assistant tool bridge (Aria calling registered capabilities, not
  just knowing about them), wake word, turn-taking/barge-in tuning, durable
  memory write-back, capability discovery framing, and boot persistence all
  remain open per Michael's stated priority order — none started this pass.

### Next safe step
Michael talks to Aria again with the new personality and reports whether the
tone lands right (still too enthusiastic / about right / overcorrected too
flat). Separately, decide whether to start the environment-context-injection
work next, since several other open items (senior pacing, room awareness)
depend on that existing before they can be done properly rather than
hard-coded.
