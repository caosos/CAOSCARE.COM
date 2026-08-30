# CAOSCare EliteDesk Node — Current Status

Single current-state snapshot for `caoscare1-hp-elitedesk`. This is a point-in-time report, not a changelog — for full history read `docs/PROJECT_STATE.md` (bottom-up, especially every 2026-08-29 entry), `docs/ELITEDESK_NODE_BUILD.md`, and `docs/ARIA_VOICE_FIRST.md`.

Generated: 2026-08-09. Last reconciled: **2026-08-29 (live physical-pendant test night + two incident TSBs)** — sections below marked accordingly; unmarked sections are the original 2026-08-09/2026-08-21 snapshot and may be stale for anything not resident-voice/RF-related.

**If you are a fresh Claude Code or Codex instance on ANY machine, read this file in full before touching resident-voice, RF/pendant, or Realtime-session code.**

## Repo / git (reconciled 2026-08-29)

```text
Branch:        main
HEAD:          9246fc3 — Fix bathroom-request tool misrouting; add mic device observability
Remote:        origin -> https://github.com/caosos/CAOSCARE.COM.git
               main is EXACTLY at origin/main right now — 0 commits ahead, 0 behind.
               (This EliteDesk pushed twice tonight: 6c65021 then 9246fc3. Both are live
               on the remote — a checkout on any other machine gets the full current state.)
Working tree:  clean except this reconciliation pass itself (docs/PROJECT_STATE.md,
               docs/reports/INDEX.md, docs/tsb/INDEX.md, docs/tsb/TSB-002-*.md,
               this file) — documentation only, no runtime code uncommitted.
Separate branch NOT on this machine: `feature/adaptive-conversation-tempo` (PR #23,
               built by a Codex instance elsewhere, draft, NOT merged). It touches the
               same turn_detection/VAD config surface (backend/routes/realtime_audio_
               config.py) this repo's main also touches tonight — real merge-conflict
               risk when it comes back, not yet reconciled. Do not assume it exists on
               this checkout.
```

## Running services right now (reconfirmed 2026-08-29)

```text
mongod                 active, systemd-enabled                        127.0.0.1:27017
CAOSCare backend        running, uvicorn, nohup                        127.0.0.1:8000   NOT systemd
CAOSCare frontend       running, craco dev server, nohup                0.0.0.0:3000    NOT systemd
android-bridge/caos_rf_bridge.py   running, nohup, listening 319.5MHz  NOT systemd
  -> spawns rtl_433 as a child process, real Nooelec NESDR SMArt v5 hardware attached
Home Assistant OS VM    (unconfirmed this session — see 2026-08-21 snapshot below)
sshd                    active, systemd-enabled                       0.0.0.0:22 (LAN only)
```

**OPERATIONALLY URGENT**: the RF bridge is genuinely still running and listening right
now. A real paired pendant (`rfd_07d25dc68a6b`, Room 401/Eleanor) emits a transmission
on an almost-exact **~64-minute cycle** (proven — see TSB-002) that the pipeline
currently cannot distinguish from a genuine HELP button press, and `auto_voice=True`
means every one of those cycles fires a full Resident Aria activation. **This will keep
happening every ~64 minutes until the RF event-semantics fix (TSB-002 remediation item
1) is built, or the bridge is stopped, or `auto_voice` is temporarily reverted.** None
of those mitigations have been applied yet — awaiting Michael's direction.

## DONE 2026-08-29 (this was one continuous live session — physical hardware + live testing, not simulated)

1. Real Nooelec NESDR SMArt v5 + real 319.5MHz Interlogix-Security pendant bring-up against the *existing* `rf.py`/`caos_rf_bridge.py` pipeline (a second, less-developed `pendants.py` scaffold was found and deliberately left alone). Host bring-up (rtl-sdr/rtl_433 install, DVB driver unbind/blacklist) — `rtl_test -t` verified real EEPROM readback.
2. Found and fixed two real bridge-script defects live: fingerprint matching preferred a noisy raw field over the decoder's stable `id` (broke cross-press matching, ~0.83 similarity below threshold) and could produce invalid odd-length hex; frequency recorded as 0 for single-band captures. Added press-count coalescing (~8 RF frames per physical press → 1 alert) and `PUT /rf/devices/{id}/assign` (reassignment, didn't exist).
3. Live multi-Aria-session defect found (auto_voice exposed two concurrent OpenAI Realtime sessions speaking over one mic) and fixed: server-side singleton lease (`backend/routes/realtime_room_lease.py`, `ResidentAriaLease` model) — atomic claim-or-reuse keyed by room, 45s staleness self-heal, wired into `POST /realtime/session`. Confirmed live: "the doubling is fixed."
4. TSB-001 (name-attribution hallucination) extended with two more independently-found root causes: a background memory-extraction pipeline storing an ungrounded name claim from the model's own hallucinated speech (fixed: extractor prompt rule + structural grounding check); `mark_resting` never actually suppressed server auto-response, only dimmed a UI flag (fixed: reuses the same `create_response:false` mechanism already proven for greeting suppression).
5. Real safety-relevant tool-routing bug found and fixed live: a correctly-transcribed "I need to go to the bathroom" led the model to discuss the lunch menu instead of requesting help — `call_for_help`'s description never covered bathroom/toileting, `request_staff_help` never named it either. Fixed both tool descriptions; live-verified on retest (correct tool fired immediately).
6. Mic device observability added — `track.label` + `enumerateDevices()` now captured and shown live on the kiosk ("· Mic: EMEET OfficeCore Luna Plus Mono", confirmed real hardware). Kiosk transcript panel got a copy button (reused existing `CopyTranscriptButton`, no duplication).
7. Both commits pushed: `6c65021` (pendant/lease/mark_resting stabilization), `9246fc3` (bathroom-tool fix + mic observability). See `docs/PROJECT_STATE.md` for full detail on each.
8. **TSB-002 opened** (see `docs/tsb/TSB-002-fabricated-emergency-and-zombie-session.md`) after a real overnight incident: `call_for_help` fired with a completely fabricated "can't breathe" claim from two unrelated fragments, creating a real staff-visible alert; the session then received zero audio for 59 minutes until OpenAI's own 60-minute platform cap ended it. **Root-cause investigation found the triggering RF transmission matches an automated ~64-minute periodic pattern, not the pattern seen during any deliberate press** — the RF pipeline conflates transmitter *identity* with transmission *semantics*. Nothing has been fixed yet — reconstruction only, per Michael's explicit instruction. Detailed remediation proposals are written up in the TSB but NOT implemented.

## PROVEN vs UNPROVEN — read this before assuming anything

**Proven (real, evidenced, not inferred):**
- RF device-identity matching, frame-coalescing, and the session-singleton lease all work correctly under real, unplanned physical triggers.
- The bathroom-request tool-routing fix works (live-verified retest).
- The `update_preferred_name` grounding guard (TSB-001) still correctly blocks ungrounded name-change attempts.
- The ~64-minute periodic RF pattern is real and repeats reliably (9 occurrences, 64.3–64.5 min apart, spanning 8+ hours) — see TSB-002.
- A genuinely different decoded RF pattern correlates with moments deliberate presses were requested tonight.

**NOT proven — do not build on these as if they were facts:**
- That the periodic pattern is specifically a "supervisory/heartbeat" frame in the formal PERS-protocol sense — that's the strongest evidenced hypothesis, not a confirmed fact.
- That the "press-like" pattern is *actually* caused by a physical button press — no isolated, controlled A/B test (deliberate press vs. deliberate non-press, both captured raw) has been run. The correlation so far is inferred from conversation timing.
- Root cause of the 59-minute total-audio-silence VAD dead zone — same open question as the broader dead-zone pattern documented elsewhere in `docs/PROJECT_STATE.md`'s 2026-08-29 entries (39% short-fragment rate, dozens of 10s–283s gaps across nearly every session that night). Not root-caused. Do not touch EliteDesk audio/VAD/AEC config without evidence specifically isolating the cause — it works well here per Michael.
- Anything about the Codex `feature/adaptive-conversation-tempo` branch's actual live behavior beyond Michael's own description ("randomly starts talking without prompting") — not independently verified from this machine.

## What NOT to redo

- Do not re-litigate whether the RF pipeline should use `rf.py`/`caos_rf_bridge.py` vs. `pendants.py` — this was decided and confirmed correct tonight (see `docs/PROJECT_STATE.md`'s first 2026-08-29 entry).
- Do not re-attempt a prompt-only fix for anything already shown to need a *structural* guard (`update_preferred_name`, the memory-extraction check) — prompt-only has already failed once for exactly this class of problem.
- Do not touch EliteDesk audio/VAD/AEC/eMeet configuration based on TSB-002 or the dead-zone pattern — explicitly out of scope per Michael, this machine's audio path is not the suspected defect.
- Do not assume the "press vs. periodic" RF pattern distinction is proven — it needs the controlled A/B test in TSB-002's Verification Required section before any classification logic is built on it.
- Do not merge or build against the Codex branch without first checking it against `main`'s current `backend/routes/realtime_audio_config.py`/`realtime.py`/`useRealtimeVoice.js` for conflicts — flagged, not yet reconciled.

## Machine roles

- **This EliteDesk** (`caoscare1-hp-elitedesk`): primary dev/test node. Runs backend, frontend, MongoDB, the real RF bridge + physical Nooelec SDR + physical Room-401 pendant. Audio (eMeet) confirmed working well here.
- **Michael's laptop**: a separate physical environment where eMeet audio behavior has been reported as worse/inconsistent. Not inspected — no access from this session. Suspected (not proven) cause: CAOSCare currently relies on OS/browser default audio input/output rather than explicitly binding/persisting its intended device.
- **Codex** (elsewhere): built the draft `feature/adaptive-conversation-tempo` PR, not on this machine, not merged.

## Single best next action

Run the controlled A/B RF test proposed in TSB-002 (deliberate presses vs. deliberate non-presses, raw decoded fields captured for each) to actually prove the periodic-vs-press distinction, since the RF bridge is still live right now and will keep firing every ~64 minutes until this is resolved. In parallel, get Michael's direction on which TSB-002 remediation item to build first — the `call_for_help` grounding guard is the most safety-critical and has a direct, already-proven precedent to copy from TSB-001.

---

*Everything below this line is the original 2026-08-09 → 2026-08-21 snapshot, preserved for history. Superseded content is struck through; unmarked content may still be accurate but has not been reconfirmed this session.*

## DONE this session (2026-08-09) — in order

1. **Home Assistant Phase 3/4 closed out**: onboarding completed, Mosquitto installed, HA's own `mqtt` integration wired via config-flow API, dedicated `caoscare-mqtt` HA service account created, raw MQTT pub/sub proven via CLI.
2. **Terminal 7 — local owner auth bypass**: `CAOSCARE_LOCAL_OWNER_BYPASS` env flag (off by default; currently **off** on this host per Michael's own request — he wants real credentials, not the bypass). Fails closed to normal login when disabled. A new owner password was generated and given to Michael directly (not stored anywhere retrievable).
3. **Aria personality tuning**: calmer, less "AI-assistant"-sounding, no stacked enthusiasm — first pass on the operator build only.
4. **Real fabrication caught and fixed**: Aria claimed to "see" Michael at a desk — she has no camera. Added an explicit senses/truth-discipline rule (audio-only, never claim to perceive anything with no sensor for it).
5. **Real conversation records built**: every Aria turn now persists to `db.aria_conversations`; a "Past conversations" chat-thread UI was added to `/aria`. (Resident/kiosk turns were already being recorded via a pre-existing, separate mechanism — not new.)
6. **Sensitive-topic audit**: audited the prompt for language causing over-broad refusals on legitimate adult-life topics (grief, body image, sexual health, fear of dying) — found none, so added explicit permission/guidance instead. Verified behaviorally via real API calls, not just read.
7. **Unprompted-Spanish bug fixed**: no language config existed anywhere; added an English default to both transcription and both prompts.
8. **THE ACTUAL ROOT CAUSE FOUND AND FIXED** (this is the important one — read `docs/ARIA_VOICE_FIRST.md`'s "THE ACTUAL ROOT CAUSE" entry in full): the kiosk's live WebRTC call was **never actually using the instructions from the session-mint step**. `useRealtimeVoice.js` minted a correctly-configured ephemeral OpenAI session, then discarded the key entirely — the real SDP negotiation (`/realtime/negotiate`) authenticated with the server's own raw API key and built a brand-new, generic, instructions-less session from scratch. Every single symptom (generic "Hey" opener, no name knowledge, sounds like the base model) was this one wiring bug, not a persona/prompt problem — which is why repeated, correctly-verified prompt fixes kept appearing to have no effect. **Fixed and empirically proven**: generated a real SDP offer with `aiortc`, tested the ephemeral key directly against OpenAI (real key → success/expected-expiry; garbage key → different, explicit rejection — proving OpenAI actually validates the specific token), then verified the fix end-to-end through our own backend (`HTTP 200`, valid SDP answer). This is proven at the wire-protocol level; a real human conversation still hasn't confirmed it (see WORKING BUT NOT VERIFIED below).
9. **Why there were two resident-facing voice systems, explained and resolved**: Turn mode (`backend/routes/ai.py`, built 2026-04-19) was the original resident voice system; Live/Realtime (`backend/routes/realtime.py`, 2026-04-24) was added 5 days later as an upgrade with a fallback toggle. Neither was "for staff" — both were always resident-facing; Aria's separate `/aria` build is the actual staff-facing one. Michael chose to retire Turn mode now that the drift between the two was understood to be the earlier root cause of persona bugs. **Kiosk.jsx: 1,346 → 589 lines.** Found and closed a real gap first (medication reminders only spoke through Turn mode's code, marked with an explicit unbuilt-TODO for Realtime) before removing anything, so no feature regressed.
10. **Honest 13-part audit delivered**: a large combined "Aria continuity/self-control" directive was audited item-by-item against live evidence (grep, live API calls, direct DB queries) rather than credited from documentation or intent. Result: 0 fully DONE, 5 PARTIAL, 7 NOT DONE, 2 NOT VERIFIABLE. Full detail in `~/Desktop/FROM_CLAUDE.txt`. Nothing from that directive was implemented — audit only, as instructed.
11. **Claude Code onboarding skeleton added**: root `CLAUDE.md` (imports `AGENTS.md` + four placeholder canonical docs — `CAOS_THESIS.md`, `CAOSCARE_BLUEPRINT.md`, `ARIA_CONTRACT.md`, `ENGINEERING_CONTRACT.md`, all explicitly unwritten, not to be invented by an agent) plus a global `~/.claude/CLAUDE.md` with universal engineering principles (outside this repo, not in git).

## WORKING BUT NOT FULLY VERIFIED (2026-08-09/21 snapshot)

- ~~The negotiate fix (item 8 above) has not been confirmed by an actual human voice conversation.~~ **Resolved by 2026-08-09→2026-08-21 sessions**: a real voice conversation and a real end-to-end maintenance request (faucet leak) have since been proven working (commit `3a4bd7f`). See `docs/PROJECT_STATE.md` for detail.
- Kiosk emergency-call flow, TV auto-muting, and the new `announceLine()` medication-reminder path: code-reviewed and compile-verified after the Turn-mode removal, not yet exercised in a real browser.
- HA LAN port-forward (`192.168.1.151:8123` → VM) from a second physical device — still not confirmed from any device other than this host.
- **(2026-08-21)** Admin → Departments/Schedule/Transportation/Menu: wired and compiling, but Michael has not yet reviewed any of them live in the browser this session.
- **(2026-08-21)** The full resident voice transportation path ("I need a ride to the pharmacy tomorrow" → tool call → DB record → receipt) has not yet been run as a real microphone test — see Terminal 9 checkpoint in `docs/PROJECT_STATE.md`.

## BLOCKED (2026-08-09/21 snapshot)

- ~~Google Sign-In still not configured on this host.~~ **Resolved 2026-08-21**: GSI owner login for `mytaxicloud@gmail.com` confirmed working in the browser (see 2026-08-21 reconciliation note above and `docs/PROJECT_STATE.md`'s Terminal 9 checkpoint entry).
- Midea/Matter LAN integration still paused (no wired NIC).
- Wake word ("Aria"): not implemented, confirmed lowest priority per Michael's own directive.
- The 8 NOT DONE/PARTIAL items from the 13-part audit (memory continuity, barge-in, adjustable pacing, voice-controlled settings, environment awareness, HA/MQTT tool-wiring, acceptance test suite) — see `FROM_CLAUDE.txt` for the exact breakdown and recommended build order.

## Boot / reliability persistence — still not solved

Backend/frontend/RF bridge are still manual `nohup` processes, not systemd. This has been true and explicitly deferred every entry so far. If this host reboots, all three need to be manually restarted.

## Note for future agents on this host

1. Michael's clipboard/copy-paste does not work reliably here — never ask him to copy/paste long strings; find another way or have him type short things by hand.
2. **Read `~/CAOSCARE.COM/CLAUDE.md` first now** — it points at `AGENTS.md` and this file. If `AGENTS.md`'s referenced canonical docs (CAOS_THESIS.md etc.) have real content by the time you're reading this, they supersede ad-hoc assumptions about CAOSCare's architecture.
3. When a prompt fix doesn't seem to take effect no matter how many times it's re-verified correct, check the actual wire-level connection setup before assuming the prompt text is still wrong.
4. **(2026-08-29)** Use evidence, not description, for every resident-voice/RF finding — this session repeatedly found that a user's honest description of what happened ("it randomly started talking," "he bumped the pendant") did not match what the persisted DB evidence actually showed. Always reconstruct from `db.conversations`/`db.realtime_diagnostics`/`db.alerts`/`db.rf_events` before concluding anything.
