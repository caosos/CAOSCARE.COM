# CAOSCare EliteDesk Node — Current Status

Single current-state snapshot for `caoscare1-hp-elitedesk`. This is a point-in-time report, not a changelog — for full history read `docs/PROJECT_STATE.md` (bottom-up), `docs/ELITEDESK_NODE_BUILD.md`, and `docs/ARIA_VOICE_FIRST.md` (the most detailed log — several real bugs were found and fixed there, worth reading in full if picking up this work).

Generated: 2026-08-09, by Claude Code, from a live inspection of the running host. Last reconciled: 2026-08-21 (Terminal 9 checkpoint) — sections below marked accordingly; unmarked sections are still the original 2026-08-09 snapshot and may be stale.

## Repo / git (reconciled 2026-08-21)

```text
Branch:        main
HEAD:          3a4bd7f — Fix transcript-labeling bug; prove faucet-leak maintenance request works end-to-end
Remote:        origin -> https://github.com/caosos/CAOSCARE.COM.git, 2 commits ahead
               (077cf4a doc-only progress handoff, 48a84e0 the Terminal 9 directive) —
               fetched only, not merged.
Working tree:  18 modified + 15 untracked files (Departments/Schedule/Menu/Transportation
               backend+frontend, realtime tool wiring, password dialogs, seed script).
               Full file list and line-count detail: docs/PROJECT_STATE.md, 2026-08-21 entries.
```

## Running services right now (reconfirmed 2026-08-21)

```text
mongod                 active, systemd-enabled                        127.0.0.1:27017
CAOSCare backend        running, uvicorn, setsid/nohup                 127.0.0.1:8000   NOT systemd
CAOSCare frontend       running, craco dev server, setsid/nohup        0.0.0.0:3000     NOT systemd
Home Assistant OS VM    running, libvirt, autostart=yes                192.168.122.137:8123
Mosquitto MQTT broker   running (HA Supervisor add-on)                 192.168.122.137:1883
sshd                    active, systemd-enabled                       0.0.0.0:22 (LAN only)
                        + laptop relay confirmed 2026-08-21: laptop `ssh caoscare`
                        (via ~/.ssh/config Host entry) -> caoscare-1@caoscare1-hp-elitedesk
```

DB snapshot (2026-08-09): 1 user (owner, `mytaxicloud@gmail.com`), 7 `aria_capabilities` (seeded 2026-08-02, several fields now stale — see below), 0 `aria_memories`, 0 `aria_conversations` (the new conversation-thread feature exists and works, just hasn't been used in a real conversation yet).

DB snapshot (reconfirmed 2026-08-21, counts only — no PII/secrets): still 1 user, 7 `aria_capabilities`; new since 08-09: 8 `departments`, 126 `transport_slots` (14 distinct dates, `2026-08-09`→`2026-08-22`, source `internal_schedule`, 4 already booked — this covers today/tomorrow and is adequate for a pharmacy-tomorrow test without re-seeding), `schedule_items` 0, `menu_items` 0, 15 `receipts`, 9 `staff_tasks`, 5 `residents`, 1 `kiosk`, 31 `alerts`, 9 `notifications`.

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

## WORKING BUT NOT FULLY VERIFIED

- ~~The negotiate fix (item 8 above) has not been confirmed by an actual human voice conversation.~~ **Resolved by 2026-08-09→2026-08-21 sessions**: a real voice conversation and a real end-to-end maintenance request (faucet leak) have since been proven working (commit `3a4bd7f`). See `docs/PROJECT_STATE.md` for detail.
- Kiosk emergency-call flow, TV auto-muting, and the new `announceLine()` medication-reminder path: code-reviewed and compile-verified after the Turn-mode removal, not yet exercised in a real browser.
- HA LAN port-forward (`192.168.1.151:8123` → VM) from a second physical device — still not confirmed from any device other than this host.
- **(2026-08-21)** Admin → Departments/Schedule/Transportation/Menu: wired and compiling, but Michael has not yet reviewed any of them live in the browser this session.
- **(2026-08-21)** The full resident voice transportation path ("I need a ride to the pharmacy tomorrow" → tool call → DB record → receipt) has not yet been run as a real microphone test — see Terminal 9 checkpoint in `docs/PROJECT_STATE.md`.

## BLOCKED

- ~~Google Sign-In still not configured on this host.~~ **Resolved 2026-08-21**: GSI owner login for `mytaxicloud@gmail.com` confirmed working in the browser (see 2026-08-21 reconciliation note above and `docs/PROJECT_STATE.md`'s Terminal 9 checkpoint entry).
- Midea/Matter LAN integration still paused (no wired NIC).
- Wake word ("Aria"): not implemented, confirmed lowest priority per Michael's own directive.
- The 8 NOT DONE/PARTIAL items from the 13-part audit (memory continuity, barge-in, adjustable pacing, voice-controlled settings, environment awareness, HA/MQTT tool-wiring, acceptance test suite) — see `FROM_CLAUDE.txt` for the exact breakdown and recommended build order.

## Boot / reliability persistence — still not solved

Backend/frontend are still manual `setsid`/`nohup` processes, not systemd. This has been true and explicitly deferred every entry this session — Terminal 3 Phase 6 has still not been started. If this host reboots, both need to be manually restarted (commands are in `docs/ELITEDESK_NODE_BUILD.md`).

## Note for future agents on this host

1. Michael's clipboard/copy-paste does not work reliably here — never ask him to copy/paste long strings; find another way or have him type short things by hand.
2. **Read `~/CAOSCARE.COM/CLAUDE.md` first now** — it points at `AGENTS.md` and four (currently placeholder) canonical docs. If those docs have real content by the time you're reading this, they supersede ad-hoc assumptions about CAOSCare's architecture.
3. When a prompt fix doesn't seem to take effect no matter how many times it's re-verified correct, check the actual wire-level connection setup before assuming the prompt text is still wrong — that exact mistake cost significant time this session (see item 8 above).

## Single best next action

~~Michael has a real voice conversation...~~ **Done (2026-08-09→2026-08-21)** — superseded below.

**(2026-08-21, current)** Michael reviews Admin → Departments/Schedule/Transportation/Menu live in the browser, then performs the real microphone test ("I need a ride to the pharmacy tomorrow") at the kiosk while the backend/DB are observed in real time — per Terminal 9 Phases 4-5 in `docs/PROJECT_STATE.md`'s latest entry. A known 300-line production-code rule violation was also found this session in `backend/models.py`, `frontend/src/pages/Admin.jsx`, `backend/routes/auth.py`, and `backend/routes/transportation.py` — Michael's direction is needed on how/when to remediate before more work stacks on top.
