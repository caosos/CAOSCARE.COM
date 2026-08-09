# CAOSCare EliteDesk Node — Current Status

Single current-state snapshot for `caoscare1-hp-elitedesk`. This is a point-in-time report, not a changelog — for full history read `docs/PROJECT_STATE.md` (bottom-up), `docs/ELITEDESK_NODE_BUILD.md`, and `docs/ARIA_VOICE_FIRST.md`. Regenerate/update this file rather than trying to keep it perfectly current by hand every session.

Generated: 2026-08-09, by Claude Code, from a live inspection of the running host (not from memory or docs alone).

## Repo / git

```text
Branch:        main
HEAD:          a0acfa7 — Record EliteDesk Phase 3 HA onboarding closeout and Phase 4 Mosquitto/MQTT setup
Remote:        origin -> https://github.com/caosos/CAOSCARE.COM.git, up to date with origin/main
Working tree:  1 modified file — backend/requirements.txt (paho-mqtt added, not yet used by any
               committed code; part of in-progress Phase 5 MQTT contract work, uncommitted by design
               until the module that uses it is finished)
```

## Running services right now

```text
mongod                 active, systemd-enabled (survives reboot)      127.0.0.1:27017
CAOSCare backend        running, uvicorn, PID-based setsid/nohup       127.0.0.1:8000   NOT systemd
CAOSCare frontend       running, craco dev server, setsid/nohup        0.0.0.0:3000     NOT systemd
Home Assistant OS VM    running, libvirt, autostart=yes                192.168.122.137:8123
Mosquitto MQTT broker   running (HA Supervisor add-on)                 192.168.122.137:1883
sshd                    active, systemd-enabled                       0.0.0.0:22 (LAN only)
libvirtd                active, systemd-enabled
```

LAN-facing address for this host: `192.168.1.151` (Wi-Fi only — `eno1` wired port has no cable connected). Home Assistant is also reachable from other LAN devices at `192.168.1.151:8123` via an iptables port-forward (not self-testable from this host due to hairpin NAT — see Known blockers).

## DONE (verified working, right now)

- **CAOSCare core app**: backend health `{"ok":true,"db":"up"}`, frontend HTTP 200, MongoDB active. One owner account exists: `mytaxicloud@gmail.com`, `role=owner`, `auth_provider=jwt`. Password login works end-to-end.
- **Home Assistant OS VM**: installed, onboarded (Michael completed the wizard), persistent + autostart in libvirt, reachable and responding.
- **Mosquitto MQTT broker**: installed as an HA add-on, running, port 1883 open. HA Core's own `mqtt` integration is configured and `loaded` (confirmed via `/api/config` components list).
- **Dedicated MQTT service account**: a non-owner HA user `caoscare-mqtt` was created via the HA WebSocket admin API specifically for CAOSCare's future backend MQTT client (not reusing Michael's owner login). Credentials stored outside git at `~/.config/caoscare/mqtt_service_password` (0600).
- **Raw MQTT round-trip**: proven via `mosquitto_pub`/`mosquitto_sub` with the `caoscare-mqtt` account — publish and subscribe both work against the broker. (Not yet wired into CAOSCare backend code — see NEXT.)
- **HA Long-Lived Access Token**: minted, verified against the HA REST API, stored outside git at `~/.config/caoscare/ha_long_lived_token` (0600). Usable for further HA API automation without more browser steps.
- **Aria capability registry**: `AriaCapability` model + `/api/capabilities` API (owner-only), 7 initial entries seeded, receipt-backed verify endpoint proven working.
- **Aria operator memory scope**: `AriaMemory`/`AriaVoiceSession` models + `/api/aria/memory` API, structurally separate from resident memory. Currently empty (0 memories, 0 voice sessions — nobody has talked to Aria yet).
- **OpenAI Realtime voice pipeline**: `OPENAI_API_KEY` is configured in `backend/.env`. `POST /api/realtime/aria-session` mints real ephemeral sessions with Aria's own persona, live capability-portfolio summary, and memory context injected.
- **A real pre-existing bug fixed**: `frontend/src/lib/useRealtimeVoice.js` was reading the ephemeral key from the wrong field — would have silently broken *every* Realtime voice session (resident-facing and Aria) at the first step. Already committed and pushed.
- **Login redirect fix**: logged-out visitors to owner/admin-only routes now correctly land on `/admin-login` and return to the page they wanted after signing in.
- **eMeet Luna Plus USB mic/speaker**: mechanically verified — `arecord`/`speaker-test` both produced valid audio through it, and it's the OS default input/output device.
- **SSH access**: installed and enabled on this host for LAN-only remote access (`192.168.1.151:22`, this machine's normal login).

## WORKING BUT NOT FULLY VERIFIED

- **Aria voice, end-to-end**: session minting is proven; the actual browser/WebRTC/microphone conversation has **never been tested**. This is the single most-repeated "next step" across the last two build sessions.
- **eMeet audio quality**: capture/playback work mechanically, but nobody has confirmed it's audible/clear from normal room distance.
- **HA LAN port-forward** (`192.168.1.151:8123` → VM): structurally correct (iptables rules verified) but only tested from the VM/host itself, which hits an expected hairpin-NAT limitation. Genuine confirmation from a second LAN device (e.g. a phone) is still pending.
- **Resident-facing realtime voice** (`RealtimeChatScreen.jsx`/Kiosk): shares the same bugfix as Aria's path but has apparently never been exercised live either, per its own build notes.

## BLOCKED

- **Google Sign-In**: not configured on this host (`GOOGLE_CLIENT_ID` unset in both `backend/.env` and `frontend/.env`). Michael has an existing Client ID from a prior session but hadn't provided it as of the last handoff.
- **Midea/Matter LAN integration (Terminal 4)**: deliberately paused. The HA VM only has a private NAT address (`192.168.122.137`); giving it a real LAN presence needs either a physical Ethernet cable into `eno1` (currently unplugged) or a router-level change — both need Michael, and voice-first (Terminal 5) has explicit priority over this.
- **Wake word ("Aria")**: not implemented at all — no Wyoming/openWakeWord/Piper/Whisper stack installed anywhere. This is Phase D of the voice-first build, not started.
- **Tool routing** from Aria to the capability registry: `get_capability_summary()` exists but isn't wired into `routes/realtime.py` yet — deliberately deferred until the voice round-trip itself is proven.

## Boot / reliability persistence — none of this survives a reboot yet

```text
mongod, libvirtd, sshd     — systemd-managed, DO survive reboot
HAOS VM                    — libvirt autostart=yes, DOES survive reboot (once libvirtd is up)
CAOSCare backend/frontend  — manual setsid/nohup processes, do NOT survive reboot (confirmed:
                              already died and were manually restarted once this build cycle)
iptables 8123 port-forward — runtime-only, no iptables-persistent installed, does NOT survive reboot
```

This is a known, deliberately-deferred gap (Terminal 3 Phase 6 — "reliability and boot behavior" — has not been started), not an oversight. The plan is to convert backend/frontend to systemd units and persist the firewall rules together, then prove it with one real controlled reboot, rather than fixing pieces separately and re-testing each time.

## Note for future agents on this host

Michael's clipboard/copy-paste does not work reliably in this environment (repeatedly confirmed across sessions). Do not ask him to copy/paste tokens, keys, or long strings. If a credential is needed, either: have him type it by hand into a local text file you then read from disk, or find a path that avoids needing one at all (as was done for the Long-Lived Access Token and the MQTT service account).

## Single best next action

**Michael opens `http://localhost:3000/aria` in a browser on this machine, logs in as owner, and actually talks to Aria** (mic + speaker via the eMeet Luna Plus). Every other capability (memory, tool routing, wake word, MQTT-to-HA control) is gated behind first proving this one real conversation works. Second priority, independent of that: confirm the HA LAN port-forward from a phone or other LAN device.
