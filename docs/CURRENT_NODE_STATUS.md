# CAOSCare EliteDesk Node — Current Status

Single current-state snapshot for `caoscare1-hp-elitedesk`. This is a point-in-time report, not a changelog — for full history read `docs/PROJECT_STATE.md` (bottom-up), `docs/ELITEDESK_NODE_BUILD.md`, and `docs/ARIA_VOICE_FIRST.md` (the most detailed log — several real bugs were found and fixed there, worth reading in full if picking up this work).

Generated: 2026-08-09, by Claude Code, from a live inspection of the running host.

## Repo / git

```text
Branch:        main
HEAD:          c79be25 — Add Claude Code onboarding skeleton (CLAUDE.md + placeholder canon docs)
Remote:        origin -> https://github.com/caosos/CAOSCARE.COM.git, up to date
Working tree:  1 modified file — backend/requirements.txt (paho-mqtt added, still
               completely unused — no MQTT client code exists anywhere. Left
               uncommitted on purpose until that work actually happens.)
```

## Running services right now

```text
mongod                 active, systemd-enabled                        127.0.0.1:27017
CAOSCare backend        running, uvicorn, setsid/nohup                 127.0.0.1:8000   NOT systemd
CAOSCare frontend       running, craco dev server, setsid/nohup        0.0.0.0:3000     NOT systemd
Home Assistant OS VM    running, libvirt, autostart=yes                192.168.122.137:8123
Mosquitto MQTT broker   running (HA Supervisor add-on)                 192.168.122.137:1883
sshd                    active, systemd-enabled                       0.0.0.0:22 (LAN only)
```

DB snapshot: 1 user (owner, `mytaxicloud@gmail.com`), 7 `aria_capabilities` (seeded 2026-08-02, several fields now stale — see below), 0 `aria_memories`, 0 `aria_conversations` (the new conversation-thread feature exists and works, just hasn't been used in a real conversation yet).

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

- **The negotiate fix (item 8 above) has not been confirmed by an actual human voice conversation.** It's proven correct at the protocol level (real SDP + real ephemeral key + our own backend → valid answer) — that's strong evidence, not a guess — but "the handshake completes" and "Michael hears her say 'I'm Aria' with no stray 'Hey'" are two different claims. **This is the single most important thing to test next.**
- Kiosk emergency-call flow, TV auto-muting, and the new `announceLine()` medication-reminder path: code-reviewed and compile-verified after the Turn-mode removal, not yet exercised in a real browser.
- HA LAN port-forward (`192.168.1.151:8123` → VM) from a second physical device — still not confirmed from any device other than this host.

## BLOCKED

- Google Sign-In still not configured on this host.
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

**Michael has a real voice conversation** — either at `/aria` or a real kiosk — and reports plainly: did she introduce herself correctly, did she avoid opening with "Hey," did the conversation otherwise feel right. That single test now carries more weight than any further code change, because the actual wiring bug behind every earlier failed attempt has been found, fixed, and proven correct up to (but not including) a real human ear.
