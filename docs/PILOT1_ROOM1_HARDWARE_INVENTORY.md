# Pilot Room 1 — Hardware Inventory and Compatibility Matrix

**Ready-queue item:** RQ-004 · **Branch:** `agent/pilot-room1-hardware-inventory` (from `origin/integration/2026-09-27` @ `9488066`)
**Compiled:** 2026-10-02/03 by Claude Code (Opus 5.5), Agent 2 · **Status:** inventory only — nothing purchased, configured or changed

## How to read this

- **Pilot Room 1 has not been selected** (`PILOT1_EXECUTION_CHECKLIST.md` Phase 8, "Select room" open). All proven hardware below is the **development test room** on the development EliteDesk, on the development local network — not a community room.
- Evidence levels used in the matrix:
  - **OS-verified** — seen by this agent on 2026-10-02/03 from the EliteDesk (DMI, `lsusb`, ALSA/PulseAudio, `ip`, `virsh`, process list).
  - **HA-verified** — present in the Home Assistant VM's live state (read-only `GET /api/states`) on 2026-10-03.
  - **DB-recorded** — a CAOSCare record (`smart_devices`, `rf_devices`) or a repo document states it; not physically re-checked.
  - **Reported** — Michael said he owns it; no model, protocol or record anywhere in the repo, DB or HA.
  - **Not owned / not recorded** — no evidence it exists.
- A USB ID or a Home Assistant name proves a device class, not a physical label. Exact models marked *(label not seen)* need Michael's photo.
- "Works" is claimed only where a dated physical test with read-back is cited.

## Summary

| Area | State for Room 1 |
|---|---|
| Room node, audio, lights, RF receiver, pendant | Present and partly proven **in the development test room**. None installed in a pilot room. |
| Thermostat / heating-cooling | **Unproven.** The Midea portable AC has been unavailable in HA since 2026-09-13. Michael's "wireless thermostat" has no model on record. |
| Smart plugs | **Reported only.** No model, protocol or HA entity. |
| TV + IR | **Nothing.** TV model unknown, no IR hardware, no TV integration. The test room's TV record is `mock`. |
| Calling (handset / ATA / SIP / Asterisk) | **Nothing physical.** Asterisk is not installed. ATA, handset, front-desk SIP phone and SIP trunk are not owned or recorded. Lane F code is tests-only and not integrated. |
| Network | Development host is on Wi-Fi only (`eno1` has no cable). The **community network is unknown**, and the Matter/SIP requirements below depend on it. |

## Compatibility matrix

### 1. Room node (computer/server)

| Field | Value |
|---|---|
| Exact model | **HP EliteDesk 705 G4 DM 35W (TAA)**, BIOS Q26 Ver. 02.09.00; AMD Ryzen 5 PRO 2400GE (8 threads); 14 GiB RAM visible to the OS; Samsung NVMe `MZVLB256HBHQ-000L7` 238.5 GB; Intel Wireless-AC 9260 (Wi-Fi + Bluetooth); Ubuntu 22.04.5, kernel 6.8.0-138 |
| Presence | **OS-verified** (DMI, `lscpu`, `lsblk`, `lsusb`) |
| Function | Hidden room node behind/near the TV: room screen (browser), Aria realtime client, wake listener, RF decode, HA VM, local backend |
| Connection | Wi-Fi on the local network (EliteDesk LAN address); Ethernet `eno1` NO-CARRIER; video to TV — port/cable not inspected |
| Software state | Development host, not a room appliance. It runs: integration backend `:8092` (started 2026-10-02 22:28), stale lane backends `:8000`/`:8001`/`:8070`/`:8093`, frontend dev server `:3000` (systemd --user), HA VM `caoscare-homeassistant` (libvirt), `rtl_433`, and the RF bridge. Listener/backend run under `nohup`, not systemd (PROJECT_STATE 2026-09-24). |
| Test evidence | Voice, wake word and light control in the test room ran on this host (PROJECT_STATE 2026-09-05, 2026-09-24). No reboot-recovery or autostart test. |
| Missing | Decision: relocate this unit to Room 1, or provision a second node. Room-appliance autostart (systemd) for backend/room page/listener/RF bridge. Power adapter model *(label not seen)*. Video cable/adapter to the TV *(not inspected)*. Mounting behind the TV. Remove dev peripherals (Logitech K120 keyboard and Unifying receiver, OS-verified). |
| Next acceptance test | Phase 8 "Reboot recovery": cold power-cycle → room page, Aria session, wake listener and RF decode all return with no keyboard/SSH. |

### 2. Audio — eMeet

| Field | Value |
|---|---|
| Exact model | **EMEET OfficeCore Luna Plus** (USB `328f:0079`, product string) |
| Presence | **OS-verified** — attached now. ALSA card 1. PulseAudio default sink **and** source are the Luna Plus (`mono-fallback` profile, 48 kHz out / 16 kHz in). |
| Function | Single room capture + playback endpoint for Aria; wake-word input (`docs/ROOM_AUDIO_ARCHITECTURE.md` is canonical) |
| Connection | USB to the EliteDesk (cable type not inspected) |
| Software state | Wake listener (`room-node/aria_wake/`) taps the eMeet through PulseAudio; listener is off since the single-word "Aria" was rejected (2026-09-24). TV audio does not route through the eMeet (planned only). |
| Test evidence | 2026-09-24, test room, eMeet as mic: 4 hands-free wake sessions and light off/on with HA read-back (PROJECT_STATE). Earlier note (2026-09-23 Phase 0): recent test-room sessions had used the onboard analog audio, not the eMeet — so which endpoint a given session used must be checked per session. |
| Missing | Production wake phrase (Wake Phrase Lab). Far-field and TV-noise soak. Placement at the resident's chair/bed in Room 1, plus USB cable length/extension *(not measured)*. |
| Next acceptance test | Phase 7 "Far-field" + "TV/noise soak": at Room 1's chair/bed position with the TV playing, wake + one request; record wake rate and false wakes over a set period. |

### 3. TV and IR control

| Field | Value |
|---|---|
| Exact model | **Unknown** — TV in the test room and in Room 1 |
| Presence | The test room's TV exists only as a `mock` device record. No HA `media_player`/`remote` entity. IR hardware: **not owned / not recorded**. `ir-ctl`/`lircd` not installed. |
| Function | Normal TV; CAOSCare visual surface; Aria TV power/volume/input/channel (checklist Phase 7) |
| Connection / protocol | Unknown until the model is known. Candidates to evaluate only after the model is known: IR (an HA-supported IR bridge), HDMI-CEC from the node, or the TV's own network control. |
| Software state | Device adapter path exists (`backend/device_adapters.py`, HA). No real TV device is configured. The demo kiosk TV is a simulated device (Lane G). |
| Test evidence | None on real hardware |
| Missing | TV make/model **(Michael: photograph the rear label and the remote)**. The node's video output to it. Choice of control method. IR hardware purchase (CURRENT_PRIORITY P4 authorises the minimum compatible IR hardware once the TV is known). |
| Next acceptance test | "TV on/off" by voice with read-back. If IR has no read-back, the receipt must say `unverified` rather than claiming success. |

### 4. Lights

| Field | Value |
|---|---|
| Exact model | Two **TP-Link Tapo L535E** (Matter) *(label not seen by this agent)*. HA detects them as "Tapo Smart Multicolor Bulb" (Matter vendor 5010 / product 769, hw 3.0 — PROJECT_STATE 2026-09-05). |
| Presence | **HA-verified**: `light.smart_multicolor_bulb` = off (last change 2026-09-27), `light.smart_multicolor_bulb_2` = on (last change 2026-10-03 01:51 UTC). **DB-recorded** as two test-room devices, protocol `home_assistant`. |
| Function | Room lighting by voice/touch |
| Connection | Matter over Wi-Fi → HA VM Matter Server (HA 2026.7.4; `matter`, `mqtt`, `bluetooth` loaded) |
| Software state | Integrated: HA adapter with post-command read-back |
| Test evidence | Voice + touch control with HA read-back verified 2026-09-05, 09-19, 09-23/24 (test room) |
| Missing | Room 1 lamp/fixture with a socket that fits the bulb *(not checked)*. **Re-commissioning on the community network**: commissioning on this host needed an IPv6 fix, a scoped Avahi mDNS reflector and NAT changes (PROJECT_STATE 2026-09-05). These are host/network-specific and must be re-proven on the community LAN. |
| Next acceptance test | In Room 1, on the community network: "turn the light off/on" with `verified=True` read-back, then repeat after a node reboot. |

### 5. Thermostat / heating / cooling

| Field | Value |
|---|---|
| Exact model (a) | **Midea Duo Smart Inverter portable AC `MAP14AS1TWT-C`** (Matter). DB-recorded as a test-room device. *(label not seen by this agent)* |
| Presence (a) | **HA-verified as configured but `unavailable`** since 2026-09-13 16:18 UTC (the Midea climate entity). Physically powered/present: not verified. |
| Exact model (b) | Michael's **"wireless thermostat"** — **Reported only**: no make, model, protocol, HA entity or DB record |
| Heater | **Not recorded** anywhere |
| Function | "Thermostat up/down" (checklist Phase 7) |
| Connection | (a) Matter over Wi-Fi. (b) Unknown. |
| Software state | Climate read-back is implemented in the adapter. Midea control was never verified. 2026-09-06 diagnosis: Matter CASE/session establishment fails; IP and mDNS pass. |
| Test evidence | No verified temperature change (checklist Phase 7 `[!]`) |
| Missing | **What heating/cooling Room 1 actually has** (wall thermostat, PTAC, central — and whether the community allows CAOSCare to control it) **(Michael / facility)**. Make/model photo of the wireless thermostat. Whether the Midea is meant for the pilot at all. |
| Next acceptance test | One "set temperature to N" with read-back of the set-point from the real device in the pilot room. Until then the capability stays non-advertised. |

### 6. Smart plugs

| Field | Value |
|---|---|
| Exact model | **Unknown — Reported only** ("wireless smart plugs", CURRENT_PRIORITY P4) |
| Presence | Not in HA, not in the DB, not in the repo |
| Function | Not yet assigned. An earlier proposal was power-only control of a fan/heater/lamp (`docs/reports/2026-08-27-0230-…hardware-adapter.md`). |
| Connection | Unknown (Matter / Wi-Fi vendor cloud / Zigbee — cannot tell without the model) |
| Missing | Make/model photo. Which Room 1 load it would control (none is required by the checklist today). |
| Next acceptance test | Only if a Room 1 need is named: on/off with HA read-back. |

### 7. RF receiver

| Field | Value |
|---|---|
| Exact model | Recorded as **Nooelec NESDR SMArt v5** (checklist Phase 7). OS sees a Realtek RTL2838 DVB-T USB device (`0bda:2838`) — that proves the chipset class, not the Nooelec brand *(label not seen)*. Antenna: *not inspected*. |
| Presence | **OS-verified** (USB) |
| Function | Additive listening to pendant/call-button RF; never replaces the facility's call path |
| Connection | USB → `rtl_433 -F json -M utc -M level -f 319.500M` (running, started 2026-10-02 22:37) → RF bridge |
| Software state | **The RF bridge is the old process** `android-bridge/caos_rf_bridge.py`. It was started 2026-09-06 from an older lane checkout and posts to the stale lane backend on `:8000` under a test kiosk record. It writes to the same Mongo database, which is why the integration backend sees pendant activity. Single frequency (319.5 MHz) only. |
| Test evidence | Test-room pendant decode and pairing (2026-09-06 onward). Staff response loop not accepted. |
| Missing | Point a supervised bridge at the canonical backend under systemd (ops/coordinator work, not done here). The frequency of the **community's** pendant system. Antenna placement in Room 1. |
| Next acceptance test | Phase 8 "Pendant parallel-path": press the resident's facility pendant in Room 1 → the facility's own call system responds as normal **and** CAOSCare records the press with a receipt. |

### 8. Pendant

| Field | Value |
|---|---|
| Exact model | "Lifeline" pendant. Decodes as **Interlogix-Security** at **319.5 MHz** — exact Lifeline model *(label not seen)* |
| Presence | **DB-recorded and recently heard**: a test pendant (Lifeline), paired to the test room, enabled. Last supervisory frame 2026-10-03 03:15:50 UTC. 146 presses, 1491 supervisory frames. A second bring-up pendant is disabled (0.893 similarity conflict). |
| Function | Resident safety activation → `record_resident_activation()` |
| Connection | 319.5 MHz OOK → SDR |
| Test evidence | Paired and receiving in the test room. Supervisory traffic proves the radio path, not a staff response. |
| Missing | **The pilot community's own pendant/call system: make, frequency, and whether listening in parallel is permitted** (facility). The current admin text overclaims multi-band support (checklist "Correct pendant frequency overclaims"). |
| Next acceptance test | Same as §7 parallel-path test, using the community's pendant. |

### 9. Network

| Field | Value |
|---|---|
| Current | Development local network over Wi-Fi (EliteDesk LAN address, IPv4 + IPv6). `eno1` has no cable. HA VM on a libvirt NAT network with an Avahi mDNS reflector between Wi-Fi and the VM bridge. |
| Community network | **Unknown** |
| Requirements from repo evidence | Outbound HTTPS to OpenAI (Realtime). Matter over Wi-Fi needs the node and bulbs on one L2 segment with mDNS and IPv6 — client isolation on a guest/resident Wi-Fi will break it. SIP calling needs outbound TLS 5061 and RTP both ways to OpenAI ranges, possibly an RTP port-forward (`PILOT1_COMMUNICATIONS.md` on `pilot/communications`). A wired port is preferred. |
| Missing | Community IT answers: wired jack in Room 1? SSID/VLAN for devices? client isolation? IPv6? outbound ports? **(Michael / facility IT)** |
| Next acceptance test | Phase 8 "Network loss/recovery": unplug/drop the network for 5 min → the room says it is offline truthfully, then recovers with no intervention. |

### 10. Calling — handset / ATA / SIP / PBX

| Field | Value |
|---|---|
| Decided architecture | Michael D1–D8 (2026-09-27): Asterisk on the room node. Analog handset → ATA (FXS, warm line) → Asterisk. Front desk SIP phone ext 200. SIP trunk. OpenAI Realtime SIP. 911 bypasses Aria. |
| Asterisk | **Not installed** (OS-verified: no `asterisk` binary). Config is in `telephony/asterisk/` on `pilot/communications` only — not integrated. |
| ATA | **Not owned / not recorded.** Requirement: FXS port(s) with a warm-line (off-hook auto-dial delay) setting — confirm the setting exists before buying. |
| Analog handset | **Not owned / not recorded.** Requirement: corded, large-button. |
| Front-desk SIP phone | **Not owned / not recorded.** PoE or with its own power supply. |
| SIP trunk / DID / E911 | **Not provisioned.** Lane F recommends a Telnyx credential trunk (not decided). |
| Test evidence | None on hardware. Lane F code is tests-only. |
| Missing | Everything physical above, plus the room's phone jack/wiring *(not inspected)*, OpenAI SIP project setup, and a webhook tunnel |
| Next acceptance test | Phase 6: lift the Room 1 handset → Aria answers. Dial 0 → front desk phone rings; two-way audio; call receipt shows each state. |

### 11. Adapters, power and mounting

| Item | State |
|---|---|
| EliteDesk power adapter | Present (host runs); model *(label not seen)* |
| Video cable/adapter node → TV | *Not inspected* |
| Power strip / surge protector / UPS for node + ATA | Not recorded |
| USB extension for the eMeet to the bed/chair | Not recorded; length depends on Room 1 layout |
| SDR antenna / extension | *Not inspected* |
| Ethernet cable (if a wired jack exists) | Not recorded |
| ATA power supply, phone cord | With the ATA (not owned) |
| Node mount behind the TV | Not recorded |

### 12. Other devices seen (not part of the room stack)

- Home Assistant also lists two personal phones via its companion app. Not room hardware; not counted.
- Bluetooth controller (Intel 9260): present, unused by CAOSCare.

## What Michael needs to inspect or photograph

Photograph the front and the rear label of each item. One photo set, in priority order:

1. **Choose Pilot Room 1**, then photograph the **TV's rear model label, its remote and its input ports**. This gates the only required purchase (IR) and the TV control method.
2. Room 1's **heating/cooling control** (wall thermostat / PTAC / other) and whether the community allows CAOSCare to control it.
3. The **"wireless thermostat"** he owns — label and box.
4. The **smart plugs** — label and box.
5. The community's **pendant/call-button system** — the pendant's back label and the brand of the receiver/console, if visible.
6. Room 1's **wall plates** — network jack? phone jack? — and outlet positions near the TV and the bed.
7. The Lifeline pendant back label, the SDR dongle label and antenna, and the EliteDesk power-adapter label (confirms recorded models).

Questions for community IT (not physical): wired port, device SSID/VLAN, client isolation, IPv6, outbound TLS 5061/RTP.

## Not done by this pass

No purchases, no device configuration, no HA changes, no runtime or service restarts, no shared-code changes. HA and Mongo were read only.
