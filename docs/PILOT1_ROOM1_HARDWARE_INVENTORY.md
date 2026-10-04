# Pilot Room 1 — Hardware Inventory / BOM (RQ-004)

**Ready-queue item:** RQ-004 · **Branch:** `pilot/rq-004-room1-bom` (from `origin/integration/2026-09-27` @ `55b733e`)
**Compiled:** 2026-10-04 by Claude Code (Opus 5.5), Agent Five, Round 5. Refreshes the 2026-10-02/03 draft (`401fb90` on `agent/pilot-room1-hardware-inventory`) onto the corrected room architecture.
**Status:** evidence inventory only. Nothing purchased, configured, restarted or changed. **No purchase is authorized because an item appears here.**

## Architecture this BOM follows

`docs/ROOM_AUDIO_ARCHITECTURE.md` correction (Michael, 2026-10-03): the HP EliteDesk is the **central community server** (Home Assistant + CAOSCare). Apartments get **no EliteDesk and no eMeet**. The room voice endpoint is the **Home Assistant Voice Preview Edition** over Wi-Fi. Front-desk calling stays a **separate handset/telephony** path. TV control order: native local IP → HDMI-CEC where useful → room-local IR fallback (`docs/2026-10-03-hardware-priority-reset`, not yet merged). Pendant listening is optional/additive.

## Evidence levels

| Tag | Meaning |
|---|---|
| **OS** | Seen by this agent on the EliteDesk on 2026-10-04 (USB, network link, VM and kernel-log state) |
| **HA** | Live Home Assistant state, read-only, 2026-10-03 (`401fb90`). **HA cannot be re-read today: the VM is down — see §A1.** |
| **DB** | Local Mongo `caoscare.smart_devices` record, read-only 2026-10-04 (3 non-mock devices: 2 bulbs, 1 Midea AC) |
| **Doc** | Stated in a repo document or commit; cited. Not physically re-checked. |
| **Reported** | Michael said he has it; no model/protocol anywhere in repo, DB or HA |

Pilot Room 1 is **not selected** (`PILOT1_EXECUTION_CHECKLIST.md` Phase 8 "Select room" open). Everything proven below was proven in the **development test room (Room 214)** on the development network.

## A. ALREADY OWNED / PROVEN

| # | Item | Exact model (verified) | Protocol / interface | Evidence | Pilot 1 role | Acceptance test required | Blocker |
|---|---|---|---|---|---|---|---|
| A1 | Central community server | **HP EliteDesk 705 G4 DM 35W (TAA)**; Ryzen 5 PRO 2400GE; 14 GiB; Intel Wireless-AC 9260 | Wi-Fi only on the development LAN; the wired Ethernet port has **no cable**. HA runs as libvirt VM `caoscare-homeassistant` (HA 2026.7.4, Matter Server add-on) | OS (DMI in `401fb90`; links today). **HA VM state today: `shut off (crashed)`**, qemu log last written 2026-10-03 20:19 CDT | Runs HA + CAOSCare backend + (planned) Asterisk for the whole community | Cold power-cycle → HA VM, backend, frontend and (if used) RF bridge return with no keyboard/SSH; HA reachable from a Voice PE on the community LAN | **YES** — HA VM is down, and nothing autostarts as a supervised service. Restart/supervision is ops work, not done here. |
| A2 | Room lights | **TP-Link Tapo L535E** ×2 | **Matter over Wi-Fi** → HA Matter Server (HA detects vendor 5010 / product 769, hw 3.0) | DB (`dev_f8be14de18e3`, `dev_facc6dbc7e13`, model "Tapo L535E (Matter)"); HA 2026-10-03; voice/touch control with read-back 2026-09-05/19/23/24 (PROJECT_STATE) | "Turn the light on/off" | In Room 1 on the **community** network: on/off with `verified=True` read-back, then repeat after a server reboot. Commissioning here needed IPv6 + scoped mDNS reflector + NAT fixes (PROJECT_STATE 2026-09-05) — must be re-proven on the community LAN | No (owned and proven); re-commissioning is part of Network §D4 |

## B. ALREADY OWNED / MODEL UNKNOWN

| # | Item | Exact model | Protocol / interface | Evidence | Pilot 1 role | Acceptance test required | Blocker |
|---|---|---|---|---|---|---|---|
| B1 | "Wireless thermostat" | **UNKNOWN** | **UNKNOWN** | Reported (`CURRENT_PRIORITY.md` P4). No HA entity, no DB record | "Thermostat up/down" (checklist Phase 7) — only if it can control Room 1's actual heating/cooling | One "set temperature to N" with set-point read-back from the real device in Room 1 | **YES** for the thermostat capability, unless Michael descopes it. Also needs: what HVAC Room 1 has and whether the community allows control |
| B2 | Smart plugs | **UNKNOWN** | **UNKNOWN** | Reported (P4). Not in HA, DB or repo | None named yet. No Room 1 load is required by the checklist | On/off with HA read-back, only once a Room 1 load is named | No |
| B3 | Midea portable AC | `MAP14AS1TWT-C` (Duo Smart Inverter) — DB-recorded, **label not seen** | Matter over Wi-Fi | DB (`dev_fa83aeda0cd4`); HA entity `unavailable` since 2026-09-13; Matter CASE/session failure diagnosed 2026-09-06 | Not assigned to Pilot Room 1. Dev-room test device | Only if Michael assigns it to Room 1 | No (not a Room 1 requirement) |
| B4 | RF receiver (SDR) | Recorded as **Nooelec NESDR SMArt v5**; OS saw only the chipset class RTL2838 `0bda:2838` — **brand label not seen** | USB → `rtl_433` 319.5 MHz → `android-bridge/caos_rf_bridge.py` | OS today: **not enumerated**. Kernel log: 74 connect events since 2026-09-30; last disconnect 2026-10-04 06:30:51 and not back. `rtl_433` not running; the RF bridge process (started 2026-09-06) still posts to a stale lane backend | Optional/additive pendant listening | See D-opt; first reseat/replace cable and confirm stable enumeration for 24 h | No (optional) |
| B5 | Pendant (dev) | "Lifeline", decodes as **Interlogix-Security** 319.5 MHz — **exact Lifeline model not seen** | 319.5 MHz OOK | DB `rf_devices` (paired to Room 214; last supervisory frame 2026-10-03 03:15:50 UTC) | Dev test only. The **community's** pendant system is what matters | Pendant parallel-path test (Phase 8) with the community's pendant | No (optional) |

## C. ORDERED / NOT YET ACCEPTED

Source for both orders: PROJECT_STATE entry "2026-10-03 — Hardware architecture + Pilot 1 priority reconciliation" on branch `docs/2026-10-03-hardware-priority-reset` (**not merged into integration**). The firmware lane also records "the Voice PE has not arrived" (`firmware/voice-pe-aria` PROJECT_STATE).

| # | Item | Exact model | Protocol / interface | Order state | Pilot 1 role | Acceptance test required | Blocker |
|---|---|---|---|---|---|---|---|
| C1 | Room voice endpoint | **Home Assistant Voice Preview Edition** (no unit serial yet) | Wi-Fi to central HA; ESPHome firmware (`firmware/voice-pe-aria`, ESPHome 2026.9.0, compiled, **not flashed**) | CloudFree order, **backordered** as of 2026-10-03 | Aria wake ("Hey Aria"), mic, playback, LEDs, controls in Room 1 | (1) Joins the community Wi-Fi and HA; (2) stock firmware works end-to-end with central HA; (3) Aria wake/false-wake soak and far-field at the bed/chair with TV on (`lab/device_test/PHYSICAL_TEST_SHEET.md`); (4) one light command with read-back by voice | **YES** for the target room design. Legacy EliteDesk/eMeet rig can keep software acceptance moving meanwhile |
| C2 | IR controller | **Seeed Studio XIAO Smart IR Mate** | Network-controlled IR learn/transmit (per reset branch). Exact radio, firmware and HA integration path **UNKNOWN until arrival** — not guessed | RobotShop order; arrival not recorded | TV (and possibly PTAC/fan) control **only if** the Room 1 TV has no usable native IP/CEC path | Learn + replay a real TV remote's power and volume; receipt says `unverified` where IR gives no read-back | **CONDITIONAL** — blocking only if the TV needs IR |

## D. REQUIRED / NOT YET OWNED

| # | Item | Exact model | Protocol / interface | Evidence of requirement | Pilot 1 role | Acceptance test required | Blocker |
|---|---|---|---|---|---|---|---|
| D1 | Voice PE power supply + USB-C cable | Not selected | USB-C. Reset branch records "minimum 5 V / 2 A" — **not verified here against the manufacturer's spec; confirm on arrival** | Reset-branch checklist: "purchase/receipt not yet recorded" | Powers C1 near the resident's chair/bed | Voice PE runs 24 h on the chosen supply with no brownout/reboot | **YES** (with C1) |
| D2 | IR Mate power/accessories | **UNKNOWN** — what is in the box is not recorded | **UNKNOWN** | Reset-branch checklist: "verify included accessories / exact room power plan on arrival" | Powers C2 with line-of-sight to the TV IR window | Stays powered and responsive 24 h in its mounted position | CONDITIONAL (with C2) |
| D3 | Pilot TV | **UNKNOWN** make/model | **UNKNOWN** — native IP / HDMI-CEC / IR not determinable until the model is known | Only a `mock` TV record exists (no real TV record). No HA `media_player` | Normal TV; Aria TV power/volume/input/channel (Phase 7) | TV on/off and volume by voice through the chosen path, with read-back where the path has it | **YES** — gates the control method and whether C2 is needed. Owned by the resident/community, not a purchase |
| D4 | Community network | **UNKNOWN** | Requirements from evidence: outbound HTTPS to OpenAI; Voice PE, bulbs and HA on one L2 segment with mDNS + IPv6 (Matter); **no client isolation** between devices and the server; SIP outbound TLS 5061 + RTP (`PILOT1_COMMUNICATIONS.md`, `pilot/communications`); wired port preferred for the server/ATA/desk phone | Phase 8 "Network access" open | Everything | Network loss/recovery: drop 5 min → room reports offline truthfully → recovers unaided | **YES** |
| D5 | Analog handset | Not selected. Requirement: corded, large-button | RJ11 analog → ATA | D2 decision (Michael 2026-09-27); checklist Phase 6 `[ ]` | Resident lifts handset → Aria; dial 0 → front desk | Lift → Aria answers; dial 0 → ext 200 rings; two-way audio; call receipt per state | **YES** (calling) |
| D6 | ATA | Not selected. Requirement: FXS port(s) with **warm-line** (off-hook auto-dial delay) and immediate-dial plan for 0/911/9911/933; G.711 µ-law; RFC 2833/4733 DTMF | SIP over LAN → Asterisk | `PILOT1_COMMUNICATIONS.md` §2.3 ("confirm on the purchased unit") | Bridges the handset to Asterisk | Warm-line delay reaches Aria; 0 and 911 dial immediately (911 via provider test number 933 only) | **YES** (calling) |
| D7 | Front-desk endpoint | Not selected. SIP desk phone, ext 200; PoE or own PSU | SIP over LAN → Asterisk | D5 decision; checklist Phase 6 | Receives dial-0 and Aria transfers; 911 on-site alert | Rings on dial 0 and on Aria transfer; two-way audio | **YES** (calling) |
| D8 | SIP/PBX + trunk | Asterisk on the central server (**not installed** — OS: no `asterisk` binary). Trunk/DID/E911: **not provisioned**; Telnyx credential trunk *recommended, not decided* | SIP/TLS 5061, SRTP; OpenAI Realtime SIP | D1/D3/D7 decisions; config only on `pilot/communications` (tests-only, not integrated) | Calling backbone | Phase 6 end-to-end; per-room DID with dispatchable E911 address confirmed with provider/counsel before a handset goes in | **YES** (calling). Service subscription, not hardware |
| D9 | Cabling/power for D5–D8 | Ethernet patch cables, ATA PSU (normally with the ATA), RJ11 cord (normally with the handset), desk-phone PSU or PoE injector — lengths/quantities **UNKNOWN until Room 1 and the front desk are surveyed** | — | Derived from D5–D7 | Physical install | Covered by D5–D7 tests | With D5–D7 |

## E. OPTIONAL / NOT PILOT BLOCKING

| # | Item | Status / evidence | Why not blocking |
|---|---|---|---|
| E1 | Zigbee / Thread / Z-Wave coordinator | **None owned; none required.** Every verified Room 1 device is Matter over Wi-Fi (bulbs). No verified device needs another radio | Buy only if B1/B2 turn out to need one (reset branch: "no speculative dongle pile") |
| E2 | RF receiver + pendant listening | B4/B5. Community pendant system make/frequency/permission **UNKNOWN** | Pendant integration is optional/additive; the facility call path stays authoritative (P4) |
| E3 | Smart plugs | B2 | No Room 1 load named |
| E4 | UPS / surge protection for the central server | Not recorded | Improves reboot-recovery; not a checklist gate |
| E5 | Installation consumables: Voice PE/IR Mate mounts or adhesive, cable clips/raceway, labels | Not recorded | Buy once Room 1 is surveyed |
| E6 | eMeet OfficeCore Luna Plus (`328f:0079`, OS: attached today) | Owned; legacy dev/fallback endpoint (`room-node/aria_wake/` re-scoped 2026-10-03) | Not in the standard room; fallback only if Voice PE coverage fails (ROOM_AUDIO_ARCHITECTURE item 6) |

## F. SUPERSEDED / DO NOT BUY

| Item | Superseded by | Source |
|---|---|---|
| Per-apartment EliteDesk / any room PC | Central EliteDesk server + Voice PE | ROOM_AUDIO_ARCHITECTURE correction 2026-10-03; AGENTS.md |
| eMeet (or any speakerphone) per room | Voice PE built-in mics; test first in a real apartment | Same, items 5–6 |
| HDMI cable/adapter and behind-TV mount for a room node | No room node exists | Same |
| Amazon Echo fleet | Voice PE | Reset branch, purchase freeze item 3 |
| HDMI-CEC adapters | TV model unknown; CEC only "where useful" after the TV is known | Reset branch, purchase freeze item 3 |
| Extra radios / dongles (Zigbee, Z-Wave, Thread, extra SDRs for "multi-band" pendants) | Only radios a selected device actually needs | Reset branch; checklist "pendant frequency overclaims" |
| Extra speakers | Voice PE playback | Reset branch, purchase freeze item 3 |
| Duplicate thermostat / bulbs / plugs | Inventory Michael's owned units first (B1, B2) | CURRENT_PRIORITY P4 |
| A second IR blaster of a different make | XIAO IR Mate already ordered | Reset branch |
| More Voice PE units for Room 2 | Hold until Room 1 acceptance (Phase 9 "repeatable, not a second custom build") | Checklist Phase 9 |

## Pilot blockers (summary)

1. **Pilot Room 1 not selected** — every room-specific fact below depends on it.
2. **HA VM down** (crashed 2026-10-03 ~20:19 CDT) and no supervised autostart on the central server (A1).
3. **Voice PE not arrived** (C1) + its power supply not bought (D1).
4. **TV make/model unknown** (D3) → control path and IR need undecided (C2/D2 conditional).
5. **Thermostat** unknown (B1) and Room 1 HVAC/permission unknown — unless Michael descopes it.
6. **Community network** unknown (D4).
7. **Calling stack**: handset, ATA, desk phone, Asterisk install, SIP trunk/DID/E911 — none owned or provisioned (D5–D8).

## One request for Michael (all missing physical facts)

Please send one photo set / answer list:

1. **Which room is Pilot Room 1?**
2. Room 1 **TV**: rear model label, its remote, and the input-port panel.
3. Room 1 **heating/cooling**: what controls it (wall thermostat / PTAC / central) and whether the community allows CAOSCare to control it.
4. Your **"wireless thermostat"**: label and box (make/model).
5. Your **smart plugs**: label and box (make/model).
6. **Voice PE** and **XIAO IR Mate**: has either arrived? If so, a photo of the box contents (power supply/cable included?).
7. Room 1 **wall plates**: network jack? phone jack? outlets near the bed/chair and the TV.
8. **Front desk**: is there a network port and power for a desk phone?
9. **Community IT** (send to them): device SSID/VLAN, client isolation, IPv6, outbound TLS 5061 + RTP, a wired port for the server.
10. Optional only: community pendant brand/frequency and whether passive listening is permitted.

## Not done by this pass

No purchases, device configuration, HA changes, VM/service restarts or code changes. HA could not be re-read (VM down). Mongo and the host were read only. Coordinator-owned trackers (checklist, ready queue, active-work board) were not edited.
