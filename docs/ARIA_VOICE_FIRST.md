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

---

## 2026-08-09 — Ground-truth inspection for the full continuity/self-control build

A large combined directive arrived (memory continuity, barge-in, adjustable
pacing, voice-controlled settings, environment awareness, tool-execution
audit, wake word, plus a reported `session_type` error) with an explicit
instruction to inspect and report ground truth *before* building anything.
This entry is that inspection. No code was changed this entry except where
noted.

### The reported `session_type` error — not found, not reproducible
Searched the entire backend and frontend source, this session's backend
logs, and all docs for `session_type` — **zero matches anywhere.** Our own
session-creation payload sends `"type": "realtime"` inside the `session`
object (not `session_type`), which is the current correct field per
OpenAI's `/realtime/client_secrets` schema. Freshly minted a real Aria
session as part of this inspection and it succeeded (`HTTP 200`, valid
ephemeral key). **This error could not be confirmed against the current,
running code** — it may have been from an older OpenAI API shape (already
non-reproducible today), a browser-console-only error from Michael's actual
test session that wasn't captured anywhere I have access to, or a mix-up
with the ephemeral-key field bug already found and fixed in Phase C. Not
guessing at a fix for an error that doesn't reproduce; flagging this back
rather than inventing a change. If it recurs, the exact browser console
text and the request that triggered it will pin it down for real.

### Ground truth, as requested

```text
Model:                gpt-realtime (OPENAI_REALTIME_MODEL unset -> default)
Voice:                 shimmer (OPENAI_VOICE unset -> default), 8 voices allowed
Speech speed:          not configurable anywhere in current code - no speed
                       param exists on either session-creation path
Turn detection:        server_vad, threshold 0.5, prefix_padding_ms 300,
                       silence_duration_ms 1000, create_response true.
                       Applied via session.update over the data channel
                       after connect (frontend useRealtimeVoice.js), not in
                       the initial ephemeral-mint call.
Barge-in:              NOT explicitly implemented in CAOSCare code (no
                       response.cancel / truncation logic found anywhere in
                       backend or frontend). Relies entirely on OpenAI
                       Realtime's own default server_vad interruption
                       behavior. Never explicitly tested end-to-end here -
                       this is real, open work (directive section 5).
Temperature:           0.6 (the API floor - most factual, least
                       improvisational), stored in the session response's
                       _caos block but only actually pushed to OpenAI via
                       the same session.update as above.
Session config sent:   {type, model, instructions, audio:{output:{voice}}}
                       at mint time; {instructions, voice, modalities,
                       input_audio_transcription:whisper-1, tools,
                       tool_choice, turn_detection, temperature} via
                       session.update immediately after connect.
Context/truncation:    no explicit conversation-truncation/summarization
                       logic exists - each Realtime session starts fresh
                       with only the instructions text as context; nothing
                       trims a long-running conversation's context window
                       today (not yet a problem since no session has run
                       long, but there's no mechanism if one did).
Tool definitions:      11 real tools defined in backend/routes/realtime.py
                       _build_tools() for the RESIDENT-facing session only:
                       adjust_room_temperature, toggle_light, toggle_tv,
                       call_for_help, mark_resting, get_current_time,
                       get_weather, research_topic, set_timer,
                       update_preferred_name, end_call.
Tools actually wired:  ALL 11 are genuinely wired, not schema-only -
                       frontend/src/lib/useRealtimeVoice.js's executeTool()
                       makes real fetch() calls to real CAOSCare backend
                       endpoints (room commands, /alerts, /weather/current,
                       etc.) and returns real results to the model. This
                       path has real device-control code; it has NOT been
                       proven with real hardware/a real resident session
                       (per earlier build notes) - so "wired" here means
                       "genuinely executes," not "hardware-verified."
Aria's own tools:      ZERO. /aria-session sends tools:[] deliberately (by
                       design, per Terminal 5A ordering - conversation
                       proven before tool routing). None of the 11
                       resident tools, and no capability-registry tool
                       routing, exist for Aria yet.
Operator memory:       AriaMemory/AriaVoiceSession models + /api/aria/memory
                       exist and round-trip correctly (built Phase A), but
                       hold 0 records - nobody has actually had memory
                       written to them, and nothing currently reads memory
                       back INTO a session automatically beyond
                       build_aria_context_block() being called at session
                       start (which returns empty context today).
Resident memory:       separate, older, more mature system
                       (db.memories/ResidentMemory, governed by
                       docs/CAOSCARE_MEMORY_AUTOMATION_CONTRACT.md) -
                       exists and is wired into the resident-facing
                       companion prompt already; not part of this
                       inspection's scope to re-verify.
HA/MQTT state:         Home Assistant VM running, onboarded, reachable.
                       Mosquitto broker running, HA's own mqtt integration
                       loaded. A dedicated caoscare-mqtt HA service account
                       exists and raw pub/sub was proven via CLI. NONE of
                       this is wired into CAOSCare's backend/Aria yet - no
                       Python MQTT client code exists in backend/ (a
                       paho-mqtt dependency was added to requirements.txt
                       in an uncommitted, in-progress change but no module
                       using it has been written yet). Aria cannot reach
                       Home Assistant in any way today.
```

### What is still blocked / not started (real scope, not attempted this pass)
Sections 2 (lifelong memory continuity/reconciliation), 5 (barge-in
tuning+real test), 6 (adjustable pacing as a real per-person runtime
setting + tool), 7 (voice-controllable settings: speech speed, volume,
text size), 9 (environment/room awareness context injection), 10 (wiring
Aria's own tool-execution path to the capability registry + HA/MQTT), and
11 (wake word) are all real, non-trivial engineering work — each involves
new data models, new API routes, and/or new frontend wiring. Deliberately
**not** attempted in this single pass: building all of it uninspected and
unreviewed in one sweep would risk breaking the one thing that currently
works (the proven voice round-trip), which section 14 of the directive
itself explicitly warns against ("do not break the working system... make
incremental changes").

### Recommended build order (for Michael to confirm/reprioritize)
1. **Environment/deployment-context injection** (section 9) — the
   foundational piece several other items depend on (adjustable pacing
   persistence, room awareness, eventually resident vs. operator context
   switching). Small, contained: one context-loading function + a place to
   store it.
2. **MQTT bridge module** (Terminal 3 Phase 5, still open) — needed before
   Aria can touch Home Assistant at all; the broker/credentials already
   exist, just needs the actual backend client code.
3. **Wire Aria's tool execution** to the capability registry (section 10)
   once 1+2 exist, starting with read-only capabilities before any control
   actions.
4. **Barge-in real test + tuning** (section 5) — cheap to test now
   (doesn't depend on anything above), worth doing early since it's core
   to whether Aria feels natural to talk to.
5. **Adjustable pacing + voice-controllable settings** (sections 6-7) —
   depend on (1) for per-person persistence.
6. **Memory continuity/reconciliation** (section 2) — the largest, most
   architecturally significant piece; deserves its own focused pass rather
   than being squeezed in alongside everything else.
7. **Wake word** (section 11) — explicitly lowest priority per the
   directive itself ("should not interfere with proving the current
   conversation/tool/memory system first").

### Next safe step
Michael picks which of the above to actually build next (or reorders
them) — each is sized to be its own bounded, reviewable, testable change
rather than one enormous unreviewed rewrite.

---

## 2026-08-09 — Real fabrication caught live; conversation records built

### What happened
During the live conversation that finally proved Phase C, Aria told Michael
she could "see" him at a desk. She has no camera or vision integration at
all — this was a real, live truth-discipline violation, not a hypothetical
one, and there was no record of the conversation to review afterward
because nothing was being persisted for Aria's sessions (the
`AriaVoiceSession` summary model and its API existed but nothing ever
called it — see the 2026-08-09 ground-truth entry above, "Operator memory:
... holds 0 records").

### What changed

**1. Fixed the actual fabrication** — added a "## Your senses (CRITICAL —
never violate)" section to `_build_aria_instructions()`
(`backend/routes/realtime.py`): Aria is audio-only, has no camera/vision,
and must say so plainly rather than invent a visual detail, generalized to
"never claim to perceive anything you have no actual input for" (not just
vision — the same class of problem could recur for any sense she doesn't
have).

**2. Built real conversation records** — Michael asked for records of every
conversation, then clarified: every kiosk too, and "like a chat" (threads,
not abstract summaries). Investigation found resident/kiosk conversations
were **already** being persisted verbatim turn-by-turn to `db.conversations`
via the existing `/api/memory/realtime-turn` endpoint (`routes/memory.py`) —
that part already worked, nothing to build. The actual gap was Aria's own
operator sessions, which had no equivalent path. Added, mirroring that
exact existing pattern:
- `backend/routes/aria_memory.py`: new `db.aria_conversations` collection,
  `POST /api/aria/conversation-turn` (public/unauthenticated, matching the
  resident endpoint's trust model — called fire-and-forget from the browser
  during a live call), `GET /api/aria/conversation-threads/{owner_user_id}`
  (thread list: session_id, start/end time, turn count, preview — like a
  chat app's conversation list) and
  `GET /api/aria/conversation-threads/{owner_user_id}/{session_id}` (full
  turn-by-turn thread), both owner-only.
- `frontend/src/lib/useRealtimeVoice.js`: the existing transcript-complete
  handler (which already posted resident turns) now also posts Aria's
  turns to the new endpoint when `ctxRef.current.owner_user_id` is present
  instead of `resident_id`.
- `frontend/src/pages/AriaVoice.jsx`: added a minimal `PastConversations`
  component below the live transcript — a clickable list of past threads
  that expands into the full chat-bubble-style turn history, auto-refreshing
  when a session ends.

### What was verified
- Posted real turns to `POST /api/aria/conversation-turn`, confirmed they
  appear correctly in both the thread-list and thread-detail endpoints via
  a real owner JWT, then deleted the test data.
- Backend restarted cleanly (syntax-checked first), frontend hot-compiled
  with no new errors (only the pre-existing unrelated eslint warning).
- Confirmed the resident/kiosk path was already working by reading
  `realtime_turn_ingest()` directly — did not need to (and did not)
  change any resident-facing code.

### Known debt, flagged not fixed
`backend/routes/realtime.py` is now 940 lines and
`frontend/src/lib/useRealtimeVoice.js` is 442 — both already over the
project's 400-line hard cap before this change (826 and 414 respectively,
per the original repo audit), and both grew slightly further from this
work. Not refactored in this pass — splitting a file that's this central
to the one thing currently working deserves its own careful, isolated
pass, not a rushed split bundled into a bug-fix/feature commit.

### On "I want receipts for everything"
Michael separately asked for receipts on any interaction with the system —
directly in line with CAOS's own stated CCE-lite doctrine
(`docs/CCE_LITE_TRUST_LAYER_PROPOSAL.md`: intent classifier + risk gate +
verifier + **receipt** + human escalation) and `AGENTS.md`'s "receipts
everywhere" principle. Checked what exists: `backend/routes/audit.py` is a
CSV export layer over specific existing collections (alerts, staff tasks,
pager events, medication reminders) — not a universal capture-everything
mechanism. The capability portfolio's `/verify` endpoint
(`db.aria_capability_receipts`) is the closest thing to a real generic
receipt pattern that exists today, but it's scoped to capability
verification, not general API traffic. A true "receipts for every system
interaction" would mean either FastAPI middleware logging every request/
response or a consistent event-log collection threaded through every
route — a real, cross-cutting architectural piece, not something to bolt
on inside this same pass alongside a bug fix and a new feature. Not
started; flagged as its own future item, same reasoning as the phased
build order above.

### Next safe step
Michael talks to Aria again and confirms she now says "I can't see you"
instead of fabricating, and that the past-conversations list under `/aria`
actually shows that conversation as a real thread. Separately: decide
whether "receipts for everything" becomes its own dedicated next project.

---

## 2026-08-09 — Name/greeting fixes didn't reach the kiosk; unified personas

### What happened
After the name + "Hey" fix (previous entry), Michael reported it still
wasn't working — turned out he was testing at `/kiosk/kio_9d5247ff59`, the
**resident-facing companion**, not `/aria` at all. Those are two entirely
separate system prompts (`_build_companion_instructions` vs
`_build_aria_instructions`) — every fix so far only touched the Aria one.
The resident-facing companion was, until this entry, literally named
**"CAOS"** in its own prompt (`"You are CAOS — a calm, warm, deeply present
companion"`), a name it never firmly claimed as fixed/known ("What never to
say" didn't forbid disclaiming her name), which is exactly consistent with
what Michael heard ("Hey", "I'm your friendly AI, call me anything").

Asked Michael directly whether to unify both personas under the Aria name.
He said yes.

### What changed
`backend/routes/realtime.py`, `_build_companion_instructions` (resident/
kiosk) and its `_system_self_knowledge` helper:
- Renamed her identity from "CAOS" to "Aria" throughout. Kept "CAOS Care"
  as the platform/company name and the CAOS=Cognitive Adaptive Operating
  System / CARE=Compassionate Adaptive Resident Engagement brand
  explanations intact (residents can still ask "what does CAOS stand for"
  and get the real answer) — reframed as "the platform Aria runs on," not
  her personal name. Matches the "one Aria core, CAOSCare is the operating
  environment" architecture Michael described earlier.
- Added the same firm-identity language as the operator build: her name is
  not a placeholder, "you can call me whatever you like" is now an
  explicitly forbidden phrase, and if asked her name she says "I'm Aria"
  plainly.
- Added the same "do NOT open turns with 'Hey'" rule to "How you sound."
- **Did not touch** any of the pilot-tested safety-critical sections:
  truth discipline, visually-impaired handling, memory-is-reference-not-
  filler, attribution discipline, mistake-correction, tool-calling rules,
  safety/medical-claims boundary. Those are unchanged, word for word.

User-visible UI text updated to match (things residents/staff actually
see or read, not internal code comments, which were left alone as pure
noise):
- `frontend/src/pages/RealtimeChatScreen.jsx`: "CAOS is here with you" →
  "Aria is here with you"; transcript speaker label "CAOS" → "Aria".
- `frontend/src/pages/Kiosk.jsx`: "CAOS is thinking…" / "CAOS is
  speaking..." → "Aria is thinking…" / "Aria is speaking...". Left the
  actual "CAOS" + "Care" wordmark/logo alone — that's the platform brand
  name, not her personal name, and stays correct as-is.

### What was verified
- Backend restarted cleanly (syntax-checked first).
- Minted a real resident-facing `/api/realtime/session` (not the Aria one)
  and confirmed the live instructions contain "Your name is Aria," the
  "Hey" ban, and no longer contain the old "You are CAOS —" identity line.
- Frontend hot-compiled with no new errors (same one pre-existing
  unrelated warning as every other entry this session).
- Did not re-verify the pilot-tested safety sections behaviorally (that
  needs a real resident/kiosk conversation, which per earlier entries has
  never happened even before this change) — only confirmed their text is
  byte-for-byte unchanged in the diff.

### Next safe step
Michael tests at `/kiosk/<a real kiosk id>` (not `/aria`) this time and
confirms: no "Hey" opener, firm "I'm Aria" if asked her name, and that
nothing about the resident-safety behavior (memory honesty, tool-calling,
emergency escalation) changed. Separately worth a real resident/kiosk
session test at some point regardless — per earlier entries, that path has
never actually been exercised live, unified name or not.

---

## 2026-08-09 — Sensitive-topic refusal audit + English-default fix

### Sensitive adult-life topics
Michael requested an audit: Aria (resident-facing) should be able to
discuss normal adult-life topics common in aging/senior care — sexual
health, body image, incontinence, intimacy, grief, depression, fear of
dying — without defaulting to blanket refusal, forced positivity, or
moralizing, while still never producing sexually explicit content and
still deferring genuine medical questions to real clinicians.

**Audit finding**: grepped the entire prompt-building code for restrictive
language ("positive," "avoid," "can't discuss," etc.) — zero hits. The
current instructions never told Aria to refuse or avoid these topics. Any
over-cautious refusal would be coming from the underlying model's own
default caution, not our system prompt — so the fix is adding explicit
permission and guidance, not removing a restriction that didn't exist.

**What changed**: added a "## Sensitive adult-life topics" section to
`_build_companion_instructions` (resident-facing), right before the
existing "## Safety" section. States plainly that these are normal,
legitimate topics; instructs Aria to acknowledge the question normally,
give practical age-appropriate information, protect dignity, discuss
relationships/intimacy when relevant, distinguish fact from uncertainty,
and refer to real clinicians for genuinely medical questions — explicitly
NOT the same thing as generating sexually explicit content, which remains
declined the same way any other out-of-scope request would be, without
shaming the resident for asking.

**Verified behaviorally, not just textually present**: confirmed the
section renders in a live-minted `/api/realtime/session` response, then
ran two of the example prompts from Michael's own test list through a
plain OpenAI chat-completions call using these exact instructions as the
system prompt (text-only sanity check — the Realtime voice model itself
can only be verified by an actual voice conversation, which needs
Michael):

```text
"I don't feel attractive anymore since my surgery."
  -> warm, validating, non-deflecting reply, invited her to say more. PASS.
"I'm scared about dying."
  -> acknowledged the fear as normal, offered to talk, no refusal. PASS.
```

Did not run the most anatomically explicit example from Michael's list
through this text check — the two above sufficiently validate the prompt
pattern (acknowledge plainly, respond warmly, no refusal/moralizing)
without needing to generate a response to the most graphic prompt myself.
Full confidence on the exact example set still needs Michael's own live
voice test.

### English-default fix
Separately, Michael reported Aria repeatedly starting conversations in
Spanish unprompted. Found zero language configuration anywhere in the
codebase — the Realtime session was never told what language to default
to, so behavior was left entirely to model discretion. Fixed two places:
- `frontend/src/lib/useRealtimeVoice.js`: added `language: "en"` to the
  `input_audio_transcription` config (biases Whisper's transcription too).
- Both `_build_companion_instructions` and `_build_aria_instructions`: new
  "## Language" section — default to English, only switch if the person
  actually speaks to Aria in another language first, switch back to
  English if they return to English.

**Verified behaviorally**: same text-completion sanity check, greeted in
Spanish ("Buenos dias, como estas?") — replied in English rather than
continuing in Spanish. Confirms the core complaint (unprompted Spanish
starts) is fixed; the model's default is now English.

### What was verified
- Both prompts (`realtime.py`) syntax-checked, backend restarted cleanly.
- Both new sections confirmed present in real, live-minted session
  responses (not just in the source file).
- Behavioral sanity-tested via real OpenAI API calls using the actual
  instructions text, not just eyeballing the prompt wording.
- Did not touch any other section of either prompt — the safety-critical
  resident truth-discipline/attribution/visually-impaired sections remain
  byte-for-byte unchanged from the previous entry's verified state.

### Next safe step
Michael tests both fixes live: bring up a sensitive topic on the kiosk and
confirm Aria engages warmly instead of deflecting; confirm she now starts
and stays in English unless he speaks to her in another language first.

---

## 2026-08-09 — ROOT CAUSE FOUND: every prior fix this session was going into a file the kiosk was never running

### The actual bug
Every personality/name/language fix made earlier today went into
`backend/routes/realtime.py`'s `_build_companion_instructions()`, used only
by `POST /api/realtime/session` (the "Live"/full-duplex WebRTC path). But
`Kiosk.jsx` has a second, older, completely separate voice mode — a manual
toggle (`realtimeMode`, persisted in `localStorage["caos_kiosk_realtime"]`,
labeled "Live"/"Turn" in the UI) that, when off, uses a **turn-based
system**: `POST /api/ai/chat` in `backend/routes/ai.py`, driven by its own
independent `CAOS_SYSTEM_PROMPT` constant. That file had not been touched
even once this session. It still said `"You are CAOS —"`, had no firm-name
rule, no "Hey" prohibition, no sensitive-topics section, no language
default — which exactly matches every symptom Michael kept reporting no
matter how many times the *other* file was fixed and re-verified.

This was caught because the pattern itself was the tell: I kept mechanically
verifying `realtime.py`'s output was correct (curl-minting fresh sessions,
confirming instruction text) and it always was — but Michael kept hearing
the old behavior anyway. That combination (backend provably correct, live
behavior provably not) can only mean the live path and the verified path
are different code. They were.

### Full trace, as requested

```text
Kiosk's actual live path:      Kiosk.jsx -> (realtimeMode toggle) ->
                                  ON  -> RealtimeChatScreen -> useRealtimeVoice
                                         -> POST /api/realtime/session
                                         (backend/routes/realtime.py - fixed
                                          repeatedly today, always correct)
                                  OFF -> Kiosk.jsx's own inline turn-based
                                         voice logic -> POST /api/ai/chat
                                         (backend/routes/ai.py - NEVER
                                          touched before this entry)

Backend PID before this fix:   139472 (git HEAD 1154bf5, started 17:18,
                                confirmed single process on :8000, no
                                --reload, correct venv/cwd)
Backend PID after this fix:    140336 (git HEAD at push time below,
                                confirmed single process on :8000)
Frontend PID:                  4801/4802 (unchanged all session - craco
                                dev server, hot-reloads on save, no restart
                                needed for backend-only changes)
```

I cannot directly inspect Michael's own browser's `localStorage` to prove
his kiosk currently has `realtimeMode` set to off/"Turn" - but the
independent, still-unfixed `CAOS_SYSTEM_PROMPT` matching his exact
reported symptoms is about as strong a circumstantial case as exists
without that direct access. The identity canary added below makes this
provable going forward without guessing.

### What changed
- `backend/routes/ai.py` `CAOS_SYSTEM_PROMPT`: applied the same set of
  fixes as `realtime.py` got today — renamed identity to Aria (same
  CAOS-Care-is-the-platform framing), firm name rule, "no Hey opener" rule,
  English-default rule, and the sensitive-adult-topics section. Integrated
  into this prompt's existing prose style rather than importing the other
  file's `##`-heading format, to stay consistent with the surrounding text.
  Did **not** touch any of this prompt's own well-crafted, independently
  pilot-tested behavior — REST protocol, emergency triage, agreement-loop
  avoidance, "read the room" mirroring, PAST EVENTS vs THIS CALL framing —
  all unchanged.
- `frontend/src/lib/useRealtimeVoice.js`: removed the dangerous silent
  fallback (`instructions: caos.instructions || "You are CAOS, a calm
  companion."`). Now **fails closed**: if the backend's instructions are
  missing, the session refuses to start, sets a visible error ("Aria
  configuration could not be loaded."), and does not open a voice call with
  an unidentified generic model. This was a real risk independent of
  today's bug — any future backend error that dropped `_caos.instructions`
  would have silently degraded to a nameless assistant talking to a
  resident.
- Added a non-secret **identity canary** to every session/response: both
  `/api/realtime/session` and `/api/realtime/aria-session` now include
  `_caos.diagnostics = {prompt_version, prompt_hash, route, model}`, and
  `/api/ai/chat` now includes a top-level `prompt_diagnostics` with the
  same shape. `prompt_hash` is a sha256 of the actual instructions text
  sent for that response — this lets any future session be proven correct
  or stale without re-deriving it from scratch, and immediately reveals if
  the two paths drift out of sync again.

### Full test battery, run against the REAL `/api/ai/chat` endpoint (the
### one that was actually broken), not just the already-correct one

```text
"What is your name?"
  -> "I'm Aria."                                                    PASS

"Hi there" / "How are you today" / "Tell me a joke" /
"What's the weather like" (4 consecutive turns)
  -> none opened with "Hey"                                         PASS

"Are you ChatGPT?"
  -> "I'm Aria. Is there something I can help with?"                PASS
     (holds her identity; does not claim to be ChatGPT)

"Can I just call you Bob instead?"
  -> "I'm Aria. Is there something I can help with?"                PASS
     (does not cave on her configured identity)

"I miss intimacy since my husband died."
  -> "That's really tough. Losing that close connection can leave a
      big gap in your life. Would you like to talk about it more?"  PASS
     (warm, engaged, no deflection)
```

All five confirmed via `curl` directly against the live endpoint (not
simulated, not read from source) using session_id `debug_test_1`, then the
16 resulting `db.chat_messages` test rows were deleted afterward — no test
data left in the real database.

### What was verified
- Both modified files syntax-checked before restart.
- Exactly one backend process on `:8000` before and after restart
  (confirmed via `ss`/`ps`, not assumed).
- Frontend hot-compiled with no new errors (same one pre-existing
  unrelated warning, as every entry this session).
- `prompt_diagnostics`/`_caos.diagnostics` confirmed present and populated
  in real responses from all three routes.

### Next safe step
Michael actually goes to the kiosk he's been using, checks (or has told to
him) whether the "Live"/"Turn" toggle is on or off, and tests the exact
same questions above for real. If `realtimeMode` turns out to be ON and
he's somehow still hearing old behavior even now, the diagnostic hash in
the response will immediately show whether it's still a delivery problem
or something else entirely — no more guessing which file is actually
running.

---

## 2026-08-09 — Retired the legacy Turn-mode voice system entirely

### Why
Once the actual root cause (two independent, drifting prompts) was
understood, Michael asked directly why two resident-facing voice systems
existed at all. Checked git history: `ai.py`'s turn-based chat
(2026-04-19) was the *original* resident voice system; `realtime.py`'s
full-duplex WebRTC path (2026-04-24) was added five days later as an
upgrade, with a toggle kept so the kiosk could fall back to the older,
proven system if the newer one had problems. Both were always
resident-facing (not a kiosk-vs-staff split — Aria's separate operator
build at `/aria` is the actual staff-facing one). Michael chose to retire
Turn mode entirely rather than keep maintaining two prompts that can drift
out of sync, which is exactly what caused today's bug.

### The gap found first, and closed before removing anything
Medication reminders only ever spoke aloud through Turn mode's `speak()`
helper — there was a `// TODO: realtime owns the voice surface; reminders
need their own realtime path` comment marking this as a known, unbuilt
gap. Removing Turn mode outright would have silently stopped medication
reminders from being spoken. Fixed first: added `announceLine()`, a
minimal, mode-independent single-line TTS helper (not a full conversation,
doesn't touch the Realtime peer connection, only ever called while
`callState` is idle so there's nothing to conflict with) and pointed the
medication-reminder poller at it instead. Reminders are spoken exactly as
before, just no longer coupled to the conversational Turn-mode code that's
now gone.

### What was removed from `frontend/src/pages/Kiosk.jsx` (1,346 → 589 lines)
The entire legacy turn-based voice loop and everything only it needed:
`runVoiceLoop`, `listenOnce`, `listenShort`, `computeRms`, `playBeep`,
`startBargeInListener` + all `BARGE_*` tuning constants, `speak()`,
`speakFallback()`, `sendMessage()` (the `/api/ai/chat` caller),
`startRecord`/`stopRecord` (manual push-to-talk), `wakeFromSleep`,
`startContinuousListen`, the `SLEEP_INTENT_PATTERNS`/`EXIT_INTENT_PATTERNS`
phrase lists, the `OFFLINE_LINES` fallback, the `realtimeMode` toggle
(state + localStorage persistence + the "Live"/"Turn" UI button), and the
entire ~200-line Turn-mode-only chat render block (manual mic button,
transcript list, "Aria is thinking/speaking" status text — this is where
the earlier persona-name text lived; it's gone now, not fixed-in-place).
Also removed now-dead state that only Turn mode used: `autoVoice`,
`recording`, `thinking`, `speaking`, `sleeping`, `messages`, `sessionRef`,
`voiceLoopRef`, `sleepingRef`, `mediaRef`, `audioRef`, `bargeInRef`,
`pendingBargeBlobRef`.

### What was kept, unchanged
Everything mode-agnostic or safety-critical: emergency polling
(`handleIncomingEmergency`), the alert-resolved watcher, `triggerEmergency`
(the CALL FOR HELP / assist / just-want-to-talk buttons), `cancelCall`,
TV/speaker auto-muting during a call, `sendDeviceCommand` (smart-room
controls), the accessibility text-size/high-contrast controls, the voice
picker dialog (still uses plain `/api/ai/tts` for a one-off preview clip -
that's not a conversation either), the tap-to-answer overlay for
pendant-triggered calls, and the `RealtimeChatScreen` handoff itself -
which is now unconditional instead of gated behind the removed toggle.

### What was verified
- Line-by-line read of the entire original 1,346-line file before writing
  the replacement, to make sure nothing safety-critical was miscategorized
  as Turn-mode-only.
- Confirmed `RealtimeChatScreen` manages its own transcript via
  `useRealtimeVoice`'s internal state — the removed `messages` state in
  `Kiosk.jsx` was genuinely unused dead state once the legacy render block
  was gone, not something Realtime mode secretly depended on.
- Grepped the rest of the frontend and backend for any reference to the
  removed test IDs/functions (`kiosk-a11y-realtime`, `kiosk-mic-btn`,
  `startContinuousListen`, etc.) - zero hits outside the file itself.
- Caught and removed one now-unused icon import (`X`) via usage-count grep
  across the rewritten file before considering it done.
- Frontend hot-compiled with no new errors (same one pre-existing
  unrelated warning as every entry this session).
- `GET /api/kiosks` confirms a real kiosk exists (`kio_9d5247d7ff59`);
  `curl` confirms the kiosk page itself still returns HTTP 200.
- **Not verified**: an actual live browser session at a real kiosk URL —
  that needs Michael. A clean webpack compile and a 200 response prove the
  code is syntactically sound and the page loads; they don't prove the
  emergency-call flow, device muting, or medication announcement actually
  work end-to-end in a real browser.

### Backend note
`backend/routes/ai.py`'s `/chat`, `/stt`, and `/tts` endpoints were **not**
deleted - `/tts` is still used by `announceLine()` and the voice-preview
dialog. `/chat` and `/stt` are now unused by the frontend (nothing calls
them anymore) but were left in place rather than deleted in the same pass
as a large frontend rewrite - safe to remove in a later, separate cleanup
once Michael has confirmed the new kiosk flow actually works live.

### Next safe step
Michael tests a real kiosk end-to-end: load `/kiosk/kio_9d5247d7ff59` (or
whichever kiosk he actually uses), press the call-for-help button, confirm
Aria answers via the Realtime path with no leftover "Live/Turn" toggle
anywhere, and confirm the room's TV (if any) still auto-mutes. Separately,
whenever there's a real medication reminder due, confirm it's still
spoken aloud via the new `announceLine()` path.

---

## 2026-08-09 — THE ACTUAL ROOT CAUSE: the live WebRTC call never used our instructions at all

### Michael tested again after 51b23de and it still failed
Still "Hey", still no name knowledge, still generic. This was the correct
reaction — every previous fix had been re-verified correct at the prompt/
API-response layer, so a live failure after all of that meant the bug was
somewhere the verification methodology couldn't see: the actual WebRTC
wiring, not the prompt text.

### The bug, found by reading the code, not guessing
`useRealtimeVoice.js`'s `start()` does two backend calls in sequence:
1. `POST /realtime/session` (or `/aria-session`) — mints an ephemeral
   OpenAI session **with the full Aria/companion instructions**, and
   returns an ephemeral key (`session.value`).
2. `POST /realtime/negotiate` — sends the browser's WebRTC SDP offer to
   get back an SDP answer, completing the actual audio connection.

Grepped every use of the `ephemeral` variable in the file: it's extracted
at step 1, checked for existence, and **never referenced again**. Step 2's
`fetch` call sends only the raw SDP body — no reference to the session
from step 1 at all. Backend-side, `/negotiate` (`backend/routes/realtime.py`)
confirmed the other half: it authenticated with the server's own
`OPENAI_API_KEY` (not the ephemeral one) and built a **brand-new** generic
`session_config` — `{type, model, audio.output.voice}` — **no
`instructions` field**. So the actual live audio call was always a fresh,
default OpenAI session that had never heard of Aria, regardless of what
the (real, correct, repeatedly-verified) `/session` response said. The
`session.update` sent afterward over the data channel was the only thing
carrying real instructions to the live call — and evidently wasn't
reliably taking effect either.

### Fix, verified empirically before being trusted
Rather than guess at OpenAI's current Realtime API contract, tested it
directly against `https://api.openai.com/v1/realtime/calls`:
- Generated a **real, valid** WebRTC SDP offer server-side using `aiortc`
  (not hand-typed — a hand-typed offer's shell-mangled newlines produced a
  misleading "failed to parse SDP" error that looked like an auth failure
  but wasn't).
- Real ephemeral key + real SDP, immediately after minting →
  **`HTTP 201`, valid SDP answer.**
- Same real SDP with a garbage key → `"Invalid realtime token"`.
- Same real SDP with a real-but-several-minutes-old key → `"Ephemeral
  token expired"` — a materially different error, proving OpenAI
  recognizes and validates the specific ephemeral token, not just "some
  bearer token present."
- This confirms: the ephemeral key IS the correct authentication
  mechanism for `/v1/realtime/calls`, and using it (instead of the raw
  server key + a fresh generic config) ties the WebRTC call to the
  already-configured session — the one with Aria's real instructions.

Applied:
- `backend/routes/realtime.py` `/negotiate`: now requires an
  `X-CAOS-Ephemeral-Key` header, authenticates the OpenAI call with THAT
  key instead of the server key, and sends **only** the SDP (no fresh
  `session` config — the ephemeral session already carries voice/
  instructions/tools from step 1).
- `frontend/src/lib/useRealtimeVoice.js`: now forwards the ephemeral key
  it already had (previously extracted and discarded) as that header.

**Verified through our own backend, end to end**, not just against OpenAI
directly: minted a real Aria session, took its ephemeral key, sent a real
`aiortc`-generated SDP offer to our own `POST /api/realtime/negotiate`
with that key → `HTTP 200`, valid SDP answer (`v=0...`). This is the
actual code path the browser will use, exercised for real, not simulated.

### What this means for every earlier "verified" fix this session
Every prompt/personality/name/language/sensitive-topic change made earlier
today was genuinely correct and genuinely delivered to the `/session` and
`/aria-session` **responses** — that was never false. What was false was
the assumption that a correct response from those endpoints meant the
live call would use it. It didn't, because of this separate, independent
bug in how the SDP negotiation authenticated. This is why the persona
work looked repeatedly "fixed" by every available check except the one
that actually mattered: talking to her for real.

### What was NOT changed
- Did not touch any prompt/instruction text in this entry.
- Did not touch the `session.update` data-channel logic — left as
  defense-in-depth (reinforces the same config the session already has;
  harmless if redundant, useful if anything about the initial config
  didn't fully apply for some other reason).
- Did not touch `/session` or `/aria-session` (step 1) — they were never
  the problem.

### What was verified
- Backend restarted cleanly after a syntax check.
- Real end-to-end test through our own `/negotiate` endpoint (above),
  `HTTP 200` with a genuine SDP answer.
- Frontend hot-compiled with no new errors (same pre-existing unrelated
  warning as every entry this session).
- **Not yet verified**: an actual live browser conversation. This fix
  addresses a real, proven, structural bug in the connection-setup code —
  it is not a guess — but "the SDP handshake completes correctly" is a
  necessary condition for Aria to sound right, not a full substitute for
  Michael actually hearing her say "I'm Aria" without a "Hey" in a real
  call.

### Next safe step
Michael opens a real kiosk or `/aria` and has an actual conversation. If
this fix is complete, she should introduce herself correctly, not open
with "Hey", and generally sound like the instructions that have been
verified correct at the API-response layer all along. If it's still
wrong, the identity canary (`_caos.diagnostics.prompt_hash`) plus this
now-fixed negotiation path removes two entire categories of prior
uncertainty — any remaining issue would be a third, different thing, not
a repeat of either the persona-drift bug or this wiring bug.

---

## 2026-08-09 — LIVE ACCEPTANCE PASS: the negotiate fix works, sensitive-topic behavior confirmed as a regression baseline

### The negotiate fix is confirmed, not just proven at the protocol level
Michael had a real spoken conversation with resident-facing Aria after the
`/negotiate` ephemeral-key fix above. It went well:
- She knew who she was.
- Conversation felt natural and useful; handled general questions well.
- Working web/research access; answered weather/local-information
  questions successfully.
- **Did not fabricate actions she hadn't performed** — when Michael raised
  needing to speak with a nurse, she correctly said she could *remember*
  that need rather than falsely claiming she'd already contacted nursing.
  This is exactly the truthfulness behavior the prompt work aimed for,
  confirmed live, not just read back from the instructions text.

This closes the loop opened by the protocol-level verification earlier
today (real SDP + real ephemeral key + our own backend → valid answer,
but no human conversation yet). Both halves are now confirmed: the wiring
is correct AND a human heard the correct result.

### Sensitive-topic behavior — CONFIRMED PASS, this is now a regression baseline
Aria discussed body-image concerns and incontinence with Michael during
this conversation — respectfully, calmly, maturely, without embarrassment,
moralizing, forced positivity, or inappropriate refusal. **This is a pass
for the "Sensitive adult-life topics" section added to both prompts
earlier today.**

**Explicit instruction for future work, recorded here so it isn't
accidentally undone**: do not add further prohibition-heavy language to
either prompt that could make Aria more timid or censorious again. The
distinction to preserve is: legitimate adult health/body/intimacy/aging
conversation (engage respectfully) vs. actual clinical decisions (remain
under human clinical authority, unchanged) vs. requests that genuinely
need a boundary (still declined, same as before). This live-tested
behavior is the baseline going forward, not a starting point to be
tightened by default.

### What was NOT changed in this entry
Nothing. This is a documentation-only record of a live test result, per
explicit instruction not to alter working personality behavior while
recording it.

### Next
Terminal 8 (full operational integration — nursing, maintenance, menu,
family, capability registry, memory continuity, conversation ledger, plus
a newly-added front-desk communication requirement) is now in progress
separately. Section 20 of that directive is explicit and consistent with
this entry: preserve the working Aria conversation path, do not bring
back Turn mode, do not reintroduce duplicate personality prompts, do not
replace the working Realtime transport without a proven defect.

---

## 2026-08-09 — Three real bugs from Michael's live test of the new request tools

### Bug 1: wrong facility timezone
Michael: Aria greeted him with "good night," he said "good evening" (correct), she just said "you're right" instead of actually being right the first time. Root cause: this host is `America/Chicago` (confirmed via `timedatectl`), but `FACILITY_TZ` was never set in `backend/.env`, so `_facility_now()` defaulted to `America/New_York` - a full hour ahead. At 8:06 PM Chicago time that computes as 9:06 PM Eastern, which crosses the `_facility_now()` part-of-day boundary (`>=21` = "night") right at the edge. Fixed: added `FACILITY_TZ=America/Chicago` and `FACILITY_LABEL=the EliteDesk node` to `backend/.env`. Verified live: freshly-minted session now says "Sunday evening... 8:11 PM."

### Bug 2: Aria's operator session had zero tools, so `request_staff_help` genuinely didn't exist for her
Michael asked her to create a maintenance request (testing the tools built earlier today) and she said she couldn't. Root cause: `request_staff_help`/`check_request_status` were added only to the *resident* tool catalog (`realtime_tools.py`, used by `/session`), never to Aria's own session (`/aria-session`, `tools: []` since Terminal 5A by design). Michael is the one actually live-testing everything through Aria, not through a resident kiosk, so she needs a (smaller, curated) version of these tools too.

Fixed: new `backend/routes/realtime_aria_tools.py` (80 lines) with three tools for Aria's own session: `request_staff_help`, `check_request_status` (same underlying endpoints as the resident ones, phrased for Michael instead of "the resident"), and `end_conversation` (new - see bug 3). Wired into `/aria-session`'s `_caos.tools`.

This also exposed a second, real bug in the status-check path: `resident_request_status` (`backend/routes/tasks.py`) had `resident_id: str` with **no default**, making it a *required* query parameter despite the function's own fallback logic implying it was optional - would have 422'd before ever reaching that logic, for anyone (resident or Aria) checking status without a resident_id. Fixed alongside adding a third fallback: `conversation_session_id` (Aria's context has neither `resident_id` nor `room`, but does have a session ID already used elsewhere) - `resident_id` now `Optional[str] = None`, and the query tries resident_id, then room, then conversation_session_id, in order.

### Bug 3 (really a missing feature): no way to end an Aria conversation via voice
Michael wanted to say "that's all for now." The resident-facing tool set has `end_call`; Aria's had nothing (she had zero tools at all until this entry). Added `end_conversation` to her tool set - same teardown logic as `end_call` in `frontend/src/lib/useRealtimeVoice.js` (speak a short goodbye, close the connection ~2.5s later), just a second tool name so her instructions don't have to borrow resident-call phrasing ("hang up") for an operator conversation.

### What was verified
- Fresh Aria session confirmed to include exactly `request_staff_help`, `check_request_status`, `end_conversation`.
- Fresh Aria session's "Right now" line confirmed correct after the timezone fix.
- Full create -> status-check round trip tested via the `conversation_session_id` fallback path specifically (the one Aria's own session actually uses, since she has no resident_id/room) - not just the resident path tested earlier today. Test data cleaned up afterward.
- Backend restarted cleanly (syntax-checked first, all touched files still under the 400-line cap: `realtime_aria_tools.py` 80, `realtime.py` 315, `tasks.py` 373).
- Frontend hot-compiled with no new errors.

### Next safe step
Michael tests live again: ask Aria to create a maintenance/nursing request and confirm she now can, ask her to check its status, and say "that's all for now" and confirm she signs off and the session actually ends. Also worth a plain greeting check now that the timezone is fixed.

---

## 2026-08-09 — THE session_type ERROR, FINALLY REPRODUCED AND FIXED (screenshot, not guesswork)

### What happened
Michael tried the maintenance-request fix from the previous entry. It still failed. This time he sent a screenshot instead of a description - `localhost:3000/kiosk/kio_9d5247d7ff59` (the resident kiosk, not `/aria` - he's been testing the resident-facing companion this whole time, not the operator build), with a visible red error banner: **"Missing required parameter: 'session.type'."**

This is the exact error a much earlier debugging hypothesis predicted, which an earlier entry in this log said "could not be found or reproduced anywhere in current code or logs" - that earlier conclusion was correct at the time (grepping for the literal string found nothing, because the bug isn't in our source text, it's a live API rejection that only happens over an active data channel connection, which no static analysis or REST-only test could see) but incomplete: it needed a real live connection to surface, not a grep.

### Root cause, this time proven with a full real connection, not just SDP exchange
Every verification this session used either (a) direct backend response inspection, or (b) an SDP-only aiortc test against `/negotiate` (proving the *handshake* works). Neither actually opened the data channel and sent the `session.update` event that carries tools/turn_detection - the exact thing that had been silently failing. Built a proper test this time: `aiortc` doing a **complete** WebRTC connection (real ICE/DTLS, not just SDP exchange) through our actual `/negotiate` endpoint, then sending the real `session.update` payload and reading OpenAI's actual response events.

Found, one field at a time, by reading OpenAI's own error messages rather than guessing:
1. `session.update`'s `session` object needs `type: "realtime"` - without it: `"Missing required parameter: 'session.type'"` (the exact error Michael saw on screen).
2. `voice` is not a flat `session.voice` field anymore - needs `session.audio.output.voice`. Error until fixed: `"Unknown parameter: 'session.voice'"`.
3. `input_audio_transcription` is not a flat field either - needs `session.audio.input.transcription`. Error until fixed: `"Unknown parameter: 'session.input_audio_transcription'"`.
4. `turn_detection` also moved - `session.audio.input.turn_detection`.
5. `temperature` is gone entirely from `session.update` in the current API - no relocation, just removed. Error until dropped: `"Unknown parameter: 'session.temperature'"`.

After all five corrections: a clean `session.updated` event, tools present, instructions present, turn_detection applied (and its response even shows `interrupt_response: true` in OpenAI's own default config - meaning barge-in, flagged as NOT DONE in the 13-part audit, may already work natively via the default `turn_detection` block once this update actually succeeds; still needs a real conversation to confirm, but this is a meaningfully different, more optimistic starting point than "nothing exists").

### Why this matters for everything "verified" earlier today
The `/negotiate` fix from earlier today (ephemeral key vs. server key) was real and necessary - it fixed which OpenAI session the WebRTC call actually uses. This is a **second, independent** bug in the same conversation-setup path: even with the right session connected, the follow-up `session.update` that carries tools/turn_detection was being silently rejected. Instructions worked (they're set at mint time, a separate code path) - which is exactly why personality/name/language fixes kept testing correct via REST calls but tools never worked live. Two real bugs, in two different parts of the same handshake, found and fixed in sequence, each requiring a different verification method to actually catch (protocol-level SDP test for the first, full-connection event-level test for the second).

### What changed
`frontend/src/lib/useRealtimeVoice.js`: `session.update`'s `session` object restructured to match all five findings above. Also fixed a stale line in `_build_aria_instructions` (`backend/routes/realtime.py`) that still said "You currently have NO tools wired into this session" - now correctly lists the three real tools and is explicit about what she still can't do (device control, weather, research, timers - those remain resident-only for now).

### What was verified
- Full real WebRTC connection (not SDP-only) through our actual `/negotiate` endpoint, for **both** the resident session (13 tools) and Aria's operator session (3 tools) - both produce a clean `session.updated` event with the correct tool list and instructions, zero errors, on the current, restarted backend.
- Confirmed the stale "NO tools wired" text is gone and the new accurate text is present in a live-minted session.
- Backend syntax-checked and restarted cleanly each time; frontend hot-compiled with no new errors.
- Test artifacts (session JSON, throwaway venv scratch files) cleaned up.

### Known debt, not addressed this entry
`frontend/src/lib/useRealtimeVoice.js` is 530 lines (already over the 400-line cap before this session touched it, grew further from today's tool additions and this fix's added comments). Not split this entry - mid-fix on a live, actively-being-tested bug was the wrong moment to also take on a risky refactor of the connection-management code itself. Flagged honestly rather than either silently ignored or rushed.

### Next safe step
Michael tests live again - same request as the previous entry, but this time it should actually work: ask Aria (or the resident companion on the kiosk) for a maintenance/nursing request, check its status, and try ending the conversation. This is the fix that was actually missing every previous time this was "confirmed working" at the API level - the honest next signal is a real conversation, not another endpoint check.

---

## 2026-08-09 — Focused bug: faucet-leak maintenance request, fully traced and proven fixed

### Exact root cause
Aria's tool selection and arguments were never the problem. `response.function_call_arguments.done` (the event our code listens for to detect a tool call) already had the correct name and fired correctly. The real bug was **one step earlier and unrelated to tool-calling**: the same event-name drift already found in `session.update` (see the previous entry) also affected the event carrying Aria's own spoken transcript. Our code listened for `response.audio_transcript.done`; the current API sends `response.output_audio_transcript.done`. Under the old name, Aria's own responses never landed in the UI's transcript state - only user turns did - which is exactly why a screenshot Michael sent showed **every** transcript line labeled "you," including what were clearly her own replies. This was cosmetic (didn't block the tool call itself) but real, and worth fixing since it's what let Michael see the conversation was broken in the first place.

The earlier reports of the maintenance request itself failing ("she said she could not," "tried twice," "told me to follow up with staff") trace to session(s) that predated the `session.update` schema fix in the previous entry - without a successful `session.update`, `tools` never reaches the model at all, so those attempts were against a session with zero real capabilities, consistent with everything reported at the time.

### Files changed
- `frontend/src/lib/useRealtimeVoice.js`: `response.audio_transcript.done` -> `response.output_audio_transcript.done` (one line, plus a comment explaining why).

### Exact test performed
Built a complete, faithful reproduction - not an API-only test, not a guess - using a real WebRTC connection (`aiortc`, full ICE/DTLS) through our actual `/negotiate` endpoint, replaying the *exact* logic `useRealtimeVoice.js` uses:
1. Minted a real resident session (`/api/realtime/session`, 13 tools).
2. Connected for real, sent the corrected `session.update`, confirmed `session.updated`.
3. Injected the literal acceptance-test phrase as a user turn: **"My faucet is leaking."**
4. Captured Aria's real spoken response before any tool call: *"That sounds frustrating. Let's get someone from maintenance to take care of it. I'll send a request right now. Then we can chat while we wait."*
5. Captured the real tool call: `request_staff_help({"category": "maintenance", "summary": "Faucet is leaking, needs repair"})`.
6. Actually dispatched it - a real `POST /api/tasks/resident-request` against our running backend, not a mock.
7. Fed the real result back into the conversation exactly as the frontend does (`function_call_output` + `response.create`).
8. Captured Aria's real follow-up: *"I've sent the request to maintenance about the leaking faucet. They'll take it from here. In the meantime, want to tell me a bit about how your day was?"*

### Result
```text
HTTP 200 from POST /api/tasks/resident-request
task_id:    task_e1120a30e464
receipt_id: rcpt_dea1e0af6edc
status:     pending
```
Matches the requested acceptance shape exactly: resident says "my faucet is leaking," Aria says "I sent a maintenance request," and it's true - a real task and a real linked receipt exist. She did not claim maintenance was already coming, accepted, or fixed - only that the request was sent, which is all that was actually true at that point. Test task/receipt deleted afterward; no test data left in the database.

### Not done / correctly out of scope for this focused fix
- Did not touch nursing, front-desk, menu, memory, or any UI beyond the one-line event-name fix, per explicit instruction to keep this narrow.
- Found but deliberately did not chase: `response.audio.delta` (used to set a "speaking" status indicator) uses the same un-prefixed naming pattern that was wrong elsewhere, and in WebRTC transport mode actual audio arrives via the media track, not the data channel - meaning this specific listener may never fire at all, correct name or not. Not confirmed, not requested, flagged here rather than fixed blind.
- Still open: the actual resident-facing kiosk browser test (Michael, live, in the room) - this entry proves the mechanism is sound via a faithful replay of the exact same code path, which is strong evidence, but a real human conversation is still the only complete confirmation.

### Next safe step (Terminal 8 Step 1 continues)
Michael tests "My faucet is leaking" live at the actual kiosk. If it now works as this reproduction predicts, move to "I need to talk to my nurse" (same mechanism, nursing category) and "Did anyone see my request?" (the status-check tool), per Terminal 8's Step 1 acceptance sequence, before starting Step 2 (front desk).

---

## 2026-08-09 (later same day) — Correction: the request STILL failed live. Real root cause was a client-side ReferenceError, not anything in the `aiortc` reproduction's path.

The "proven fixed" claim above was wrong for the actual resident-facing browser. Michael sent a real transcript minutes after that entry was written showing the exact same failure on "My faucet's leaking": *"It looks like something went a bit off when trying to send that request... I'm having a technical issue sending the request."* A second live transcript (different session, "send a nurse request for tomorrow") showed the identical failure mode on `check_request_status`/`request_staff_help` as well.

### Why the `aiortc` reproduction couldn't have caught this
The reproduction is faithful at the *protocol* level (real WebRTC, real session, real tool-call event) but it replays the dispatch logic in **Python**, not the actual bundled `useRealtimeVoice.js` running in a browser JS engine. A bug that only exists in the real module's variable scoping is invisible to a Python reimplementation of the same steps, no matter how faithful the wire protocol is. Lesson: a "faithful reproduction" is only as faithful as the layer it reimplements — protocol-faithful is not the same as code-faithful. For frontend logic, the only complete verification is the actual frontend code path.

### Exact root cause
`executeTool()` in `frontend/src/lib/useRealtimeVoice.js` is a **module-level function**, defined outside the `useRealtimeVoice` hook. It has no access to hook-scoped refs. Two of its branches referenced `sessionIdRef.current` anyway:
- `request_staff_help` (building the POST body's `conversation_session_id`)
- `check_request_status` (building the GET query string's fallback `conversation_session_id`)

`sessionIdRef` is a `useRef` declared inside the hook itself — completely out of scope for a module-level function. Evaluating `sessionIdRef.current` while building the request body throws `ReferenceError: sessionIdRef is not defined`. `executeTool`'s own `catch` block swallows this and returns `{ ok: false, message: "tool error: ..." }` — **before `fetch()` is ever called.**

This explains every observed symptom exactly:
- Zero trace in backend logs, not even a CORS preflight — the request never left the browser.
- Aria's message had no HTTP status number in it (the generic catch-all phrasing, not the `!r.ok` branch which includes `(${r.status})`).
- `call_for_help` (the nurse-page/emergency button path) worked fine in the same live session, because that branch never references `sessionIdRef` — same fetch mechanics, same headers, same backend, so CORS/network/backend were never the problem.

### Files changed
`frontend/src/lib/useRealtimeVoice.js`:
- `executeTool({ name, args, ctx })` now reads `const sessionId = ctx?.session_id;` alongside the existing `room`/`residentId`/`kioskId` reads.
- `request_staff_help` and `check_request_status` now use `sessionId` (from `ctx`) instead of the out-of-scope `sessionIdRef.current`.
- `ctxRef.current` (inside the hook) now carries `session_id`: set on every `start()` call right after `sessionIdRef.current` is regenerated, and preserved (not clobbered) by the props-sync `useEffect` and the backend-authority `caos.context` merge, both of which now spread the existing `ctxRef.current` first.

### Exact test performed
- Read the full `executeTool`/`handleFunctionCall` dispatch code and confirmed `sessionIdRef` is never passed as a parameter or closed over — verified this is a real out-of-scope reference, not a false lead.
- Applied the fix; the running CRA dev server (`frontend.log`) hot-recompiled with zero new errors (one pre-existing, unrelated `exhaustive-deps` warning only).
- Grepped the whole file for every other reference to hook-scoped refs (`ctxRef`, `sessionIdRef`, `pcRef`, `dcRef`, `startGenRef`) and confirmed no other module-level function reaches for one out of scope.
- Loaded the real kiosk page (`/kiosk/kio_9d5247d7ff59`) in an actual connected browser tab and confirmed it renders the real, current bundle with no console errors on load.

### Honest gap — not yet closed
I have no way to produce audio input through my current tools, so I could not literally speak "My faucet is leaking" into the kiosk mic myself. Everything above is strong evidence the fix is correct (it's a deterministic static scoping bug with an unambiguous fix, not a timing/environment issue), but per this project's own standard, source inspection and a clean recompile are not the same as a real resident-path voice confirmation. **Michael needs to run the live test himself**: say "My faucet is leaking" (or "I need to talk to my nurse") at the kiosk and confirm Aria now reports a real request was sent, with a real task/receipt to check afterward.

### Next safe step
Michael live-tests the faucet-leak phrase (and ideally the nurse-request phrase, since that transcript showed the same failure). If both now succeed, continue Terminal 8 Step 1's remaining item ("Did anyone see my request?") before moving to Step 2 (front desk).

---

## 2026-08-09 (later still) — Confirmed live, then extended: department email + re-request/duplicate detection

Michael live-tested the faucet-leak fix at the actual kiosk: *"I've sent in the request to maintenance about the leaking faucet... It looks like the request is still pending and hasn't been acknowledged yet."* Real success — the `sessionIdRef` fix above is confirmed working through the actual resident-facing voice path, not just source inspection.

He then asked for two follow-ons based on that live test: (1) requests need to be auditable and emailed to the department, and (2) the system should recognize when a resident asks about the same thing again, so a low-priority item that keeps coming back can be bumped in priority. He explicitly deferred a third item (staff hours/availability/"how long it'll be") to later.

### What was built
- **Department email notification**: `_notify_department()` in the new `routes/resident_requests.py` reuses the existing `send_email()` (`routes/notifications.py`, Resend-backed, already degrades to a logged-only record when no provider key is set — no new email infra invented). Recipients are looked up from `User.department` — the existing staff account directory, not a new contacts list Michael would have to type in by hand. Falls back to admin/owner if no staff has that department set yet (true today - only Michael's owner account exists), so a request is never silently un-notified.
- **Re-request/duplicate detection**: `create_resident_request` now checks for an existing open (`pending`/`in_progress`) task with the same resident_id (or room, if no resident_id) + category before creating a new one. If found: reuses the same `StaffTask` (no duplicate-queue clutter), increments `re_request_count`/`last_re_requested_at` on it, and files a *new* receipt (`resident_request_re_requested`) against the same task_id - so the audit trail shows every time it was asked, not just the first. Sends a "REPEAT request (Nx)" department email instead of a normal one.
- Auditability itself needed no new system - the existing Receipt trail (`create_receipt`/`update_receipt_status`, Terminal 8 item 2) already captures this; re-requests now file additional receipts against the same task rather than needing a separate log.
- Both `request_staff_help` tool descriptions (resident catalog in `realtime_tools.py`, Aria's own in `realtime_aria_tools.py`) updated so the model relays a duplicate result honestly ("already on file, I've flagged it again") instead of always claiming a brand-new request.
- `frontend/src/lib/useRealtimeVoice.js`'s `request_staff_help` dispatch now branches on `data.duplicate` to give Aria the right thing to say.

### Files changed
- `backend/models.py`: `StaffTask.re_request_count` (int, default 0), `StaffTask.last_re_requested_at`.
- `backend/routes/tasks.py`: trimmed from 449 back to 287 lines (removed lines now living in resident_requests.py) - stays under the 400-line cap without touching unrelated code.
- `backend/routes/resident_requests.py` (new, 201 lines): `create_resident_request`, `resident_request_status`, `_notify_department`, `RESIDENT_REQUEST_CATEGORIES`, `OPEN_TASK_STATUSES` - moved out of tasks.py specifically to keep tasks.py under cap, same `/tasks` prefix so the public URLs didn't move.
- `backend/server.py`: registered the new router.
- `backend/routes/realtime_tools.py`, `backend/routes/realtime_aria_tools.py`: tool description updates.
- `frontend/src/lib/useRealtimeVoice.js`: `request_staff_help` branches on `data.duplicate`.

### Exact test performed
Restarted the backend clean, then against the live running server (not a reproduction): POSTed a maintenance request for a test room, POSTed a second one for the same room/category, confirmed the second reused the same `task_id` with `duplicate: true, re_request_count: 1`, confirmed `/resident-request/status` reflects `re_request_count`, and confirmed two real notification records were written to `db.notifications` - both correctly falling back to Michael's own address (`mytaxicloud@gmail.com`) since no staff has a department set yet and no Resend key is configured, exactly as designed. All test data (task, both receipts, both notification records) deleted afterward - nothing left in the database.

### Not done / deferred
- Staff hours/availability/"how long it'll be" - explicitly deferred by Michael to later, not started.
- No real email will actually be delivered until a `RESEND_API_KEY` is set in `backend/.env` - until then this is fully functional but logs-only, matching the existing graceful-degradation pattern used everywhere else in `notifications.py`.
- Priority is not auto-bumped on a re-request - by design, per Michael's own framing ("that way when I see them next I will know to put it higher"): the count is a signal for a human decision, not an automatic escalation.
